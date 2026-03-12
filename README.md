# GoPro Cloud Downloader - Enhanced Edition

![Tests](https://github.com/harpreetsingh888/gopro/actions/workflows/test.yml/badge.svg)

Download your entire GoPro cloud library organized by date with rich metadata, location info, and activity tags.

## Features

- **Fast parallel downloads**: Uses aiohttp for concurrent downloads (5 simultaneous)
- **Parallel metadata fetching**: 50 concurrent API calls for speed
- **Smart folder structure**: `2024-Vietnam-Laos/Feb-Vietnam/26-Hanoi-BikeRide/`
- **Max resolution selection**: Automatically selects highest available quality
- **GPS reverse geocoding**: Automatically detects city/country from GPS coordinates
- **Activity detection**: Tags folders with activities (Bike, Hike, Sunset, etc.)
- **Per-day metadata.json**: Detailed file metadata for each day
- **README summaries**: Auto-generated summaries at year/month/day levels
- **Master index**: Searchable `library_index.json` with all files
- **Location symlinks**: `_by_location/Vietnam/Hanoi/` for browsing by place
- **Verification**: Checks all downloads and auto-retries failed ones
- **Resume support**: Skips already downloaded files

## Quick Start

### 1. Get Your Credentials

1. Go to [gopro.com/login](https://gopro.com/login) and sign in
2. Open DevTools (**Cmd+Option+I** on Mac)
3. Go to **Application** tab → **Cookies** → **gopro.com**
4. Copy these values:
   - `gp_access_token` → AUTH_TOKEN
   - `gp_user_id` → USER_ID

### 2. Configure

Create a `.env` file:

```bash
GOPRO_AUTH_TOKEN=your_token_here
GOPRO_USER_ID=your_user_id_here
```

Or export them:

```bash
export GOPRO_AUTH_TOKEN='your_token_here'
export GOPRO_USER_ID='your_user_id_here'
```

### 3. Run

```bash
# Interactive mode - prompts for download path
python3 downloader.py

# Download to specific path
python3 downloader.py /Volumes/H4TB/GoPro

# Download specific date only
python3 downloader.py --date 2024-03-12

# Show help
python3 downloader.py --help
```

Or use the shell wrapper:
```bash
./download.sh /Volumes/H4TB/GoPro
```

## Folder Structure

```
/Volumes/H4TB/GoPro/
├── 2024-Vietnam-Laos-Japan/              # Year with all countries
│   ├── Feb-Vietnam-Laos/                 # Month with countries
│   │   ├── 26-Hanoi-BikeRide/            # Day with cities + activities
│   │   │   ├── GX010001.MP4
│   │   │   ├── GX010002.MP4
│   │   │   ├── metadata.json             # Per-day file metadata
│   │   │   └── README.md                 # Day summary
│   │   ├── 27/                           # Day without location data
│   │   │   └── GX010003.MP4
│   │   ├── 28-Vientiane-Laos/
│   │   └── README.md                     # Month summary
│   ├── Mar-Japan/
│   │   └── 01-Tokyo-Shibuya-Walking/
│   └── README.md                         # Year summary
│
├── _by_location/                         # Symlinks organized by location
│   ├── Vietnam/
│   │   ├── Hanoi/
│   │   │   └── 2024_Feb_26-Hanoi → ../../../2024-Vietnam/Feb-Vietnam/26-Hanoi
│   │   └── Sapa/
│   ├── Laos/
│   │   └── Vientiane/
│   └── Japan/
│       └── Tokyo/
│
├── library_index.json                    # Master searchable index
├── verification_report.json              # Download verification results
├── failed_downloads.txt                  # Failed files with browser URLs
├── retry_ids.txt                         # Media IDs for retry
├── non_source_quality.txt                # Files not downloaded in source quality
├── non_source_quality.json               # Same data in JSON format
└── README.md                             # Library overview
```

## Generated Files

### metadata.json (per day)

```json
{
  "date": "2024-02-26",
  "total_files": 5,
  "total_size_mb": 1245.5,
  "cities": ["Hanoi", "Sapa"],
  "countries": ["Vietnam"],
  "activities": ["BikeRide", "Sunset"],
  "files": [
    {
      "filename": "GX010001.MP4",
      "type": "video",
      "duration": "00:02:34",
      "resolution": "3840x2160",
      "size_mb": 245.5,
      "camera_mode": "TimeWarp",
      "camera_model": "HERO12 Black",
      "gps": {"lat": 21.0285, "lng": 105.8542},
      "city": "Hanoi",
      "country": "Vietnam",
      "activities": ["BikeRide"]
    }
  ]
}
```

### library_index.json (master index)

```json
{
  "generated_at": "2024-03-12T01:30:00",
  "total_files": 1247,
  "total_size_gb": 156.8,
  "date_range": {
    "earliest": "2023-01-15",
    "latest": "2024-03-10"
  },
  "countries": {
    "Vietnam": {"count": 450, "size_mb": 52000, "cities": ["Hanoi", "Sapa", "HaLongBay"]},
    "Japan": {"count": 320, "size_mb": 38000, "cities": ["Tokyo", "Kyoto", "Osaka"]}
  },
  "cities": {...},
  "activities": {...},
  "years": {...},
  "files": [...]
}
```

### failed_downloads.txt

```
# GoPro Failed Downloads
# Generated: 2024-03-12 01:30:00
# Total Failed: 3
#
# Format: MEDIA_ID | FILENAME | DATE | FOLDER_PATH | BROWSER_URL
# You can open the URL in browser to verify/download manually
# Use the MEDIA_ID to retry specific files with: ./download.sh --retry ID1,ID2,ID3
#================================================================================

P3zD0D8JyW4Og | GX010045.MP4 | 2024-02-26 | 2024-Vietnam/Feb-Vietnam/26-Hanoi
  └─ https://gopro.com/media-library/P3zD0D8JyW4Og/

X7yK2L9MnQ3Rp | GOPR0012.JPG | 2024-02-27 | 2024-Vietnam/Feb-Vietnam/27-Sapa
  └─ https://gopro.com/media-library/X7yK2L9MnQ3Rp/
```

### retry_ids.txt

```
# Media IDs for retry - copy these to retry specific files
# Usage: export RETRY_IDS='id1,id2,id3' && ./download.sh

P3zD0D8JyW4Og,X7yK2L9MnQ3Rp
```

### non_source_quality.txt

Files that were downloaded in lower quality because source quality was unavailable:

```
# Files NOT Downloaded in Source Quality
# Generated: 2024-03-12 01:30:00
# Total: 2
#
# These files were downloaded in a lower quality because source was unavailable.
# You can try downloading them manually from the browser URLs below.
#================================================================================

File: GX010099.MP4
  Path: 2024-Vietnam/Feb-Vietnam/26-Hanoi
  Downloaded Quality: high
  Available Qualities:
    - high: 125.5 MB ← downloaded
    - low: 25.2 MB
  Media ID: A1b2C3d4E5f6G
  Browser URL: https://gopro.com/media-library/A1b2C3d4E5f6G/
```

## Commands

```bash
# Show all options
python3 downloader.py --help

# Interactive mode (prompts for path)
python3 downloader.py

# Download to specific path
python3 downloader.py /Volumes/H4TB/GoPro

# Download specific date only
python3 downloader.py /Volumes/H4TB/GoPro --date 2024-03-12

# Retry specific media IDs
python3 downloader.py --retry P3zD0D8JyW4Og,X7yK2L9MnQ3Rp

# Retry all failed (reads from retry_ids.txt)
python3 downloader.py --retry-failed
```

### Search Your Library

```bash
# Find all files from a city
grep -r 'Hanoi' */*/metadata.json

# Find all videos
find . -name '*.MP4' -o -name '*.mp4'

# Browse by location
ls _by_location/Vietnam/

# Search master index
jq '.files[] | select(.city == "Tokyo")' library_index.json
```

## Verification

After downloading, the script automatically:

1. **Verifies every file exists** on disk
2. **Checks file sizes** match expected (flags >10% difference)
3. **Detects zero-size files** (incomplete downloads)
4. **Auto-retries** failed downloads (up to 2 attempts)
5. **Generates verification_report.json**

### Verification Output

```
==================================================
📋 VERIFICATION REPORT
==================================================
   Total Expected:  1247
   ✅ Verified:     1243
   ❌ Missing:      2
   ⚠️  Size Mismatch: 1
   🚫 Zero Size:    1
   📊 Success Rate: 99.7%

❌ Missing Files (2):
   - 2024-Vietnam/Feb-Vietnam/26-Hanoi/GX010045.MP4
   - 2024-Vietnam/Feb-Vietnam/27-Sapa/GOPR0012.JPG

📄 Failed downloads saved to: failed_downloads.txt
📄 Retry IDs saved to: retry_ids.txt
```

## Media ID

GoPro uses a unique **Media ID** for each file (e.g., `P3zD0D8JyW4Og`):

- Browser URL: `https://gopro.com/media-library/{MEDIA_ID}/`
- Used for retry: `./download.sh --retry {MEDIA_ID}`
- Stored in `metadata.json`, `library_index.json`, and `failed_downloads.txt`

## Requirements

- Python 3.7+
- `requests` library (auto-installed)
- `aiohttp` library (auto-installed) - for parallel downloads
- GoPro subscription with cloud storage

## Project Structure

```
gopro/
├── downloader.py       # Main entry point & orchestrator
├── utils.py            # Formatting utilities
├── geo.py              # GeoCache + reverse geocoding
├── api.py              # Sync API client
├── async_client.py     # Async parallel downloads (aiohttp)
├── generators.py       # README/metadata generation
├── verification.py     # Download verification
├── download.sh         # Shell wrapper script
├── requirements.txt    # Python dependencies
└── .env                # Your credentials (create this)
```

| File | Description |
|------|-------------|
| `downloader.py` | Main orchestrator with `GoProDownloader` class |
| `async_client.py` | Parallel downloads using aiohttp (5 concurrent) |
| `api.py` | Synchronous GoPro API client |
| `generators.py` | Creates README.md and metadata.json files |
| `verification.py` | Verifies downloads and logs failures |
| `utils.py` | Formatting helpers (time, size, duration) |
| `geo.py` | GPS reverse geocoding with caching |
| `download.sh` | Shell wrapper for easy usage |

## Troubleshooting

### Token Expired

GoPro tokens expire. If you get 401 errors:
1. Log out and log back into gopro.com
2. Get fresh `gp_access_token` and `gp_user_id` from cookies
3. Update your `.env` file

### Download Speed

Downloads use parallel connections for maximum speed:
- **Metadata fetching**: 50 concurrent requests
- **File downloads**: 5 concurrent downloads
- **Chunk size**: 1MB per read

To adjust concurrency, edit `async_client.py`:
```python
MAX_CONCURRENT_METADATA = 50   # API calls
MAX_CONCURRENT_DOWNLOADS = 5   # File downloads
```

### Slow First Run

- GPS reverse geocoding uses OpenStreetMap (1 request/second rate limit)
- First run is slower due to geocoding; results are cached in `.geo_cache.json`
- Subsequent runs skip geocoding for cached locations

### Missing Location Data

- Some GoPro files don't have GPS data (GPS was off or indoors)
- These files go into folders like `26/` instead of `26-Hanoi/`

### Non-Source Quality

Some files may download in lower quality if source isn't available:
- Check `non_source_quality.txt` for affected files
- Use browser URLs to manually download source quality

## License

MIT
