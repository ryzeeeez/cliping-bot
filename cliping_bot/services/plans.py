"""Gestion des plans Free/Pro et quotas."""

from __future__ import annotations

from dataclasses import dataclass

from ..const import (
    MAX_CLIPS_FREE,
    MAX_CLIPS_PRO,
    MAX_FREE_CLIP_DURATION,
    MAX_PRO_CLIP_DURATION,
    SubscriptionPlan,
)


@dataclass(frozen=True)
class PlanDetails:
    name: str
    description: str
    max_clips: int
    max_duration: int
    watermark_locked: bool
    priority_multiplier: float


PLAN_REGISTRY: dict[SubscriptionPlan, PlanDetails] = {
    SubscriptionPlan.FREE: PlanDetails(
        name="Free",
        description="3 clips max / jour, watermark obligatoire, file standard.",
        max_clips=MAX_CLIPS_FREE,
        max_duration=MAX_FREE_CLIP_DURATION,
        watermark_locked=True,
        priority_multiplier=1.0,
    ),
    SubscriptionPlan.PRO: PlanDetails(
        name="Pro",
        description="10 clips max, watermark optionnel, priorité et support.",
        max_clips=MAX_CLIPS_PRO,
        max_duration=MAX_PRO_CLIP_DURATION,
        watermark_locked=False,
        priority_multiplier=0.5,
    ),
}


def describe_plan(plan: SubscriptionPlan) -> str:
    details = PLAN_REGISTRY[plan]
    watermark = "obligatoire" if details.watermark_locked else "optionnel"
    return (
        f"**{details.name}** — jusqu'à {details.max_clips} clips, {details.max_duration}s max, "
        f"watermark {watermark}, priorité ×{details.priority_multiplier}.\n"
        f"{details.description}"
    )


__all__ = ["PLAN_REGISTRY", "PlanDetails", "describe_plan"]
