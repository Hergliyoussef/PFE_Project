import asyncio
import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(r"e:\projets\pm-chatbot-pfe\backend"))

from services.redmine_client import redmine

async def main():
    project_ids = ["87", "86", "84"]
    for pid in project_ids:
        print(f"--- Projet {pid} ---")
        try:
            # We need to set the context or use the admin key
            # The RedmineClient uses settings.redmine_api_key by default
            metrics = redmine.compute_project_metrics(pid)
            print(f"Retards : {metrics.get('overdue_issues')} tâches")
            for issue in metrics.get('overdue_list', []):
                print(f"  - #{issue['id']}: {issue['subject']} (Retard: {issue['delay_days']} jours, Assigné à: {issue['assignee']})")
        except Exception as e:
            print(f"Erreur pour le projet {pid}: {e}")
        print()

if __name__ == "__main__":
    asyncio.run(main())
