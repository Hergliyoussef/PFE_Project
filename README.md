🤖 PM Assistant — Chatbot IA de Gestion de Projet
Système multi-agents intelligent connecté à Redmine
Projet de Fin d'Études — Ingénieur Data Science & Intelligence Artificielle
Elyos Digital — 2026
🎯 À propos
PM Assistant est un chatbot intelligent basé sur une architecture multi-agents LangChain qui assiste les chefs de projet dans leurs tâches quotidiennes. Il se connecte directement à Redmine pour analyser les données en temps réel, détecter les anomalies de manière proactive et générer des rapports automatiques.

"Transformez vos données Redmine en intelligence conversationnelle"

✨ Fonctionnalités
💬 Chat en langage naturel

Interface conversationnelle en français et anglais
Classification NLP de l'intention via LLM
Gestion des questions hors sujet et clarifications
Historique persistant des conversations

📊 Analyse temps réel

Métriques globales du projet (avancement, retards, charge)
Détection automatique des tâches en retard
Score de risque calculé (0 → 1) avec 3 critères pondérés
Charge de travail par membre de l'équipe

🚨 Monitoring proactif

Vérification automatique toute 1 minute
Alertes Redis temps réel (retards, surcharge, risques)
Notifications toast dans l'interface React
Refresh automatique côté frontend toutes les 30 secondes

📋 Génération de rapports

Rapport de statut structuré pour réunions
Résumé exécutif pour CEO
Rapport client professionnel
Export téléchargeable

⚡ Actions sur Redmine

Création de tâches en langage naturel
Réaffectation automatique des ressources
Mise à jour des échéances
Création de sprints


🏗️ Architecture
┌─────────────────────────────────────────────────────────┐
│                    Frontend React                        │
│         Dashboard · Chat · Alertes · Métriques          │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP REST
┌──────────────────────▼──────────────────────────────────┐
│                   FastAPI Backend                        │
│              /chat · /metrics · /alerts                  │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│             Système Multi-Agents LangChain               │
│                                                          │
│  ┌─────────────┐    ┌──────────┐    ┌────────────────┐  │
│  │ Superviseur │───▶│ Analyste │    │   Rapporteur   │  │
│  │  NLP Router │    │ ReAct+   │    │  Génération    │  │
│  └──────┬──────┘    │  Tools   │    │   Rapports     │  │
│         │           └──────────┘    └────────────────┘  │
│         │           ┌────────────────────────────────┐  │
│         └──────────▶│   Agent de Planification       │  │
│                     │   Écriture sur Redmine          │  │
│                     └────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
┌───────▼──────┐ ┌─────▼────┐ ┌──────▼──────┐
│   Redmine    │ │PostgreSQL│ │    Redis     │
│  API REST    │ │Historique│ │Cache+Alertes│
│  localhost   │ │   Users  │ │  TTL auto   │
└──────────────┘ └──────────┘ └─────────────┘
