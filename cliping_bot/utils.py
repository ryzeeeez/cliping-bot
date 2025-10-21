"""Fonctions utilitaires diverses."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Iterable

URL_REGEX = re.compile(r"^https?://[\w.-]+(?:/[\w\-.~:/?#\[\]@!$&'()*+,;=%]*)?$")


class URLValidationError(ValueError):
    """Exception levée si l'URL fournie est invalide ou non autorisée."""


def validate_source_url(url: str) -> str:
    """Valide l'URL entrante selon les contraintes plateformes."""

    if not URL_REGEX.match(url):
        raise URLValidationError("URL invalide ou protocole non supporté.")
    return url


def human_readable_timedelta(seconds: float) -> str:
    """Transforme un float (en secondes) en chaîne 'M:SS'."""

    delta = timedelta(seconds=int(seconds))
    total_minutes = delta.seconds // 60
    remaining_seconds = delta.seconds % 60
    return f"{total_minutes}:{remaining_seconds:02d}"


def moving_average(data: Iterable[float], alpha: float = 0.3) -> float:
    """Calcule une moyenne mobile exponentielle simple."""

    iterator = iter(data)
    try:
        value = next(iterator)
    except StopIteration as exc:  # pragma: no cover - garde-fou
        raise ValueError("data must contain at least one value") from exc

    avg = value
    for value in iterator:
        avg = alpha * value + (1 - alpha) * avg
    return avg
