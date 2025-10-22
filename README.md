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
    routing.py          # Assemblage du routeur aiogram (polling + tâches récurrentes).
  config.py             # Paramètres (tokens, URLs, quotas) avec Pydantic.
  const.py              # Constantes partagées (phases, formats, plans, etc.).
  logging.py            # Initialisation de structlog avec enrichissement contextuel.
  main.py               # Point d'entrée pour lancer le bot.
  models.py             # Modèles Pydantic (presets, options pro, jobs, quotas).
  services/
    local_clip.py       # Pipeline local (yt-dlp, sélection segments, encodage FFmpeg).
    manual.py           # Gestion de l'assistant manuel (états et transitions).
    pipeline.py         # Orchestrateur des jobs (phases, progression, stockage).
    presets.py          # Catalogue des presets 1-clic.
    progress.py         # Calcul du pourcentage/ETA et publication des statuts.
    storage.py          # Gestion du stockage local (volume/RAM disk) et cloud (pré-signature S3).
    preferences.py      # Persistance des préférences utilisateur (/settings).
    prerequisites.py    # Vérifications de démarrage (FFmpeg/yt-dlp, stockage prêt).
    telegram.py         # Fonctions utilitaires spécifiques à Telegram (claviers, callbacks).
    plans.py            # Gestion des plans Free/Pro, quotas et facturation.
  telemetry.py          # Instrumentation (métriques, traces, alertes).
  utils.py              # Helpers communs (validation URL, conversions durées, etc.).
```

Des tests unitaires couvrent les règles métier essentielles (presets, options pro, progression et scoring).

## Configuration

Créez un fichier `.env` (ou exportez les variables) avec les paramètres minimums suivants :

```
BOT_TOKEN=123456:ABCDEF
STORAGE_MODE=local
LOCAL_OUTPUT_DIR=~/Downloads/Clips_TMP
LOCAL_DELETE_ON_COMPLETE=true
LOCAL_RETENTION_MIN=60
# Optionnels :
# EXTERNAL_VOLUME_PATH=/Volumes/CLIPS
# USE_RAMDISK=false
# RAMDISK_SIZE_MB=4096
```

Le mode cloud reste configurable (variables `S3_*`), mais le pipeline fourni ici implémente avant tout le chemin local
(téléchargement via yt-dlp, analyse audio/chapitres, encodage FFmpeg, upload direct vers Telegram).

## Lancement local macOS

1. Installer les dépendances système avec Homebrew :

   ```bash
   brew install ffmpeg yt-dlp
   ```

2. Installer les dépendances Python :

   ```bash
   pip install poetry
   poetry install
   ```

3. Vérifier/adapter le dossier local configuré (`LOCAL_OUTPUT_DIR`) : il est créé automatiquement au démarrage si besoin.

4. Lancer le bot en mode polling :

   ```bash
   poetry run python -m cliping_bot.main
   ```

Au lancement, le bot purge les jobs temporaires plus anciens que `LOCAL_RETENTION_MIN`, contrôle la présence de `ffmpeg` et
`yt-dlp`, puis accepte les commandes `/clip`, `/select`, `/status`, `/settings`, etc. La commande `/clip` télécharge la source,
sélectionne automatiquement les segments pertinents (chapitres s'il y en a, sinon détection des silences et pics d'énergie
audio), encode chaque clip au format demandé (TikTok 9:16 par défaut, fallback 720p si nécessaire) puis les envoie
directement sur Telegram avant de supprimer les fichiers locaux si `LOCAL_DELETE_ON_COMPLETE=true`.

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
