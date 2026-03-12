"""Tests for geo.py"""

import sys
import tempfile
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from geo import GeoCache


def test_geocache_set_and_get():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = os.path.join(tmpdir, "test_cache.json")
        cache = GeoCache(cache_file)

        cache.set(21.0285, 105.8542, {"city": "Hanoi", "country": "Vietnam"})
        result = cache.get(21.0285, 105.8542)

        assert result is not None
        assert result["city"] == "Hanoi"
        assert result["country"] == "Vietnam"


def test_geocache_get_missing():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = os.path.join(tmpdir, "test_cache.json")
        cache = GeoCache(cache_file)

        result = cache.get(0.0, 0.0)
        assert result is None


def test_geocache_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = os.path.join(tmpdir, "test_cache.json")

        # Write to cache
        cache1 = GeoCache(cache_file)
        cache1.set(35.6762, 139.6503, {"city": "Tokyo", "country": "Japan"})

        # Read from new instance
        cache2 = GeoCache(cache_file)
        result = cache2.get(35.6762, 139.6503)

        assert result is not None
        assert result["city"] == "Tokyo"


def test_geocache_precision():
    """Test that coordinates are rounded to 4 decimal places for caching."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_file = os.path.join(tmpdir, "test_cache.json")
        cache = GeoCache(cache_file)

        # Set with high precision
        cache.set(21.02851234, 105.85421234, {"city": "Hanoi"})

        # Get with slightly different precision (should match due to rounding)
        result = cache.get(21.02855, 105.85425)
        assert result is not None
        assert result["city"] == "Hanoi"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
