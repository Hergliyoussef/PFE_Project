from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import logging
from sqlalchemy.orm import Session
from datetime import datetime , timedelta
import uuid
import json

from db.session import get_db
from db.models import Message as DBMessage, Conversation as DBConv, User as DBUser
from services.auth import get_current_user, require_authorized_role, AUTHORIZED_ROLES
from services.redmine_client import redmine, redmine_api_key_ctx, redmine_user_login_ctx, active_project_id_ctx, current_user_role_ctx
from services.redis_client import (
    save_message, get_history,
    get_cached_metrics, cache_metrics,
    pop_alerts, get_alerts, delete_alert, clear_all_alerts,
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
    user_message_id: Optional[int] = None
    ai_message_id:   Optional[int] = None

# ── UTILS SÉCURITÉ ────────────────────────────────────────────

async def verify_project_access(project_id: str, current_user: dict):
    """
    Vérifie si l'utilisateur a le droit d'accéder aux données de gestion d'un projet.
    CEO -> Accès total.
    PM -> Accès si rôle autorisé sur le projet.
    """
    from services.redmine_client import redmine
    from config import settings
    
    is_ceo = current_user.get("is_admin", False)
    if is_ceo:
        redmine_api_key_ctx.set(settings.redmine_api_key)
        redmine_user_login_ctx.set(None)
        return True
    
    # Pour les PM, on vérifie leur rôle sur ce projet précis
    user_api_key = current_user.get("api_key")
    effective_api_key = user_api_key if user_api_key and user_api_key.strip() else settings.redmine_api_key
    redmine_api_key_ctx.set(effective_api_key)
    redmine_user_login_ctx.set(current_user.get("sub"))
    try:
        user_id = current_user.get("user_id")
        memberships = redmine.get_project_members(project_id)
        user_membership = next((m for m in memberships if m.get("user", {}).get("id") == user_id), None)
        
        if not user_membership:
            logger.warning(f"[Access] Utilisateur {user_id} non trouvé parmi les membres de {project_id}")
            return False
            
        from services.auth import AUTHORIZED_ROLES
        user_roles = {r.get("name", "").lower().strip() for r in user_membership.get("roles", [])}
        allowed_roles = {r.lower().strip() for r in AUTHORIZED_ROLES}
        
        has_access = bool(user_roles & allowed_roles)
        if not has_access:
            logger.warning(f"[Access] Accès refusé pour {user_id} sur {project_id}. Rôles: {user_roles} | Requis: {allowed_roles}")
            
        return has_access
    except Exception as e:
        logger.error(f"[Access] Erreur verify_project_access: {e}")
        return False

def check_unauthorized_project_access(question: str, active_project_id: str, is_ceo: bool) -> str | None:
    """
    Vérifie de manière déterministe en Python si l'utilisateur (non-CEO) tente de poser 
    une question sur un autre projet que le projet actif.
    Retourne le message de refus si c'est le cas, sinon None.
    """
    if is_ceo:
        return None
        
    try:
        # Récupérer tous les projets de Redmine
        projects = redmine.get_projects()
        question_lower = question.lower()
        active_project_id_lower = active_project_id.lower()
        
        # Trouver si la question contient le nom ou l'identifiant d'un AUTRE projet
        for p in projects:
            p_id = p.get("identifier", "").lower()
            p_name = p.get("name", "").lower()
            
            # Si le projet est le projet actif, on autorise
            if p_id == active_project_id_lower:
                continue
                
            # Vérifier si l'identifiant ou le nom du projet est mentionné dans la question
            if p_id and (p_id in question_lower):
                return f"Accès refusé. Vous n'êtes pas autorisé à interroger le projet '{p.get('name')}' car vous n'en êtes pas le Project Manager."
            if p_name and (p_name in question_lower):
                return f"Accès refusé. Vous n'êtes pas autorisé à interroger le projet '{p.get('name')}' car vous n'en êtes pas le Project Manager."
                
    except Exception as e:
        logger.error(f"Erreur lors de la vérification déterministe des projets : {e}")
        
    return None

# ── LOGIQUE DE PERSISTENCE POSTGRES ───────────────────────────

def _save_to_postgres(db: Session, project_id: str, project_name: str, question: str, answer: str, conversation_id: str, username: str, user_role: str):
    """Gère la création de la conversation et l'ajout des messages."""
    try:
        # 1. Vérifier ou créer la conversation
        db_conv = db.query(DBConv).filter(DBConv.id == conversation_id).first()
        if not db_conv:
            db_conv = DBConv(
                id=conversation_id, 
                username=username,
                role_user=user_role,
                title=f"Chat {project_id} - {datetime.now().strftime('%d/%m %H:%M')}",
                project_name=project_name or project_id
            )
            db.add(db_conv)
            db.flush()

        # 2. Ajouter les messages
        msg_user = DBMessage(
            conversation_id=conversation_id, 
            name_user=username,
            role=user_role, # CEO ou PROJECT_MANAGER
            content=question
        )
        msg_ai = DBMessage(
            conversation_id=conversation_id, 
            name_user=None,  # NULL : l'assistant n'est pas un vrai user en DB
            role="assistant", 
            content=answer
        )
        
        db.add(msg_user)
        db.add(msg_ai)
        db.commit()
        db.refresh(msg_user)
        db.refresh(msg_ai)
        return msg_user.id, msg_ai.id
    except Exception as e:
        logger.error(f"[Postgres] Erreur : {e}")
        db.rollback()
        return None, None

# ── ROUTES API ────────────────────────────────────────────────

@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    current_user: dict = Depends(require_authorized_role),
    db: Session = Depends(get_db)
):
    # 1. Vérification accès
    has_access = await verify_project_access(req.project_id, current_user)
    if not has_access:
        raise HTTPException(status_code=403, detail="Accès refusé.")

    user_id_str = current_user.get("sub")
    user_id_int = current_user.get("user_id", 1)
    
    # Rôle
    user_roles = current_user.get("roles", [])
    primary_role = "PROJECT_MANAGER"
    if "CEO" in user_roles or current_user.get("is_admin"):
        primary_role = "CEO"

    redmine_user_login_ctx.set(None if primary_role == "CEO" else user_id_str)
    active_project_id_ctx.set(req.project_id)
    current_user_role_ctx.set(primary_role)

    # Gestion de l'ID conversation (Multi-session)
    conv_id = req.conversation_id
    safe_proj_id = str(req.project_id) if req.project_id and str(req.project_id) != "None" else "inconnu"
    if not conv_id:
        conv_id = f"conv_{user_id_int}_{safe_proj_id}_{uuid.uuid4().hex[:8]}"

    # Détection déterministe d'une tentative d'accès à un autre projet non autorisé avant d'appeler l'IA
    refusal_msg = check_unauthorized_project_access(
        question=req.question,
        active_project_id=req.project_id,
        is_ceo=(primary_role == "CEO")
    )
    if refusal_msg:
        save_message(user_id_str, f"{safe_proj_id}:{conv_id}", "user", req.question)
        save_message(user_id_str, f"{safe_proj_id}:{conv_id}", "assistant", refusal_msg)
        _save_to_postgres(
            db=db,
            project_id=req.project_id,
            project_name=req.project_name or "",
            question=req.question,
            answer=refusal_msg,
            conversation_id=conv_id,
            username=user_id_str,
            user_role=primary_role
        )
        async def generate_refusal():
            yield f"data: {json.dumps({'token': refusal_msg})}\n\n"
        return StreamingResponse(generate_refusal(), media_type="text/event-stream")

    from config import settings
    user_api_key = current_user.get("api_key")
    effective_api_key = user_api_key if user_api_key and user_api_key.strip() else settings.redmine_api_key

    from agents.supervisor_agent import run_agent_stream
    return StreamingResponse(
        run_agent_stream(
            question=req.question,
            project_id=req.project_id,
            project_name=req.project_name or "",
            user_id=user_id_str,
            user_role=primary_role,
            history=req.history or [],
            conversation_id=conv_id,
            api_key=effective_api_key
        ),
        media_type="text/event-stream"
    )

@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    current_user: dict = Depends(require_authorized_role),
    db: Session = Depends(get_db)
):
    # 1. Vérification de la permission sur le projet
    has_access = await verify_project_access(req.project_id, current_user)
    if not has_access:
        raise HTTPException(
            status_code=403, 
            detail=f"Accès refusé. Vous n'avez pas les droits de gestion sur le projet '{req.project_id}'."
        )

    redmine_user_login_ctx.set(current_user.get("sub"))
    user_id_str = current_user.get("sub")
    user_id_int = current_user.get("user_id", 1)

    # Gestion de l'ID conversation (Multi-session)
    conv_id = req.conversation_id
    safe_proj_id = str(req.project_id) if req.project_id and str(req.project_id) != "None" else "inconnu"
    
    if not conv_id:
        conv_id = f"conv_{user_id_int}_{safe_proj_id}_{uuid.uuid4().hex[:8]}"

    # 1. Historique court-terme (Redis - Isolé par session)
    redis_key = f"{safe_proj_id}:{conv_id}"
    redis_history = get_history(user_id_str, redis_key, last_n=20)
    context_history = redis_history if redis_history else req.history

    try:
        # Déterminer le rôle principal
        user_roles = current_user.get("roles", [])
        primary_role = "PROJECT_MANAGER"
        if "CEO" in user_roles or current_user.get("is_admin"):
            primary_role = "CEO"
        elif "Manager" in user_roles:
            primary_role = "PROJECT_MANAGER"

        redmine_user_login_ctx.set(None if primary_role == "CEO" else user_id_str)
        active_project_id_ctx.set(req.project_id)
        current_user_role_ctx.set(primary_role)

        # Détection déterministe d'une tentative d'accès à un autre projet non autorisé avant d'appeler l'IA
        refusal_msg = check_unauthorized_project_access(
            question=req.question,
            active_project_id=req.project_id,
            is_ceo=(primary_role == "CEO")
        )
        if refusal_msg:
            save_message(user_id_str, redis_key, "user", req.question)
            save_message(user_id_str, redis_key, "assistant", refusal_msg)
            u_msg_id, a_msg_id = _save_to_postgres(
                db=db,
                project_id=req.project_id,
                project_name=req.project_name or "",
                question=req.question,
                answer=refusal_msg,
                conversation_id=conv_id,
                username=user_id_str,
                user_role=primary_role
            )
            return ChatResponse(
                answer=refusal_msg,
                intent="hors_sujet",
                agent_used="supervisor",
                project_id=req.project_id,
                display_type="text",
                data={},
                conversation_id=conv_id,
                user_message_id=u_msg_id,
                ai_message_id=a_msg_id
            )

        from config import settings
        user_api_key = current_user.get("api_key")
        effective_api_key = user_api_key if user_api_key and user_api_key.strip() else settings.redmine_api_key

        from agents.supervisor_agent import run_agent
        result = run_agent(
            question=req.question,
            project_id=str(req.project_id),
            project_name=req.project_name or "",
            user_id=user_id_str,
            user_role=primary_role,
            history=context_history or [],
            api_key=effective_api_key
        )

        intent = result.get("intent", "general")
        answer = result.get("answer", "")
        agent_used = result.get("agent_used", "supervisor")

        # (primary_role déjà calculé plus haut)

        # 2. Formatage
        display_type = _get_display_type(intent, req.question)
        
        # Si c'est l'agent de planification, on parse la réponse qui est un JSON
        if intent == "planning" and answer.startswith("{"):
            try:
                data = json.loads(answer)
                answer = data.get("summary", "Plusieurs actions ont été planifiées.")
            except Exception:
                data = {}
        else:
            data = _get_display_data(display_type, req.project_id)

        # 3. Sauvegarde hybride (avec l'answer formatée)
        save_message(user_id_str, redis_key, "user", req.question)
        save_message(user_id_str, redis_key, "assistant", answer, intent=intent)
        user_msg_id, ai_msg_id = _save_to_postgres(db, req.project_id, req.project_name, req.question, answer, conv_id, user_id_str, primary_role)

        return ChatResponse(
            answer=answer, intent=intent,
            agent_used=agent_used, project_id=req.project_id,
            display_type=display_type, data=data,
            conversation_id=conv_id,
            user_message_id=user_msg_id,
            ai_message_id=ai_msg_id
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
    user_id_str = current_user.get("sub")
    
    if conversation_id:
        # Vérifier que la conversation appartient à l'utilisateur
        conv = db.query(DBConv).filter(DBConv.id == conversation_id, DBConv.username.ilike(user_id_str)).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation non trouvée ou non autorisée")
        conv_id = conversation_id
    else:
        # On cherche la dernière discussion de l'utilisateur pour ce projet
        last_conv = (
            db.query(DBConv)
            .filter(DBConv.username.ilike(user_id_str))
            .filter(DBConv.id.like(f"conv_%_{project_id}_%"))
            .order_by(DBConv.created_at.desc())
            .first()
        )
        if not last_conv:
             return {"history": [], "conversation_id": None}
        conv_id = last_conv.id

    messages = db.query(DBMessage).filter(DBMessage.conversation_id == conv_id).order_by(DBMessage.created_at.asc()).all()
    
    return {
        "history": [{"id": m.id, "role": m.role, "content": m.content, "display_type": "text", "data": {}} for m in messages],
        "conversation_id": conv_id
    }

class ExecuteTaskRequest(BaseModel):
    action_type: str
    parameters: dict

@router.post("/execute-task")
async def execute_task(
    req: ExecuteTaskRequest,
    current_user: dict = Depends(require_authorized_role)
):
    # Set Redmine context
    redmine_api_key_ctx.set(current_user.get("api_key"))
    redmine_user_login_ctx.set(current_user.get("sub"))
    
    user_roles = current_user.get("roles", [])
    primary_role = "PROJECT_MANAGER"
    if "CEO" in user_roles or current_user.get("is_admin"):
        primary_role = "CEO"
        
    current_user_role_ctx.set(primary_role)
    if req.parameters and req.parameters.get("project_id"):
        active_project_id_ctx.set(str(req.parameters.get("project_id")))

    try:
        from services.redmine_client import redmine
        
        is_admin = current_user.get("is_admin", False)
        roles = current_user.get("roles", [])
        
        # Contrôle d'accès strict
        if not (is_admin or "CEO" in roles):
            # 1. Actions interdites au Project Manager
            forbidden_actions = ["create_project", "delete_project", "create_user", "update_user", "delete_user"]
            if req.action_type in forbidden_actions:
                logger.warning(f"Tentative interdite : {req.action_type} par User {current_user.get('sub')} (PM)")
                raise HTTPException(status_code=403, detail=f"Accès refusé : Seul le CEO peut effectuer l'action '{req.action_type}'.")

            # 2. Vérification du projet cible pour les autres actions
            target_project_id = None
            if req.action_type in ["update_issue", "delete_issue"]:
                issue_id = req.parameters.get("issue_id")
                if issue_id:
                    issue_data = redmine._get(f"/issues/{issue_id}.json")
                    target_project_id = str(issue_data.get("issue", {}).get("project", {}).get("id", ""))
            else:
                target_project_id = str(req.parameters.get("project_id", ""))
                
            if target_project_id and target_project_id.strip():
                # --- RÉSOLUTION DE L'IDENTIFIANT ---
                # Si on a un identifiant texte (ex: "shopflow"), on le convertit en ID (ex: "2")
                if not target_project_id.isdigit():
                    try:
                        all_projects = redmine.get_projects()
                        for p in all_projects:
                            if p.get("identifier") == target_project_id:
                                logger.info(f"[Auth] Résolution identifiant : {target_project_id} -> ID {p.get('id')}")
                                target_project_id = str(p.get("id"))
                                # Mettre à jour les paramètres pour l'exécution réelle
                                req.parameters["project_id"] = target_project_id
                                break
                    except Exception as e:
                        logger.error(f"[Auth] Erreur résolution projet : {e}")
                # -----------------------------------

                user_id = current_user.get("user_id")
                # Récupérer les memberships en direct pour être sûr
                # NOTE: /users/{id}.json?include=memberships nécessite des droits admin dans Redmine
                user_data = redmine._get_admin(f"/users/{user_id}.json", {"include": "memberships"})
                memberships = user_data.get("user", {}).get("memberships", [])
                
                is_authorized = False
                logger.info(f"[Auth Debug] Vérification accès pour User {user_id} sur Projet {target_project_id}")
                
                for m in memberships:
                    p = m.get("project", {})
                    p_id = str(p.get("id"))
                    p_ident = str(p.get("identifier"))
                    m_roles_raw = [r.get("name", "") for r in m.get("roles", [])]
                    
                    logger.info(f"[Auth Debug] Comparaison avec Projet {p_ident} ({p_id}) | Rôles: {m_roles_raw}")
                    
                    if p_id == target_project_id or p_ident == target_project_id:
                        m_roles = {r.lower().strip() for r in m_roles_raw}
                        allowed_roles = {r.lower().strip() for r in AUTHORIZED_ROLES}
                        
                        if m_roles & allowed_roles:
                            is_authorized = True
                            logger.info("[Auth Debug] ACCÈS ACCORDÉ")
                            break
                        else:
                            logger.warning(f"[Auth Debug] Rôles insuffisants: {m_roles} vs {allowed_roles}")
                            
                if not is_authorized:
                    # Construction d'un message clair pour l'utilisateur
                    access_summary = []
                    for m in memberships:
                        p = m.get("project", {})
                        r = [role.get("name") for role in m.get("roles", [])]
                        access_summary.append(f"{p.get('name')} ({p.get('identifier')}) → Rôles: {r}")
                    
                    # Message adapté selon l'action
                    if req.action_type in ["add_project_member", "remove_project_member"]:
                        error_msg = (
                            f"Accès refusé : vous n'êtes pas Manager du projet '{target_project_id}'. "
                            f"Un Chef de Projet ne peut gérer les membres que des projets dont il est lui-même Manager. "
                            f"Vos projets : {access_summary}"
                        )
                    else:
                        error_msg = (
                            f"Accès refusé au projet '{target_project_id}'. "
                            f"Vos projets autorisés : {access_summary}"
                        )
                    
                    logger.warning(f"Tentative non autorisée : User {user_id} sur {target_project_id} ({req.action_type}). Accès : {access_summary}")
                    raise HTTPException(status_code=403, detail=error_msg)

        api_key = current_user.get("api_key")
        result = redmine.execute_action(req.action_type, req.parameters, api_key=api_key)
        return {"success": True, "result": result, "message": "Action exécutée avec succès sur Redmine."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Execute Task] Erreur : {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── LOGIQUE D'AFFICHAGE ───────────────────────────────────────

def _get_display_type(intent: str, question: str) -> str:
    q = question.lower()
    if intent == "planning": return "action_confirmation"
    # Détecter si on parle de PLUSIEURS projets
    if "projets" in q and any(k in q for k in ["retard", "overdue", "état", "status", "liste"]):
        return "projects_table"
    
    if any(k in q for k in ["gantt", "planning", "diagramme"]): return "gantt"
    if any(k in q for k in ["risque", "danger"]): return "risk_table"
    if any(k in q for k in ["charge", "équipe"]): return "workload"
    if any(k in q for k in ["retard", "overdue"]): return "issues_table"
    if any(k in q for k in ["avancement", "progression", "taux", "kpi", "métrique", "metrique", "statistique", "chiffre"]): return "metrics_card"
    return {"risques": "risk_table"}.get(intent, "text")

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
        elif display_type == "issues_table":
            return {"issues": redmine.get_overdue_issues(project_id)}
        elif display_type == "projects_table":
            # On utilise le nouvel outil global
            projects = redmine.get_projects()
            results = []
            for p in projects:
                try:
                    m = redmine.compute_project_metrics(p["identifier"])
                    results.append({
                        "name": p["name"],
                        "identifier": p["identifier"],
                        "progress": m["avg_progress"],
                        "overdue_issues": m["overdue_issues"],
                        "critical_issues": m.get("critical_issues_count", 0)
                    })
                except: continue
            return {"projects": sorted(results, key=lambda x: x["overdue_issues"], reverse=True)}
        elif display_type == "metrics_card":
            return redmine.compute_project_metrics(project_id)
        return {}
    except Exception:
        return {}

# ── ROUTES DE MONITORING ──────────────────────────────────────

@router.get("/alerts/{project_id}")
async def get_alerts_endpoint(
    project_id: str,
    current_user: dict = Depends(require_authorized_role)
):
    try:
        # redmine.get_projects() retourne uniquement les projets autorisés pour l'utilisateur connecté !
        projects = redmine.get_projects()
        p_name_map = {p.get("identifier"): p.get("name") for p in projects if p.get("identifier")}
        
        all_alerts = []
        for p_id, p_name in p_name_map.items():
            alerts = get_alerts(p_id)
            for a in alerts:
                if not a.get("project_name"):
                    a["project_name"] = p_name
                if not a.get("project_id"):
                    a["project_id"] = p_id
            all_alerts.extend(alerts)
            
        # Trier du plus récent au plus ancien globalement
        all_alerts.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return {"alerts": all_alerts}
    except Exception as e:
        logger.error(f"[Alerts] Erreur : {e}")
        try:
            alerts = get_alerts(project_id)
            return {"alerts": alerts}
        except:
            return {"alerts": []}


@router.delete("/alerts/{project_id}/{alert_id}")
async def delete_single_alert(
    project_id: str,
    alert_id: str,
    current_user: dict = Depends(require_authorized_role)
):
    try:
        success = delete_alert(project_id, alert_id)
        if not success:
            # Fallback : chercher dans tous les projets si l'utilisateur est CEO
            is_ceo = any("CEO" in r.upper() for r in current_user.get("roles", [])) or "CEO" in current_user.get("role", "").upper() or current_user.get("is_admin", False)
            if is_ceo:
                projects = redmine.get_projects()
                for p in projects:
                    p_id = p.get("identifier")
                    if p_id and p_id != project_id:
                        if delete_alert(p_id, alert_id):
                            success = True
                            break
        return {"success": success}
    except Exception as e:
        logger.error(f"[Alerts] Erreur suppression : {e}")
        return {"success": False}


@router.get("/projects/{project_id}/sprint-tasks")
async def get_sprint_tasks_endpoint(
    project_id: str,
    sprint_name: str,
    current_user: dict = Depends(require_authorized_role)
):
    # Set Redmine context
    redmine_api_key_ctx.set(current_user.get("api_key"))
    redmine_user_login_ctx.set(current_user.get("sub"))
    
    try:
        # 1. Obtenir l'ID du sprint par son nom
        sprint_id = redmine.get_version_id_by_name(project_id, sprint_name)
        
        # 2. Obtenir toutes les tâches ouvertes du projet
        all_issues = redmine.get_issues(project_id, status="open")
        
        # 3. Obtenir toutes les tâches (même fermées si besoin) du sprint spécifique
        sprint_issues = []
        if sprint_id:
            sprint_issues_data = redmine._get(f"/issues.json", {"project_id": project_id, "fixed_version_id": sprint_id, "status_id": "*", "limit": 100})
            sprint_issues = sprint_issues_data.get("issues", [])
        
        # Construire la liste des tâches du projet
        tasks = []
        seen_ids = set()
        
        # Ajouter d'abord les tâches du sprint (au cas où certaines sont fermées)
        for issue in sprint_issues:
            if issue.get("id") not in seen_ids:
                status_val = issue.get("status")
                status_name = "Nouveau"
                if isinstance(status_val, dict):
                    status_name = status_val.get("name", "Nouveau")
                elif isinstance(status_val, str):
                    status_name = status_val

                tasks.append({
                    "id": issue.get("id"),
                    "subject": issue.get("subject"),
                    "status": status_name,
                    "in_sprint": True
                })
                seen_ids.add(issue.get("id"))
                
        # Ajouter les autres tâches ouvertes du projet
        for issue in all_issues:
            if issue.get("id") not in seen_ids:
                status_val = issue.get("status")
                status_name = "Nouveau"
                if isinstance(status_val, dict):
                    status_name = status_val.get("name", "Nouveau")
                elif isinstance(status_val, str):
                    status_name = status_val

                fv = issue.get("fixed_version")
                other_sprint = None
                if isinstance(fv, dict):
                    other_sprint = fv.get("name")
                elif isinstance(fv, str):
                    other_sprint = fv

                tasks.append({
                    "id": issue.get("id"),
                    "subject": issue.get("subject"),
                    "status": status_name,
                    "in_sprint": False,
                    "other_sprint": other_sprint
                })
                seen_ids.add(issue.get("id"))
                
        return {
            "sprint_id": sprint_id,
            "tasks": tasks
        }
    except Exception as e:
        logger.error(f"[Sprint Tasks] Erreur : {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/alerts/{project_id}")
async def clear_all_project_alerts(
    project_id: str,
    current_user: dict = Depends(require_authorized_role)
):
    try:
        is_ceo = any("CEO" in r.upper() for r in current_user.get("roles", [])) or "CEO" in current_user.get("role", "").upper() or current_user.get("is_admin", False)
        if is_ceo:
            projects = redmine.get_projects()
            for p in projects:
                p_id = p.get("identifier")
                if p_id:
                    clear_all_alerts(p_id)
        else:
            clear_all_alerts(project_id)
        return {"success": True}
    except Exception as e:
        logger.error(f"[Alerts] Erreur nettoyage : {e}")
        return {"success": False}

@router.get("/projects/{project_id}/metrics")
async def get_project_metrics(
    project_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_authorized_role)
):
    # Vérification de la permission par projet
    has_access = await verify_project_access(project_id, current_user)
    if not has_access:
        raise HTTPException(status_code=403, detail="Accès Dashboard refusé. Rôle de gestionnaire requis sur ce projet.")

    redmine_user_login_ctx.set(current_user.get("sub"))

    # Lancer une vérification proactive d'alerte en arrière-plan (ultra-rapide, temps réel sous 5s)
    from services.monitor import check_project
    background_tasks.add_task(check_project, project_id)

    try:
        # On récupère les métriques complètes de Redmine
        computed = redmine.compute_project_metrics(project_id)
        
        # 1. Préparation des KPIs simples
        time_by_user = computed.get("time_by_user", {})
        total_hours = sum(time_by_user.values())
        members_count = len(redmine.get_project_members(project_id))
        
        # 2. Préparation des données pour le graphique de charge (BarChart)
        workload_data = [
            {"name": name, "hours": round(hours, 1)} 
            for name, hours in time_by_user.items()
        ]
        
        # 3. Préparation des données pour le graphique de progression (AreaChart)
        # Simulation d'historique (Redmine ne donne pas l'historique direct sans bcp de requêtes)
        # On crée une courbe qui monte jusqu'au taux actuel avec des dates réelles (JJ/MM)
        current_rate = computed.get("completion_rate", 0)
        today = datetime.now()
        progress_data = [
            {"date": (today - timedelta(days=20)).strftime("%d / %m"), "percent": round(max(0, current_rate - 15), 1)},
            {"date": (today - timedelta(days=15)).strftime("%d / %m"), "percent": round(max(0, current_rate - 12), 1)},
            {"date": (today - timedelta(days=10)).strftime("%d / %m"), "percent": round(max(0, current_rate - 8), 1)},
            {"date": (today - timedelta(days=5)).strftime("%d / %m"),  "percent": round(max(0, current_rate - 3), 1)},
            {"date": "Aujourd'hui", "percent": current_rate},
        ]

        logger.info(f"[Metrics] Dashboard synchronisé pour {project_id} ({current_rate}%)")

        return {
            "completion_rate": current_rate,
            "avg_progress":    computed.get("avg_progress", 0),
            "delayed_tasks":   computed.get("overdue_issues", 0),
            "total_hours":     round(total_hours, 1),
            "members_count":   members_count,
            "workload_data":   workload_data,
            "progress_data":   progress_data,
            "overload_rate":   computed.get("max_workload", 0),
            "risks_count":     computed.get("critical_issues_count", 0),
            "total_issues":    computed.get("total_issues", 0),
            "velocity":        computed.get("velocity", 0),
            "status_distribution": computed.get("status_distribution", []),
            "priority_distribution": computed.get("priority_distribution", []),
            "tracker_distribution": computed.get("tracker_distribution", []),
            "critical_issues_list": computed.get("critical_issues_list", []),
            "team_workload":   computed.get("team_workload", []),
            "bottleneck_alert": computed.get("bottleneck_alert"),
            "members_detailed": computed.get("members_detailed", []),
            "overdue_issues":  computed.get("overdue_issues", 0),
            "total_estimated": computed.get("total_estimated", 0),
            "not_started_list": computed.get("not_started_list", [])
        }
    except Exception as e:
        logger.error(f"[Metrics] Erreur critique pour {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ── ROUTES CONVERSATIONS ────────────────────────────────────────────

@router.get("/conversations")
async def list_conversations(
    current_user: dict = Depends(require_authorized_role),
    db: Session = Depends(get_db)
):
    user_id_str = current_user.get("sub")
    conversations = (
        db.query(DBConv)
        .filter(DBConv.username.ilike(user_id_str))
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
    
    logger.info(f"[Conversations] User {user_id_str} -> {len(result)} trouvées")
    return {"conversations": result}

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: dict = Depends(require_authorized_role),
    db: Session = Depends(get_db)
):
    user_id_str = current_user.get("sub")
    
    # Vérifier que la conversation appartient bien à l'utilisateur
    conv = db.query(DBConv).filter(DBConv.id == conversation_id, DBConv.username.ilike(user_id_str)).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation non trouvée ou non autorisée")
    
    try:
        db.delete(conv)
        db.commit()
        logger.info(f"[Conversations] ID {conversation_id} supprimée par User {user_id_str}")
        return {"message": "Conversation supprimée avec succès", "id": conversation_id}
    except Exception as e:
        db.rollback()
        logger.error(f"[Conversations] Erreur suppression : {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la suppression")

@router.delete("/messages/{message_id}")
async def delete_message(
    message_id: int,
    current_user: dict = Depends(require_authorized_role),
    db: Session = Depends(get_db)
):
    user_id_str = current_user.get("sub")
    
    # On cherche le message en vérifiant qu'il appartient à une conversation de l'utilisateur
    # On fait un join explicite pour garantir la sécurité
    msg = (
        db.query(DBMessage)
        .join(DBConv, DBMessage.conversation_id == DBConv.id)
        .filter(DBMessage.id == message_id)
        .filter(DBConv.username == user_id_str)
        .first()
    )
    
    if not msg:
        # Tentative de secours avec comparaison insensible à la casse
        msg = (
            db.query(DBMessage)
            .join(DBConv, DBMessage.conversation_id == DBConv.id)
            .filter(DBMessage.id == message_id)
            .filter(DBConv.username.ilike(user_id_str))
            .first()
        )
        
    if not msg:
        logger.warning(f"[Messages] Tentative de suppression échouée : Message {message_id} non trouvé pour {user_id_str}")
        raise HTTPException(status_code=404, detail="Message non trouvé ou non autorisé")
    
    try:
        db.delete(msg)
        db.commit()
        logger.info(f"[Messages] Message {message_id} supprimé par {user_id_str}")
        return {"message": "Message supprimé avec succès"}
    except Exception as e:
        db.rollback()
        logger.error(f"[Messages] Erreur suppression : {e}")
        raise HTTPException(status_code=500, detail="Erreur lors de la suppression")
