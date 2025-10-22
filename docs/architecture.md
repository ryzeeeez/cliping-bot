# Architecture fonctionnelle

Cette architecture vise à satisfaire les exigences de clipping vidéo multi-plateformes tout en respectant le mode de stockage
choisi par l'utilisateur : local (Mac/volume externe/RAM disk) ou cloud URL→URL. L'accent est mis sur le découplage entre le bot
Telegram (orchestration) et les workers (traitement vidéo) qu'ils s'exécutent localement ou dans le cloud.

## Vue d'ensemble

```
Utilisateur ─Telegram─> Bot (aiogram v3)
                     │
                     ├─> Redis (file d'attente jobs + états manuels)
                     ├─> API Workers (HTTP/JSON, idempotent)
                     ├─> Stockage local (volume externe / RAM disk / dossier temporaire)
                     └─> Stockage éphémère (S3/R2) via URL pré-signées

Workers (local ou cloud)
  ├─ Ingestion (download URL -> stockage éphémère)
  ├─ Auto-pick (analyse audio/vidéo, scoring, diversité)
  ├─ ASR & diarisation (Whisper ou équivalent)
  ├─ Export FFmpeg (recadrage, safe zones, normalisation audio)
  └─ Livraison (mode local : chemin fichier + upload Telegram / mode cloud : URL pré-signée + file_id reuse)
```

Le bot ne manipule que des métadonnées ; il délègue l'écriture des fichiers soit au dossier local éphémère, soit au stockage
cloud. En mode cloud, le worker renvoie une URL pré-signée et, si disponible, un `file_id` Telegram permettant de réutiliser le
média sans upload. En mode local, le worker renvoie le chemin du fichier afin que le bot déclenche l'envoi à Telegram puis la
suppression.

## Pipeline d'un job

1. **Analyse (0-10 %)** : récupération métadonnées de la source (API plateformes, HEAD HTTP, durée, DRM, droits).
2. **Auto-pick (10-30 %)** : scoring énergétique + indices contextuels + sous-titres existants.
3. **Sous-titres (30-60 %)** : ASR multilingue, diarisation simple (A/B), stylage (clean/karaoke/compact).
4. **Export (60-90 %)** : transcodage FFmpeg avec préréglages (format, fps, LUT safe zones, watermark selon plan).
5. **Livraison (90-100 %)** :
   - Mode Local : upload final vers Telegram à partir du fichier local, suivi de la suppression selon `LOCAL_DELETE_ON_COMPLETE`.
   - Mode Cloud : upload dans le bucket éphémère via URL pré-signée, puis envoi à Telegram par URL.

Chaque phase est tracée via `ProgressTracker`, qui alimente le message de statut édité toutes les 2–3 secondes.

## Gestion de la progression

Le `ProgressTracker` stocke pour chaque job :

- phase courante
- pourcentage cible de début/fin
- débit moyen historique par phase (dérivé des jobs précédents)
- timecodes des clips générés

Un filtre exponentiel permet de lisser les ETA et de réagir aux ralentissements. Les boutons du message de statut :

- 🔕 *Mute* : stop les éditions, ne laisse que la notification finale.
- 📊 *Détails* : affiche un résumé détaillé (temps/phase, résolution, poids, clips).
- ⏩ *Priorité Pro* : propose l'upgrade plan Pro si l'utilisateur est Free.
- ❌ *Annuler* : annule le job (DELETE sur API workers + nettoyage TTL).

## Mode Auto

La stratégie de scoring mixe :

- énergie audio RMS + dérivées (pics)
- rythme de parole (ASR) et pauses détectées
- détection de cuts via histogrammes/flux optique
- pics de chat (via API plateformes si accessible)
- mots-clés positifs/émotionnels dans les sous-titres

Les segments sont triés, filtrés pour la diversité (>10 s de séparation), puis ajustés sur les pauses pour éviter les coupes
brusques (marge +20 % max).

## Mode Manuel

Une machine à états conserve la position actuelle, les clips définis et les points d'entrée/sortie. Les interactions se font via
un clavier inline : décalages ±1 s/±10 s, fixateurs de début/fin, aperçu 10 s (URL pré-signée du worker), ajout de clip et
confirmation. Les coupes finales sont ajustées avec une marge de 300 ms pour éviter les coupures de mots.

## Monétisation et plans

Les plans sont décrits dans `services/plans.py` avec quotas par type d'utilisateur. Le watermark est activé par défaut pour le plan
Free et peut être désactivé en Pro. Les commandes `/plans` et `/start` affichent des informations détaillées et incitent à l'upgrade.

Les limites (clips max, durée, formats) sont validées côté bot et côté worker pour éviter les abus.

## Observabilité

- Logs structurés par `structlog`, corrélés via `job_id`.
- Metrics (Prometheus/OpenTelemetry) : temps par phase, débit upload, taux d'échec.
- Alertes sur taux d'erreur > seuil, lenteurs, dépassement quota.

## Sécurité et conformité

- Validation stricte des URLs (protocoles https, domaines autorisés, absence de DRM). Les vidéos privées/DRM renvoient un message
  pédagogique expliquant l'échec.
- Confirmation utilisateur sur le respect des droits lors du premier job.
- Commande RGPD pour suppression des données (`/delete_me`).

## Nettoyage

Les workers cloud utilisent des buckets avec règle de cycle de vie < 24 h. Les URLs pré-signées expirent en < 24 h. Les jobs
locaux suppriment les dossiers temporaires une fois l'envoi Telegram confirmé ou lors de la purge périodique. En cas d'annulation
ou d'échec, un webhook/cleanup supprime immédiatement les ressources temporaires (locales ou cloud).

## Admin et dashboard

Une commande restreinte `/admin` affiche : jobs actifs, échecs récents, boutons pour remboursement (annulation + crédit), ban/unban
utilisateur, ajustement des quotas et export CSV quotidien. Les logs JSON sont consultables via un outil tiers (par ex. Loki/Kibana).
## Mode Local

Lorsque `storage_mode=local`, le bot réserve un dossier par job en respectant l'ordre de priorité suivant : volume externe monté
(`EXTERNAL_VOLUME_PATH`), RAM disk (`USE_RAMDISK=true`) puis dossier local (`LOCAL_OUTPUT_DIR`). Un nettoyeur périodique supprime
les dossiers dont l'âge dépasse `LOCAL_RETENTION_MIN` minutes ou immédiatement si `LOCAL_DELETE_ON_COMPLETE=true`. Les
problèmes d'accès disque (volume éjecté, permissions) déclenchent un fallback automatique vers le support suivant avec journal
d'avertissement et message utilisateur.

## Mode Cloud

Lorsque `storage_mode=cloud`, le traitement reste 100 % cloud : ingestion, transcodage et livraison se font dans un bucket à
TTL < 24 h. Les URL pré-signées sont envoyées au bot qui publie le média vers Telegram par URL. Les reposts identiques peuvent
réutiliser le `file_id` retourné.
