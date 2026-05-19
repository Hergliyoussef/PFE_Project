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

    def _get(self, path: str, params: dict = None, api_key: str = None, user_login: str = None, cache_ttl: int = 300) -> dict:
        """Méthode de base pour les requêtes GET avec gestion d'erreurs et cache Redis."""
        from services.redis_client import r as redis_conn
        import json
        import hashlib

        # 1. Gestion de l'API Key
        effective_key = api_key or redmine_api_key_ctx.get()
        effective_login = user_login or redmine_user_login_ctx.get()
        
        # 2. Construction de la clé de cache
        cache_key_raw = f"redmine_cache:{path}:{json.dumps(params or {}, sort_keys=True)}:{effective_key}:{effective_login}"
        cache_key = hashlib.md5(cache_key_raw.encode()).hexdigest()

        # 3. Tentative de lecture du cache (si TTL > 0)
        if cache_ttl > 0:
            cached_data = redis_conn.get(f"api:redmine_cache:{cache_key}")
            if cached_data:
                # logger.debug(f"[Cache] Hit pour {path}")
                return json.loads(cached_data)

        headers = {}
        if effective_key:
            headers["X-Redmine-API-Key"] = effective_key
        if effective_login and (not effective_key or effective_key == self.api_key):
            headers["X-Redmine-Switch-User"] = effective_login
            
        try:
            r = self.client.get(path, headers=headers, params=params or {})
            r.raise_for_status()
            data = r.json()
            
            # 4. Stockage en cache
            if cache_ttl > 0:
                redis_conn.setex(f"api:redmine_cache:{cache_key}", cache_ttl, json.dumps(data))
                
            return data
        except httpx.TimeoutException:
            logger.error(f"Redmine timeout (30s) — {path} | Params: {params}")
            raise Exception("Le serveur Redmine est trop lent à répondre. Veuillez réessayer.")
        except httpx.HTTPStatusError as e:
            logger.error(f"Redmine HTTP {e.response.status_code} — {path} | Params: {params} | Resp: {e.response.text}")
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
            # Invalider le cache après une création
            self._invalidate_project_cache()
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
            # Invalider le cache après une suppression
            self._invalidate_project_cache()
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
            # Invalider le cache après une modification
            self._invalidate_project_cache()
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

    def _invalidate_project_cache(self):
        """Supprime les entrées de cache liées à l'API Redmine pour forcer le rafraîchissement."""
        from services.redis_client import r as redis_conn
        try:
            keys = redis_conn.keys("api:redmine_cache:*")
            if keys:
                redis_conn.delete(*keys)
                logger.info(f"[Cache] Invalidation de {len(keys)} entrées suite à une action.")
        except Exception as e:
            logger.error(f"[Cache] Erreur lors de l'invalidation : {e}")

    def get_version_id_by_name(self, project_id: str, version_name: str, api_key: str = None) -> int:
        """Récupère l'ID d'une version/sprint par son nom pour un projet donné sur Redmine."""
        if not project_id or not version_name:
            return None
        try:
            data = self._get(f"/projects/{project_id}/versions.json", api_key=api_key)
            if data and "versions" in data:
                # 1. Correspondance exacte d'abord (insensible à la casse)
                version_name_clean = version_name.lower().strip()
                for v in data["versions"]:
                    if v.get("name", "").lower().strip() == version_name_clean:
                        return int(v["id"])
                
                # 2. Correspondance floue par normalisation (sprint -> s, suppr non-alpha)
                import re
                def _norm(text: str) -> str:
                    t = text.lower().replace("sprint", "s")
                    return re.sub(r'[^a-z0-9]', '', t)
                
                norm_input = _norm(version_name)
                if len(norm_input) >= 2:
                    for v in data["versions"]:
                        norm_v = _norm(v.get("name", ""))
                        if norm_input in norm_v:
                            return int(v["id"])
        except Exception as e:
            logger.error(f"[Redmine] Erreur lors de la recherche de la version '{version_name}' : {e}")
        return None

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
        elif action == "create_version":
            return self.create_version_and_assign_issues(api_key=api_key, **params)
        elif action == "delete_version":
            return {"success": self.delete_version(api_key=api_key, **params)}
        elif action == "update_version":
            return {"success": self.update_version(api_key=api_key, **params)}
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

        # Résolution de fixed_version par son nom en fixed_version_id
        fixed_version = kwargs.get("fixed_version")
        if fixed_version:
            version_id = self.get_version_id_by_name(project_id, str(fixed_version), api_key=api_key)
            if version_id:
                payload["issue"]["fixed_version_id"] = version_id
        
        # Gestion des dates (start_date et due_date)
        start_date = kwargs.get("start_date")
        due_date = kwargs.get("due_date")
        if start_date and str(start_date).strip():
            payload["issue"]["start_date"] = str(start_date).strip()
        if due_date and str(due_date).strip():
            payload["issue"]["due_date"] = str(due_date).strip()
        
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

        # Résolution de fixed_version par son nom en fixed_version_id si présent
        fixed_version = kwargs.get("fixed_version")
        if fixed_version:
            project_id = kwargs.get("project_id")
            if not project_id:
                try:
                    issue_data = self._get(f"/issues/{issue_id}.json", api_key=api_key)
                    if issue_data and "issue" in issue_data:
                        project_id = issue_data["issue"].get("project", {}).get("id")
                except Exception as e:
                    logger.error(f"[Redmine] Impossible de récupérer le projet pour le ticket {issue_id} : {e}")
            if project_id:
                version_id = self.get_version_id_by_name(str(project_id), str(fixed_version), api_key=api_key)
                if version_id:
                    issue_payload["fixed_version_id"] = version_id

        if kwargs.get("fixed_version_id") is not None:
            try:
                issue_payload["fixed_version_id"] = int(kwargs.get("fixed_version_id"))
            except (ValueError, TypeError):
                pass

        # Gestion des dates de début et d'échéance
        start_date = kwargs.get("start_date")
        if start_date is not None and str(start_date).strip() != "":
            issue_payload["start_date"] = str(start_date).strip()
            
        due_date = kwargs.get("due_date")
        if due_date is not None and str(due_date).strip() != "":
            issue_payload["due_date"] = str(due_date).strip()

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
        # 1. Résolution de l'ID interne pour filtrage strict
        internal_id = None
        try:
            p_data = self._get(f"/projects/{project_id}.json", cache_ttl=3600).get("project", {})
            internal_id = p_data.get("id")
        except:
            pass

        params = {
            "project_id": project_id,
            "status_id": status,
            "limit": limit,
            "include": "relations",
        }
        # Cache désactivé (TTL=0) pour une précision maximale
        data = self._get("/issues.json", params, api_key=api_key, cache_ttl=0)
        
        issues = data.get("issues", [])
        light_issues = []
        for i in issues:
            # FILTRAGE STRICT : On ignore les tickets qui ne sont pas de ce projet (ex: cross-project queries)
            ticket_project_id = i.get("project", {}).get("id")
            if internal_id and ticket_project_id != internal_id:
                continue

            light_issues.append({
                "id": i.get("id"),
                "subject": i.get("subject"),
                "project_id": ticket_project_id,
                "project_name": i.get("project", {}).get("name"),
                "status": i.get("status", {}).get("name"),
                "status_id": i.get("status", {}).get("id"),
                "priority": i.get("priority", {}).get("name"),
                "priority_id": i.get("priority", {}).get("id"),
                "tracker": i.get("tracker", {}).get("name"),
                "tracker_id": i.get("tracker", {}).get("id"),
                "assigned": i.get("assigned_to", {}).get("name"),
                "due_date": i.get("due_date"),
                "done_ratio": i.get("done_ratio"),
                "estimated_hours": i.get("estimated_hours")
            })
        return light_issues

    def get_overdue_issues(self, project_id: str) -> list[dict]:
        today = str(date.today())
        issues = self.get_issues(project_id, status="open")
        return [i for i in issues if i.get("due_date") and i["due_date"] < today]

    def get_not_started_issues(self, project_id: str) -> list[dict]:
        issues = self.get_issues(project_id, status="open")
        return [i for i in issues if i.get("done_ratio", 0) == 0]

    # --- TEMPS & ÉQUIPE ---
    def get_time_entries(self, project_id: str, days_back: int = 30) -> list[dict]:
        # Résolution d'ID pour filtrage fiable
        try:
            p_data = self._get(f"/projects/{project_id}.json").get("project", {})
            internal_id = p_data.get("id")
        except:
            internal_id = None

        params = {"project_id": project_id, "limit": 200}
        data = self._get("/time_entries.json", params)
        entries = data.get("time_entries", [])
        
        # Filtrage manuel strict par ID interne
        if internal_id:
            return [e for e in entries if e.get("project", {}).get("id") == internal_id]
        return entries

    def get_time_by_user(self, project_id: str) -> dict[str, float]:
        entries = self.get_time_entries(project_id)
        time_map = {}
        for entry in entries:
            user = entry.get("user", {}).get("name", "Inconnu")
            hours = float(entry.get("hours", 0))
            time_map[user] = time_map.get(user, 0) + hours
        return time_map

    def get_news(self, project_id: str) -> list[dict]:
        data = self._get(f"/projects/{project_id}/news.json")
        return data.get("news", [])
    
    def get_project_members(self, project_id: str) -> list[dict]:
        """Récupère les membres du projet avec un cache très court (10s) pour la réactivité."""
        data = self._get(f"/projects/{project_id}/memberships.json", {"limit": 100}, cache_ttl=10)
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
        # --- RÉSOLUTION ID NUMÉRIQUE ---
        try:
            p_data = self._get(f"/projects/{project_id}.json", cache_ttl=0).get("project", {})
            internal_id = p_data.get("id")
            p_name = p_data.get("name")
            logger.info(f"[Metrics] Début analyse pour {p_name} (ID: {internal_id})")
        except Exception as e:
            logger.error(f"[Metrics] Échec résolution projet {project_id}: {e}")
            internal_id = None

        versions = self.get_versions(project_id)
        # On récupère les tickets (normalement filtrés par Redmine)
        raw_issues = self.get_issues(project_id, status="*")
        
        # --- FILTRAGE MANUEL ULTRA-STRICT ---
        # On ne garde que les tickets dont le project_id correspond EXACTEMENT à l'internal_id
        if internal_id:
            all_issues = [i for i in raw_issues if i.get("project_id") == internal_id]
            diff = len(raw_issues) - len(all_issues)
            if diff > 0:
                logger.warning(f"[Metrics] {diff} tickets d'AUTRES PROJETS éliminés pour {project_id}")
        else:
            all_issues = raw_issues

        logger.info(f"[Metrics] {len(all_issues)} tickets validés sur ce projet.")
        
        closed_ids = self.get_closed_status_ids()
        
        def is_issue_closed(i):
            s_id = i.get("status_id")
            if s_id in closed_ids: return True
            name = str(i.get("status", "")).lower()
            return any(x in name for x in ["clos", "fermé", "resolv", "résolu", "termin", "rejet", "fini"])

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
        critical_keywords = ["urgent", "immédiat", "haut", "high", "critical", "prioritaire"]
        critical_issues = []
        for i in all_issues:
            p_name = str(i.get("priority", "")).lower()
            p_id = i.get("priority_id", 0)
            if not is_issue_closed(i):
                if p_id >= 4 or any(kw in p_name for kw in critical_keywords):
                    critical_issues.append(i)
        
        logger.info(f"[Metrics] {len(critical_issues)} tâches critiques détectées sur {len(all_issues)} tickets total")

        total = len(all_issues) or 1
        total_estimated = sum(float(i.get("estimated_hours") or 0) for i in all_issues)
        
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

        # Distributions pour les graphiques
        status_counts = {}
        priority_counts = {}
        tracker_counts = {}
        for i in all_issues:
            s_val = i.get("status")
            s_name = s_val if isinstance(s_val, str) else s_val.get("name", "Inconnu") if s_val else "Inconnu"
            status_counts[s_name] = status_counts.get(s_name, 0) + 1
            
            p_val = i.get("priority")
            p_name = p_val if isinstance(p_val, str) else p_val.get("name", "Normal") if p_val else "Normal"
            priority_counts[p_name] = priority_counts.get(p_name, 0) + 1

            t_val = i.get("tracker")
            t_name = t_val if isinstance(t_val, str) else t_val.get("name", "Tâche") if t_val else "Tâche"
            tracker_counts[t_name] = tracker_counts.get(t_name, 0) + 1

        status_colors = {
            "Nouveau": "#3b82f6", 
            "En cours": "#9ACD32", 
            "Résolu": "#10b981", 
            "Fermé": "#64748b", 
            "Commentaire": "#f59e0b",
            "Rejeté": "#ef4444"
        }
        priority_colors = {
            "Urgent": "#f43f5e", 
            "Immédiat": "#ef4444", 
            "Haut": "#fbbf24", 
            "Normal": "#10b981", 
            "Bas": "#94a3b8"
        }
        tracker_colors = {
            "Bug": "#ef4444",
            "Anomalie": "#ef4444",
            "Erreur": "#ef4444",
            "Tâche": "#3b82f6",
            "Task": "#3b82f6",
            "Évolution": "#10b981",
            "Feature": "#10b981",
            "Assistance": "#10b981",
            "Soutien": "#f59e0b"
        }

        # 6. Vélocité (Nombre de tickets fermés sur les 7 derniers jours)
        seven_days_ago = date.today() - timedelta(days=7)
        closed_recently = [
            i for i in done_issues 
            if i.get("closed_on") and date.fromisoformat(i["closed_on"][:10]) >= seven_days_ago
        ]
        velocity = len(closed_recently)

        # 7. Analyse de la Charge Humaine (Resource Management)
        user_load = {}
        urgent_priorities = ["Urgent", "Immédiat"]
        total_urgent_project = 0
        
        for i in all_issues:
            # Gestion hybride des assignés (assigned_to dans format complet, assigned dans format light)
            raw_assignee = i.get("assigned") or i.get("assigned_to")
            assignee = raw_assignee if isinstance(raw_assignee, str) else raw_assignee.get("name", "Non assigné") if raw_assignee else "Non assigné"
            
            raw_prio = i.get("priority")
            prio = raw_prio if isinstance(raw_prio, str) else raw_prio.get("name", "Normal") if raw_prio else "Normal"
            
            if assignee not in user_load:
                user_load[assignee] = {"total": 0, "urgent": 0}
            
            user_load[assignee]["total"] += 1
            if prio in urgent_priorities:
                user_load[assignee]["urgent"] += 1
                total_urgent_project += 1

        # Résoudre les rôles de chaque membre depuis Redmine pour le tableau de bord
        member_roles = {}
        try:
            raw_members = self.get_project_members(project_id)
            for m in raw_members:
                m_name = m.get("user", {}).get("name", "")
                m_roles = [r.get("name") for r in m.get("roles", [])]
                if m_name:
                    member_roles[m_name] = ", ".join(m_roles) if m_roles else "Développeur"
        except Exception as e:
            logger.error(f"[Metrics] Erreur récupération membres pour rôles : {e}")

        team_workload = []
        bottleneck_user = None
        max_urgent_share = 0
        
        for name, stats in user_load.items():
            urgent_share = (stats["urgent"] / total_urgent_project * 100) if total_urgent_project > 0 else 0
            team_workload.append({
                "name": name,
                "total": stats["total"],
                "urgent": stats["urgent"],
                "share": round(urgent_share, 1),
                "is_overloaded": stats["urgent"] >= 3 or stats["total"] >= 10,
                "role": member_roles.get(name, "Chef de Projet" if name == "Superviseur" else ("Non Assigné" if name == "Non assigné" else "Développeur"))
            })
            
            if urgent_share > max_urgent_share:
                max_urgent_share = urgent_share
                bottleneck_user = name

        # Toujours trier la charge d'équipe de la plus élevée à la moins élevée
        team_workload.sort(key=lambda x: x["total"], reverse=True)

        bottleneck_alert = None
        if max_urgent_share > 50 and bottleneck_user != "Non assigné" and total_urgent_project > 3:
            bottleneck_alert = f"Attention : {round(max_urgent_share)}% de la charge critique repose sur {bottleneck_user}. Risque élevé de goulot d'étranglement."

        # Retourne un dictionnaire propre et structuré
        # Récupération sécurisée des membres avec tri hiérarchique
        members_list = []
        role_priority = {
            "ceo": 0,
            "manager": 1,
            "gestionnaire": 1,
            "projet manager": 1,
            "project manager": 1,
            "développeur": 2,
            "developer": 2,
            "rapporteur": 3,
            "reporter": 3
        }

        try:
            raw_members = self.get_project_members(project_id)
            for m in raw_members:
                roles = [r.get("name") for r in m.get("roles", [])]
                # Déterminer la priorité la plus haute (le chiffre le plus petit) pour cet utilisateur
                prio = min([role_priority.get(r.lower(), 10) for r in roles], default=10)
                
                members_list.append({
                    "name": m.get("user", {}).get("name", "Inconnu"),
                    "roles": roles,
                    "priority": prio
                })
            
            # Trier par priorité, puis par nom
            members_list.sort(key=lambda x: (x["priority"], x["name"]))
        except Exception as e:
            logger.error(f"[Metrics] Erreur récupération membres pour {project_id} : {e}")

        # Construction propre de status_distribution avec toujours les 6 statuts standards
        all_standard_statuses = ["Nouveau", "En cours", "Résolu", "Commentaire", "Fermé", "Rejeté"]
        computed_status_dist = []
        for s in all_standard_statuses:
            computed_status_dist.append({
                "name": s,
                "value": status_counts.get(s, 0),
                "color": status_colors.get(s, "#a855f7")
            })
        for k, v in status_counts.items():
            if k not in all_standard_statuses:
                computed_status_dist.append({
                    "name": k,
                    "value": v,
                    "color": status_colors.get(k, "#a855f7")
                })

        # Construction propre de priority_distribution avec toujours les 5 priorités standards
        all_standard_priorities = ["Immédiat", "Urgent", "Haut", "Normal", "Bas"]
        computed_priority_dist = []
        for p in all_standard_priorities:
            computed_priority_dist.append({
                "name": p,
                "value": priority_counts.get(p, 0),
                "color": priority_colors.get(p, "#64748b")
            })
        for k, v in priority_counts.items():
            if k not in all_standard_priorities:
                computed_priority_dist.append({
                    "name": k,
                    "value": v,
                    "color": priority_colors.get(k, "#64748b")
                })

        return {
            "project_id": project_id,
            "total_issues": len(all_issues),
            "open_issues": len(open_issues),
            "done_issues": len(done_issues),
            "overdue_issues": len(overdue),
            "not_started": len(not_started),
            "blocking_issues_count": len(blocking_issues),
            "critical_issues_count": len(critical_issues),
            "active_versions": len([v for v in versions if v.get("status") == "open"]),
            "avg_progress": round(final_progress, 1),
            "completion_rate": round(completion_rate, 1),
            "velocity": velocity,
            "max_workload": round(max([min((h / 40) * 100, 100) for h in self.get_time_by_user(project_id).values()], default=0), 1),
            "time_by_user": self.get_time_by_user(project_id),
            "status_distribution": computed_status_dist,
            "priority_distribution": computed_priority_dist,
            "tracker_distribution": [
                {"name": k, "value": v, "color": tracker_colors.get(k, "#3b82f6")}
                for k, v in tracker_counts.items()
            ],
            "critical_issues_list": [
                {
                    "id": i["id"],
                    "subject": i["subject"],
                    "priority": i.get("priority") if isinstance(i.get("priority"), str) else i.get("priority", {}).get("name", "Normal"),
                    "status": i.get("status") if isinstance(i.get("status"), str) else i.get("status", {}).get("name", "Nouveau"),
                    "assigned": (i.get("assigned") or i.get("assigned_to")) if isinstance(i.get("assigned") or i.get("assigned_to"), str) else (i.get("assigned_to") or {}).get("name", "Non assigné")
                } for i in (critical_issues[:4] if critical_issues else open_issues[:4])
            ],
            "overdue_list": [
                {
                    "id": i["id"], 
                    "subject": i["subject"], 
                    "due_date": i.get("due_date"),
                    "assignee": (i.get("assigned") or i.get("assigned_to")) if isinstance(i.get("assigned") or i.get("assigned_to"), str) else (i.get("assigned_to") or {}).get("name", "Non assigné"),
                    "delay_days": (date.today() - date.fromisoformat(i["due_date"])).days if i.get("due_date") else 0
                } for i in overdue
            ],
            "team_workload": team_workload,
            "bottleneck_alert": bottleneck_alert,
            "members_detailed": members_list,
            "total_estimated": total_estimated,
            "not_started_list": [
                {
                    "id": i["id"],
                    "subject": i["subject"],
                    "priority": i.get("priority") if isinstance(i.get("priority"), str) else i.get("priority", {}).get("name", "Normal"),
                    "assignee": (i.get("assigned") or i.get("assigned_to")) if isinstance(i.get("assigned") or i.get("assigned_to"), str) else (i.get("assigned_to") or {}).get("name", "Non assigné")
                } for i in not_started[:4]
            ]
        }

    def create_version_and_assign_issues(self, project_id: str, name: str, description: str = "", issue_ids: list = None, api_key: str = None, **kwargs) -> dict:
        """Crée une version (sprint) sur Redmine et y associe optionnellement des tâches (ou automatiquement si vide)."""
        if not project_id:
            raise Exception("Le projet (project_id) est obligatoire pour créer une version/sprint.")
        if not name:
            raise Exception("Le nom de la version/sprint est obligatoire.")

        # 1. Création de la version dans Redmine
        payload = {
            "version": {
                "name": name,
                "description": description or "",
                "status": "open",
                "sharing": "none"
            }
        }
        
        # Envoyer la requête POST
        version_data = self._post(f"/projects/{project_id}/versions.json", payload, api_key=api_key)
        
        version_id = version_data.get("version", {}).get("id")
        if not version_id:
            raise Exception("Erreur lors de la création de la version sur Redmine.")

        assigned_issues = []
        # 2. Association des tickets (spécifiés ou résolus automatiquement si vide)
        resolved_issue_ids = []
        if issue_ids:
            # S'assurer que c'est une liste
            if isinstance(issue_ids, str):
                try:
                    resolved_issue_ids = [int(id_str.strip()) for id_str in issue_ids.split(",") if id_str.strip()]
                except ValueError:
                    resolved_issue_ids = []
            elif isinstance(issue_ids, list):
                for item in issue_ids:
                    try:
                        resolved_issue_ids.append(int(item))
                    except (ValueError, TypeError):
                        pass
            else:
                try:
                    resolved_issue_ids = [int(issue_ids)]
                except (ValueError, TypeError):
                    pass

        for issue_id in resolved_issue_ids:
            try:
                self._put(f"/issues/{issue_id}.json", {"issue": {"fixed_version_id": version_id}}, api_key=api_key)
                assigned_issues.append(issue_id)
            except Exception as e:
                logger.error(f"[Redmine] Impossible d'associer la tâche {issue_id} à la version {version_id} : {e}")

        # Invalider le cache des tickets pour ce projet pour rafraîchir l'UI
        self._invalidate_project_cache()

        return {
            "success": True,
            "version": version_data.get("version"),
            "assigned_issues": assigned_issues
        }

    def delete_version(self, project_id: str, name: str, api_key: str = None, **kwargs) -> bool:
        """Supprime une version (sprint) sur Redmine."""
        if not project_id:
            raise Exception("Le projet (project_id) est obligatoire pour supprimer une version.")
        if not name:
            raise Exception("Le nom de la version/sprint est obligatoire.")

        # Résoudre l'ID de la version par son nom
        version_id = self.get_version_id_by_name(project_id, name, api_key=api_key)
        if not version_id:
            raise Exception(f"La version/sprint '{name}' n'existe pas dans ce projet.")

        success = self._delete(f"/versions/{version_id}.json", api_key=api_key)
        if success:
            self._invalidate_project_cache()
            logger.info(f"[Redmine] Version '{name}' (ID: {version_id}) supprimée avec succès.")
        return success

    def update_version(self, project_id: str, name: str, new_name: str = None, description: str = None, status: str = None, issue_ids: list = None, api_key: str = None, **kwargs) -> bool:
        """Modifie une version (sprint) sur Redmine."""
        if not project_id:
            raise Exception("Le projet (project_id) est obligatoire pour modifier une version.")
        if not name:
            raise Exception("Le nom de la version actuelle est obligatoire.")

        # Résoudre l'ID de la version par son nom
        version_id = self.get_version_id_by_name(project_id, name, api_key=api_key)
        if not version_id:
            raise Exception(f"La version/sprint '{name}' n'existe pas dans ce projet.")

        # Préparer le payload
        payload = {"version": {}}
        if new_name:
            payload["version"]["name"] = new_name
        if description is not None:
            payload["version"]["description"] = description
        if status:
            payload["version"]["status"] = status

        success = True
        if payload["version"]:
            success = self._put(f"/versions/{version_id}.json", payload, api_key=api_key)

        # Mettre à jour les tâches associées si issue_ids est spécifié
        if issue_ids is not None:
            # Récupérer les tâches actuellement dans la version
            current_sprint_issues = self._get(f"/issues.json", {"project_id": project_id, "fixed_version_id": version_id, "status_id": "*", "limit": 100}, api_key=api_key)
            current_sprint_issue_ids = {i.get("id") for i in current_sprint_issues.get("issues", [])}

            # Normaliser la liste des nouveaux issue_ids
            new_issue_ids = []
            if isinstance(issue_ids, str):
                try:
                    new_issue_ids = [int(id_str.strip()) for id_str in issue_ids.split(",") if id_str.strip()]
                except:
                    pass
            elif isinstance(issue_ids, list):
                for item in issue_ids:
                    try:
                        new_issue_ids.append(int(item))
                    except:
                        pass

            new_issue_ids_set = set(new_issue_ids)

            # A. Retirer les tâches qui ne sont plus cochées
            for cur_id in current_sprint_issue_ids:
                if cur_id not in new_issue_ids_set:
                    try:
                        self._put(f"/issues/{cur_id}.json", {"issue": {"fixed_version_id": ""}}, api_key=api_key)
                        logger.info(f"[Redmine] Tâche {cur_id} retirée du sprint {name}.")
                    except Exception as e:
                        logger.error(f"[Redmine] Erreur lors du retrait de la tâche {cur_id} du sprint {name} : {e}")

            # B. Ajouter les nouvelles tâches cochées
            for new_id in new_issue_ids_set:
                if new_id not in current_sprint_issue_ids:
                    try:
                        self._put(f"/issues/{new_id}.json", {"issue": {"fixed_version_id": version_id}}, api_key=api_key)
                        logger.info(f"[Redmine] Tâche {new_id} ajoutée au sprint {name}.")
                    except Exception as e:
                        logger.error(f"[Redmine] Erreur lors de l'ajout de la tâche {new_id} au sprint {name} : {e}")

        if success:
            self._invalidate_project_cache()
            logger.info(f"[Redmine] Version '{name}' (ID: {version_id}) mise à jour avec succès.")
        return success

# Instance singleton
redmine = RedmineClient()
