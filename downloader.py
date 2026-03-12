#!/usr/bin/env python3
"""
GoPro Cloud Downloader - Enhanced Edition
Downloads media with rich metadata organization.
"""

import os
import sys
import asyncio
from datetime import datetime
from collections import defaultdict
from pathlib import Path

from utils import (
    format_time, format_size, format_duration,
    sanitize_name, get_camera_mode, extract_activity_from_title
)
from geo import GeoCache, reverse_geocode
from api import GoProAPI
from async_client import AsyncGoProClient
from generators import (
    create_day_metadata, create_day_readme,
    create_month_readme, create_year_readme,
    create_master_readme, create_master_index,
    create_by_location_symlinks
)
from verification import verify_downloads, save_non_source_log


class GoProDownloader:
    """Main orchestrator for GoPro Cloud downloads."""

    def __init__(self, auth_token, user_id, download_path="./downloads"):
        self.download_path = Path(download_path)
        self.download_path.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.api = GoProAPI(auth_token, user_id)
        self.async_client = AsyncGoProClient(auth_token, user_id, self.download_path)
        self.geo_cache = GeoCache(self.download_path / ".geo_cache.json")

    def validate(self):
        """Validate credentials."""
        return self.api.validate()

    def process_media_metadata(self, all_media):
        """Process all media and extract rich metadata."""
        print("\nProcessing metadata and locations...")

        # Fetch all media details in parallel
        details_map = asyncio.run(self.async_client.fetch_all_media_details(all_media))

        processed = []
        total = len(all_media)

        print("   Enriching with location data...")
        for i, item in enumerate(all_media):
            if (i + 1) % 50 == 0 or i == total - 1:
                print(f"\r   Enriching: {i + 1}/{total}...", end="", flush=True)

            media_id = item["id"]
            details = details_map.get(media_id)

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
                    location = reverse_geocode(gps["lat"], gps["lng"], self.geo_cache)

            # Extract activity from title
            title = item.get("content_title") or ""
            activities = extract_activity_from_title(title)

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
                "city": sanitize_name(location.get("city")) if location else None,
                "country": sanitize_name(location.get("country")) if location else None,
                "country_code": location.get("country_code") if location else None,
                "activities": activities,
                "title": title,
                "camera_mode": get_camera_mode(item.get("type"), item.get("gopro_media_type")),
                "duration": format_duration(item.get("source_duration")),
                "resolution": f"{width}x{height}",
                "size_mb": round(file_size / (1024 * 1024), 2),
                "camera_model": details.get("camera_model") if details else None,
            }

            processed.append(processed_item)

        print(f"\n   Processed {len(processed)} items")
        return processed

    def build_folder_structure(self, processed_media):
        """Build folder structure based on metadata."""
        print("\nBuilding folder structure...")

        structure = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

        for item in processed_media:
            structure[item["year"]][item["month"]][item["day"]].append(item)

        folder_map = {}

        for year, months in structure.items():
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
                month_countries = set()
                for day, items in days.items():
                    for item in items:
                        if item["country"]:
                            month_countries.add(item["country"])

                month_folder = month
                if month_countries:
                    month_folder = f"{month}-{'-'.join(sorted(month_countries))}"

                for day, items in days.items():
                    day_cities = set()
                    day_activities = set()
                    for item in items:
                        if item["city"]:
                            day_cities.add(item["city"])
                        if item["activities"]:
                            day_activities.update(item["activities"])

                    day_folder = f"{day:02d}"
                    tags = list(day_cities) + list(day_activities)[:2]
                    if tags:
                        day_folder = f"{day:02d}-{'-'.join(tags[:4])}"

                    folder_path = f"{year_folder}/{month_folder}/{day_folder}"

                    for item in items:
                        folder_map[item["id"]] = folder_path

        return folder_map

    def generate_all_readmes(self, processed_media, folder_map):
        """Generate all README and metadata files."""
        print("\nGenerating metadata and README files...")

        structure = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for item in processed_media:
            structure[item["year"]][item["month"]][item["day"]].append(item)

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
                        create_day_metadata(day_path, items)
                        create_day_readme(day_path, items)

                if month_path.exists():
                    create_month_readme(month_path, days)

            if year_path.exists():
                create_year_readme(year_path, months)

    def download_by_date(self, skip_existing=True, target_date=None):
        """Main method: download all media organized by date."""
        if not self.validate():
            return

        # Fetch all media
        all_media = self.api.get_all_media()
        if not all_media:
            print("No media found!")
            return

        # Filter by date if specified
        total_cloud_files = len(all_media)
        if target_date:
            filtered_media = []
            for item in all_media:
                date_str = item.get("captured_at") or item.get("created_at", "")
                try:
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    if dt.strftime("%Y-%m-%d") == target_date:
                        filtered_media.append(item)
                except ValueError:
                    continue

            all_media = filtered_media
            if not all_media:
                print(f"\nNo media found for date: {target_date}")
                return

        # Process metadata
        processed = self.process_media_metadata(all_media)

        # Build folder structure
        folder_map = self.build_folder_structure(processed)

        # Identify files to download
        files_to_download = []
        for item in processed:
            folder_path_str = folder_map.get(item["id"], "unknown")
            folder = self.download_path / folder_path_str
            filepath = folder / item["filename"]

            if not (skip_existing and filepath.exists()):
                files_to_download.append(item)

        print(f"\nDownload Summary:")
        print(f"   Total Cloud Library: {total_cloud_files} files")
        if target_date:
            print(f"   Target Date: {target_date} ({len(processed)} files)")
        print(f"   To download: {len(files_to_download)} files ({sum(item['size_mb'] for item in files_to_download):.1f} MB)")
        print(f"   Skipping: {len(processed) - len(files_to_download)} existing files")

        skipped_count = len(processed) - len(files_to_download)

        # Download files
        if files_to_download:
            asyncio.run(self.async_client.download_files(files_to_download, folder_map))

        downloaded_count = self.async_client.downloaded_files
        failed_count = len(files_to_download) - downloaded_count

        # Generate metadata and README files
        self.generate_all_readmes(processed, folder_map)

        # Create symlinks and master index
        create_by_location_symlinks(self.download_path, processed, folder_map)
        create_master_index(self.download_path, processed, folder_map)
        create_master_readme(self.download_path, processed)

        # Log non-source quality downloads
        save_non_source_log(self.download_path, self.async_client.non_source_downloads)

        print(f"\n{'=' * 50}")
        print("Download Phase Complete!")
        print(f"   Downloaded: {downloaded_count}")
        print(f"   Skipped:    {skipped_count}")
        print(f"   Failed:     {failed_count}")
        print(f"   Total Expected: {len(processed)}")
        print(f"   Location:   {self.download_path.absolute()}")

        # Verification step
        verification, retry_ids = verify_downloads(self.download_path, processed, folder_map)

        # Auto-retry failed downloads
        max_retries = 2
        retry_attempt = 0
        while retry_ids and retry_attempt < max_retries:
            retry_attempt += 1
            print(f"\nRetry Attempt {retry_attempt}/{max_retries}")

            items_to_retry = [item for item in processed if item["id"] in retry_ids]

            # Remove zero-size files
            for item in items_to_retry:
                folder_path_str = folder_map.get(item["id"], "unknown")
                folder = self.download_path / folder_path_str
                filepath = folder / item["filename"]
                if filepath.exists() and filepath.stat().st_size == 0:
                    filepath.unlink()

            if items_to_retry:
                asyncio.run(self.async_client.download_files(items_to_retry, folder_map))

            verification, retry_ids = verify_downloads(self.download_path, processed, folder_map)

            if not retry_ids:
                print("\nAll files successfully downloaded!")
                break

        # Final summary
        print(f"\n{'=' * 50}")
        print("FINAL SUMMARY")
        print(f"{'=' * 50}")
        print(f"   Total Cloud Files: {total_cloud_files}")
        if target_date:
            print(f"   Target Date Files: {len(processed)}")
        print(f"   Verified:        {verification['verified']}")
        print(f"   Missing:         {len(verification['missing'])}")
        print(f"   Success Rate:    {verification['success_rate']}%")
        print(f"   Location:        {self.download_path.absolute()}")
        print(f"\nGenerated:")
        print("   - metadata.json in each day folder")
        print("   - README.md summaries at each level")
        print("   - library_index.json (master searchable index)")
        print("   - _by_location/ symlinks for browsing by location")
        print("   - verification_report.json (download verification)")
        if self.async_client.non_source_downloads:
            print(f"   - non_source_quality.txt ({len(self.async_client.non_source_downloads)} files not in source quality)")

    def download_specific_ids(self, media_ids):
        """Download specific media by IDs (for retry)."""
        if not self.validate():
            return

        clean_ids = [mid.strip() for mid in media_ids if mid.strip()]
        if not clean_ids:
            print("No valid media IDs provided")
            return

        print(f"\nFetching metadata for {len(clean_ids)} specific media items...")

        media_list = [{"id": mid} for mid in clean_ids]
        details_map = asyncio.run(self.async_client.fetch_all_media_details(media_list))

        processed = []
        for media_id in clean_ids:
            details = details_map.get(media_id)

            if not details:
                print(f"   Could not fetch metadata for {media_id}")
                continue

            date_str = details.get("captured_at") or details.get("created_at", "")
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except ValueError:
                dt = datetime.now()

            gps = None
            location = None
            if "gps" in details and details["gps"]:
                gps_data = details["gps"]
                if isinstance(gps_data, dict) and gps_data.get("lat") and gps_data.get("lng"):
                    gps = {"lat": gps_data["lat"], "lng": gps_data["lng"]}
                    location = reverse_geocode(gps["lat"], gps["lng"], self.geo_cache)

            title = details.get("content_title") or ""
            activities = extract_activity_from_title(title)

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
                "city": sanitize_name(location.get("city")) if location else None,
                "country": sanitize_name(location.get("country")) if location else None,
                "country_code": location.get("country_code") if location else None,
                "activities": activities,
                "title": title,
                "camera_mode": get_camera_mode(details.get("type"), details.get("gopro_media_type")),
                "duration": format_duration(details.get("source_duration")),
                "resolution": f"{width}x{height}",
                "size_mb": round(file_size / (1024 * 1024), 2),
                "camera_model": details.get("camera_model"),
            }
            processed.append(item)

        if not processed:
            print("No valid media items found")
            return

        folder_map = self.build_folder_structure(processed)

        # Remove zero-size files
        for item in processed:
            folder_path_str = folder_map.get(item["id"], "unknown")
            folder = self.download_path / folder_path_str
            filepath = folder / item["filename"]
            if filepath.exists() and filepath.stat().st_size == 0:
                filepath.unlink()

        asyncio.run(self.async_client.download_files(processed, folder_map))

        downloaded = self.async_client.downloaded_files
        failed = len(processed) - downloaded

        print("\nGenerating metadata...")
        for item in processed:
            folder_path_str = folder_map.get(item["id"], "unknown")
            folder = self.download_path / folder_path_str
            filepath = folder / item["filename"]
            if filepath.exists() and filepath.stat().st_size > 0:
                create_day_metadata(folder, [item])
                create_day_readme(folder, [item])

        print(f"\n{'=' * 50}")
        print("Retry Complete!")
        print(f"   Downloaded: {downloaded}")
        print(f"   Failed:     {failed}")

        if failed > 0:
            print("\nSome files still failed. Check the browser URLs to download manually.")


def load_env_file():
    """Load .env file if it exists."""
    script_dir = Path(__file__).parent
    env_file = script_dir / ".env"

    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    value = value.strip().strip('"').strip("'")
                    if key not in os.environ:  # Don't override existing
                        os.environ[key] = value


def list_volumes():
    """List available volumes/drives."""
    volumes_path = Path("/Volumes")
    if volumes_path.exists():
        volumes = [v for v in volumes_path.iterdir() if v.is_dir() and v.name != "Macintosh HD"]
        if volumes:
            print("\nAvailable volumes:")
            for vol in sorted(volumes):
                print(f"   {vol}")
            print()


def prompt_download_path():
    """Interactively prompt for download path."""
    list_volumes()
    print("Enter download path (or press Enter for ./downloads):")
    path = input("Path: ").strip()

    if not path:
        return Path("./downloads").resolve()

    # Expand ~
    path = os.path.expanduser(path)
    return Path(path).resolve()


def parse_args():
    """Parse command line arguments."""
    import argparse

    parser = argparse.ArgumentParser(
        description="GoPro Cloud Downloader - Download your GoPro cloud library",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 downloader.py                         # Interactive mode
  python3 downloader.py /Volumes/H4TB/GoPro     # Download to path
  python3 downloader.py --date 2024-03-12       # Specific date only
  python3 downloader.py --retry ID1,ID2,ID3     # Retry specific IDs
  python3 downloader.py --retry-failed          # Retry from retry_ids.txt
        """
    )

    parser.add_argument(
        "path",
        nargs="?",
        help="Download path (default: ./downloads or interactive)"
    )
    parser.add_argument(
        "--date",
        help="Download only files from this date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--retry",
        help="Retry specific media IDs (comma-separated)"
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry all failed downloads from retry_ids.txt"
    )

    return parser.parse_args()


def main():
    # Load .env file first
    load_env_file()

    # Parse arguments
    args = parse_args()

    # Get credentials
    auth_token = os.environ.get("GOPRO_AUTH_TOKEN")
    user_id = os.environ.get("GOPRO_USER_ID")

    if not auth_token or not user_id:
        print("=" * 50)
        print("GoPro Cloud Downloader")
        print("=" * 50)
        print()
        print("Credentials not found. Set them up:")
        print()
        print("1. Go to https://gopro.com/login and sign in")
        print("2. Open DevTools (Cmd+Option+I)")
        print("3. Go to Application -> Cookies -> gopro.com")
        print("4. Copy these values:")
        print("   - gp_access_token")
        print("   - gp_user_id")
        print()
        print("Create a .env file:")
        print("   GOPRO_AUTH_TOKEN=your_token_here")
        print("   GOPRO_USER_ID=your_user_id_here")
        print()
        print("Or export them:")
        print("   export GOPRO_AUTH_TOKEN='your_token'")
        print("   export GOPRO_USER_ID='your_user_id'")
        print()
        sys.exit(1)

    # Determine download path
    if args.path:
        download_path = Path(os.path.expanduser(args.path)).resolve()
    elif os.environ.get("DOWNLOAD_PATH"):
        download_path = Path(os.environ["DOWNLOAD_PATH"]).resolve()
    else:
        download_path = prompt_download_path()

    # Validate path
    try:
        download_path.mkdir(parents=True, exist_ok=True)
        test_file = download_path / ".write_test"
        test_file.touch()
        test_file.unlink()
    except (PermissionError, OSError) as e:
        print(f"Cannot write to {download_path}: {e}")
        sys.exit(1)

    print(f"\nDownload location: {download_path}")

    # Check disk space
    try:
        import shutil
        total, used, free = shutil.disk_usage(download_path)
        free_gb = free / (1024 ** 3)
        print(f"Disk space available: {free_gb:.1f} GB")
        if free_gb < 1:
            print("Warning: Less than 1GB free space!")
    except Exception:
        pass

    # Create downloader
    downloader = GoProDownloader(auth_token, user_id, str(download_path))

    # Handle retry modes
    if args.retry_failed:
        retry_file = download_path / "retry_ids.txt"
        if not retry_file.exists():
            print(f"No retry_ids.txt found at {retry_file}")
            print("Run a full download first to generate this file.")
            sys.exit(1)

        # Read IDs from file
        with open(retry_file) as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
            retry_ids = ','.join(lines).replace('\n', ',')

        print("\nRetry mode: loading IDs from retry_ids.txt")
        downloader.download_specific_ids(retry_ids.split(","))

    elif args.retry:
        print("\nRetry mode: specific media IDs")
        downloader.download_specific_ids(args.retry.split(","))

    else:
        downloader.download_by_date(skip_existing=True, target_date=args.date)


if __name__ == "__main__":
    main()
