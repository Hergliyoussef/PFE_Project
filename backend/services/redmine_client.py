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
        # Client persistant pour de meilleures perfs et timeouts unifiés
        self.client = httpx.Client(
            base_url=self.base_url,
            headers=self.headers,
            timeout=30.0,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5)
        )

    def _get(self, path: str, params: dict = None, api_key: str = None, user_login: str = None) -> dict:
        """Méthode de base pour les requêtes GET avec gestion d'erreurs."""
        headers = {}
        
        # 1. Gestion de l'API Key
        effective_key = api_key or redmine_api_key_ctx.get()
        if effective_key:
            headers["X-Redmine-API-Key"] = effective_key
            
        # 2. Gestion de l'impersonnation
        effective_login = user_login or redmine_user_login_ctx.get()
        if effective_login and (not effective_key or effective_key == self.api_key):
            headers["X-Redmine-Switch-User"] = effective_login
            
        try:
            r = self.client.get(path, headers=headers, params=params or {})
            r.raise_for_status()
            return r.json()
        except httpx.TimeoutException:
            logger.error(f"Redmine timeout (30s) — {path}")
            raise Exception("Le serveur Redmine est trop lent à répondre. Veuillez réessayer.")
        except httpx.HTTPStatusError as e:
            logger.error(f"Redmine HTTP {e.response.status_code} — {path} : {e.response.text}")
            raise Exception(f"Erreur Redmine {e.response.status_code}: {e.response.text}")
        except Exception as e:
            logger.error(f"Redmine inaccessible — {e}")
            raise

    def _get_admin(self, path: str, params: dict = None) -> dict:
        """Requête GET utilisant TOUJOURS la clé API admin."""
        headers = {
            "X-Redmine-API-Key": self.api_key,
        }
        try:
            r = self.client.get(path, headers=headers, params=params or {})
            r.raise_for_status()
            return r.json()
        except httpx.TimeoutException:
            logger.error(f"Redmine Admin timeout (30s) — {path}")
            raise Exception("Le serveur Redmine est trop lent à répondre (Admin).")
        except httpx.HTTPStatusError as e:
            logger.error(f"Redmine Admin HTTP {e.response.status_code} — {path} : {e.response.text}")
            raise Exception(f"Erreur Redmine {e.response.status_code}: {e.response.text}")
        except Exception as e:
            logger.error(f"Redmine Admin inaccessible — {e}")
            raise

    def _post(self, path: str, payload: dict, api_key: str = None, user_login: str = None) -> dict:
        headers = {}
        effective_key = api_key or redmine_api_key_ctx.get()
        if effective_key:
            headers["X-Redmine-API-Key"] = effective_key

        effective_login = user_login or redmine_user_login_ctx.get()
        if effective_login and (not effective_key or effective_key == self.api_key):
            headers["X-Redmine-Switch-User"] = effective_login
            
        try:
            r = self.client.post(path, headers=headers, json=payload)
            r.raise_for_status()
            return r.json() if r.text else {}
        except httpx.TimeoutException:
            logger.error(f"Redmine POST timeout (30s) — {path}")
            raise Exception("Délai d'attente dépassé lors de l'envoi des données à Redmine.")
        except httpx.HTTPStatusError as e:
            logger.error(f"Redmine HTTP POST {e.response.status_code} — {path} : {e.response.text}")
            raise Exception(f"Erreur Redmine: {e.response.text}")
        except Exception as e:
            logger.error(f"Redmine POST inaccessible — {e}")
            raise

    def _delete(self, path: str, api_key: str = None, user_login: str = None) -> bool:
        headers = {}
        effective_key = api_key or redmine_api_key_ctx.get()
        if effective_key:
            headers["X-Redmine-API-Key"] = effective_key

        effective_login = user_login or redmine_user_login_ctx.get()
        if effective_login and (not effective_key or effective_key == self.api_key):
            headers["X-Redmine-Switch-User"] = effective_login
            
        try:
            r = self.client.delete(path, headers=headers)
            r.raise_for_status()
            return True
        except httpx.TimeoutException:
            logger.error(f"Redmine DELETE timeout (30s) — {path}")
            raise Exception("Délai d'attente dépassé lors de la suppression sur Redmine.")
        except httpx.HTTPStatusError as e:
            logger.error(f"Redmine HTTP DELETE {e.response.status_code} — {path} : {e.response.text}")
            raise Exception(f"Erreur Redmine: {e.response.text}")
        except Exception as e:
            logger.error(f"Redmine DELETE inaccessible — {e}")
            raise

    def _put(self, path: str, payload: dict, api_key: str = None, user_login: str = None) -> bool:
        headers = {}
        effective_key = api_key or redmine_api_key_ctx.get()
        if effective_key:
            headers["X-Redmine-API-Key"] = effective_key

        effective_login = user_login or redmine_user_login_ctx.get()
        if effective_login and (not effective_key or effective_key == self.api_key):
            headers["X-Redmine-Switch-User"] = effective_login
            
        try:
            r = self.client.put(path, headers=headers, json=payload)
            r.raise_for_status()
            return True
        except httpx.TimeoutException:
            logger.error(f"Redmine PUT timeout (30s) — {path}")
            raise Exception("Délai d'attente dépassé lors de la mise à jour sur Redmine.")
        except httpx.HTTPStatusError as e:
            logger.error(f"Redmine HTTP PUT {e.response.status_code} — {path} : {e.response.text}")
            raise Exception(f"Erreur Redmine: {e.response.text}")
        except Exception as e:
            logger.error(f"Redmine PUT inaccessible — {e}")
            raise

    def execute_action(self, action: str, params: dict, api_key: str = None) -> dict:
        """Exécute une action planifiée."""

        def _resolve_user_id(p: dict) -> str:
            """Résout l'identifiant utilisateur depuis plusieurs champs possibles."""
            return (
                p.get("user_id") or
                p.get("utilisateur") or
                p.get("login") or
                p.get("firstname") or
                ""
            )

        if action == "create_project":
            return self.create_project(api_key=api_key, **params)
        elif action == "create_user":
            return self.create_user(api_key=api_key, **params)
        elif action == "delete_user":
            uid = _resolve_user_id(params)
            return {"success": self.delete_user(uid, api_key=api_key)}
        elif action == "delete_project":
            return {"success": self.delete_project(params.get("project_id"), api_key=api_key)}
        elif action == "add_project_member":
            return self.add_project_member(api_key=api_key, **params)
        elif action == "remove_project_member":
            uid = _resolve_user_id(params)
            return {"success": self.remove_project_member(params.get("project_id"), uid, api_key=api_key)}
        elif action == "create_issue":
            return self.create_issue(api_key=api_key, **params)
        elif action == "update_issue":
            return self.update_issue(api_key=api_key, **params)
        elif action == "delete_issue":
            issue_id = params.get("issue_id")
            if issue_id:
                return {"success": self.delete_issue(str(issue_id), api_key=api_key)}
            # Fallback : suppression par filtre si pas d'issue_id mais des filtres
            elif params.get("project_id") and (params.get("tracker_id") or params.get("status_id") or params.get("état_id")):
                return self.delete_issues_by_filter(api_key=api_key, **params)
            else:
                raise Exception("L'ID du ticket (issue_id) est obligatoire pour supprimer une tâche. Précisez le numéro du ticket.")
        elif action == "update_user":
            return self.update_user(api_key=api_key, **params)
        else:
            raise ValueError(f"Action non supportée: {action}")

    def create_project(self, name: str, identifier: str, description: str = "", api_key: str = None, **kwargs) -> dict:
        # 1. Vérifier si le projet existe déjà par son identifiant
        try:
            data = self._get(f"/projects/{identifier}.json", api_key=api_key)
            if data and "project" in data:
                logger.info(f"[Redmine] Projet existant trouvé : {identifier}")
                return data
        except Exception as e:
            # Si c'est un 404, c'est normal, on continue pour créer le projet
            if "404" not in str(e):
                raise

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
        """
        Cherche un utilisateur par login, prénom ou nom.
        Utilise TOUJOURS la clé admin car /users.json requiert des droits admin dans Redmine.
        """
        # 1. Test direct par login (le plus rapide)
        # NOTE: /users.json nécessite des droits admin — on utilise _get_admin pour éviter un 403
        data = self._get_admin("/users.json", {"name": search_term})
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
        try:
            return self._post("/users.json", payload, api_key=api_key)
        except Exception as e:
            # Si l'utilisateur a été créé entre temps ou si le mail est déjà pris
            if "déjà utilisé" in str(e).lower() or "already taken" in str(e).lower():
                logger.info(f"[Redmine] L'utilisateur {login} semble déjà exister (422).")
                # On essaye de le retrouver pour renvoyer son ID
                uid = self.get_user_id_by_fuzzy_search(login, api_key=api_key)
                if uid:
                    return {"user": {"id": int(uid), "login": login}, "already_exists": True}
            raise

    def delete_user(self, user_id: str, api_key: str = None, **kwargs) -> bool:
        """Supprime un utilisateur (compte global) via ID ou Nom/Login."""
        if not user_id:
             raise Exception("L'ID ou le Nom de l'utilisateur est obligatoire.")

        if not str(user_id).isdigit():
            resolved_id = self.get_user_id_by_fuzzy_search(str(user_id), api_key=api_key)
            if resolved_id:
                logger.info(f"[Redmine] Résolution delete_user : {user_id} -> ID {resolved_id}")
                user_id = resolved_id
            else:
                raise Exception(f"Impossible de supprimer : l'utilisateur '{user_id}' n'a pas été trouvé sur Redmine.")

        return self._delete(f"/users/{user_id}.json", api_key=api_key)

    def update_user(self, user_id: str, firstname: str = None, lastname: str = None, mail: str = None, api_key: str = None, **kwargs) -> dict:
        """Met à jour les informations d'un utilisateur."""
        if not user_id:
            raise Exception("L'ID de l'utilisateur (user_id) est obligatoire.")

        # Résolution si user_id n'est pas numérique
        if not str(user_id).isdigit():
            resolved_id = self.get_user_id_by_fuzzy_search(str(user_id), api_key=api_key)
            if resolved_id:
                user_id = resolved_id
            else:
                raise Exception(f"Utilisateur '{user_id}' non trouvé.")

        user_payload = {}
        if firstname: user_payload["firstname"] = firstname
        if lastname: user_payload["lastname"] = lastname
        if mail: user_payload["mail"] = mail
        
        # On peut aussi ajouter le password si besoin, mais restons sur les coordonnées
        if kwargs.get("login"): user_payload["login"] = kwargs.get("login")

        payload = {"user": user_payload}
        success = self._put(f"/users/{user_id}.json", payload, api_key=api_key)
        return {"success": success, "user_id": user_id, "updated_fields": list(user_payload.keys())}

    def delete_project(self, project_id: str, api_key: str = None, **kwargs) -> bool:
        """Supprime un projet par son ID ou identifiant."""
        return self._delete(f"/projects/{project_id}.json", api_key=api_key)

    def delete_issue(self, issue_id: str, api_key: str = None, **kwargs) -> bool:
        """Supprime une tâche par son ID."""
        return self._delete(f"/issues/{issue_id}.json", api_key=api_key)

    def delete_issues_by_filter(self, project_id: str, tracker_id: int = None, status_id: int = None, état_id: int = None, api_key: str = None, **kwargs) -> dict:
        """Supprime toutes les tâches d'un projet correspondant aux filtres (tracker, statut)."""
        if not project_id:
            raise Exception("Le projet (project_id) est obligatoire pour une suppression par filtre.")
        
        # Normaliser status_id / état_id
        effective_status = status_id or état_id
        
        # Construire la requête de recherche
        params: dict = {"project_id": project_id, "limit": 100}
        if tracker_id:
            params["tracker_id"] = tracker_id
        if effective_status:
            params["status_id"] = effective_status
        
        logger.info(f"[Redmine] Recherche issues à supprimer : {params}")
        data = self._get_admin("/issues.json", params)
        issues = data.get("issues", [])
        
        if not issues:
            return {"deleted": 0, "message": "Aucune tâche trouvée correspondant aux critères."}
        
        deleted, errors = 0, []
        for issue in issues:
            try:
                self._delete(f"/issues/{issue['id']}.json", api_key=api_key)
                deleted += 1
                logger.info(f"[Redmine] Issue #{issue['id']} supprimée")
            except Exception as e:
                errors.append(str(e))
        
        return {"deleted": deleted, "total": len(issues), "errors": errors}

    def add_project_member(self, project_id: str, user_id: str, role_ids: list[int] = None, copy_roles_from: str = None, api_key: str = None, **kwargs) -> dict:
        # 1. Résolution de l'utilisateur à ajouter
        if not str(user_id).isdigit():
            resolved_id = self.get_user_id_by_fuzzy_search(str(user_id), api_key=api_key)
            if resolved_id:
                user_id = resolved_id
            else:
                logger.info(f"Utilisateur introuvable pour {user_id}. Création automatique.")
                login_name = str(user_id).lower().replace(' ', '.')
                new_user = self.create_user(login=login_name, firstname=str(user_id), lastname="Nouveau", mail=f"{login_name}@pfe.local", api_key=api_key)
                user_id = str(new_user.get("user", {}).get("id"))

        # 2. Gestion de la copie des rôles ("à sa place")
        final_role_ids = role_ids or []
        if copy_roles_from:
            # Résoudre l'utilisateur source
            source_user_id = copy_roles_from
            if not str(source_user_id).isdigit():
                source_user_id = self.get_user_id_by_fuzzy_search(str(source_user_id), api_key=api_key)
            
            if source_user_id:
                # Chercher ses rôles dans le projet
                members = self.get_project_members(project_id)
                for m in members:
                    if str(m.get("user", {}).get("id")) == str(source_user_id):
                        final_role_ids = [r.get("id") for r in m.get("roles", [])]
                        logger.info(f"[Redmine] Rôles copiés de {copy_roles_from} ({final_role_ids})")
                        break

        # 3. Gestion du rôle par nom (si fourni et pas de rôle via copie)
        if kwargs.get("role") and not final_role_ids:
            role_map = {
                "manager": 3,
                "project manager": 3,
                "gestionnaire": 3,
                "chef de projet": 3,
                "ceo": 6,
                "developpeur": 4,
                "développeur": 4,
                "developer": 4,
                "rapporteur": 5,
                "reporter": 5
            }
            role_name = str(kwargs.get("role")).lower().strip()
            if role_name in role_map:
                final_role_ids = [role_map[role_name]]
                logger.info(f"[Redmine] Rôle résolu par nom : {role_name} -> {final_role_ids}")

        # Par défaut si aucun rôle trouvé
        if not final_role_ids:
            final_role_ids = [4] # Développeur par défaut

        payload = {
            "membership": {
                "user_id": int(user_id),
                "role_ids": final_role_ids
            }
        }
        try:
            return self._post(f"/projects/{project_id}/memberships.json", payload, api_key=api_key)
        except Exception as e:
            if "déjà utilisé" in str(e).lower() or "already taken" in str(e).lower() or "422" in str(e):
                logger.info(f"[Redmine] L'utilisateur {user_id} est déjà membre du projet {project_id}.")
                return {"membership": {"user_id": user_id, "project_id": project_id}, "already_exists": True}
            raise

    def remove_project_member(self, project_id: str, user_id: str, api_key: str = None, **kwargs) -> bool:
        """Retire un membre d'un projet (Compatible Project Manager)."""
        if not project_id or not user_id:
            raise Exception("project_id et user_id sont obligatoires pour retirer un membre.")

        # 1. On récupère d'abord les membres du projet (autorisé pour les PM)
        # On utilise l'ID du projet résolu si possible
        data = self._get(f"/projects/{project_id}/memberships.json", api_key=api_key)
        memberships = data.get("memberships", [])
        
        membership_id = None
        
        # 2. Recherche du membre dans la liste (par Nom ou par ID)
        search_term = str(user_id).lower().strip()
        is_digit = search_term.isdigit()
        
        for m in memberships:
            u = m.get("user", {})
            u_id = str(u.get("id"))
            u_name = u.get("name", "").lower()
            
            if is_digit:
                if u_id == search_term:
                    membership_id = m.get("id")
                    break
            else:
                # Recherche floue dans le nom du membre du projet
                if search_term in u_name:
                    membership_id = m.get("id")
                    logger.info(f"[Redmine] Membre trouvé dans le projet : {u_name} -> Membership ID {membership_id}")
                    break
        
        if not membership_id:
            raise Exception(f"L'utilisateur '{user_id}' n'a pas été trouvé parmi les membres du projet {project_id}.")
            
        return self._delete(f"/memberships/{membership_id}.json", api_key=api_key)

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
