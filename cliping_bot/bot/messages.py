"""Templates de messages en français."""

from __future__ import annotations

from ..services import plans

from ..const import StorageMode


def start_header(storage_mode: StorageMode) -> str:
    mode_label = "Local" if storage_mode is StorageMode.LOCAL else "Cloud"
    return (
        "👋 Bienvenue sur Cliping Bot !\n"
        "Choisis un preset pour clipper en 1 clic. Le Mode Pro offre des réglages avancés.\n"
        f"Mode de stockage actuel : {mode_label}. Modifie-le via /settings."
    )


HELP_MESSAGE = (
    "ℹ️ *Comment ça marche ?*\n"
    "• `/clip <URL>` : génération auto avec preset par défaut (TikTok 3×30s).\n"
    "• `/select <URL>` : mode manuel assisté avec boutons.\n"
    "• `/status` : voir la file d'attente et la progression.\n"
    "• `/plans` : comparer Free vs Pro.\n"
    "• `/settings` : choisir stockage Local/Cloud et options de rendu.\n"
    "• `/cancel` : annuler le job courant.\n"
    "Le mode Local écrit dans un dossier temporaire puis nettoie automatiquement selon ta configuration."
)

ERROR_INVALID_URL = "🚫 Lien invalide. Vérifie que l'URL commence par https://"
ERROR_PRIVATE = "🔒 Impossible de clipper une source privée ou protégée DRM."
ERROR_GENERIC = "❌ Oups, une erreur est survenue. Appuie sur Réessayer ou contacte le support."
CANCELLED_MESSAGE = "❌ Job annulé. Les ressources temporaires ont été nettoyées."


def plans_message() -> str:
    return "\n\n".join(plans.describe_plan(plan) for plan in plans.PLAN_REGISTRY)


def job_created(storage_mode: StorageMode) -> str:
    if storage_mode is StorageMode.LOCAL:
        return "Job créé. Analyse en cours… (mode local)"
    return "Job créé. Analyse en cours… (mode cloud)"


def settings_overview(storage_mode: StorageMode) -> str:
    mode_label = "Local" if storage_mode is StorageMode.LOCAL else "Cloud"
    return (
        "🗃️ *Paramètres de stockage*\n"
        f"Mode actuel : {mode_label}.\n"
        "Choisis Local pour travailler sur ce Mac (dossier temporaire nettoyé automatiquement)"
        " ou Cloud pour un pipeline URL→URL 24 h."
    )
