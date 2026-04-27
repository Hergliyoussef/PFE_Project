import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.agents.state import AgentState
from backend.agents.planning_agent import planning_node
from backend.agents.supervisor_agent import run_agent

def test():
    state = {
        "messages": [],
        "project_name": "Test",
        "project_id": "1",
        "user_id": "1",
        "intent": "general",
        "next_agent": "planning",
        "agent_result": "",
        "final_answer": "",
        "agent_status": "success",
        "agent_error": "",
        "retry_count": 0,
        "last_msg": "Crée un projet nommé Nouveau Projet PFE"
    }
    res = run_agent(question="Crée un projet nommé Nouveau Projet PFE", project_id="1", user_id="1")
    print(res)

if __name__ == "__main__":
    test()
