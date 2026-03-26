"""
Client Redmine — wrapping complet de l'API REST Redmine.
Utilisé par les agents via les outils LangChain définis dans agents/tools.py
"""
import httpx
import logging
from datetime import date, timedelta
from typing import Optional
import sys, os
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
        url = f"{self.base_url}{path}"
        try:
            r = httpx.get(url, headers=self.headers, params=params or {}, timeout=15)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Redmine HTTP {e.response.status_code} — {path}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Redmine inaccessible — {e}")
            raise

    # ----------------------------------------------------------
    # PROJETS
    # ----------------------------------------------------------
    def get_projects(self) -> list[dict]:
        data = self._get("/projects.json", {"limit": 100})
        return data.get("projects", [])

    def get_project(self, project_id: str) -> dict:
        data = self._get(f"/projects/{project_id}.json",
                         {"include": "trackers,issue_categories"})
        return data.get("project", {})

    # ----------------------------------------------------------
    # ISSUES (tâches)
    # ----------------------------------------------------------
    def get_issues(self, project_id: str,
                   status: str = "open",
                   limit: int = 100) -> list[dict]:
        """Retourne les issues d'un projet."""
        params = {
            "project_id": project_id,
            "status_id":  status,
            "limit":      limit,
            "include":    "journals,relations",
        }
        data = self._get("/issues.json", params)
        return data.get("issues", [])

    def get_overdue_issues(self, project_id: str) -> list[dict]:
        """Issues ouvertes dont la date d'échéance est dépassée."""
        today = str(date.today())
        issues = self.get_issues(project_id, status="open")
        return [
            i for i in issues
            if i.get("due_date") and i["due_date"] < today
        ]

    def get_not_started_issues(self, project_id: str) -> list[dict]:
        """Issues ouvertes à 0% d'avancement."""
        issues = self.get_issues(project_id, status="open")
        return [i for i in issues if i.get("done_ratio", 0) == 0]

    def get_critical_issues(self, project_id: str) -> list[dict]:
        """Issues avec priorité haute ou urgente."""
        issues = self.get_issues(project_id, status="open")
        CRITICAL_PRIORITY_IDS = {3, 4, 5}  # High, Urgent, Immediate
        return [
            i for i in issues
            if i.get("priority", {}).get("id") in CRITICAL_PRIORITY_IDS
        ]

    def get_issue_statuses(self) -> list[dict]:
        data = self._get("/issue_statuses.json")
        return data.get("issue_statuses", [])

    # ----------------------------------------------------------
    # TIME ENTRIES (temps passé)
    # ----------------------------------------------------------
    def get_time_entries(self, project_id: str,
                         days_back: int = 30) -> list[dict]:
        """Temps logué sur le projet les N derniers jours."""
        from_date = str(date.today() - timedelta(days=days_back))
        params = {
            "project_id": project_id,
            "from":       from_date,
            "limit":      200,
        }
        data = self._get("/time_entries.json", params)
        return data.get("time_entries", [])

    def get_time_by_user(self, project_id: str) -> dict[str, float]:
        """Heures loguées par utilisateur — pour détecter surcharge."""
        entries = self.get_time_entries(project_id)
        by_user: dict[str, float] = {}
        for e in entries:
            name = e.get("user", {}).get("name", "Inconnu")
            by_user[name] = by_user.get(name, 0) + e.get("hours", 0)
        return by_user

    # ----------------------------------------------------------
    # UTILISATEURS & MEMBRES
    # ----------------------------------------------------------
    def get_project_members(self, project_id: str) -> list[dict]:
        data = self._get(f"/projects/{project_id}/memberships.json")
        return data.get("memberships", [])

    def get_user(self, user_id: int) -> dict:
        data = self._get(f"/users/{user_id}.json")
        return data.get("user", {})

    # ----------------------------------------------------------
    # TRACKERS & VERSIONS
    # ----------------------------------------------------------
    def get_trackers(self) -> list[dict]:
        data = self._get("/trackers.json")
        return data.get("trackers", [])

    def get_versions(self, project_id: str) -> list[dict]:
        data = self._get(f"/projects/{project_id}/versions.json")
        return data.get("versions", [])

    # ----------------------------------------------------------
    # NEWS
    # ----------------------------------------------------------
    def get_news(self, project_id: str) -> list[dict]:
        data = self._get(f"/projects/{project_id}/news.json")
        return data.get("news", [])

    # ----------------------------------------------------------
    # MÉTRIQUES CALCULÉES (utilisées par les agents)
    # ----------------------------------------------------------
    def compute_project_metrics(self, project_id: str) -> dict:
        """
        Calcule les métriques clés d'un projet.
        Retourne un dict directement utilisable par les agents.
        """
        all_issues  = self.get_issues(project_id, status="*")
        open_issues = [i for i in all_issues if i.get("status", {}).get("is_closed") is False]
        done_issues = [i for i in all_issues if i.get("status", {}).get("is_closed") is True]
        overdue     = self.get_overdue_issues(project_id)
        not_started = self.get_not_started_issues(project_id)
        time_by_user = self.get_time_by_user(project_id)

        total = len(all_issues) or 1
        avg_done = (
            sum(i.get("done_ratio", 0) for i in open_issues) / len(open_issues)
            if open_issues else 0
        )

        return {
            "project_id":        project_id,
            "total_issues":      len(all_issues),
            "open_issues":       len(open_issues),
            "done_issues":       len(done_issues),
            "overdue_issues":    len(overdue),
            "not_started":       len(not_started),
            "avg_progress":      round(avg_done, 1),
            "completion_rate":   round(len(done_issues) / total * 100, 1),
            "time_by_user":      time_by_user,
            "overdue_list":      [
                {
                    "id":       i["id"],
                    "subject":  i["subject"],
                    "due_date": i.get("due_date"),
                    "assignee": i.get("assigned_to", {}).get("name", "Non assigné"),
                    "progress": i.get("done_ratio", 0),
                    "priority": i.get("priority", {}).get("name", ""),
                    "delay_days": (
                        date.today() - date.fromisoformat(i["due_date"])
                    ).days if i.get("due_date") else 0,
                }
                for i in overdue
            ],
            "not_started_list":  [
                {
                    "id":       i["id"],
                    "subject":  i["subject"],
                    "due_date": i.get("due_date"),
                    "assignee": i.get("assigned_to", {}).get("name", "Non assigné"),
                    "priority": i.get("priority", {}).get("name", ""),
                }
                for i in not_started
            ],
        }


# Instance singleton — importée partout
redmine = RedmineClient() 
