# Observabilité et monitoring

L'orchestrateur expose des logs structurés et des métriques pour suivre la santé du système.

## Logs

- Format JSON via `structlog` avec les champs : `timestamp`, `level`, `event`, `job_id`, `phase`, `user_id`, `plan`, `duration_ms`,
  `source_url`, `error_code`.
- Les logs sont envoyés vers stdout (collecté par la plateforme) et peuvent être redirigés vers Loki, Datadog ou CloudWatch.
- Les erreurs répétées (même `error_code` > N/minute) déclenchent une alerte vers l'équipe support.

## Métriques

| Nom                         | Type      | Description                                                  |
|-----------------------------|-----------|--------------------------------------------------------------|
| `clipbot_jobs_started_total`| Counter   | Jobs entrants, tags : `plan`, `mode`, `platform`.            |
| `clipbot_jobs_failed_total` | Counter   | Jobs échoués par `error_code`.                               |
| `clipbot_phase_seconds`     | Histogram | Temps passé par phase (Analyse, AutoPick, Subtitles, Export, Livraison). |
| `clipbot_upload_bitrate`    | Gauge     | Débit moyen observé vers le stockage et Telegram.            |
| `clipbot_queue_length`      | Gauge     | Longueur de la file Redis.                                   |
| `clipbot_webhook_latency`   | Histogram | Latence des webhooks worker -> bot.                          |

Les métriques sont exposées via un endpoint HTTP `/metrics` (Prometheus) optionnel ou envoyées à OpenTelemetry/OTLP.

## Traces

- Les requêtes sortantes vers l'API worker sont tracées (span `worker.call`).
- Les webhooks de retour créent un span `worker.callback` relié au `job_id`.
- Chaque commande Telegram est tracée via `command.<name>`.

## Tableaux de bord

- **Vue opérations** : jobs en cours, succès/échecs, saturation file.
- **Vue produit** : conversions Free -> Pro, durée moyenne clip, plateformes utilisées.
- **Vue qualité** : temps phase, ratio retranscodage, échecs par plateforme.

## Alertes clés

- Jobs échoués > 5 % sur 15 min.
- Temps moyen phase Export > 3 min.
- Aucune mise à jour de progression > 60 s (job bloqué).
- Stockage temporaire > 80 % de la limite.
