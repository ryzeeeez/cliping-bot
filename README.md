# Cliping Bot

Bot Telegram de clipping vidéo multi-plateformes (YouTube, Twitch, Kick, Rumble, liens directs MP4) avec pipeline 100 % cloud.
Ce dépôt contient l'orchestrateur du bot et la documentation d'architecture pour répondre aux exigences produit décrites dans le
brief.

## Fonctionnalités majeures

- **Modes Auto, Manuel et Podcast/Chapitres** avec presets 1-clic et options pro avancées.
- **Pipeline URL → URL** : aucun fichier n'est stocké localement, les fichiers temporaires sont conservés dans un stockage
  éphémère avec TTL < 24 h et transmis à Telegram via URL pré-signée.
- **Suivi de progression temps réel** (message unique édité toutes les 2–3 s) avec phases, barre de progression, ETA et boutons
  d'action.
- **Monétisation Free/Pro**, administration, observabilité (logs structurés, métriques) et respect des droits (validation d'URL,
  refus privé/DRM, RGPD).

## Structure du projet

```
cliping_bot/
  bot/
    handlers.py         # Déclarations des commandes Telegram et du routeur principal.
    keyboards.py        # Génération des claviers inline/boutons.
    messages.py         # Templates de messages localisés en français.
    routing.py          # Assemblage de l'application python-telegram-bot.
  config.py             # Paramètres (tokens, URLs, quotas) avec Pydantic.
  const.py              # Constantes partagées (phases, formats, plans, etc.).
  logging.py            # Initialisation de structlog avec enrichissement contextuel.
  main.py               # Point d'entrée pour lancer le bot.
  models.py             # Modèles Pydantic (presets, options pro, jobs, quotas).
  services/
    auto_clip.py        # Stratégie de sélection automatique des meilleurs moments (scoring).
    manual.py           # Gestion de l'assistant manuel (états et transitions).
    pipeline.py         # Orchestrateur des jobs (phases, progression, contrôle des workers).
    presets.py          # Catalogue des presets 1-clic.
    progress.py         # Calcul du pourcentage/ETA et publication des statuts.
    storage.py          # Interface de stockage éphémère (S3/R2) et nettoyage TTL.
    tasks.py            # Client pour les workers cloud (ingestion, ASR, export).
    telegram.py         # Fonctions utilitaires spécifiques à Telegram (envoi par URL, file_id).
    plans.py            # Gestion des plans Free/Pro, quotas et facturation.
    admin.py            # Services admin + observabilité.
  telemetry.py          # Instrumentation (métriques, traces, alertes).
  utils.py              # Helpers communs (validation URL, conversions durées, etc.).
```

Des tests unitaires couvrent les règles métier essentielles (presets, options pro, progression et scoring).

## Lancer le bot en local

1. Créer un fichier `.env` (ou variables d'environnement) avec au minimum :
   - `TELEGRAM_TOKEN` : token BotFather
   - `STORAGE_ENDPOINT`, `STORAGE_BUCKET`, `STORAGE_KEY`, `STORAGE_SECRET`
   - `TASKS_API_URL` : endpoint des workers cloud
2. Installer les dépendances :

```bash
pip install poetry
poetry install
```

3. Lancer le bot :

```bash
poetry run python -m cliping_bot.main
```

Le bot utilise python-telegram-bot en mode async, Redis pour la file d'attente/état et httpx pour communiquer avec les services
cloud (transcodage, ASR, scoring). Les workers traitent la vidéo en cloud et renvoient des URLs pré-signées prêtes à être
transmises à Telegram.

## Documentation

- [`docs/spec.md`](docs/spec.md) : cahier des charges complet fourni dans le brief.
- [`docs/architecture.md`](docs/architecture.md) : architecture logique, pipeline cloud et stratégie de progression.
- [`docs/observability.md`](docs/observability.md) : événements, logs et métriques.

## Tests

```bash
poetry run pytest
```

## Licence

MIT
