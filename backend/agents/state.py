"""
État partagé — backend/agents/state.py
Contient aussi le statut de chaque agent pour la résilience.
"""
from typing import TypedDict, Annotated, Optional
import operator


class AgentState(TypedDict):
    # ── Entrées ───────────────────────────────────────────────
    messages:    Annotated[list, operator.add]
    project_name: str
    project_id:  str
    user_id:     str

    # ── Superviseur ───────────────────────────────────────────
    intent:      str
    next_agent:  str

    # ── Résultats agents ──────────────────────────────────────
    agent_result:  str
    final_answer:  str

    # ── Résilience — statut de chaque agent ──────────────────
    agent_status:  str   # "success" | "error" | "fallback"
    agent_error:   str   # message d'erreur si échec
    retry_count:   int   # nombre de tentatives 
