"""Tests for utils.py"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import (
    format_time, format_size, format_duration,
    sanitize_name, get_camera_mode, extract_activity_from_title
)


def test_format_time_seconds():
    assert format_time(30) == "30s"
    assert format_time(0) == "0s"


def test_format_time_minutes():
    assert format_time(65) == "1m 5s"
    assert format_time(120) == "2m 0s"


def test_format_time_hours():
    assert format_time(3665) == "1h 1m"
    assert format_time(7200) == "2h 0m"


def test_format_time_negative():
    assert format_time(-1) == "calculating..."
    assert format_time(float('inf')) == "calculating..."


def test_format_size_bytes():
    assert format_size(500) == "500 B"


def test_format_size_kb():
    assert format_size(1024) == "1.0 KB"
    assert format_size(2048) == "2.0 KB"


def test_format_size_mb():
    assert format_size(1024 * 1024) == "1.0 MB"
    assert format_size(1024 * 1024 * 500) == "500.0 MB"


def test_format_size_gb():
    assert format_size(1024 * 1024 * 1024) == "1.00 GB"
    assert format_size(1024 * 1024 * 1024 * 2.5) == "2.50 GB"


def test_format_duration():
    assert format_duration(60000) == "01:00"
    assert format_duration(125000) == "02:05"
    assert format_duration(3661000) == "01:01:01"


def test_format_duration_none():
    assert format_duration(None) is None
    assert format_duration("invalid") is None


def test_sanitize_name():
    assert sanitize_name("Hello World") == "HelloWorld"
    assert sanitize_name("Hello!@#World") == "Helloworld"
    assert sanitize_name("café") == "Café"
    assert sanitize_name("") == ""
    assert sanitize_name(None) == ""


def test_sanitize_name_length_limit():
    long_name = "A" * 50
    assert len(sanitize_name(long_name)) == 30


def test_get_camera_mode():
    assert get_camera_mode("video", "TimeLapse") == "TimeLapse"
    assert get_camera_mode("video", "TimeWarp") == "TimeWarp"
    assert get_camera_mode("photo", "Photo") == "Photo"
    assert get_camera_mode("video", None) == "Video"
    assert get_camera_mode(None, None) == "Unknown"


def test_extract_activity_from_title():
    assert extract_activity_from_title("Morning bike ride") == ["Bike", "Ride"]
    assert extract_activity_from_title("Hiking in mountains") == ["Hiking", "Mountain"]
    assert extract_activity_from_title("Random title") is None
    assert extract_activity_from_title("") is None
    assert extract_activity_from_title(None) is None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
