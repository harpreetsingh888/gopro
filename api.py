"""Synchronous GoPro API client."""

import requests


class GoProAPI:
    """Synchronous API client for GoPro Cloud."""

    HOST = "https://api.gopro.com"

    def __init__(self, auth_token, user_id):
        self.auth_token = auth_token
        self.user_id = user_id

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
        """Validate auth credentials."""
        url = f"{self.HOST}/media/user"
        resp = requests.get(url, headers=self.default_headers(), cookies=self.default_cookies())
        if resp.status_code != 200:
            print(f"Failed to validate auth token. Status: {resp.status_code}")
            return False
        print("Credentials validated successfully!")
        return True

    def get_all_media(self, per_page=100):
        """Fetch all media metadata from GoPro Cloud."""
        url = f"{self.HOST}/media/search"
        all_media = []
        current_page = 1
        total_pages = None

        print("Fetching media list from GoPro Cloud...")

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
                print(f"Failed to fetch page {current_page}: {resp.text}")
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
        """Get detailed metadata for a single media item including GPS."""
        url = f"{self.HOST}/media/{media_id}"
        params = {
            "fields": "id,gps,camera_model,gopro_media_type,content_title,captured_at,created_at,filename,type,source_duration,height,width,file_size"
        }

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

    def get_download_url(self, media_id, filename=None, folder_path=None, non_source_tracker=None):
        """Get the actual download URL for a media item.

        Returns tuple: (url, quality_label, available_qualities)
        """
        url = f"{self.HOST}/media/{media_id}/download"
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

                    available_qualities = []
                    for f in files:
                        label = f.get("label") or f.get("type") or "unknown"
                        size_mb = round(f.get("size", 0) / (1024 * 1024), 2) if f.get("size") else 0
                        available_qualities.append({"label": label, "size_mb": size_mb})

                    # Look for source quality first
                    for f in files:
                        if f.get("label") == "source" or f.get("type") == "source":
                            return f.get("url"), "source", available_qualities

                    # Fallback to first available
                    if files:
                        fallback = files[0]
                        fallback_label = fallback.get("label") or fallback.get("type") or "unknown"

                        if non_source_tracker is not None:
                            non_source_tracker.append({
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

    def download_file(self, url, filepath, progress_callback=None):
        """Download a file from URL to filepath."""
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
                    if progress_callback and total_size > 0:
                        progress_callback(downloaded, total_size)

            return True, downloaded
        except Exception as e:
            print(f"\n      Error: {e}")
            return False, 0
