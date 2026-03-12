"""Geocoding cache and reverse geocoding functionality."""

import json
import time
from pathlib import Path

import requests


class GeoCache:
    """Simple cache for reverse geocoding results."""

    def __init__(self, cache_file):
        self.cache_file = Path(cache_file)
        self.cache = {}
        self._load()

    def _load(self):
        if self.cache_file.exists():
            try:
                self.cache = json.loads(self.cache_file.read_text())
            except Exception:
                self.cache = {}

    def _save(self):
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(json.dumps(self.cache, indent=2))

    def get(self, lat, lng):
        key = f"{lat:.4f},{lng:.4f}"
        return self.cache.get(key)

    def set(self, lat, lng, data):
        key = f"{lat:.4f},{lng:.4f}"
        self.cache[key] = data
        self._save()


def reverse_geocode(lat, lng, geo_cache=None):
    """Convert GPS coordinates to city/country using Nominatim API.

    Args:
        lat: Latitude
        lng: Longitude
        geo_cache: Optional GeoCache instance for caching results

    Returns:
        dict with city, state, country, country_code or None
    """
    if lat is None or lng is None:
        return None

    if geo_cache:
        cached = geo_cache.get(lat, lng)
        if cached:
            return cached

    try:
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": lat,
            "lon": lng,
            "format": "json",
            "zoom": 10,
            "addressdetails": 1
        }
        headers = {"User-Agent": "GoPro-Downloader/1.0"}

        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            address = data.get("address", {})

            result = {
                "city": (
                    address.get("city") or
                    address.get("town") or
                    address.get("village") or
                    address.get("municipality") or
                    address.get("county")
                ),
                "state": address.get("state"),
                "country": address.get("country"),
                "country_code": address.get("country_code", "").upper(),
            }

            if geo_cache:
                geo_cache.set(lat, lng, result)

            # Rate limit: 1 request per second for Nominatim
            time.sleep(1)
            return result
    except Exception as e:
        print(f"      Warning: Geocoding failed: {e}")

    return None
