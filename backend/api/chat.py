from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import logging
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from db.session import get_db
from db.models import Message as DBMessage, Conversation as DBConv
from services.auth import get_current_user, require_authorized_role
from services.redis_client import (
    save_message, get_history,
    get_cached_metrics, cache_metrics,
    pop_alerts,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ── SCHÉMAS DE DONNÉES ────────────────────────────────────────

class ChatRequest(BaseModel):
    question:         str
    project_id:       str
    project_name:     Optional[str] = ""
    user_id:          Optional[str] = "chef_projet"
    history:          Optional[list] = None
    conversation_id:  Optional[str] = None

class ChatResponse(BaseModel):
    answer:          str
    intent:          str
    agent_used:      str
    project_id:      str
    display_type:    str
    data:            dict
    conversation_id: str

# ── LOGIQUE DE PERSISTENCE POSTGRES ───────────────────────────

def _save_to_postgres(db: Session, user_id_int: int, project_id: str, question: str, answer: str, conversation_id: str):
    """Gère la création de la conversation et l'ajout des messages."""
    try:
        # 1. Vérifier ou créer la conversation
        db_conv = db.query(DBConv).filter(DBConv.id == conversation_id).first()
        if not db_conv:
            db_conv = DBConv(
                id=conversation_id, 
                user_id=user_id_int, 
                title=f"Chat {project_id} - {datetime.now().strftime('%d/%m %H:%M')}"
            )
            db.add(db_conv)
            db.flush()

        # 2. Ajouter les messages
        msg_user = DBMessage(conversation_id=conversation_id, role="user", content=question)
        msg_ai = DBMessage(conversation_id=conversation_id, role="assistant", content=answer)
        
        db.add(msg_user)
        db.add(msg_ai)
        db.commit()
    except Exception as e:
        logger.error(f"[Postgres] Erreur : {e}")
        db.rollback()

# ── ROUTES API ────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    current_user: dict = Depends(require_authorized_role),
    db: Session = Depends(get_db)
):
    user_id_str = current_user.get("sub")
    user_id_int = current_user.get("user_id", 1)

    # Gestion de l'ID conversation (Multi-session)
    conv_id = req.conversation_id
    safe_proj_id = str(req.project_id) if req.project_id and str(req.project_id) != "None" else "inconnu"
    
    if not conv_id:
        conv_id = f"conv_{user_id_int}_{safe_proj_id}_{uuid.uuid4().hex[:8]}"

    # 1. Historique court-terme (Redis - Isolé par session)
    redis_key = f"{safe_proj_id}:{conv_id}"
    redis_history = get_history(user_id_str, redis_key, last_n=8)
    context_history = redis_history if redis_history else req.history

    try:
        from agents.supervisor_agent import run_agent
        result = run_agent(
            question=req.question,
            project_id=str(req.project_id),
            project_name=req.project_name or "",
            user_id=user_id_str,
            history=context_history or [],
        )

        intent = result.get("intent", "general")
        answer = result.get("answer", "")
        agent_used = result.get("agent_used", "supervisor")

        # 2. Sauvegarde hybride
        save_message(user_id_str, redis_key, "user", req.question)
        save_message(user_id_str, redis_key, "assistant", answer, intent=intent)
        _save_to_postgres(db, user_id_int, req.project_id, req.question, answer, conv_id)

        # 3. Réponse
        display_type = _get_display_type(intent, req.question)
        data = _get_display_data(display_type, req.project_id)

        return ChatResponse(
            answer=answer, intent=intent,
            agent_used=agent_used, project_id=req.project_id,
            display_type=display_type, data=data,
            conversation_id=conv_id
        )

    except Exception as e:
        logger.error(f"[Chat API] Erreur : {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/{project_id}")
async def get_permanent_history(
    project_id: str,
    conversation_id: Optional[str] = None,
    current_user: dict = Depends(require_authorized_role),
    db: Session = Depends(get_db)
):
    """Charge l'historique d'une session spécifique ou la dernière active."""
    user_id_int = current_user.get("user_id", 1)
    
    if conversation_id:
        conv_id = conversation_id
    else:
        # On cherche la dernière discussion de l'utilisateur pour ce projet
        last_conv = (
            db.query(DBConv)
            .filter(DBConv.user_id == user_id_int)
            .filter(DBConv.id.like(f"conv_{user_id_int}_{project_id}_%"))
            .order_by(DBConv.created_at.desc())
            .first()
        )
        if not last_conv:
             return {"history": [], "conversation_id": None}
        conv_id = last_conv.id

    messages = db.query(DBMessage).filter(DBMessage.conversation_id == conv_id).order_by(DBMessage.created_at.asc()).all()
    
    return {
        "history": [{"role": m.role, "content": m.content} for m in messages],
        "conversation_id": conv_id
    }

# ── LOGIQUE D'AFFICHAGE ───────────────────────────────────────

def _get_display_type(intent: str, question: str) -> str:
    q = question.lower()
    if any(k in q for k in ["gantt", "planning"]): return "gantt"
    if any(k in q for k in ["risque", "danger"]): return "risk_table"
    if any(k in q for k in ["charge", "équipe"]): return "workload"
    if any(k in q for k in ["retard", "overdue"]): return "issues_table"
    return {"planning": "gantt", "risques": "risk_table"}.get(intent, "text")

def _get_display_data(display_type: str, project_id: str) -> dict:
    if display_type == "text": return {}
    try:
        from services.redmine_client import redmine
        if display_type == "gantt":
            return {"issues": redmine.get_issues(project_id, status="*")}
        elif display_type == "risk_table":
            return {"issues": redmine.get_issues(project_id, status="open")}
        elif display_type == "workload":
            return {"time_by_user": redmine.get_time_by_user(project_id)}
        return {}
    except Exception:
        return {}

# ── ROUTES DE MONITORING ──────────────────────────────────────

@router.get("/alerts/{project_id}")
async def get_alerts(
    project_id: str,
    current_user: dict = Depends(require_authorized_role)
):
    try:
        alerts = pop_alerts(project_id) or []
        return {"alerts": alerts}
    except Exception as e:
        logger.error(f"[Alerts] Erreur : {e}")
        return {"alerts": []}

@router.get("/projects/{project_id}/metrics")
async def get_project_metrics(
    project_id: str,
    current_user: dict = Depends(require_authorized_role)
):
    try:
        metrics = get_cached_metrics(project_id)
        source = "cache"
        
        # Si le cache est vide ou manque d'infos clés (ex: avg_progress), on force le live
        is_invalid_cache = not metrics or "avg_progress" not in metrics
        
        if is_invalid_cache:
            source = "redmine (live)"
            from services.redmine_client import redmine
            computed = redmine.compute_project_metrics(project_id)
            metrics_clean = {k: v for k, v in computed.items() if k != "time_by_user" and k != "overdue_list"}
            from services.redis_client import cache_metrics
            cache_metrics(project_id, metrics_clean)
            metrics = metrics_clean
        
        try:
            # Conversion robuste (supporte str, int, float)
            def _to_float(val):
                try: return float(val) if val is not None else 0.0
                except: return 0.0

            avancement = int(_to_float(metrics.get("avg_progress")))
            retard     = int(_to_float(metrics.get("overdue_issues")))
            risques    = int(_to_float(metrics.get("critical_issues")))
            charge     = int(_to_float(metrics.get("max_workload")))
            
            logger.info(f"[Metrics] Project={project_id} Source={source} -> Av={avancement}% Load={charge}%")

            return {
                "avancement": avancement, "retard": retard,
                "risques": risques, "charge": charge, "delta": 0
            }
        except Exception as e:
            logger.warning(f"[Metrics] Erreur formatage pour {project_id}: {e}")
            return {"avancement":0, "retard":0, "risques":0, "charge":0, "delta":0, "error": str(e)}
    except Exception as e:
        logger.error(f"[Metrics] Erreur critique pour {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── ROUTES CONVERSATIONS ────────────────────────────────────────────

@router.get("/conversations")
async def list_conversations(
    current_user: dict = Depends(require_authorized_role),
    db: Session = Depends(get_db)
):
    user_id_int = current_user.get("user_id", 1)
    conversations = (
        db.query(DBConv)
        .filter(DBConv.user_id == user_id_int)
        .order_by(DBConv.created_at.desc())
        .all()
    )

    result = []
    for conv in conversations:
        last_msg = (
            db.query(DBMessage)
            .filter(DBMessage.conversation_id == conv.id, DBMessage.role == "assistant")
            .order_by(DBMessage.created_at.desc())
            .first()
        )
        msg_count = db.query(DBMessage).filter(DBMessage.conversation_id == conv.id).count()
        
        # Le project_id est extrait de l'ID conv (index 2)
        parts = conv.id.split("_")
        project_id = parts[2] if len(parts) > 2 else "inconnu"

        result.append({
            "id":            conv.id,
            "title":         conv.title,
            "project_id":    project_id,
            "created_at":    conv.created_at.isoformat(),
            "last_message":  last_msg.content[:80] if last_msg else "",
            "message_count": msg_count,
        })
    
    logger.info(f"[Conversations] User {user_id_int} -> {len(result)} trouvées")
    return {"conversations": result}

@router.post("/conversations/clear/{project_id}")
async def clear_conversation_redis(
    project_id: str,
    current_user: dict = Depends(require_authorized_role),
):
    # OBSOLETE : Maintenant on préfère créer une NOUVELLE conversation ID
    user_id_str = current_user.get("sub")
    try:
        from services.redis_client import clear_history
        # On pourrait effacer tous les IDs liés au projet, ou rien
        return {"message": "Démarrage forcé d'une nouvelle session", "cleared": True}
    except Exception as e:
        return {"message": "Erreur", "cleared": False}