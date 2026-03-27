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
    MAX_CONCURRENT_DOWNLOADS = 20  # High concurrency for fast downloads
    DOWNLOAD_CHUNK_SIZE = 1024 * 1024  # 1MB
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # Base delay in seconds (exponential backoff)

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

        # Per-slot progress for UI
        self.slot_progress = {}  # slot_id -> {filename, downloaded, total, pct}
        self.ui_lock = asyncio.Lock() if asyncio.get_event_loop().is_running() else None

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

    async def _download_file(self, session, semaphore, url, filepath, filename, media_id=None, slot_id=None):
        """Download a single file asynchronously with retry logic."""
        async with semaphore:
            for attempt in range(self.MAX_RETRIES):
                try:
                    # Check if partial download exists for resume
                    existing_size = 0
                    if filepath.exists():
                        existing_size = filepath.stat().st_size

                    headers = {}
                    if existing_size > 0:
                        headers["Range"] = f"bytes={existing_size}-"

                    timeout = aiohttp.ClientTimeout(
                        total=1800,  # 30 min total
                        connect=30,
                        sock_read=120  # 2 min per read
                    )

                    async with session.get(url, headers=headers, timeout=timeout) as resp:
                        if resp.status == 416:  # Range not satisfiable = file complete
                            if slot_id is not None:
                                self.slot_progress[slot_id] = None
                            return True, existing_size

                        if resp.status not in (200, 206):
                            if attempt < self.MAX_RETRIES - 1:
                                await asyncio.sleep(self.RETRY_DELAY * (2 ** attempt))
                                continue
                            return False, 0

                        total_size = int(resp.headers.get('content-length', 0))
                        if resp.status == 206:
                            total_size += existing_size

                        downloaded = existing_size
                        mode = 'ab' if existing_size > 0 else 'wb'

                        # Update slot progress
                        if slot_id is not None:
                            self.slot_progress[slot_id] = {
                                "filename": filename[:20] if len(filename) > 20 else filename,
                                "downloaded": downloaded,
                                "total": total_size,
                                "pct": 0
                            }

                        with open(filepath, mode) as f:
                            async for chunk in resp.content.iter_chunked(self.DOWNLOAD_CHUNK_SIZE):
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    pct = (downloaded / total_size) * 100
                                    if slot_id is not None:
                                        self.slot_progress[slot_id] = {
                                            "filename": filename[:20] if len(filename) > 20 else filename,
                                            "downloaded": downloaded,
                                            "total": total_size,
                                            "pct": pct
                                        }

                        if slot_id is not None:
                            self.slot_progress[slot_id] = None
                        return True, downloaded

                except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as e:
                    if slot_id is not None:
                        short_name = filename[:15] if len(filename) > 15 else filename
                        self.slot_progress[slot_id] = {
                            "filename": f"{short_name} (retry)",
                            "downloaded": 0,
                            "total": 0,
                            "pct": 0,
                            "retry": attempt + 1
                        }
                    if attempt < self.MAX_RETRIES - 1:
                        delay = self.RETRY_DELAY * (2 ** attempt)
                        await asyncio.sleep(delay)
                    else:
                        if slot_id is not None:
                            self.slot_progress[slot_id] = None
                        return False, 0
                except Exception as e:
                    if slot_id is not None:
                        self.slot_progress[slot_id] = None
                    return False, 0

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

    def _render_progress_ui(self, completed, total, elapsed, total_bytes):
        """Render multi-line progress UI showing all active downloads."""
        lines = []

        # Overall progress bar
        pct = completed / total * 100 if total > 0 else 0
        if completed > 0 and elapsed > 0:
            speed = total_bytes / elapsed / (1024 * 1024)
            eta = (elapsed / completed) * (total - completed)
            eta_str = format_time(eta)
        else:
            speed = 0
            eta_str = "calculating..."

        bar_width = 40
        filled = int(bar_width * completed / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_width - filled)

        lines.append(f"   [{bar}] {pct:5.1f}%")
        lines.append(f"   Files: {completed}/{total} | Speed: {speed:.1f} MB/s | ETA: {eta_str}")
        lines.append("")

        # Individual download slots
        active_slots = [(k, v) for k, v in sorted(self.slot_progress.items()) if v is not None]

        for slot_id, info in active_slots[:self.MAX_CONCURRENT_DOWNLOADS]:
            filename = info.get("filename", "unknown")
            dl_pct = info.get("pct", 0)
            downloaded = info.get("downloaded", 0)
            total_size = info.get("total", 0)
            retry = info.get("retry", 0)

            # Mini progress bar
            mini_width = 15
            mini_filled = int(mini_width * dl_pct / 100) if dl_pct > 0 else 0
            mini_bar = "▓" * mini_filled + "░" * (mini_width - mini_filled)

            dl_mb = downloaded / (1024 * 1024)
            total_mb = total_size / (1024 * 1024) if total_size > 0 else 0

            if retry:
                status = f"[{mini_bar}] {filename:<20} retry {retry}"
            elif total_mb > 0:
                status = f"[{mini_bar}] {filename:<20} {dl_mb:6.1f}/{total_mb:6.1f}MB"
            else:
                status = f"[{mini_bar}] {filename:<20} {dl_mb:6.1f}MB"

            lines.append(f"   {slot_id:2d}: {status}")

        # Pad empty slots
        for i in range(len(active_slots), min(10, self.MAX_CONCURRENT_DOWNLOADS)):
            lines.append(f"   {i:2d}: [{'░' * 15}] {'waiting...':<20}")

        return lines

    async def download_files(self, items_to_download, folder_map):
        """Download multiple files in parallel with visual progress."""
        print(f"\nDownloading {len(items_to_download)} files ({self.MAX_CONCURRENT_DOWNLOADS} concurrent)...\n")

        semaphore_download = asyncio.Semaphore(self.MAX_CONCURRENT_DOWNLOADS)
        semaphore_api = asyncio.Semaphore(self.MAX_CONCURRENT_METADATA)
        connector = aiohttp.TCPConnector(
            limit=max(self.MAX_CONCURRENT_DOWNLOADS, self.MAX_CONCURRENT_METADATA) * 2,
            limit_per_host=self.MAX_CONCURRENT_DOWNLOADS * 2,
            keepalive_timeout=60,
            enable_cleanup_closed=True,
            force_close=False
        )

        downloaded_count = 0
        failed_count = 0
        total_bytes = 0
        slot_queue = asyncio.Queue()

        # Initialize slot queue
        for i in range(self.MAX_CONCURRENT_DOWNLOADS):
            await slot_queue.put(i)
            self.slot_progress[i] = None

        self.download_start_time = time.time()
        self.async_progress = {"completed": 0, "total": len(items_to_download)}

        async with aiohttp.ClientSession(
            connector=connector,
            cookies=self._get_cookies(),
            headers=self._get_headers()
        ) as session:

            async def download_one(item):
                nonlocal downloaded_count, failed_count, total_bytes

                # Get a slot
                slot_id = await slot_queue.get()

                try:
                    folder_path_str = folder_map.get(item["id"], "unknown")
                    folder = self.download_path / folder_path_str
                    folder.mkdir(parents=True, exist_ok=True)

                    filename = item.get("filename")
                    media_id = item.get("id", "unknown")

                    # Handle missing filename
                    if not filename:
                        media_type = item.get("type", "file")
                        ext = ".mp4" if media_type == "video" else ".jpg"
                        filename = f"{media_id}{ext}"

                    filepath = folder / filename

                    # Mark slot as starting
                    self.slot_progress[slot_id] = {
                        "filename": filename[:20] if len(filename) > 20 else filename,
                        "downloaded": 0,
                        "total": 0,
                        "pct": 0
                    }

                    # Skip if already downloaded and has size
                    if filepath.exists() and filepath.stat().st_size > 0:
                        expected_size = item.get("size_mb", 0) * 1024 * 1024
                        actual_size = filepath.stat().st_size
                        if expected_size > 0 and abs(actual_size - expected_size) / expected_size < 0.05:
                            self.async_progress["completed"] += 1
                            downloaded_count += 1
                            self.slot_progress[slot_id] = None
                            return True, actual_size, item

                    download_url, quality, _, _ = await self._get_download_info(
                        session, semaphore_api, media_id, filename, folder_path_str
                    )

                    if not download_url:
                        self.async_progress["completed"] += 1
                        failed_count += 1
                        self.slot_progress[slot_id] = None
                        return False, 0, item

                    success, bytes_downloaded = await self._download_file(
                        session, semaphore_download, download_url, filepath, filename, media_id, slot_id
                    )

                    self.async_progress["completed"] += 1
                    self.slot_progress[slot_id] = None

                    if success:
                        downloaded_count += 1
                        total_bytes += bytes_downloaded
                        return True, bytes_downloaded, item
                    else:
                        failed_count += 1
                        return False, 0, item

                finally:
                    # Release slot
                    await slot_queue.put(slot_id)

            async def print_progress():
                while self.async_progress["completed"] < self.async_progress["total"]:
                    elapsed = time.time() - self.download_start_time

                    # Simple single-line progress (works in all terminals)
                    completed = self.async_progress["completed"]
                    total = self.async_progress["total"]
                    pct = completed / total * 100 if total > 0 else 0

                    if completed > 0 and elapsed > 0:
                        speed = total_bytes / elapsed / (1024 * 1024)
                        eta = (elapsed / completed) * (total - completed)
                        eta_str = format_time(eta)
                    else:
                        speed = 0
                        eta_str = "calculating..."

                    # Count active downloads
                    active = sum(1 for v in self.slot_progress.values() if v is not None)

                    bar_width = 30
                    filled = int(bar_width * pct / 100)
                    bar = "█" * filled + "░" * (bar_width - filled)

                    status = f"\r   [{bar}] {pct:5.1f}% | {completed}/{total} | {active} active | {speed:.1f} MB/s | ETA: {eta_str}   "
                    sys.stdout.write(status)
                    sys.stdout.flush()

                    await asyncio.sleep(0.5)

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

        # Print final summary on new line
        print()  # New line after progress bar
        print(f"\n   ✅ Downloaded: {downloaded_count} | ❌ Failed: {failed_count}")
        print(f"   📦 Total: {format_size(total_bytes)} | ⚡ Speed: {speed:.1f} MB/s | ⏱  Time: {format_time(elapsed)}")

        self.downloaded_files = downloaded_count
        self.downloaded_bytes = total_bytes

        return results
