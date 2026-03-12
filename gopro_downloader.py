#!/usr/bin/env python3
"""
GoPro Cloud Downloader - Enhanced Edition
Downloads media with rich metadata organization:
- Year folders with all countries: 2024-Vietnam-Laos-Japan/
- Month folders with countries: Feb-Vietnam-Laos/
- Day folders with cities + activities: 26-Hanoi-BikeRide/
- Per-day metadata.json files
- Master library_index.json
- Auto-generated README.md summaries
- _by_location/ symlink structure
"""

import os
import sys
import json
import requests
from datetime import datetime
from collections import defaultdict
from pathlib import Path
import re
import time


class GeoCache:
    """Simple cache for reverse geocoding results"""
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


class GoProDownloader:
    def __init__(self, auth_token, user_id, download_path="./downloads"):
        self.host = "https://api.gopro.com"
        self.auth_token = auth_token
        self.user_id = user_id
        self.download_path = Path(download_path)
        self.download_path.mkdir(parents=True, exist_ok=True)
        self.geo_cache = GeoCache(self.download_path / ".geo_cache.json")

        # Track non-source quality downloads
        self.non_source_downloads = []

        # Download progress tracking
        self.download_start_time = None
        self.downloaded_bytes = 0
        self.downloaded_files = 0
        self.total_files = 0
        self.total_expected_bytes = 0

        # Tracking for index
        self.library_index = {
            "generated_at": datetime.now().isoformat(),
            "total_files": 0,
            "total_size_mb": 0,
            "years": {},
            "countries": {},
            "cities": {},
            "activities": {},
            "files": []
        }

    def default_headers(self):
        return {
            "Accept": "application/vnd.gopro.jk.media+json; version=2.0.0",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }

    def default_cookies(self):
        return {
            "gp_access_token": self.auth_token,
            "gp_user_id": self.user_id,
        }

    def validate(self):
        """Validate auth credentials"""
        url = f"{self.host}/media/user"
        resp = requests.get(url, headers=self.default_headers(), cookies=self.default_cookies())
        if resp.status_code != 200:
            print(f"❌ Failed to validate auth token. Status: {resp.status_code}")
            return False
        print("✅ Credentials validated successfully!")
        return True

    def reverse_geocode(self, lat, lng):
        """Convert GPS coordinates to city/country using free API"""
        if lat is None or lng is None:
            return None

        # Check cache first
        cached = self.geo_cache.get(lat, lng)
        if cached:
            return cached

        try:
            # Using Nominatim (OpenStreetMap) - free, no API key needed
            url = f"https://nominatim.openstreetmap.org/reverse"
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
                    "city": address.get("city") or address.get("town") or address.get("village") or address.get("municipality") or address.get("county"),
                    "state": address.get("state"),
                    "country": address.get("country"),
                    "country_code": address.get("country_code", "").upper(),
                }

                # Cache the result
                self.geo_cache.set(lat, lng, result)

                # Rate limit: 1 request per second for Nominatim
                time.sleep(1)

                return result
        except Exception as e:
            print(f"      ⚠️ Geocoding failed: {e}")

        return None

    def get_all_media(self, per_page=100):
        """Fetch all media metadata from GoPro Cloud"""
        url = f"{self.host}/media/search"
        all_media = []
        current_page = 1
        total_pages = None

        print("📥 Fetching media list from GoPro Cloud...")

        while True:
            params = {
                "per_page": per_page,
                "page": current_page,
                "fields": "id,created_at,captured_at,filename,file_extension,file_size,height,width,content_title,type,ready_to_view,source_duration,camera_model,orientation,gps_lock,gopro_media_type",
            }

            resp = requests.get(
                url,
                params=params,
                headers=self.default_headers(),
                cookies=self.default_cookies()
            )

            if resp.status_code != 200:
                print(f"❌ Failed to fetch page {current_page}: {resp.text}")
                break

            content = resp.json()
            media = content["_embedded"]["media"]
            all_media.extend(media)

            if total_pages is None:
                total_pages = content["_pages"]["total_pages"]
                total_items = content["_pages"]["total_items"]
                print(f"   Found {total_items} media files across {total_pages} pages")

            print(f"   Page {current_page}/{total_pages} fetched ({len(all_media)} items so far)")

            if current_page >= total_pages:
                break

            current_page += 1

        return all_media

    def get_media_details(self, media_id):
        """Get detailed metadata for a single media item including GPS"""
        url = f"{self.host}/media/{media_id}"
        params = {"fields": "id,gps,camera_model,gopro_media_type,content_title,captured_at,created_at,filename,type,source_duration,height,width,file_size"}

        try:
            resp = requests.get(
                url,
                params=params,
                headers=self.default_headers(),
                cookies=self.default_cookies()
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def extract_activity_from_title(self, title):
        """Extract activity tags from content title"""
        if not title:
            return None

        # Common activity keywords
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
        found = []
        for activity in activities:
            if activity in title_lower:
                found.append(activity.capitalize())

        return found if found else None

    def sanitize_name(self, name):
        """Sanitize folder/file names"""
        if not name:
            return ""
        # Remove special characters, keep alphanumeric and spaces
        name = re.sub(r'[^\w\s-]', '', str(name))
        # Replace spaces with nothing, capitalize each word
        name = ''.join(word.capitalize() for word in name.split())
        return name[:30]  # Limit length

    def format_time(self, seconds):
        """Format seconds to human readable time"""
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

    def format_size(self, bytes_val):
        """Format bytes to human readable size"""
        if bytes_val < 1024:
            return f"{bytes_val} B"
        elif bytes_val < 1024 * 1024:
            return f"{bytes_val / 1024:.1f} KB"
        elif bytes_val < 1024 * 1024 * 1024:
            return f"{bytes_val / (1024 * 1024):.1f} MB"
        else:
            return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"

    def print_progress(self):
        """Print download progress with ETA"""
        if not self.download_start_time or self.downloaded_files == 0:
            return

        elapsed = time.time() - self.download_start_time

        # Calculate speed
        speed_bps = self.downloaded_bytes / elapsed if elapsed > 0 else 0
        speed_str = f"{speed_bps / (1024 * 1024):.1f} MB/s" if speed_bps > 0 else "-- MB/s"

        # Calculate ETA based on files (more reliable than bytes when sizes vary)
        avg_time_per_file = elapsed / self.downloaded_files
        remaining_files = self.total_files - self.downloaded_files
        eta_seconds = avg_time_per_file * remaining_files

        # Progress percentage
        progress_pct = (self.downloaded_files / self.total_files * 100) if self.total_files > 0 else 0

        # Progress bar
        bar_width = 30
        filled = int(bar_width * self.downloaded_files / self.total_files) if self.total_files > 0 else 0
        bar = "█" * filled + "░" * (bar_width - filled)

        print(f"\n   [{bar}] {progress_pct:.1f}%")
        print(f"   📊 {self.downloaded_files}/{self.total_files} files | {self.format_size(self.downloaded_bytes)} | {speed_str}")
        print(f"   ⏱️  Elapsed: {self.format_time(elapsed)} | ETA: {self.format_time(eta_seconds)}")

    def format_duration(self, ms):
        """Format milliseconds to HH:MM:SS"""
        if not ms:
            return None
        try:
            ms = int(ms)  # Handle string input
        except (ValueError, TypeError):
            return None
        seconds = int(ms / 1000)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def get_camera_mode(self, media_type, gopro_type):
        """Determine camera mode from metadata"""
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

    def get_download_url(self, media_id, filename=None, folder_path=None):
        """Get the actual download URL for a media item
        Returns tuple: (url, quality_label, available_qualities)
        """
        url = f"{self.host}/media/{media_id}/download"
        try:
            resp = requests.get(
                url,
                headers=self.default_headers(),
                cookies=self.default_cookies(),
            )
            if resp.status_code == 200:
                data = resp.json()
                if "_embedded" in data and "files" in data["_embedded"]:
                    files = data["_embedded"]["files"]

                    # Collect available qualities
                    available_qualities = []
                    for f in files:
                        label = f.get("label") or f.get("type") or "unknown"
                        size_mb = round(f.get("size", 0) / (1024 * 1024), 2) if f.get("size") else 0
                        available_qualities.append({"label": label, "size_mb": size_mb})

                    # Look for source quality first
                    for f in files:
                        if f.get("label") == "source" or f.get("type") == "source":
                            return f.get("url"), "source", available_qualities

                    # Fallback to first available - log this as non-source
                    if files:
                        fallback = files[0]
                        fallback_label = fallback.get("label") or fallback.get("type") or "unknown"

                        # Track non-source download
                        self.non_source_downloads.append({
                            "media_id": media_id,
                            "filename": filename,
                            "folder_path": folder_path,
                            "downloaded_quality": fallback_label,
                            "available_qualities": available_qualities,
                            "browser_url": f"https://gopro.com/media-library/{media_id}/"
                        })

                        return fallback.get("url"), fallback_label, available_qualities
        except Exception:
            pass
        return None, None, []

    def download_file(self, url, filepath):
        """Download a file from URL to filepath"""
        try:
            resp = requests.get(url, stream=True, timeout=300)
            if resp.status_code != 200:
                return False, 0

            total_size = int(resp.headers.get('content-length', 0))
            downloaded = 0

            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = (downloaded / total_size) * 100
                        mb = downloaded / (1024 * 1024)
                        print(f"\r      {mb:.1f}MB ({pct:.0f}%)", end="", flush=True)

            print()
            return True, downloaded
        except Exception as e:
            print(f"\n      ❌ Error: {e}")
            return False, 0

    def process_media_metadata(self, all_media):
        """Process all media and extract rich metadata"""
        print("\n🔍 Processing metadata and locations...")

        processed = []
        total = len(all_media)

        for i, item in enumerate(all_media):
            print(f"\r   Processing {i+1}/{total}...", end="", flush=True)

            media_id = item["id"]

            # Get detailed metadata including GPS
            details = self.get_media_details(media_id)

            # Parse date
            date_str = item.get("captured_at") or item.get("created_at", "")
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                dt = datetime.now()

            # Extract GPS and reverse geocode
            gps = None
            location = None
            if details and "gps" in details and details["gps"]:
                gps_data = details["gps"]
                if isinstance(gps_data, dict) and gps_data.get("lat") and gps_data.get("lng"):
                    gps = {"lat": gps_data["lat"], "lng": gps_data["lng"]}
                    location = self.reverse_geocode(gps["lat"], gps["lng"])

            # Extract activity from title
            title = item.get("content_title") or ""
            activities = self.extract_activity_from_title(title)

            # Build processed item
            # Safely get numeric values
            file_size = item.get("file_size") or 0
            try:
                file_size = int(file_size)
            except (ValueError, TypeError):
                file_size = 0

            width = item.get("width") or 0
            height = item.get("height") or 0
            try:
                width = int(width)
                height = int(height)
            except (ValueError, TypeError):
                width = 0
                height = 0

            processed_item = {
                "id": media_id,
                "filename": item.get("filename", f"{media_id}.mp4"),
                "type": item.get("type", "video"),
                "date": dt,
                "year": dt.year,
                "month": dt.strftime("%b"),
                "month_num": dt.month,
                "day": dt.day,
                "gps": gps,
                "city": self.sanitize_name(location.get("city")) if location else None,
                "country": self.sanitize_name(location.get("country")) if location else None,
                "country_code": location.get("country_code") if location else None,
                "activities": activities,
                "title": title,
                "camera_mode": self.get_camera_mode(item.get("type"), item.get("gopro_media_type")),
                "duration": self.format_duration(item.get("source_duration")),
                "resolution": f"{width}x{height}",
                "size_mb": round(file_size / (1024 * 1024), 2),
                "camera_model": details.get("camera_model") if details else None,
            }

            processed.append(processed_item)

        print(f"\n   ✅ Processed {len(processed)} items")
        return processed

    def build_folder_structure(self, processed_media):
        """Build folder structure based on metadata"""
        print("\n📁 Building folder structure...")

        # Group by year -> month -> day
        structure = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

        for item in processed_media:
            year = item["year"]
            month = item["month"]
            day = item["day"]
            structure[year][month][day].append(item)

        # Build folder names with metadata
        folder_map = {}  # Maps items to their folder paths

        for year, months in structure.items():
            # Collect all countries for the year
            year_countries = set()
            for month, days in months.items():
                for day, items in days.items():
                    for item in items:
                        if item["country"]:
                            year_countries.add(item["country"])

            year_folder = str(year)
            if year_countries:
                year_folder = f"{year}-{'-'.join(sorted(year_countries))}"

            for month, days in months.items():
                # Collect all countries for the month
                month_countries = set()
                for day, items in days.items():
                    for item in items:
                        if item["country"]:
                            month_countries.add(item["country"])

                month_folder = month
                if month_countries:
                    month_folder = f"{month}-{'-'.join(sorted(month_countries))}"

                for day, items in days.items():
                    # Collect all cities and activities for the day
                    day_cities = set()
                    day_activities = set()
                    for item in items:
                        if item["city"]:
                            day_cities.add(item["city"])
                        if item["activities"]:
                            day_activities.update(item["activities"])

                    day_folder = f"{day:02d}"
                    tags = list(day_cities) + list(day_activities)[:2]  # Limit activities
                    if tags:
                        day_folder = f"{day:02d}-{'-'.join(tags[:4])}"  # Limit total tags

                    folder_path = f"{year_folder}/{month_folder}/{day_folder}"

                    for item in items:
                        folder_map[item["id"]] = folder_path

        return folder_map

    def create_day_metadata(self, folder_path, items):
        """Create metadata.json for a day folder"""
        if not items:
            return

        metadata = {
            "date": items[0]["date"].strftime("%Y-%m-%d"),
            "total_files": len(items),
            "total_size_mb": sum(item["size_mb"] for item in items),
            "cities": list(set(item["city"] for item in items if item["city"])),
            "countries": list(set(item["country"] for item in items if item["country"])),
            "activities": list(set(a for item in items if item["activities"] for a in item["activities"])),
            "files": []
        }

        for item in items:
            file_meta = {
                "filename": item["filename"],
                "type": item["type"],
                "duration": item["duration"],
                "resolution": item["resolution"],
                "size_mb": item["size_mb"],
                "camera_mode": item["camera_mode"],
                "camera_model": item["camera_model"],
                "gps": item["gps"],
                "city": item["city"],
                "country": item["country"],
                "activities": item["activities"],
                "title": item["title"],
            }
            metadata["files"].append(file_meta)

        metadata_path = folder_path / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2, default=str))

    def create_day_readme(self, folder_path, items):
        """Create README.md for a day folder"""
        if not items:
            return

        date = items[0]["date"].strftime("%B %d, %Y")
        cities = list(set(item["city"] for item in items if item["city"]))
        countries = list(set(item["country"] for item in items if item["country"]))
        activities = list(set(a for item in items if item["activities"] for a in item["activities"]))

        videos = [i for i in items if i["type"] == "video"]
        photos = [i for i in items if i["type"] != "video"]
        total_size = sum(item["size_mb"] for item in items)

        readme = f"# {date}\n\n"

        if cities or countries:
            readme += f"📍 **Location**: {', '.join(cities)}"
            if countries:
                readme += f" ({', '.join(countries)})"
            readme += "\n\n"

        if activities:
            readme += f"🏃 **Activities**: {', '.join(activities)}\n\n"

        readme += f"## Summary\n\n"
        readme += f"- 📹 Videos: {len(videos)}\n"
        readme += f"- 📷 Photos: {len(photos)}\n"
        readme += f"- 💾 Total Size: {total_size:.1f} MB\n\n"

        readme += f"## Files\n\n"
        readme += "| File | Type | Duration | Size |\n"
        readme += "|------|------|----------|------|\n"
        for item in items:
            duration = item["duration"] or "-"
            readme += f"| {item['filename']} | {item['camera_mode']} | {duration} | {item['size_mb']} MB |\n"

        readme_path = folder_path / "README.md"
        readme_path.write_text(readme)

    def create_month_readme(self, folder_path, month_data):
        """Create README.md for a month folder"""
        month_name = folder_path.name.split('-')[0]

        all_items = []
        for day_items in month_data.values():
            all_items.extend(day_items)

        if not all_items:
            return

        cities = list(set(item["city"] for item in all_items if item["city"]))
        countries = list(set(item["country"] for item in all_items if item["country"]))
        activities = list(set(a for item in all_items if item["activities"] for a in item["activities"]))

        total_files = len(all_items)
        total_size = sum(item["size_mb"] for item in all_items)

        readme = f"# {month_name}\n\n"

        if countries:
            readme += f"🌍 **Countries**: {', '.join(countries)}\n\n"
        if cities:
            readme += f"📍 **Cities**: {', '.join(cities)}\n\n"
        if activities:
            readme += f"🏃 **Activities**: {', '.join(activities)}\n\n"

        readme += f"## Summary\n\n"
        readme += f"- 📁 Days: {len(month_data)}\n"
        readme += f"- 📄 Files: {total_files}\n"
        readme += f"- 💾 Total Size: {total_size:.1f} MB\n\n"

        readme += f"## Days\n\n"
        for day, items in sorted(month_data.items()):
            day_cities = list(set(item["city"] for item in items if item["city"]))[:3]
            day_size = sum(item["size_mb"] for item in items)
            location_str = f" - {', '.join(day_cities)}" if day_cities else ""
            readme += f"- **Day {day}**{location_str} ({len(items)} files, {day_size:.1f} MB)\n"

        readme_path = folder_path / "README.md"
        readme_path.write_text(readme)

    def create_year_readme(self, folder_path, year_data):
        """Create README.md for a year folder"""
        year = folder_path.name.split('-')[0]

        all_items = []
        for month_data in year_data.values():
            for day_items in month_data.values():
                all_items.extend(day_items)

        if not all_items:
            return

        countries = list(set(item["country"] for item in all_items if item["country"]))
        cities = list(set(item["city"] for item in all_items if item["city"]))

        total_files = len(all_items)
        total_size = sum(item["size_mb"] for item in all_items)

        readme = f"# {year}\n\n"
        readme += f"🌍 **Countries Visited**: {', '.join(sorted(countries)) if countries else 'Unknown'}\n\n"
        readme += f"📍 **Cities**: {', '.join(sorted(cities)) if cities else 'Unknown'}\n\n"

        readme += f"## Summary\n\n"
        readme += f"- 📅 Months: {len(year_data)}\n"
        readme += f"- 📄 Total Files: {total_files}\n"
        readme += f"- 💾 Total Size: {total_size / 1024:.2f} GB\n\n"

        readme += f"## Months\n\n"
        for month, days_data in sorted(year_data.items(), key=lambda x: datetime.strptime(x[0], "%b").month):
            month_items = [item for day_items in days_data.values() for item in day_items]
            month_countries = list(set(item["country"] for item in month_items if item["country"]))
            month_size = sum(item["size_mb"] for item in month_items)
            countries_str = f" ({', '.join(month_countries)})" if month_countries else ""
            readme += f"- **{month}**{countries_str}: {len(month_items)} files, {month_size:.1f} MB\n"

        readme_path = folder_path / "README.md"
        readme_path.write_text(readme)

    def create_by_location_symlinks(self, processed_media, folder_map):
        """Create _by_location/ symlink structure"""
        print("\n🔗 Creating location-based symlinks...")

        by_location = self.download_path / "_by_location"
        by_location.mkdir(exist_ok=True)

        # Group by country -> city
        locations = defaultdict(lambda: defaultdict(set))

        for item in processed_media:
            if item["country"]:
                folder_path = folder_map.get(item["id"])
                if folder_path:
                    city = item["city"] or "Other"
                    locations[item["country"]][city].add(folder_path)

        # Create symlinks
        for country, cities in locations.items():
            country_dir = by_location / country
            country_dir.mkdir(exist_ok=True)

            for city, folder_paths in cities.items():
                city_dir = country_dir / city
                city_dir.mkdir(exist_ok=True)

                for folder_path in folder_paths:
                    source = self.download_path / folder_path
                    link_name = folder_path.replace("/", "_")
                    link_path = city_dir / link_name

                    if not link_path.exists() and source.exists():
                        try:
                            # Calculate relative path for symlink
                            rel_path = os.path.relpath(source, link_path.parent)
                            link_path.symlink_to(rel_path)
                        except Exception as e:
                            print(f"      ⚠️ Could not create symlink: {e}")

        print(f"   ✅ Created symlinks for {len(locations)} countries")

    def create_master_index(self, processed_media, folder_map):
        """Create master library_index.json"""
        print("\n📚 Creating master index...")

        index = {
            "generated_at": datetime.now().isoformat(),
            "total_files": len(processed_media),
            "total_size_gb": round(sum(item["size_mb"] for item in processed_media) / 1024, 2),
            "date_range": {
                "earliest": min(item["date"] for item in processed_media).strftime("%Y-%m-%d") if processed_media else None,
                "latest": max(item["date"] for item in processed_media).strftime("%Y-%m-%d") if processed_media else None,
            },
            "countries": {},
            "cities": {},
            "activities": {},
            "years": {},
            "files": []
        }

        # Aggregate stats
        for item in processed_media:
            # Countries
            if item["country"]:
                if item["country"] not in index["countries"]:
                    index["countries"][item["country"]] = {"count": 0, "size_mb": 0, "cities": []}
                index["countries"][item["country"]]["count"] += 1
                index["countries"][item["country"]]["size_mb"] += item["size_mb"]
                if item["city"] and item["city"] not in index["countries"][item["country"]]["cities"]:
                    index["countries"][item["country"]]["cities"].append(item["city"])

            # Cities
            if item["city"]:
                if item["city"] not in index["cities"]:
                    index["cities"][item["city"]] = {"count": 0, "size_mb": 0, "country": item["country"]}
                index["cities"][item["city"]]["count"] += 1
                index["cities"][item["city"]]["size_mb"] += item["size_mb"]

            # Activities
            if item["activities"]:
                for activity in item["activities"]:
                    if activity not in index["activities"]:
                        index["activities"][activity] = {"count": 0}
                    index["activities"][activity]["count"] += 1

            # Years
            year = str(item["year"])
            if year not in index["years"]:
                index["years"][year] = {"count": 0, "size_mb": 0, "countries": []}
            index["years"][year]["count"] += 1
            index["years"][year]["size_mb"] += item["size_mb"]
            if item["country"] and item["country"] not in index["years"][year]["countries"]:
                index["years"][year]["countries"].append(item["country"])

            # File entry
            index["files"].append({
                "filename": item["filename"],
                "path": folder_map.get(item["id"], ""),
                "date": item["date"].strftime("%Y-%m-%d"),
                "city": item["city"],
                "country": item["country"],
                "type": item["type"],
                "size_mb": item["size_mb"],
            })

        index_path = self.download_path / "library_index.json"
        index_path.write_text(json.dumps(index, indent=2, default=str))
        print(f"   ✅ Index saved to library_index.json")

    def verify_downloads(self, processed_media, folder_map):
        """Verify all files have been downloaded correctly"""
        print("\n🔍 Verifying downloads...")

        verification = {
            "verified_at": datetime.now().isoformat(),
            "total_expected": len(processed_media),
            "verified": 0,
            "missing": [],
            "size_mismatch": [],
            "zero_size": [],
            "corrupted": [],
        }

        for item in processed_media:
            folder_path_str = folder_map.get(item["id"], "unknown")
            folder = self.download_path / folder_path_str
            filepath = folder / item["filename"]

            if not filepath.exists():
                verification["missing"].append({
                    "filename": item["filename"],
                    "path": str(folder_path_str),
                    "expected_size_mb": item["size_mb"],
                    "date": item["date"].strftime("%Y-%m-%d"),
                    "id": item["id"],
                })
            else:
                actual_size = filepath.stat().st_size
                actual_size_mb = actual_size / (1024 * 1024)

                # Check for zero-size files (failed downloads)
                if actual_size == 0:
                    verification["zero_size"].append({
                        "filename": item["filename"],
                        "path": str(folder_path_str),
                        "id": item["id"],
                    })
                # Check for significant size mismatch (>10% difference)
                elif item["size_mb"] > 0:
                    size_diff_pct = abs(actual_size_mb - item["size_mb"]) / item["size_mb"] * 100
                    if size_diff_pct > 10:
                        verification["size_mismatch"].append({
                            "filename": item["filename"],
                            "path": str(folder_path_str),
                            "expected_mb": item["size_mb"],
                            "actual_mb": round(actual_size_mb, 2),
                            "diff_pct": round(size_diff_pct, 1),
                            "id": item["id"],
                        })
                    else:
                        verification["verified"] += 1
                else:
                    verification["verified"] += 1

        # Calculate stats
        total_issues = len(verification["missing"]) + len(verification["size_mismatch"]) + len(verification["zero_size"])
        verification["total_issues"] = total_issues
        verification["success_rate"] = round(verification["verified"] / len(processed_media) * 100, 1) if processed_media else 0

        # Save verification report
        report_path = self.download_path / "verification_report.json"
        report_path.write_text(json.dumps(verification, indent=2, default=str))

        # Create failed_downloads.txt with browser URLs
        all_failed = verification["missing"] + verification["zero_size"] + verification["size_mismatch"]
        if all_failed:
            failed_txt_path = self.download_path / "failed_downloads.txt"
            with open(failed_txt_path, 'w') as f:
                f.write("# GoPro Failed Downloads\n")
                f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Total Failed: {len(all_failed)}\n")
                f.write("#\n")
                f.write("# Format: MEDIA_ID | FILENAME | DATE | FOLDER_PATH | BROWSER_URL\n")
                f.write("# You can open the URL in browser to verify/download manually\n")
                f.write("# Use the MEDIA_ID to retry specific files with: ./download.sh --retry ID1,ID2,ID3\n")
                f.write("#" + "="*80 + "\n\n")

                for item in all_failed:
                    media_id = item["id"]
                    filename = item["filename"]
                    date = item.get("date", "unknown")
                    path = item.get("path", "unknown")
                    browser_url = f"https://gopro.com/media-library/{media_id}/"

                    f.write(f"{media_id} | {filename} | {date} | {path}\n")
                    f.write(f"  └─ {browser_url}\n\n")

            # Also create a simple retry IDs file
            retry_ids_path = self.download_path / "retry_ids.txt"
            with open(retry_ids_path, 'w') as f:
                f.write("# Media IDs for retry - copy these to retry specific files\n")
                f.write("# Usage: export RETRY_IDS='id1,id2,id3' && ./download.sh\n\n")
                ids = [item["id"] for item in all_failed]
                f.write(",".join(ids) + "\n")

            print(f"\n📄 Failed downloads saved to: failed_downloads.txt")
            print(f"   (Contains browser URLs for manual verification)")
            print(f"📄 Retry IDs saved to: retry_ids.txt")

        # Print summary
        print(f"\n{'='*50}")
        print(f"📋 VERIFICATION REPORT")
        print(f"{'='*50}")
        print(f"   Total Expected:  {verification['total_expected']}")
        print(f"   ✅ Verified:     {verification['verified']}")
        print(f"   ❌ Missing:      {len(verification['missing'])}")
        print(f"   ⚠️  Size Mismatch: {len(verification['size_mismatch'])}")
        print(f"   🚫 Zero Size:    {len(verification['zero_size'])}")
        print(f"   📊 Success Rate: {verification['success_rate']}%")

        if verification["missing"]:
            print(f"\n❌ Missing Files ({len(verification['missing'])}):")
            for item in verification["missing"][:10]:  # Show first 10
                print(f"   - {item['path']}/{item['filename']}")
            if len(verification["missing"]) > 10:
                print(f"   ... and {len(verification['missing']) - 10} more")

        if verification["zero_size"]:
            print(f"\n🚫 Zero-Size Files (failed downloads):")
            for item in verification["zero_size"][:10]:
                print(f"   - {item['path']}/{item['filename']}")
            if len(verification["zero_size"]) > 10:
                print(f"   ... and {len(verification['zero_size']) - 10} more")

        if verification["size_mismatch"]:
            print(f"\n⚠️  Size Mismatches:")
            for item in verification["size_mismatch"][:5]:
                print(f"   - {item['filename']}: expected {item['expected_mb']}MB, got {item['actual_mb']}MB ({item['diff_pct']}% diff)")

        print(f"\n📄 Full report saved to: verification_report.json")

        # Return list of items that need re-download
        retry_items = []
        for item in verification["missing"] + verification["zero_size"]:
            retry_items.append(item["id"])

        return verification, retry_items

    def download_specific_ids(self, media_ids):
        """Download specific media by IDs (for retry)"""
        if not self.validate():
            return

        print(f"\n📥 Fetching metadata for {len(media_ids)} specific media items...")

        processed = []
        for media_id in media_ids:
            media_id = media_id.strip()
            if not media_id:
                continue

            print(f"   Fetching: {media_id}")
            details = self.get_media_details(media_id)

            if not details:
                print(f"      ❌ Could not fetch metadata for {media_id}")
                continue

            # Parse date
            date_str = details.get("captured_at") or details.get("created_at", "")
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                dt = datetime.now()

            # GPS and location
            gps = None
            location = None
            if "gps" in details and details["gps"]:
                gps_data = details["gps"]
                if isinstance(gps_data, dict) and gps_data.get("lat") and gps_data.get("lng"):
                    gps = {"lat": gps_data["lat"], "lng": gps_data["lng"]}
                    location = self.reverse_geocode(gps["lat"], gps["lng"])

            title = details.get("content_title") or ""
            activities = self.extract_activity_from_title(title)

            # Safely get numeric values
            file_size = details.get("file_size") or 0
            try:
                file_size = int(file_size)
            except (ValueError, TypeError):
                file_size = 0

            width = details.get("width") or 0
            height = details.get("height") or 0
            try:
                width = int(width)
                height = int(height)
            except (ValueError, TypeError):
                width = 0
                height = 0

            item = {
                "id": media_id,
                "filename": details.get("filename", f"{media_id}.mp4"),
                "type": details.get("type", "video"),
                "date": dt,
                "year": dt.year,
                "month": dt.strftime("%b"),
                "month_num": dt.month,
                "day": dt.day,
                "gps": gps,
                "city": self.sanitize_name(location.get("city")) if location else None,
                "country": self.sanitize_name(location.get("country")) if location else None,
                "country_code": location.get("country_code") if location else None,
                "activities": activities,
                "title": title,
                "camera_mode": self.get_camera_mode(details.get("type"), details.get("gopro_media_type")),
                "duration": self.format_duration(details.get("source_duration")),
                "resolution": f"{width}x{height}",
                "size_mb": round(file_size / (1024 * 1024), 2),
                "camera_model": details.get("camera_model"),
            }
            processed.append(item)

        if not processed:
            print("❌ No valid media items found")
            return

        # Build folder structure for these items
        folder_map = self.build_folder_structure(processed)

        # Download
        print(f"\n⬇️  Downloading {len(processed)} files...")

        downloaded = 0
        failed = 0

        for item in processed:
            folder_path_str = folder_map.get(item["id"], "unknown")
            folder = self.download_path / folder_path_str
            folder.mkdir(parents=True, exist_ok=True)

            filepath = folder / item["filename"]

            # Remove existing zero-size file
            if filepath.exists() and filepath.stat().st_size == 0:
                filepath.unlink()

            print(f"   ⬇️  {folder_path_str}/{item['filename']}")
            print(f"      ID: {item['id']}")
            print(f"      URL: https://gopro.com/media-library/{item['id']}/")

            download_url, quality, _ = self.get_download_url(item["id"], item["filename"], folder_path_str)
            if not download_url:
                print(f"      ❌ Could not get download URL")
                failed += 1
                continue

            if quality != "source":
                print(f"      ⚠️  Quality: {quality} (not source)")

            success, bytes_downloaded = self.download_file(download_url, filepath)
            if success:
                downloaded += 1
                # Update metadata
                self.create_day_metadata(folder, [item])
                self.create_day_readme(folder, [item])
            else:
                failed += 1

        print(f"\n{'='*50}")
        print(f"✅ Retry Complete!")
        print(f"   Downloaded: {downloaded}")
        print(f"   Failed:     {failed}")

        if failed > 0:
            print(f"\n⚠️  Some files still failed. Check the browser URLs to download manually.")

    def retry_failed_downloads(self, processed_media, folder_map, retry_ids):
        """Retry downloading failed files"""
        if not retry_ids:
            return 0

        print(f"\n🔄 Retrying {len(retry_ids)} failed downloads...")

        retry_success = 0
        retry_failed = 0

        items_to_retry = [item for item in processed_media if item["id"] in retry_ids]

        for item in items_to_retry:
            folder_path_str = folder_map.get(item["id"], "unknown")
            folder = self.download_path / folder_path_str
            folder.mkdir(parents=True, exist_ok=True)
            filepath = folder / item["filename"]

            # Remove zero-size file if exists
            if filepath.exists() and filepath.stat().st_size == 0:
                filepath.unlink()

            print(f"   🔄 Retrying: {item['filename']}")

            download_url, quality, _ = self.get_download_url(item["id"], item["filename"], folder_path_str)
            if not download_url:
                print(f"      ❌ Could not get download URL")
                retry_failed += 1
                continue

            if quality != "source":
                print(f"      ⚠️  Quality: {quality} (not source)")

            success, bytes_downloaded = self.download_file(download_url, filepath)
            if success:
                retry_success += 1
            else:
                retry_failed += 1

        print(f"\n   Retry Results: {retry_success} succeeded, {retry_failed} failed")
        return retry_success

    def save_non_source_log(self):
        """Save log of files not downloaded in source quality"""
        if not self.non_source_downloads:
            return

        log_path = self.download_path / "non_source_quality.txt"
        with open(log_path, 'w') as f:
            f.write("# Files NOT Downloaded in Source Quality\n")
            f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Total: {len(self.non_source_downloads)}\n")
            f.write("#\n")
            f.write("# These files were downloaded in a lower quality because source was unavailable.\n")
            f.write("# You can try downloading them manually from the browser URLs below.\n")
            f.write("#" + "="*80 + "\n\n")

            for item in self.non_source_downloads:
                f.write(f"File: {item['filename']}\n")
                f.write(f"  Path: {item['folder_path']}\n")
                f.write(f"  Downloaded Quality: {item['downloaded_quality']}\n")
                f.write(f"  Available Qualities:\n")
                for q in item['available_qualities']:
                    marker = " ← downloaded" if q['label'] == item['downloaded_quality'] else ""
                    f.write(f"    - {q['label']}: {q['size_mb']} MB{marker}\n")
                f.write(f"  Media ID: {item['media_id']}\n")
                f.write(f"  Browser URL: {item['browser_url']}\n")
                f.write("\n")

        # Also save as JSON for programmatic access
        json_path = self.download_path / "non_source_quality.json"
        json_path.write_text(json.dumps(self.non_source_downloads, indent=2, default=str))

        print(f"\n⚠️  {len(self.non_source_downloads)} files downloaded in non-source quality")
        print(f"   See: non_source_quality.txt")

    def create_master_readme(self, processed_media):
        """Create master README.md"""
        if not processed_media:
            return

        countries = list(set(item["country"] for item in processed_media if item["country"]))
        cities = list(set(item["city"] for item in processed_media if item["city"]))
        years = list(set(str(item["year"]) for item in processed_media))
        total_size_gb = sum(item["size_mb"] for item in processed_media) / 1024

        readme = f"# GoPro Media Library\n\n"
        readme += f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n"

        readme += f"## Overview\n\n"
        readme += f"- 📄 **Total Files**: {len(processed_media)}\n"
        readme += f"- 💾 **Total Size**: {total_size_gb:.2f} GB\n"
        readme += f"- 📅 **Years**: {', '.join(sorted(years))}\n"
        readme += f"- 🌍 **Countries**: {', '.join(sorted(countries)) if countries else 'Unknown'}\n"
        readme += f"- 📍 **Cities**: {len(cities)}\n\n"

        readme += f"## Folder Structure\n\n"
        readme += f"```\n"
        readme += f"downloads/\n"
        readme += f"├── 2024-Vietnam-Japan/          # Year with countries\n"
        readme += f"│   ├── Feb-Vietnam/             # Month with countries\n"
        readme += f"│   │   ├── 26-Hanoi-BikeRide/   # Day with cities + activities\n"
        readme += f"│   │   │   ├── GX010001.MP4\n"
        readme += f"│   │   │   ├── metadata.json    # File metadata\n"
        readme += f"│   │   │   └── README.md        # Day summary\n"
        readme += f"│   │   └── README.md            # Month summary\n"
        readme += f"│   └── README.md                # Year summary\n"
        readme += f"├── _by_location/                # Symlinks by location\n"
        readme += f"│   └── Vietnam/\n"
        readme += f"│       └── Hanoi/\n"
        readme += f"│           └── 2024_Feb_26-Hanoi -> ../../../2024-Vietnam/Feb-Vietnam/26-Hanoi\n"
        readme += f"├── library_index.json           # Master searchable index\n"
        readme += f"└── README.md                    # This file\n"
        readme += f"```\n\n"

        if countries:
            readme += f"## Countries\n\n"
            for country in sorted(countries):
                count = len([i for i in processed_media if i["country"] == country])
                readme += f"- 🌍 **{country}**: {count} files\n"
            readme += "\n"

        readme += f"## Quick Search\n\n"
        readme += f"Use `library_index.json` for programmatic search, or:\n\n"
        readme += f"```bash\n"
        readme += f"# Find all files from a city\n"
        readme += f"grep -r 'Hanoi' */*/metadata.json\n\n"
        readme += f"# Find all videos\n"
        readme += f"find . -name '*.MP4' -o -name '*.mp4'\n\n"
        readme += f"# Browse by location\n"
        readme += f"ls _by_location/Vietnam/\n"
        readme += f"```\n"

        readme_path = self.download_path / "README.md"
        readme_path.write_text(readme)

    def download_by_date(self, skip_existing=True):
        """Main method: download all media organized by date with rich metadata"""
        if not self.validate():
            return

        # Fetch all media
        all_media = self.get_all_media()
        if not all_media:
            print("No media found!")
            return

        # Process metadata (including GPS reverse geocoding)
        processed = self.process_media_metadata(all_media)

        # Build folder structure
        folder_map = self.build_folder_structure(processed)

        # Group for README generation
        structure = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for item in processed:
            structure[item["year"]][item["month"]][item["day"]].append(item)

        # Download files
        # Calculate total expected size for ETA
        total_expected_mb = sum(item["size_mb"] for item in processed)
        files_to_download = []

        # First pass: identify files to download
        for item in processed:
            folder_path_str = folder_map.get(item["id"], "unknown")
            folder = self.download_path / folder_path_str
            filepath = folder / item["filename"]

            if not (skip_existing and filepath.exists()):
                files_to_download.append(item)

        print(f"\n⬇️  Downloading files...")
        print(f"   📊 Total: {len(processed)} files ({total_expected_mb:.1f} MB)")
        print(f"   📥 To download: {len(files_to_download)} files")
        print(f"   ⏭️  Skipping: {len(processed) - len(files_to_download)} existing files")

        # Initialize progress tracking
        self.download_start_time = time.time()
        self.downloaded_bytes = 0
        self.downloaded_files = 0
        self.total_files = len(files_to_download)

        downloaded_count = 0
        skipped_count = len(processed) - len(files_to_download)
        failed_count = 0
        progress_interval = max(1, len(files_to_download) // 20)  # Show progress every 5%

        for idx, item in enumerate(files_to_download):
            folder_path_str = folder_map.get(item["id"], "unknown")
            folder = self.download_path / folder_path_str
            folder.mkdir(parents=True, exist_ok=True)

            filename = item["filename"]
            filepath = folder / filename

            print(f"   ⬇️  [{idx+1}/{len(files_to_download)}] {folder_path_str}/{filename}")

            # Get download URL
            download_url, quality, _ = self.get_download_url(item["id"], filename, folder_path_str)
            if not download_url:
                print(f"      ❌ Could not get download URL")
                failed_count += 1
                continue

            if quality != "source":
                print(f"      ⚠️  Quality: {quality} (not source)")

            # Download the file
            success, bytes_downloaded = self.download_file(download_url, filepath)
            if success:
                downloaded_count += 1
                self.downloaded_files += 1
                self.downloaded_bytes += bytes_downloaded

                # Show progress periodically
                if self.downloaded_files % progress_interval == 0 or self.downloaded_files == len(files_to_download):
                    self.print_progress()
            else:
                failed_count += 1

        # Final progress
        if self.downloaded_files > 0:
            elapsed = time.time() - self.download_start_time
            print(f"\n   ✅ Download completed in {self.format_time(elapsed)}")
            print(f"   📊 Average speed: {self.downloaded_bytes / elapsed / (1024*1024):.1f} MB/s")

        # Create metadata and README files
        print("\n📝 Generating metadata and README files...")

        for year, months in structure.items():
            year_countries = set()
            for month, days in months.items():
                for day, items in days.items():
                    for item in items:
                        if item["country"]:
                            year_countries.add(item["country"])

            year_folder_name = str(year)
            if year_countries:
                year_folder_name = f"{year}-{'-'.join(sorted(year_countries))}"

            year_path = self.download_path / year_folder_name

            for month, days in months.items():
                month_countries = set()
                for day, items in days.items():
                    for item in items:
                        if item["country"]:
                            month_countries.add(item["country"])

                month_folder_name = month
                if month_countries:
                    month_folder_name = f"{month}-{'-'.join(sorted(month_countries))}"

                month_path = year_path / month_folder_name

                for day, items in days.items():
                    day_cities = set()
                    day_activities = set()
                    for item in items:
                        if item["city"]:
                            day_cities.add(item["city"])
                        if item["activities"]:
                            day_activities.update(item["activities"])

                    day_folder_name = f"{day:02d}"
                    tags = list(day_cities) + list(day_activities)[:2]
                    if tags:
                        day_folder_name = f"{day:02d}-{'-'.join(tags[:4])}"

                    day_path = month_path / day_folder_name

                    if day_path.exists():
                        self.create_day_metadata(day_path, items)
                        self.create_day_readme(day_path, items)

                if month_path.exists():
                    self.create_month_readme(month_path, days)

            if year_path.exists():
                self.create_year_readme(year_path, months)

        # Create symlinks and master index
        self.create_by_location_symlinks(processed, folder_map)
        self.create_master_index(processed, folder_map)
        self.create_master_readme(processed)

        # Log non-source quality downloads
        self.save_non_source_log()

        print(f"\n{'='*50}")
        print(f"✅ Download Phase Complete!")
        print(f"   Downloaded: {downloaded_count}")
        print(f"   Skipped:    {skipped_count}")
        print(f"   Failed:     {failed_count}")
        print(f"   Total:      {len(processed)}")
        print(f"   Location:   {self.download_path.absolute()}")

        # Verification step
        verification, retry_ids = self.verify_downloads(processed, folder_map)

        # Auto-retry failed downloads (up to 2 attempts)
        max_retries = 2
        retry_attempt = 0
        while retry_ids and retry_attempt < max_retries:
            retry_attempt += 1
            print(f"\n🔄 Retry Attempt {retry_attempt}/{max_retries}")
            self.retry_failed_downloads(processed, folder_map, retry_ids)

            # Re-verify
            verification, retry_ids = self.verify_downloads(processed, folder_map)

            if not retry_ids:
                print("\n🎉 All files successfully downloaded!")
                break

        # Final summary
        print(f"\n{'='*50}")
        print(f"📊 FINAL SUMMARY")
        print(f"{'='*50}")
        print(f"   Total Files:     {len(processed)}")
        print(f"   Verified:        {verification['verified']}")
        print(f"   Missing:         {len(verification['missing'])}")
        print(f"   Success Rate:    {verification['success_rate']}%")
        print(f"   Location:        {self.download_path.absolute()}")
        print(f"\n📁 Generated:")
        print(f"   - metadata.json in each day folder")
        print(f"   - README.md summaries at each level")
        print(f"   - library_index.json (master searchable index)")
        print(f"   - _by_location/ symlinks for browsing by location")
        print(f"   - verification_report.json (download verification)")
        if self.non_source_downloads:
            print(f"   - non_source_quality.txt ({len(self.non_source_downloads)} files not in source quality)")

        if verification["missing"] or verification["zero_size"]:
            print(f"\n⚠️  Some files failed to download. Check verification_report.json")
            print(f"   You can re-run the script to retry failed downloads.")

        if self.non_source_downloads:
            print(f"\n⚠️  {len(self.non_source_downloads)} files downloaded in lower quality (source unavailable)")
            print(f"   Check non_source_quality.txt for details and manual download URLs.")


def main():
    auth_token = os.environ.get("GOPRO_AUTH_TOKEN")
    user_id = os.environ.get("GOPRO_USER_ID")

    if not auth_token or not user_id:
        print("="*50)
        print("GoPro Cloud Downloader - Enhanced Edition")
        print("="*50)
        print()
        print("Set your credentials first:")
        print()
        print("1. Go to https://gopro.com/login and sign in")
        print("2. Open DevTools (Cmd+Option+I)")
        print("3. Go to Application → Cookies → gopro.com")
        print("4. Copy these values:")
        print("   - gp_access_token → AUTH_TOKEN")
        print("   - gp_user_id → USER_ID")
        print()
        print("Then run:")
        print("  export GOPRO_AUTH_TOKEN='your_token'")
        print("  export GOPRO_USER_ID='your_user_id'")
        print("  python3 gopro_downloader.py")
        print()
        sys.exit(1)

    download_path = os.environ.get("DOWNLOAD_PATH", "./downloads")

    # Verify the path is writable
    download_path = Path(download_path).resolve()
    try:
        download_path.mkdir(parents=True, exist_ok=True)
        test_file = download_path / ".write_test"
        test_file.touch()
        test_file.unlink()
    except (PermissionError, OSError) as e:
        print(f"❌ Cannot write to {download_path}: {e}")
        sys.exit(1)

    # Check available disk space
    try:
        import shutil
        total, used, free = shutil.disk_usage(download_path)
        free_gb = free / (1024**3)
        print(f"💾 Disk space available: {free_gb:.1f} GB")
        if free_gb < 1:
            print("⚠️  Warning: Less than 1GB free space!")
    except Exception:
        pass

    downloader = GoProDownloader(auth_token, user_id, str(download_path))

    # Check if retrying specific IDs
    retry_ids = os.environ.get("RETRY_IDS", "").strip()
    if retry_ids:
        print(f"\n🔄 Retry mode: downloading specific media IDs")
        downloader.download_specific_ids(retry_ids.split(","))
    else:
        downloader.download_by_date(skip_existing=True)


if __name__ == "__main__":
    main()
