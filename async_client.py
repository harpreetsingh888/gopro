"""Asynchronous GoPro API client using aiohttp."""

import sys
import asyncio
import time

try:
    import aiohttp
except ImportError:
    print("Error: aiohttp is required for fast downloads")
    print("Install with: pip install aiohttp")
    sys.exit(1)

from utils import format_time, format_size


class AsyncGoProClient:
    """Async API client for parallel operations."""

    HOST = "https://api.gopro.com"
    MAX_CONCURRENT_METADATA = 50
    MAX_CONCURRENT_DOWNLOADS = 5
    DOWNLOAD_CHUNK_SIZE = 1024 * 1024  # 1MB

    def __init__(self, auth_token, user_id, download_path):
        self.auth_token = auth_token
        self.user_id = user_id
        self.download_path = download_path
        self.non_source_downloads = []

        # Progress tracking
        self.download_start_time = None
        self.downloaded_bytes = 0
        self.downloaded_files = 0
        self.async_progress = {"completed": 0, "total": 0, "current_file": ""}

    def _get_cookies(self):
        return {
            "gp_access_token": self.auth_token,
            "gp_user_id": self.user_id,
        }

    def _get_headers(self):
        return {
            "Accept": "application/vnd.gopro.jk.media+json; version=2.0.0",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }

    async def _get_media_details(self, session, semaphore, media_id):
        """Fetch details for a single media item."""
        url = f"{self.HOST}/media/{media_id}"
        params = {
            "fields": "id,gps,camera_model,gopro_media_type,content_title,captured_at,created_at,filename,type,source_duration,height,width,file_size"
        }

        async with semaphore:
            try:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        return await resp.json()
            except Exception:
                pass
        return None

    async def _get_download_info(self, session, semaphore, media_id, filename=None, folder_path=None):
        """Get download URL and select highest resolution."""
        url = f"{self.HOST}/media/{media_id}/download"

        async with semaphore:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        embedded = data.get("_embedded", {})
                        files = embedded.get("files", [])
                        variations = embedded.get("variations", [])

                        all_options = files + variations

                        available_qualities = []
                        for opt in all_options:
                            width = opt.get("width", 0)
                            height = opt.get("height", 0)
                            label = opt.get("label", opt.get("type", "unknown"))
                            size_bytes = opt.get("size", 0)
                            size_mb = round(size_bytes / (1024 * 1024), 2) if size_bytes else 0
                            available_qualities.append({
                                "label": label,
                                "size_mb": size_mb,
                                "width": width,
                                "height": height
                            })

                        # Select highest resolution video
                        video_options = [
                            opt for opt in all_options
                            if opt.get("width", 0) > 0 and opt.get("available", True)
                        ]

                        if video_options:
                            best = max(video_options, key=lambda v: v.get("width", 0) * v.get("height", 0))
                            best_url = best.get("url")
                            head_url = best.get("head")
                            quality = best.get("label", "unknown")

                            if quality != "source" and filename and folder_path:
                                self.non_source_downloads.append({
                                    "media_id": media_id,
                                    "filename": filename,
                                    "folder_path": folder_path,
                                    "downloaded_quality": quality,
                                    "available_qualities": available_qualities,
                                    "browser_url": f"https://gopro.com/media-library/{media_id}/"
                                })

                            return best_url, quality, available_qualities, head_url

                        if files:
                            fallback = files[0]
                            return fallback.get("url"), fallback.get("label", "unknown"), available_qualities, fallback.get("head")

            except Exception:
                pass
        return None, None, [], None

    async def _download_file(self, session, semaphore, url, filepath, filename):
        """Download a single file asynchronously."""
        async with semaphore:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=600)) as resp:
                    if resp.status != 200:
                        return False, 0

                    total_size = int(resp.headers.get('content-length', 0))
                    downloaded = 0

                    with open(filepath, 'wb') as f:
                        async for chunk in resp.content.iter_chunked(self.DOWNLOAD_CHUNK_SIZE):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                pct = (downloaded / total_size) * 100
                                mb = downloaded / (1024 * 1024)
                                self.async_progress["current_file"] = f"{filename}: {mb:.1f}MB ({pct:.0f}%)"

                    return True, downloaded
            except Exception as e:
                print(f"\n      Download error for {filename}: {e}")
                return False, 0

    async def fetch_all_media_details(self, all_media):
        """Fetch media details for all items in parallel."""
        print(f"\nFetching media details ({self.MAX_CONCURRENT_METADATA} concurrent)...")

        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_METADATA)
        connector = aiohttp.TCPConnector(limit=self.MAX_CONCURRENT_METADATA)

        results = {}
        progress = {"completed": 0, "total": len(all_media)}

        async with aiohttp.ClientSession(
            connector=connector,
            cookies=self._get_cookies(),
            headers=self._get_headers()
        ) as session:

            async def fetch_one(media_id):
                result = await self._get_media_details(session, semaphore, media_id)
                progress["completed"] += 1
                return media_id, result

            async def print_progress():
                while progress["completed"] < progress["total"]:
                    pct = progress["completed"] / progress["total"] * 100
                    print(f"\r   Processing: {progress['completed']}/{progress['total']} ({pct:.0f}%)", end="")
                    sys.stdout.flush()
                    await asyncio.sleep(0.1)

            progress_task = asyncio.create_task(print_progress())
            tasks = [fetch_one(item["id"]) for item in all_media]
            fetched = await asyncio.gather(*tasks)

            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass

            for media_id, details in fetched:
                results[media_id] = details

        print(f"\r   Fetched details for {len(results)} items" + " " * 20)
        return results

    async def download_files(self, items_to_download, folder_map):
        """Download multiple files in parallel."""
        print(f"\nDownloading {len(items_to_download)} files ({self.MAX_CONCURRENT_DOWNLOADS} concurrent)...")

        semaphore_download = asyncio.Semaphore(self.MAX_CONCURRENT_DOWNLOADS)
        semaphore_api = asyncio.Semaphore(self.MAX_CONCURRENT_METADATA)
        connector = aiohttp.TCPConnector(limit=max(self.MAX_CONCURRENT_DOWNLOADS, self.MAX_CONCURRENT_METADATA))

        downloaded_count = 0
        failed_count = 0
        total_bytes = 0

        self.download_start_time = time.time()
        self.async_progress = {"completed": 0, "total": len(items_to_download), "current_file": ""}

        async with aiohttp.ClientSession(
            connector=connector,
            cookies=self._get_cookies(),
            headers=self._get_headers()
        ) as session:

            async def download_one(item):
                nonlocal downloaded_count, failed_count, total_bytes

                folder_path_str = folder_map.get(item["id"], "unknown")
                folder = self.download_path / folder_path_str
                folder.mkdir(parents=True, exist_ok=True)
                filename = item["filename"]
                filepath = folder / filename

                download_url, quality, _, _ = await self._get_download_info(
                    session, semaphore_api, item["id"], filename, folder_path_str
                )

                if not download_url:
                    self.async_progress["completed"] += 1
                    failed_count += 1
                    return False, 0, item

                success, bytes_downloaded = await self._download_file(
                    session, semaphore_download, download_url, filepath, filename
                )

                self.async_progress["completed"] += 1

                if success:
                    downloaded_count += 1
                    total_bytes += bytes_downloaded
                    return True, bytes_downloaded, item
                else:
                    failed_count += 1
                    return False, 0, item

            async def print_progress():
                while self.async_progress["completed"] < self.async_progress["total"]:
                    completed = self.async_progress["completed"]
                    total = self.async_progress["total"]
                    pct = completed / total * 100 if total > 0 else 0

                    elapsed = time.time() - self.download_start_time
                    if completed > 0:
                        eta = (elapsed / completed) * (total - completed)
                        eta_str = format_time(eta)
                    else:
                        eta_str = "calculating..."

                    current = self.async_progress["current_file"]
                    if len(current) > 50:
                        current = current[:47] + "..."

                    bar_width = 30
                    filled = int(bar_width * completed / total) if total > 0 else 0
                    bar = "█" * filled + "░" * (bar_width - filled)

                    print(f"\r   [{bar}] {pct:.0f}% | {completed}/{total} | ETA: {eta_str} | {current}" + " " * 10, end="")
                    sys.stdout.flush()
                    await asyncio.sleep(0.2)

            progress_task = asyncio.create_task(print_progress())
            tasks = [download_one(item) for item in items_to_download]
            results = await asyncio.gather(*tasks)

            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass

        elapsed = time.time() - self.download_start_time
        speed = total_bytes / elapsed / (1024 * 1024) if elapsed > 0 else 0

        print(f"\r   Downloaded: {downloaded_count} | Failed: {failed_count} | {format_size(total_bytes)} | {speed:.1f} MB/s" + " " * 30)

        self.downloaded_files = downloaded_count
        self.downloaded_bytes = total_bytes

        return results
