from cliping_bot.const import SubscriptionPlan
from cliping_bot.models import ClipOptions
from cliping_bot.services.presets import PRESETS, get_default_preset


def test_presets_contains_expected_count():
    assert len(PRESETS) == 5


def test_default_preset_auto_tiktok():
    preset = get_default_preset()
    assert "TikTok" in preset.name
    assert preset.options.format.value == "tiktok"


def test_plan_limits_free_enforces_watermark():
    options = ClipOptions(clips=3, duration=60)
    options.ensure_plan_limits(SubscriptionPlan.FREE)
    assert options.watermark == "on"
    assert options.watermark_text == "@clipingbot"


def test_plan_limits_pro_keeps_duration():
    options = ClipOptions(clips=5, duration=90, watermark="off")
    options.ensure_plan_limits(SubscriptionPlan.PRO)
    assert options.watermark_text == "@clipingbot"
