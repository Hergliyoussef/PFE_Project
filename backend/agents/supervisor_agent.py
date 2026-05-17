import logging
import json
from typing import Literal, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from agents.state import AgentState
from agents.analyse_agent import analyse_node
from agents.rapporteur_agent import rapporteur_node
from agents.planning_agent import planning_node
from services.llm_client import get_llm

logger = logging.getLogger(__name__)

REFUSAL_MSG = "Je suis un assistant spécialisé uniquement dans la gestion de projet et Redmine. Je ne peux pas répondre à cette demande."

# --- SCHÉMAS ET CONFIGURATION ---

class RouterDecision(BaseModel):
    """Décision du superviseur sur l'agent à appeler."""
    action: Literal["analyse", "rapporteur", "planning", "hors_sujet"] = Field(description="L'agent spécialisé ou hors_sujet.")
    intent: str = Field(default="general", description="L'intention détectée.")
    message: str = Field(default="", description="Réponse directe si hors_sujet.")

parser = PydanticOutputParser(pydantic_object=RouterDecision)

SYSTEM_PROMPT = """Tu es le cerveau d'un chatbot de gestion de projet. Tu dois décider quel agent appeler en fonction de la question ET de l'historique.

RÈGLES :
1. Si l'utilisateur demande des chiffres, métriques, membres ou l'état du projet -> action="analyse"
2. Si l'utilisateur demande de créer, modifier ou supprimer quelque chose -> action="planning"
3. Si l'utilisateur demande un rapport, une synthèse ou un résumé -> action="rapporteur"

IMPORTANT : Réponds TOUJOURS au format JSON suivant :
{{
  "action": "analyse" | "planning" | "rapporteur" | "hors_sujet",
  "intent": "court résumé de l'intention",
  "message": "Ta réponse directe si tu as choisi hors_sujet (ex: Bonjour ! ou Voici le tableau :)"
}}

Regarde bien les messages précédents pour comprendre les questions courtes comme 'en tableau' ou 'pourquoi ?'."""

def convert_history_to_messages(history: list) -> list[BaseMessage]:
    """Convertit une liste de dicts (Redis/API) en objets Messages LangChain."""
    messages = []
    for msg in (history or []):
        if isinstance(msg, dict):
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "assistant":
                messages.append(AIMessage(content=content))
            else:
                # Tous les autres rôles (CEO, PROJECT_MANAGER) sont traités comme HumanMessage
                messages.append(HumanMessage(content=content))
        elif isinstance(msg, BaseMessage):
            messages.append(msg)
    return messages

def get_router_chain():
    llm = get_llm("supervisor")
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{question}"),
    ])
    return prompt | llm

# --- LOGIQUE DE ROUTAGE SÉCURISÉE ---

def _get_decision(question: str, history: list) -> RouterDecision:
    """Invoque l'LLM et tente de parser le JSON, avec repli sécurisé."""
    print(f"\n[DEBUG HISTORY] Supervisor reçu {len(history)} messages d'historique.")
    for i, m in enumerate(history):
        print(f"  -> Msg {i} [{m.__class__.__name__}]: {m.content[:100]}")
    
    chain = get_router_chain()
    try:
        response = chain.invoke({"question": question, "history": history})
        # Si la réponse est déjà un objet (certains LLMs le font avec bind_tools), on l'utilise
        content = response.content if hasattr(response, "content") else str(response)
        
        try:
            # Nettoyage si le modèle ajoute du texte avant/après le JSON
            clean_content = content.strip()
            if "```json" in clean_content:
                clean_content = clean_content.split("```json")[1].split("```")[0].strip()
            elif "{" in clean_content:
                clean_content = "{" + clean_content.split("{", 1)[1].rsplit("}", 1)[0] + "}"
                
            data = json.loads(clean_content)
            
            # Injection automatique des champs optionnels manquants pour éviter les erreurs de validation
            if "intent" not in data:
                data["intent"] = "general"
            if "action" not in data or data["action"] not in ["analyse", "rapporteur", "planning", "hors_sujet"]:
                data["action"] = "hors_sujet"
            if "message" not in data:
                data["message"] = ""
                
            return RouterDecision(**data)
        except Exception as parse_err:
            logger.warning(f"[Router] Échec parsing JSON initial : {parse_err}. Tentative de récupération par expressions régulières...")
            
            # Essayer d'extraire le message par regex si la réponse contient du JSON
            import re
            msg_match = re.search(r'"message"\s*:\s*"([^"]+)"', content)
            if msg_match:
                extracted_msg = msg_match.group(1)
                try:
                    # Décoder les échappements unicode si présents
                    extracted_msg = bytes(extracted_msg, "utf-8").decode("unicode_escape")
                except Exception:
                    pass
                return RouterDecision(action="hors_sujet", intent="general", message=extracted_msg)
            
            # Si le parsing échoue mais que le message a l'air d'une salutation ou d'une réponse textuelle, on le garde
            # Sinon, si c'est un refus connu ou un bug, on utilise le REFUSAL_MSG
            if "assistant spécialisé" in content or "pas répondre" in content:
                return RouterDecision(action="hors_sujet", intent="off_topic", message=REFUSAL_MSG)
            
            # Cas par défaut : on fait confiance au texte de l'IA s'il n'est pas trop long ET ne ressemble pas à du JSON
            if len(content) < 200 and "{" not in content and "action" not in content:
                return RouterDecision(action="hors_sujet", intent="general", message=content)
            
            return RouterDecision(action="hors_sujet", intent="off_topic", message=REFUSAL_MSG)
    except Exception as e:
        logger.error(f"[Router] Erreur invocation : {e}")
        return RouterDecision(action="hors_sujet", intent="error", message="Une erreur technique est survenue.")

def _execute_routing(inputs: Dict[str, Any]) -> Dict[str, Any]:
    decision = inputs["decision"]
    state = inputs["state"]
    
    state["intent"] = decision.intent
    state["next_agent"] = decision.action
    
    if decision.action == "analyse":
        return analyse_node(state)
    elif decision.action == "rapporteur":
        return rapporteur_node(state)
    elif decision.action == "planning":
        return planning_node(state)
    else:
        return {
            **state, 
            "next_agent": "end", 
            "final_answer": decision.message or "Désolé, ce sujet n'est pas lié à la gestion de projet."
        }

# La chaîne maîtresse
master_chain = (
    RunnablePassthrough.assign(
        decision=lambda x: _get_decision(x["last_msg"], x["state"]["messages"][:-1])
    ) 
    | RunnableLambda(_execute_routing)
)

async def run_agent_stream(question: str, project_id: str, user_id: str, user_role: str = "PROJECT_MANAGER", history: list = None, project_name: str = "", conversation_id: str = None):
    """Version asynchrone qui streame la réponse finale."""
    converted_history = convert_history_to_messages(history)
    
    state: AgentState = {
        "messages": converted_history + [HumanMessage(content=question)],
        "project_id": str(project_id),
        "project_name": project_name,
        "user_id": user_id,
        "user_role": user_role,
        "next_agent": "supervisor",
        "final_answer": "",
        "data": {},
        "intent": "general",
        "last_msg": question
    }

    try:
        # 1. Obtenir la décision (synchrone pour l'instant car c'est rapide)
        decision = _get_decision(question, converted_history)
        
        # 2. Exécuter l'agent correspondant de manière asynchrone si possible
        # Pour simplifier et garantir la stabilité, on exécute l'agent et on streame son résultat
        # NOTE: Dans une version avancée, on utiliserait .astream() sur les noeuds
        final_state = _execute_routing({"decision": decision, "state": state})
        answer = final_state.get("final_answer", "")
        # Utiliser l'intent du noeud final s'il existe (ex: 'planning')
        final_intent = final_state.get("intent", decision.intent)
        final_data = final_state.get("data", {})
        
        # Simuler le streaming du texte final
        # Si c'est du planning, le final_answer est souvent du JSON, on ne veut pas l'afficher tel quel
        # On affiche plutôt le summary du planning s'il existe
        display_text = answer
        if final_intent == "planning" and isinstance(final_data, dict) and "summary" in final_data:
            display_text = final_data["summary"]

        words = display_text.split(" ")
        for i, word in enumerate(words):
            yield f"data: {json.dumps({'token': word + (' ' if i < len(words)-1 else ''), 'intent': final_intent, 'agent': decision.action, 'data': final_data, 'conversation_id': conversation_id})}\n\n"
            import asyncio
            await asyncio.sleep(0.01) # Un peu plus rapide

        # 3. Sauvegarde hybride (Redis + Postgres)
        from services.redis_client import save_message
        
        redis_key = f"{project_id}:{conversation_id}"
        save_message(user_id, redis_key, "user", question)
        save_message(user_id, redis_key, "assistant", display_text, intent=final_intent, data=final_data)
        
        # Sauvegarde Postgres
        try:
            from db.session import SessionLocal
            from db.models import Message as DBMessage, Conversation as DBConv
            from datetime import datetime
            
            db = SessionLocal()
            try:
                # 1. Vérifier ou créer la conversation
                db_conv = db.query(DBConv).filter(DBConv.id == conversation_id).first()
                if not db_conv:
                    db_conv = DBConv(
                        id=conversation_id,
                        username=user_id,
                        role_user=user_role,
                        title=f"Chat {project_id} - {datetime.now().strftime('%d/%m %H:%M')}",
                        project_name=project_name or project_id
                    )
                    db.add(db_conv)
                    db.flush()
                
                # 2. Ajouter les messages
                msg_user = DBMessage(
                    conversation_id=conversation_id,
                    name_user=user_id,
                    role=user_role,
                    content=question
                )
                msg_ai = DBMessage(
                    conversation_id=conversation_id,
                    name_user=None,
                    role="assistant",
                    content=display_text
                )
                db.add(msg_user)
                db.add(msg_ai)
                db.commit()
                logger.info(f"[Postgres Stream] Discussion et messages sauvegardés avec succès pour {conversation_id}")
            except Exception as inner_db_err:
                db.rollback()
                logger.error(f"[Postgres Stream] Erreur transaction : {inner_db_err}")
            finally:
                db.close()
        except Exception as db_err:
            logger.error(f"[Postgres Stream] Erreur de session ou de connexion : {db_err}")
        
        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"[Stream Agent] Erreur : {e}")
        yield f"data: {json.dumps({'token': 'Erreur technique...', 'intent': 'error'})}\n\n"
        yield "data: [DONE]\n\n"

def run_agent(question: str, project_id: str, user_id: str, user_role: str = "PROJECT_MANAGER", history: list = None, project_name: str = "") -> dict:
    # 1. Conversion de l'historique en objets Messages
    converted_history = convert_history_to_messages(history)
    
    state: AgentState = {
        "messages": converted_history + [HumanMessage(content=question)],
        "project_id": str(project_id),
        "project_name": project_name,
        "user_id": user_id,
        "user_role": user_role,
        "next_agent": "supervisor",
        "final_answer": "",
        "data": {},
        "intent": "general",
        "last_msg": question
    }

    try:
        final_state = master_chain.invoke({"last_msg": question, "state": state})
        return {
            "answer": final_state.get("final_answer"),
            "intent": final_state.get("intent"),
            "agent_used": final_state.get("next_agent"),
            "data": final_state.get("data", {})
        }
    except Exception as e:
        logger.error(f"[MasterChain] Erreur critique : {e}")
        return {"answer": "Erreur système, veuillez reformuler.", "intent": "error", "agent_used": "none", "data": {}}