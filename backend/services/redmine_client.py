"""
Client Redmine — wrapping complet de l'API REST Redmine.
Utilisé par les agents via les outils LangChain définis dans agents/tools.py.
Incorpore l'analyse des bloqueurs et des versions pour le PFE.
"""
import httpx
import logging
from datetime import date, timedelta
from typing import Optional
import sys, os

# --- CONFIGURATION DU PATH ---
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import settings

logger = logging.getLogger(__name__)

class RedmineClient:
    def __init__(self):
        self.base_url = settings.redmine_url.rstrip("/")
        self.api_key  = settings.redmine_api_key
        self.headers  = {
            "X-Redmine-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict = None) -> dict:
        """Méthode de base pour les requêtes GET avec gestion d'erreurs."""
        url = f"{self.base_url}{path}"
        try:
            r = httpx.get(url, headers=self.headers, params=params or {}, timeout=15)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Redmine HTTP {e.response.status_code} — {path}")
            return {}
        except Exception as e:
            logger.error(f"Redmine inaccessible — {e}")
            return {}

    # --- PROJETS & VERSIONS ---
    def get_projects(self) -> list[dict]:
        data = self._get("/projects.json", {"limit": 100})
        return data.get("projects", [])

    def get_versions(self, project_id: str) -> list[dict]:
        data = self._get(f"/projects/{project_id}/versions.json")
        return data.get("versions", [])

    # --- ISSUES (TÂCHES) ---
    def get_issues(self, project_id: str, status: str = "open", limit: int = 100) -> list[dict]:
        params = {
            "project_id": project_id,
            "status_id": status,
            "limit": limit,
            "include": "journals,relations",
        }
        data = self._get("/issues.json", params)
        return data.get("issues", [])

    def get_overdue_issues(self, project_id: str) -> list[dict]:
        today = str(date.today())
        issues = self.get_issues(project_id, status="open")
        return [i for i in issues if i.get("due_date") and i["due_date"] < today]

    def get_not_started_issues(self, project_id: str) -> list[dict]:
        issues = self.get_issues(project_id, status="open")
        return [i for i in issues if i.get("done_ratio", 0) == 0]

    # --- TEMPS & ÉQUIPE ---
    def get_time_entries(self, project_id: str, days_back: int = 30) -> list[dict]:
        from_date = str(date.today() - timedelta(days=days_back))
        params = {"project_id": project_id, "from": from_date, "limit": 200}
        data = self._get("/time_entries.json", params)
        return data.get("time_entries", [])

    def get_time_by_user(self, project_id: str) -> dict[str, float]:
        entries = self.get_time_entries(project_id)
        by_user = {}
        for e in entries:
            name = e.get("user", {}).get("name", "Inconnu")
            by_user[name] = by_user.get(name, 0) + e.get("hours", 0)
        return by_user

    def get_news(self, project_id: str) -> list[dict]:
        data = self._get(f"/projects/{project_id}/news.json")
        return data.get("news", [])
    
    def get_project_members(self, project_id: str) -> list[dict]:
        """Récupère les membres du projet."""
        data = self._get(f"/projects/{project_id}/memberships.json", {"limit": 100})
        memberships = data.get("memberships", [])
        # Extraire les informations clés (id, name, roles)
        return [
            {
                "id": m.get("id"),
                "user": m.get("user", {}),
                "roles": m.get("roles", []),
            } for m in memberships
        ]

    def get_closed_status_ids(self) -> list[int]:
        data = self._get("/issue_statuses.json")
        statuses = data.get("issue_statuses", [])
        return [s["id"] for s in statuses if s.get("is_closed")]

    # --- MÉTRIQUES CALCULÉES (LE CŒUR DE L'IA) ---
    def compute_project_metrics(self, project_id: str) -> dict:
        """
        Analyse profonde du projet pour alimenter les agents de décision.
        """
        versions = self.get_versions(project_id)
        all_issues = self.get_issues(project_id, status="*")
        
        closed_ids = self.get_closed_status_ids()
        
        def is_issue_closed(i):
            if i.get("status", {}).get("id") in closed_ids:
                return True
            # Fallback
            name = str(i.get("status", {}).get("name", "")).lower()
            if any(x in name for x in ["clos", "fermé", "resolv", "résolu", "termin", "rejet"]):
                return True
            if i.get("status", {}).get("is_closed"):
                return True
            return False

        open_issues = [i for i in all_issues if not is_issue_closed(i)]
        done_issues = [i for i in all_issues if is_issue_closed(i)]
        overdue = self.get_overdue_issues(project_id)
        not_started = self.get_not_started_issues(project_id)
        
        # Détection des bloqueurs (Chemin Critique) via les relations Redmine
        blocking_issues = [
            i for i in all_issues 
            if any(rel["relation_type"] == "precedes" for rel in i.get("relations", []))
            and not is_issue_closed(i)
        ]
        
        # Détection des problèmes critiques (priorité haute + non terminé)
        critical_issues = [
            i for i in all_issues
            if i.get("priority", {}).get("id", 0) >= 4 and not is_issue_closed(i)
        ]

        total = len(all_issues) or 1
        
        # Calcul de la progression sur TOUS les problèmes
        computed_ratios = []
        for i in all_issues:
            ratio = i.get("done_ratio", 0)
            if is_issue_closed(i) and ratio == 0:
                ratio = 100
            computed_ratios.append(ratio)
            
        avg_done = sum(computed_ratios) / total
        completion_rate = (len(done_issues) / total) * 100
        
        final_progress = max(avg_done, completion_rate)

        # Retourne un dictionnaire propre et structuré
        return {
            "project_id": project_id,
            "total_issues": len(all_issues),
            "open_issues": len(open_issues),
            "done_issues": len(done_issues),
            "overdue_issues": len(overdue),
            "not_started": len(not_started),
            "blocking_issues_count": len(blocking_issues),
            "critical_issues": len(critical_issues),
            "active_versions": len([v for v in versions if v.get("status") == "open"]),
            "avg_progress": round(final_progress, 1),
            "completion_rate": round(completion_rate, 1),
            "max_workload": round(max([min((h / 40) * 100, 100) for h in self.get_time_by_user(project_id).values()], default=0), 1),
            "time_by_user": self.get_time_by_user(project_id),
            "overdue_list": [
                {
                    "id": i["id"], 
                    "subject": i["subject"], 
                    "due_date": i.get("due_date"),
                    "assignee": i.get("assigned_to", {}).get("name", "Non assigné"),
                    "delay_days": (date.today() - date.fromisoformat(i["due_date"])).days if i.get("due_date") else 0
                } for i in overdue
            ]
        }

# Instance singleton
redmine = RedmineClient()