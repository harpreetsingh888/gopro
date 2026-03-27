#!/usr/bin/env python3
"""Check if GoPro cloud files have GPS data."""

import os
import requests

def check_gps():
    auth_token = os.environ.get("GOPRO_AUTH_TOKEN")
    user_id = os.environ.get("GOPRO_USER_ID")

    if not auth_token or not user_id:
        print("Error: Set GOPRO_AUTH_TOKEN and GOPRO_USER_ID environment variables")
        return

    cookies = {"gp_access_token": auth_token, "gp_user_id": user_id}
    headers = {
        "Accept": "application/vnd.gopro.jk.media+json; version=2.0.0",
        "User-Agent": "Mozilla/5.0"
    }

    # Get first page of media
    url = "https://api.gopro.com/media/search"
    params = {"fields": "id,filename,captured_at", "per_page": 20, "page": 1}

    resp = requests.get(url, params=params, cookies=cookies, headers=headers)
    if resp.status_code != 200:
        print(f"Error: {resp.status_code}")
        return

    media_list = resp.json().get("_embedded", {}).get("media", [])

    print(f"Checking GPS data for {len(media_list)} files...\n")

    gps_count = 0
    no_gps_count = 0

    for item in media_list:
        media_id = item["id"]
        filename = item.get("filename", "unknown")

        # Get detailed info including GPS
        detail_url = f"https://api.gopro.com/media/{media_id}"
        detail_params = {"fields": "id,filename,gps,captured_at"}

        detail_resp = requests.get(detail_url, params=detail_params, cookies=cookies, headers=headers)
        if detail_resp.status_code == 200:
            data = detail_resp.json()
            gps = data.get("gps")

            if gps and isinstance(gps, dict) and gps.get("lat") and gps.get("lng"):
                gps_count += 1
                print(f"✅ {filename}: GPS found - lat={gps['lat']:.4f}, lng={gps['lng']:.4f}")
            else:
                no_gps_count += 1
                print(f"❌ {filename}: No GPS data (gps={gps})")

    print(f"\n{'='*50}")
    print(f"Summary: {gps_count} with GPS, {no_gps_count} without GPS")

    if no_gps_count > gps_count:
        print("\n⚠️  Most files don't have GPS. Check if GPS is enabled on your GoPro:")
        print("   Settings → GPS → ON")

if __name__ == "__main__":
    check_gps()
