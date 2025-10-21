# Cliping Bot

Bot Telegram de clipping vidéo multi-plateformes (YouTube, Twitch, Kick, Rumble, liens MP4 directs) avec deux modes de stockage
exclusifs : traitement local (Mac/volume externe/RAM disk) ou pipeline cloud URL→URL. Ce dépôt contient l'orchestrateur du bot
et la documentation d'architecture pour répondre aux exigences produit décrites dans le brief.

## Fonctionnalités majeures

- **Modes Auto, Manuel et Podcast/Chapitres** avec presets 1-clic et options pro avancées.
- **Stockage local ou cloud** : choix par utilisateur (via /settings) entre un dossier temporaire nettoyé automatiquement
  (supportant volume externe ou RAM disk) et le pipeline URL→URL 100 % cloud (TTL < 24 h, URL pré-signées envoyées à Telegram).
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
    pipeline.py         # Orchestrateur des jobs (phases, progression, stockage).
    presets.py          # Catalogue des presets 1-clic.
    progress.py         # Calcul du pourcentage/ETA et publication des statuts.
    storage.py          # Gestion du stockage local (volume/RAM disk) et cloud (pré-signature S3).
    preferences.py      # Persistance des préférences utilisateur (/settings).
    prerequisites.py    # Vérifications de démarrage (FFmpeg/yt-dlp, stockage prêt).
    tasks.py            # Client pour les workers locaux/cloud (ingestion, ASR, export).
    telegram.py         # Fonctions utilitaires spécifiques à Telegram (claviers, callbacks).
    plans.py            # Gestion des plans Free/Pro, quotas et facturation.
  telemetry.py          # Instrumentation (métriques, traces, alertes).
  utils.py              # Helpers communs (validation URL, conversions durées, etc.).
```

Des tests unitaires couvrent les règles métier essentielles (presets, options pro, progression et scoring).

## Lancer le bot en local

1. Installer les dépendances système : `ffmpeg` et `yt-dlp` doivent être disponibles dans le `PATH`.
2. Créer un fichier `.env` (ou exporter les variables) avec au minimum :
   - `TELEGRAM_TOKEN` : token BotFather
   - `TASKS_API_URL` : endpoint de l'orchestrateur worker (local ou cloud)
   - `STORAGE_MODE=local|cloud`
   - Mode Local (par défaut si variable absente)
     - `LOCAL_OUTPUT_DIR=~/Downloads/Clips_TMP`
     - `LOCAL_RETENTION_MIN=60`
     - `LOCAL_DELETE_ON_COMPLETE=true`
     - `EXTERNAL_VOLUME_PATH=/Volumes/CLIPS` (optionnel)
     - `USE_RAMDISK=false` / `RAMDISK_SIZE_MB=4096`
   - Mode Cloud
     - `STORAGE_PROVIDER=s3`
     - `S3_ENDPOINT=https://...`
     - `S3_BUCKET=...`
     - `S3_ACCESS_KEY_ID=...`
     - `S3_SECRET_ACCESS_KEY=...`
     - `STORAGE_TTL_HOURS=24`
3. Installer les dépendances Python :

```bash
pip install poetry
poetry install
```

4. Lancer le bot :

```bash
poetry run python -m cliping_bot.main
```

Au démarrage, le bot vérifie la présence de `ffmpeg`/`yt-dlp` et prépare le stockage local (création du dossier, purge des
fichiers > `LOCAL_RETENTION_MIN`). La commande `/settings` permet ensuite à chaque utilisateur de basculer entre le mode Local
et le mode Cloud :

- *Local* : les vidéos sont téléchargées/transcodées sur la machine hôte (volume externe prioritaire, sinon RAM disk si activé,
  sinon dossier local). `LOCAL_DELETE_ON_COMPLETE=true` supprime les fichiers dès l'envoi réussi vers Telegram, sinon une purge
  périodique les retire.
- *Cloud* : pipeline URL→URL avec génération d'URL pré-signée (TTL < 24 h) et envoi direct de l'URL à Telegram.

Le bot utilise python-telegram-bot en mode async, Redis pour la file d'attente/état et httpx pour communiquer avec les services
de traitement (transcodage, ASR, scoring). Les workers renvoient soit un chemin local (mode local) soit une URL pré-signée
(mode cloud) afin de finaliser la livraison vers Telegram.

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
