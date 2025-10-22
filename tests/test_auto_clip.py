from cliping_bot.models import ClipOptions
from cliping_bot.services.auto_clip import AutoClipper, ScoredWindow


def test_auto_clipper_respects_diversity():
    options = ClipOptions(clips=3, duration=30)
    clipper = AutoClipper(options)
    candidates = [
        ScoredWindow(start=i * 5, end=i * 5 + 35, score=10 - i)
        for i in range(6)
    ]
    selected = clipper.pick(candidates)
    assert len(selected) <= options.clips
    assert all(b.start - a.start >= 10 for a, b in zip(selected, selected[1:]))
