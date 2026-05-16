import logging
from fastapi import WebSocket
from typing import List, Dict

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # On stocke les connexions par project_id
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, project_id: str):
        await websocket.accept()
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []
        self.active_connections[project_id].append(websocket)
        logger.info(f"[WS] Nouvelle connexion sur le projet : {project_id}")

    def disconnect(self, websocket: WebSocket, project_id: str):
        if project_id in self.active_connections:
            self.active_connections[project_id].remove(websocket)
            if not self.active_connections[project_id]:
                del self.active_connections[project_id]
        logger.info(f"[WS] Déconnexion du projet : {project_id}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)

    async def broadcast_to_project(self, project_id: str, message: dict):
        """Envoie un message à tous les utilisateurs connectés à ce projet."""
        if project_id in self.active_connections:
            for connection in self.active_connections[project_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"[WS] Erreur broadcast : {e}")

manager = ConnectionManager()
