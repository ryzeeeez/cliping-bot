from cliping_bot.const import JobPhase
from cliping_bot.services.progress import ProgressTracker


def test_progress_tracker_estimate_eta():
    tracker = ProgressTracker("job-1")
    tracker.phase_started(JobPhase.ANALYSE)
    progress = tracker.update_progress(JobPhase.ANALYSE, 0.5)
    assert progress.percent == 5.0
    tracker.phase_completed(JobPhase.ANALYSE)
    progress = tracker.update_progress(JobPhase.AUTO_PICK, 0.25)
    assert progress.percent == 15.0
    assert progress.eta_seconds is None or progress.eta_seconds >= 1


def test_progress_tracker_stalled_flag():
    tracker = ProgressTracker("job-2")
    tracker._last_update_ts -= 120  # simulate old update
    assert tracker.stalled()
