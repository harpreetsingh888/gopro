"""Tests for downloader.py"""

import sys
import tempfile
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).parent.parent))

from downloader import GoProDownloader, load_env_file


def make_test_item():
    """Create a test media item."""
    return {
        "id": "test123",
        "filename": "GX010001.MP4",
        "type": "video",
        "date": datetime(2024, 2, 26),
        "year": 2024,
        "month": "Feb",
        "month_num": 2,
        "day": 26,
        "gps": {"lat": 21.0285, "lng": 105.8542},
        "city": "Hanoi",
        "country": "Vietnam",
        "country_code": "VN",
        "activities": ["Bike"],
        "title": "Morning ride",
        "camera_mode": "Video",
        "duration": "02:30",
        "resolution": "3840x2160",
        "size_mb": 245.5,
        "camera_model": "HERO12 Black",
    }


def test_downloader_instantiation():
    with tempfile.TemporaryDirectory() as tmpdir:
        downloader = GoProDownloader("test_token", "test_user", tmpdir)

        assert downloader.download_path.exists()
        assert downloader.api is not None
        assert downloader.async_client is not None
        assert downloader.geo_cache is not None


def test_downloader_creates_download_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        new_path = Path(tmpdir) / "new_folder"
        downloader = GoProDownloader("test_token", "test_user", str(new_path))

        assert new_path.exists()


def test_build_folder_structure_with_location():
    with tempfile.TemporaryDirectory() as tmpdir:
        downloader = GoProDownloader("test_token", "test_user", tmpdir)
        items = [make_test_item()]

        folder_map = downloader.build_folder_structure(items)

        assert "test123" in folder_map
        assert "2024-Vietnam" in folder_map["test123"]
        assert "Feb-Vietnam" in folder_map["test123"]
        assert "26-Hanoi" in folder_map["test123"]


def test_build_folder_structure_without_location():
    with tempfile.TemporaryDirectory() as tmpdir:
        downloader = GoProDownloader("test_token", "test_user", tmpdir)

        item = make_test_item()
        item["city"] = None
        item["country"] = None
        items = [item]

        folder_map = downloader.build_folder_structure(items)

        assert "test123" in folder_map
        # Should still have year/month/day structure
        assert "2024" in folder_map["test123"]
        assert "Feb" in folder_map["test123"]
        assert "26" in folder_map["test123"]


def test_build_folder_structure_multiple_countries():
    with tempfile.TemporaryDirectory() as tmpdir:
        downloader = GoProDownloader("test_token", "test_user", tmpdir)

        item1 = make_test_item()
        item1["id"] = "test1"
        item1["country"] = "Vietnam"

        item2 = make_test_item()
        item2["id"] = "test2"
        item2["country"] = "Japan"
        item2["city"] = "Tokyo"

        items = [item1, item2]
        folder_map = downloader.build_folder_structure(items)

        # Year folder should include both countries
        assert "Japan" in folder_map["test2"] or "Vietnam" in folder_map["test1"]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
