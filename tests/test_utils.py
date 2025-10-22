import pytest

from cliping_bot.utils import URLValidationError, human_readable_timedelta, moving_average, validate_source_url


def test_validate_source_url_accepts_https():
    assert validate_source_url("https://example.com/video") == "https://example.com/video"


def test_validate_source_url_rejects_invalid():
    with pytest.raises(URLValidationError):
        validate_source_url("ftp://example.com")


def test_human_readable_timedelta():
    assert human_readable_timedelta(125) == "2:05"


def test_moving_average():
    assert round(moving_average([1, 2, 3], alpha=0.5), 2) == 2.25
