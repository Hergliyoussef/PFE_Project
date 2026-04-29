
import sys
import os
# Adjust path to include backend
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.redmine_client import redmine
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Hardcode config for the script
redmine.base_url = "http://127.0.0.1:3000"
redmine.api_key = "8d54329fd5592c351bfe0e3b5c2108160ca292bb"
redmine.headers["X-Redmine-API-Key"] = redmine.api_key

def init_innostream():
    try:
        # 1. Create Project
        logger.info("Creating project InnoStream...")
        project = redmine.create_project(
            name="InnoStream",
            identifier="innostream",
            description="Projet de test pour la validation des fonctionnalités du chatbot PFE 2024 — focus sur l'innovation et le streaming."
        )
        project_id = "innostream"
        logger.info(f"Project created/found: {project}")

        # 2. Add Members
        members = [
            {"user": "youssef", "role_id": 6}, # CEO
            {"user": "teyssir", "role_id": 4}, # Développeur
            {"user": "amira", "role_id": 3},   # Manager (Chef de projet)
            {"user": "ibrahim", "role_id": 5}, # Rapporteur
            {"user": "mariem", "role_id": 4},  # Développeur
            {"user": "khalil", "role_id": 4},  # Développeur
            {"user": "aziz", "role_id": 4},    # Développeur (Nouveau)
            {"user": "bassem", "role_id": 5},  # Rapporteur (Nouveau)
        ]

        for m in members:
            logger.info(f"Adding member {m['user']} with role {m['role_id']}...")
            try:
                redmine.add_project_member(
                    project_id=project_id,
                    user_id=m['user'],
                    role_ids=[m['role_id']]
                )
            except Exception as e:
                logger.error(f"Error adding member {m['user']}: {e}")

        # 3. Create Issues
        issues = [
            {
                "subject": "Mise à jour du dashboard analytique",
                "user_id": "teyssir",
                "tracker_id": 2, # Evolution
                "status_id": 1,  # Nouveau
                "priority_id": 2 # Normal
            },
            {
                "subject": "Bug affichage des rôles CEO",
                "user_id": "youssef",
                "tracker_id": 1, # Anomalie
                "status_id": 2,  # En cours
                "priority_id": 3 # Haut
            },
            {
                "subject": "Rédaction des tests unitaires",
                "user_id": "aziz",
                "tracker_id": 2, # Evolution
                "status_id": 1,  # Nouveau
                "priority_id": 2 # Normal
            },
            {
                "subject": "Revue de la documentation technique",
                "user_id": "bassem",
                "tracker_id": 3, # Assistance
                "status_id": 1,  # Nouveau
                "priority_id": 1 # Bas
            }
        ]

        for issue_params in issues:
            logger.info(f"Creating issue: {issue_params['subject']}...")
            try:
                redmine.create_issue(
                    project_id=project_id,
                    **issue_params
                )
            except Exception as e:
                logger.error(f"Error creating issue {issue_params['subject']}: {e}")

        logger.info("Initialization of InnoStream completed successfully.")

    except Exception as e:
        logger.error(f"Global error during init: {e}")

if __name__ == "__main__":
    init_innostream()
