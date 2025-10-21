"""Templates de messages en français."""

from __future__ import annotations

from ..services import plans

START_HEADER = (
    "👋 Bienvenue sur Cliping Bot !\n"
    "Choisis un preset pour clipper en 1 clic. Le Mode Pro offre des réglages avancés."
)

HELP_MESSAGE = (
    "ℹ️ *Comment ça marche ?*\n"
    "• `/clip <URL>` : génération auto avec preset par défaut (TikTok 3×30s).\n"
    "• `/select <URL>` : mode manuel assisté avec boutons.\n"
    "• `/status` : voir la file d'attente et la progression.\n"
    "• `/plans` : comparer Free vs Pro.\n"
    "• `/cancel` : annuler le job courant.\n"
    "Toutes les vidéos sont traitées dans le cloud, aucun fichier n'est stocké localement."
)

ERROR_INVALID_URL = "🚫 Lien invalide. Vérifie que l'URL commence par https://"
ERROR_PRIVATE = "🔒 Impossible de clipper une source privée ou protégée DRM."
ERROR_GENERIC = "❌ Oups, une erreur est survenue. Appuie sur Réessayer ou contacte le support."
CANCELLED_MESSAGE = "❌ Job annulé. Les ressources cloud ont été nettoyées."


def plans_message() -> str:
    return "\n\n".join(plans.describe_plan(plan) for plan in plans.PLAN_REGISTRY)
