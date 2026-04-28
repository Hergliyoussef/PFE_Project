"""
Client Redmine — wrapping complet de l'API REST Redmine.
Utilisé par les agents via les outils LangChain définis dans agents/tools.py.
Incorpore l'analyse des bloqueurs et des versions pour le PFE.
"""
import httpx
import logging
from datetime import date, timedelta
from typing import Optional
from contextvars import ContextVar
import sys, os

# --- CONFIGURATION DU PATH ---
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import settings

logger = logging.getLogger(__name__)

# --- CONTEXTE POUR L'IMPERSONNATION ---
redmine_api_key_ctx: ContextVar[Optional[str]] = ContextVar("redmine_api_key", default=None)
redmine_user_login_ctx: ContextVar[Optional[str]] = ContextVar("redmine_user_login", default=None)

class RedmineClient:
    def __init__(self):
        self.base_url = settings.redmine_url.rstrip("/")
        self.api_key  = settings.redmine_api_key
        self.headers  = {
            "X-Redmine-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict = None, api_key: str = None, user_login: str = None) -> dict:
        """Méthode de base pour les requêtes GET avec gestion d'erreurs."""
        url = f"{self.base_url}{path}"
        headers = self.headers.copy()
        
        # 1. Gestion de l'API Key (Priorité : argument direct > contextvar)
        effective_key = api_key or redmine_api_key_ctx.get()
        if effective_key:
            headers["X-Redmine-API-Key"] = effective_key
            
        # 2. Gestion de l'impersonnation (X-Redmine-Switch-User)
        # On ne l'utilise que si on utilise la clé API Admin globale
        # Si on utilise une clé spécifique à l'utilisateur, Redmine l'attribuera déjà correctement
        effective_login = user_login or redmine_user_login_ctx.get()
        if effective_login and (not effective_key or effective_key == self.api_key):
            headers["X-Redmine-Switch-User"] = effective_login
            
        try:
            r = httpx.get(url, headers=headers, params=params or {}, timeout=15)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Redmine HTTP {e.response.status_code} — {path}")
            return {}
        except Exception as e:
            logger.error(f"Redmine inaccessible — {e}")
            return {}

    def _post(self, path: str, payload: dict, api_key: str = None, user_login: str = None) -> dict:
        url = f"{self.base_url}{path}"
        headers = self.headers.copy()
        
        effective_key = api_key or redmine_api_key_ctx.get()
        if effective_key:
            headers["X-Redmine-API-Key"] = effective_key

        effective_login = user_login or redmine_user_login_ctx.get()
        if effective_login and (not effective_key or effective_key == self.api_key):
            headers["X-Redmine-Switch-User"] = effective_login
            
        try:
            r = httpx.post(url, headers=headers, json=payload, timeout=15)
            r.raise_for_status()
            # Some Redmine POST responses might be empty (e.g. 201 Created without body)
            return r.json() if r.text else {}
        except httpx.HTTPStatusError as e:
            logger.error(f"Redmine HTTP POST {e.response.status_code} — {path} : {e.response.text}")
            raise Exception(f"Erreur Redmine: {e.response.text}")
        except Exception as e:
            logger.error(f"Redmine POST inaccessible — {e}")
            raise

    def _delete(self, path: str, api_key: str = None, user_login: str = None) -> bool:
        url = f"{self.base_url}{path}"
        headers = self.headers.copy()
        
        effective_key = api_key or redmine_api_key_ctx.get()
        if effective_key:
            headers["X-Redmine-API-Key"] = effective_key

        effective_login = user_login or redmine_user_login_ctx.get()
        if effective_login and (not effective_key or effective_key == self.api_key):
            headers["X-Redmine-Switch-User"] = effective_login
            
        try:
            r = httpx.delete(url, headers=headers, timeout=15)
            r.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Redmine HTTP DELETE {e.response.status_code} — {path} : {e.response.text}")
            raise Exception(f"Erreur Redmine: {e.response.text}")
        except Exception as e:
            logger.error(f"Redmine DELETE inaccessible — {e}")
            raise

    def _put(self, path: str, payload: dict, api_key: str = None, user_login: str = None) -> bool:
        url = f"{self.base_url}{path}"
        headers = self.headers.copy()
        
        effective_key = api_key or redmine_api_key_ctx.get()
        if effective_key:
            headers["X-Redmine-API-Key"] = effective_key

        effective_login = user_login or redmine_user_login_ctx.get()
        if effective_login and (not effective_key or effective_key == self.api_key):
            headers["X-Redmine-Switch-User"] = effective_login
            
        try:
            r = httpx.put(url, headers=headers, json=payload, timeout=15)
            r.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            logger.error(f"Redmine HTTP PUT {e.response.status_code} — {path} : {e.response.text}")
            raise Exception(f"Erreur Redmine: {e.response.text}")
        except Exception as e:
            logger.error(f"Redmine PUT inaccessible — {e}")
            raise

    def execute_action(self, action: str, params: dict, api_key: str = None) -> dict:
        """Exécute une action planifiée."""
        if action == "create_project":
            return self.create_project(api_key=api_key, **params)
        elif action == "create_user":
            return self.create_user(api_key=api_key, **params)
        elif action == "delete_user":
            return {"success": self.delete_user(params.get("user_id"), api_key=api_key)}
        elif action == "delete_project":
            return {"success": self.delete_project(params.get("project_id"), api_key=api_key)}
        elif action == "add_project_member":
            return self.add_project_member(api_key=api_key, **params)
        elif action == "create_issue":
            return self.create_issue(api_key=api_key, **params)
        elif action == "update_issue":
            return self.update_issue(api_key=api_key, **params)
        else:
            raise ValueError(f"Action non supportée: {action}")

    def create_project(self, name: str, identifier: str, description: str = "", api_key: str = None, **kwargs) -> dict:
        # 1. Vérifier si le projet existe déjà par son identifiant
        data = self._get(f"/projects/{identifier}.json", api_key=api_key)
        if data and "project" in data:
            logger.info(f"[Redmine] Projet existant trouvé : {identifier}")
            return data

        # 2. Sinon, créer
        payload = {
            "project": {
                "name": name,
                "identifier": identifier,
                "description": description
            }
        }
        return self._post("/projects.json", payload, api_key=api_key)

    def get_user_id_by_fuzzy_search(self, search_term: str, api_key: str = None) -> Optional[str]:
        """Cherche un utilisateur par login, prénom ou nom."""
        # 1. Test direct par login (le plus rapide)
        data = self._get("/users.json", {"name": search_term}, api_key=api_key)
        users = data.get("users", [])
        
        # 2. Chercher une correspondance exacte sur le login
        for u in users:
            if u.get("login", "").lower() == search_term.lower():
                return str(u.get("id"))
        
        # 3. Chercher une correspondance sur le prénom ou nom
        for u in users:
            first = u.get("firstname", "").lower()
            last = u.get("lastname", "").lower()
            if search_term.lower() in first or search_term.lower() in last:
                return str(u.get("id"))
        
        return None

    def create_user(self, login: str, firstname: str, lastname: str, mail: str, password: str = "PFE@2024", api_key: str = None, **kwargs) -> dict:
        # 1. Vérifier si l'utilisateur existe déjà (par login ou par nom/prénom)
        existing_id = self.get_user_id_by_fuzzy_search(login, api_key=api_key) or self.get_user_id_by_fuzzy_search(firstname, api_key=api_key)
        if existing_id:
            logger.info(f"[Redmine] Utilisateur existant trouvé via recherche floue : {login}/{firstname} (ID: {existing_id})")
            return {"user": {"id": int(existing_id), "login": login}}

        # 2. Sinon, créer
        if not firstname or firstname == "": firstname = login
        if not lastname or lastname == "": lastname = "Utilisateur"
        if not mail or mail == "": mail = f"{login}@pfe.local"

        payload = {
            "user": {
                "login": login,
                "firstname": firstname,
                "lastname": lastname,
                "mail": mail,
                "password": password
            }
        }
        return self._post("/users.json", payload, api_key=api_key)

    def delete_user(self, user_id: str, api_key: str = None, **kwargs) -> bool:
        return self._delete(f"/users/{user_id}.json", api_key=api_key)

    def delete_project(self, project_id: str, api_key: str = None, **kwargs) -> bool:
        """Supprime un projet par son ID ou identifiant."""
        return self._delete(f"/projects/{project_id}.json", api_key=api_key)

    def add_project_member(self, project_id: str, user_id: str, role_ids: list[int], api_key: str = None, **kwargs) -> dict:
        # Si user_id n'est pas un chiffre, on tente de le résoudre (fuzzy search)
        if not str(user_id).isdigit():
            resolved_id = self.get_user_id_by_fuzzy_search(str(user_id), api_key=api_key)
            if resolved_id:
                user_id = resolved_id
            else:
                # Auto-création si l'utilisateur n'existe pas
                logger.info(f"Utilisateur introuvable pour {user_id}. Création automatique.")
                login_name = str(user_id).lower().replace(' ', '.')
                new_user = self.create_user(login=login_name, firstname=str(user_id), lastname="Nouveau", mail=f"{login_name}@pfe.local", api_key=api_key)
                user_id = str(new_user.get("user", {}).get("id"))
                if not user_id:
                    raise Exception(f"Impossible de créer l'utilisateur '{user_id}' automatiquement.")

        payload = {
            "membership": {
                "user_id": int(user_id),
                "role_ids": role_ids
            }
        }
        return self._post(f"/projects/{project_id}/memberships.json", payload, api_key=api_key)

    def _ensure_project_member(self, project_id: str, user_id: int, api_key: str = None):
        """S'assure que l'utilisateur est membre du projet (rôle développeur=4 par défaut)."""
        payload = {
            "membership": {
                "user_id": user_id,
                "role_ids": [4]
            }
        }
        try:
            self._post(f"/projects/{project_id}/memberships.json", payload, api_key=api_key)
            logger.info(f"[Redmine] Utilisateur {user_id} ajouté automatiquement au projet {project_id}.")
        except Exception:
            pass # L'utilisateur est probablement déjà membre

    def create_issue(self, project_id: str, subject: str, description: str = "", user_id: str = None, tracker_id: int = 1, status_id: int = 1, priority_id: int = 2, estimated_hours: float = None, done_ratio: int = None, api_key: str = None, **kwargs) -> dict:
        """Crée une tâche sur Redmine avec des valeurs par défaut (Tracker=1, Statut=1, Priorité=2)."""
        if not project_id:
             raise Exception("Le projet (project_id) est obligatoire pour créer une tâche.")
 
        # Vérifier si la tâche existe déjà pour éviter les doublons
        if subject:
            existing_issues = self.get_issues(project_id, status="open", api_key=api_key)
            for issue in existing_issues:
                if issue.get("subject", "").lower().strip() == subject.lower().strip():
                    logger.info(f"[Redmine] Tâche '{subject}' déjà existante. Création ignorée.")
                    return {"issue": issue, "already_exists": True}
 
        # Conversion sécurisée en entier, avec fallback de mapping si l'IA renvoie du texte
        try:
            safe_tracker = int(tracker_id) if tracker_id else 1
        except (ValueError, TypeError):
            mapping_tracker = {"anomalie": 1, "bug": 1, "evolution": 2, "feature": 2, "assistance": 3, "support": 3}
            safe_tracker = mapping_tracker.get(str(tracker_id).lower().strip(), 1)
 
        try:
            safe_priority = int(priority_id) if priority_id else 2
        except (ValueError, TypeError):
            mapping_priority = {"bas": 1, "normal": 2, "haut": 3, "urgent": 4, "immédiat": 5, "immediate": 5}
            safe_priority = mapping_priority.get(str(priority_id).lower().strip(), 2)
 
        safe_status = int(status_id) if status_id else 1
 
        payload = {
            "issue": {
                "project_id": project_id,
                "subject": subject or "Tâche sans titre",
                "description": description or "",
                "tracker_id": safe_tracker,
                "status_id": safe_status,
                "priority_id": safe_priority
            }
        }
        
        if estimated_hours is not None and str(estimated_hours).strip() != "":
            try:
                payload["issue"]["estimated_hours"] = float(estimated_hours)
            except ValueError:
                pass
                
        if done_ratio is not None and str(done_ratio).strip() != "":
            try:
                payload["issue"]["done_ratio"] = int(done_ratio)
            except ValueError:
                pass
 
        # Gestion de l'assignation (résolution login -> ID si nécessaire)
        if user_id:
            if not str(user_id).isdigit():
                resolved_id = self.get_user_id_by_fuzzy_search(str(user_id), api_key=api_key)
                if resolved_id:
                    user_id = resolved_id
                else:
                    # Auto-création de l'utilisateur s'il n'existe pas
                    logger.info(f"Assigné {user_id} introuvable. Création automatique.")
                    login_name = str(user_id).lower().replace(' ', '.')
                    new_user = self.create_user(login=login_name, firstname=str(user_id), lastname="Nouveau", mail=f"{login_name}@pfe.local", api_key=api_key)
                    user_id = str(new_user.get("user", {}).get("id", ""))
            
            if str(user_id).isdigit() and user_id:
                self._ensure_project_member(project_id, int(user_id), api_key=api_key)
                payload["issue"]["assigned_to_id"] = int(user_id)
 
        return self._post("/issues.json", payload, api_key=api_key)

    def update_issue(self, issue_id: int, status_id: int = None, priority_id: int = None, tracker_id: int = None, notes: str = None, done_ratio: int = None, api_key: str = None, **kwargs) -> dict:
        """Modifie une tâche existante sur Redmine."""
        if not issue_id:
             raise Exception("L'ID du ticket (issue_id) est obligatoire pour le modifier.")
 
        issue_payload = {}
        
        if status_id is not None:
            issue_payload["status_id"] = int(status_id)
            
        if tracker_id is not None:
            issue_payload["tracker_id"] = int(tracker_id)
            
        if done_ratio is not None:
            try:
                issue_payload["done_ratio"] = int(done_ratio)
            except ValueError:
                pass
            
        if priority_id is not None:
            try:
                safe_priority = int(priority_id)
            except ValueError:
                mapping_priority = {"bas": 1, "normal": 2, "haut": 3, "urgent": 4, "immédiat": 5, "immediate": 5}
                safe_priority = mapping_priority.get(str(priority_id).lower().strip(), 2)
            issue_payload["priority_id"] = safe_priority
            
        if notes and str(notes).strip() != "":
            issue_payload["notes"] = str(notes)
            
        if kwargs.get("subject") and str(kwargs.get("subject")).strip() != "":
            issue_payload["subject"] = str(kwargs.get("subject"))
            
        if kwargs.get("estimated_hours") is not None and str(kwargs.get("estimated_hours")).strip() != "":
            try:
                issue_payload["estimated_hours"] = float(kwargs.get("estimated_hours"))
            except ValueError:
                pass
            
        if kwargs.get("user_id"):
            user_id = kwargs.get("user_id")
            if not str(user_id).isdigit():
                resolved_id = self.get_user_id_by_fuzzy_search(str(user_id), api_key=api_key)
                if resolved_id:
                    user_id = resolved_id
                else:
                    logger.info(f"Assigné {user_id} introuvable lors de la mise à jour. Création automatique.")
                    login_name = str(user_id).lower().replace(' ', '.')
                    new_user = self.create_user(login=login_name, firstname=str(user_id), lastname="Nouveau", mail=f"{login_name}@pfe.local", api_key=api_key)
                    user_id = str(new_user.get("user", {}).get("id", ""))
            
            if str(user_id).isdigit() and user_id:
                # Note: On suppose que l'utilisateur est déjà dans le projet, sinon il faudrait project_id
                issue_payload["assigned_to_id"] = int(user_id)
 
        if not issue_payload:
            raise Exception("Aucune modification valide n'a été demandée pour ce ticket.")
 
        payload = {"issue": issue_payload}
        
        success = self._put(f"/issues/{issue_id}.json", payload, api_key=api_key)
        return {"success": success, "issue_id": issue_id, "updated_fields": list(issue_payload.keys())}


    # --- PROJETS & VERSIONS ---
    def get_projects(self) -> list[dict]:
        data = self._get("/projects.json", {"limit": 100})
        return data.get("projects", [])

    def get_versions(self, project_id: str) -> list[dict]:
        data = self._get(f"/projects/{project_id}/versions.json")
        return data.get("versions", [])

    # --- ISSUES (TÂCHES) ---
    def get_issues(self, project_id: str, status: str = "open", limit: int = 100, api_key: str = None) -> list[dict]:
        params = {
            "project_id": project_id,
            "status_id": status,
            "limit": limit,
            "include": "journals,relations",
        }
        data = self._get("/issues.json", params, api_key=api_key)
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