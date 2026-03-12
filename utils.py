"""Utility functions for formatting and text processing."""

import re


def format_time(seconds):
    """Format seconds to human readable time."""
    if seconds < 0 or seconds == float('inf'):
        return "calculating..."

    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins}m {secs}s"
    else:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h {mins}m"


def format_size(bytes_val):
    """Format bytes to human readable size."""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"


def format_duration(ms):
    """Format milliseconds to HH:MM:SS."""
    if not ms:
        return None
    try:
        ms = int(ms)
    except (ValueError, TypeError):
        return None
    seconds = int(ms / 1000)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def sanitize_name(name):
    """Sanitize folder/file names."""
    if not name:
        return ""
    name = re.sub(r'[^\w\s-]', '', str(name))
    name = ''.join(word.capitalize() for word in name.split())
    return name[:30]


def get_camera_mode(media_type, gopro_type):
    """Determine camera mode from metadata."""
    if gopro_type:
        modes = {
            "TimeLapse": "TimeLapse",
            "TimeWarp": "TimeWarp",
            "Photo": "Photo",
            "Video": "Video",
            "Burst": "Burst",
            "NightLapse": "NightLapse",
        }
        for key, value in modes.items():
            if key.lower() in str(gopro_type).lower():
                return value
    return media_type.capitalize() if media_type else "Unknown"


def extract_activity_from_title(title):
    """Extract activity tags from content title."""
    if not title:
        return None

    activities = [
        "bike", "biking", "cycling", "ride",
        "walk", "walking", "hike", "hiking", "trek", "trekking",
        "swim", "swimming", "dive", "diving", "snorkel",
        "ski", "skiing", "snowboard", "snow",
        "surf", "surfing", "kayak", "paddle",
        "drive", "driving", "road", "roadtrip",
        "sunset", "sunrise", "night", "timelapse",
        "drone", "aerial", "fly", "flying",
        "food", "market", "temple", "beach", "mountain"
    ]

    title_lower = title.lower()
    found = [activity.capitalize() for activity in activities if activity in title_lower]
    return found if found else None
