"""Tests for generators.py"""

import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).parent.parent))

from generators import (
    create_day_metadata, create_day_readme,
    create_master_index
)


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


def test_create_day_metadata():
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        items = [make_test_item()]

        create_day_metadata(folder, items)

        metadata_file = folder / "metadata.json"
        assert metadata_file.exists()

        with open(metadata_file) as f:
            data = json.load(f)

        assert data["date"] == "2024-02-26"
        assert data["total_files"] == 1
        assert data["total_size_mb"] == 245.5
        assert "Hanoi" in data["cities"]
        assert "Vietnam" in data["countries"]
        assert len(data["files"]) == 1
        assert data["files"][0]["filename"] == "GX010001.MP4"


def test_create_day_readme():
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        items = [make_test_item()]

        create_day_readme(folder, items)

        readme_file = folder / "README.md"
        assert readme_file.exists()

        content = readme_file.read_text()
        assert "February 26, 2024" in content
        assert "Hanoi" in content
        assert "Vietnam" in content
        assert "GX010001.MP4" in content


def test_create_master_index():
    with tempfile.TemporaryDirectory() as tmpdir:
        download_path = Path(tmpdir)
        items = [make_test_item()]
        folder_map = {"test123": "2024-Vietnam/Feb-Vietnam/26-Hanoi"}

        create_master_index(download_path, items, folder_map)

        index_file = download_path / "library_index.json"
        assert index_file.exists()

        with open(index_file) as f:
            data = json.load(f)

        assert data["total_files"] == 1
        assert "Vietnam" in data["countries"]
        assert "Hanoi" in data["cities"]
        assert len(data["files"]) == 1


def test_create_day_metadata_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        create_day_metadata(folder, [])

        # Should not create file for empty items
        assert not (folder / "metadata.json").exists()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
