"""README, metadata.json, and index generation."""

import os
import json
from datetime import datetime
from collections import defaultdict


def create_day_metadata(folder_path, items):
    """Create metadata.json for a day folder."""
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


def create_day_readme(folder_path, items):
    """Create README.md for a day folder."""
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
        readme += f"**Location**: {', '.join(cities)}"
        if countries:
            readme += f" ({', '.join(countries)})"
        readme += "\n\n"

    if activities:
        readme += f"**Activities**: {', '.join(activities)}\n\n"

    readme += "## Summary\n\n"
    readme += f"- Videos: {len(videos)}\n"
    readme += f"- Photos: {len(photos)}\n"
    readme += f"- Total Size: {total_size:.1f} MB\n\n"

    readme += "## Files\n\n"
    readme += "| File | Type | Duration | Size |\n"
    readme += "|------|------|----------|------|\n"
    for item in items:
        duration = item["duration"] or "-"
        readme += f"| {item['filename']} | {item['camera_mode']} | {duration} | {item['size_mb']} MB |\n"

    readme_path = folder_path / "README.md"
    readme_path.write_text(readme)


def create_month_readme(folder_path, month_data):
    """Create README.md for a month folder."""
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
        readme += f"**Countries**: {', '.join(countries)}\n\n"
    if cities:
        readme += f"**Cities**: {', '.join(cities)}\n\n"
    if activities:
        readme += f"**Activities**: {', '.join(activities)}\n\n"

    readme += "## Summary\n\n"
    readme += f"- Days: {len(month_data)}\n"
    readme += f"- Files: {total_files}\n"
    readme += f"- Total Size: {total_size:.1f} MB\n\n"

    readme += "## Days\n\n"
    for day, items in sorted(month_data.items()):
        day_cities = list(set(item["city"] for item in items if item["city"]))[:3]
        day_size = sum(item["size_mb"] for item in items)
        location_str = f" - {', '.join(day_cities)}" if day_cities else ""
        readme += f"- **Day {day}**{location_str} ({len(items)} files, {day_size:.1f} MB)\n"

    readme_path = folder_path / "README.md"
    readme_path.write_text(readme)


def create_year_readme(folder_path, year_data):
    """Create README.md for a year folder."""
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
    readme += f"**Countries Visited**: {', '.join(sorted(countries)) if countries else 'Unknown'}\n\n"
    readme += f"**Cities**: {', '.join(sorted(cities)) if cities else 'Unknown'}\n\n"

    readme += "## Summary\n\n"
    readme += f"- Months: {len(year_data)}\n"
    readme += f"- Total Files: {total_files}\n"
    readme += f"- Total Size: {total_size / 1024:.2f} GB\n\n"

    readme += "## Months\n\n"
    for month, days_data in sorted(year_data.items(), key=lambda x: datetime.strptime(x[0], "%b").month):
        month_items = [item for day_items in days_data.values() for item in day_items]
        month_countries = list(set(item["country"] for item in month_items if item["country"]))
        month_size = sum(item["size_mb"] for item in month_items)
        countries_str = f" ({', '.join(month_countries)})" if month_countries else ""
        readme += f"- **{month}**{countries_str}: {len(month_items)} files, {month_size:.1f} MB\n"

    readme_path = folder_path / "README.md"
    readme_path.write_text(readme)


def create_master_readme(download_path, processed_media):
    """Create master README.md."""
    if not processed_media:
        return

    countries = list(set(item["country"] for item in processed_media if item["country"]))
    cities = list(set(item["city"] for item in processed_media if item["city"]))
    years = list(set(str(item["year"]) for item in processed_media))
    total_size_gb = sum(item["size_mb"] for item in processed_media) / 1024

    readme = "# GoPro Media Library\n\n"
    readme += f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n"

    readme += "## Overview\n\n"
    readme += f"- **Total Files**: {len(processed_media)}\n"
    readme += f"- **Total Size**: {total_size_gb:.2f} GB\n"
    readme += f"- **Years**: {', '.join(sorted(years))}\n"
    readme += f"- **Countries**: {', '.join(sorted(countries)) if countries else 'Unknown'}\n"
    readme += f"- **Cities**: {len(cities)}\n\n"

    readme += "## Folder Structure\n\n"
    readme += "```\n"
    readme += "downloads/\n"
    readme += "├── 2024-Vietnam-Japan/          # Year with countries\n"
    readme += "│   ├── Feb-Vietnam/             # Month with countries\n"
    readme += "│   │   ├── 26-Hanoi-BikeRide/   # Day with cities + activities\n"
    readme += "│   │   │   ├── GX010001.MP4\n"
    readme += "│   │   │   ├── metadata.json    # File metadata\n"
    readme += "│   │   │   └── README.md        # Day summary\n"
    readme += "│   │   └── README.md            # Month summary\n"
    readme += "│   └── README.md                # Year summary\n"
    readme += "├── _by_location/                # Symlinks by location\n"
    readme += "│   └── Vietnam/\n"
    readme += "│       └── Hanoi/\n"
    readme += "│           └── 2024_Feb_26-Hanoi -> ../../../2024-Vietnam/Feb-Vietnam/26-Hanoi\n"
    readme += "├── library_index.json           # Master searchable index\n"
    readme += "└── README.md                    # This file\n"
    readme += "```\n\n"

    if countries:
        readme += "## Countries\n\n"
        for country in sorted(countries):
            count = len([i for i in processed_media if i["country"] == country])
            readme += f"- **{country}**: {count} files\n"
        readme += "\n"

    readme += "## Quick Search\n\n"
    readme += "Use `library_index.json` for programmatic search, or:\n\n"
    readme += "```bash\n"
    readme += "# Find all files from a city\n"
    readme += "grep -r 'Hanoi' */*/metadata.json\n\n"
    readme += "# Find all videos\n"
    readme += "find . -name '*.MP4' -o -name '*.mp4'\n\n"
    readme += "# Browse by location\n"
    readme += "ls _by_location/Vietnam/\n"
    readme += "```\n"

    readme_path = download_path / "README.md"
    readme_path.write_text(readme)


def create_master_index(download_path, processed_media, folder_map):
    """Create master library_index.json."""
    print("\nCreating master index...")

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

    for item in processed_media:
        if item["country"]:
            if item["country"] not in index["countries"]:
                index["countries"][item["country"]] = {"count": 0, "size_mb": 0, "cities": []}
            index["countries"][item["country"]]["count"] += 1
            index["countries"][item["country"]]["size_mb"] += item["size_mb"]
            if item["city"] and item["city"] not in index["countries"][item["country"]]["cities"]:
                index["countries"][item["country"]]["cities"].append(item["city"])

        if item["city"]:
            if item["city"] not in index["cities"]:
                index["cities"][item["city"]] = {"count": 0, "size_mb": 0, "country": item["country"]}
            index["cities"][item["city"]]["count"] += 1
            index["cities"][item["city"]]["size_mb"] += item["size_mb"]

        if item["activities"]:
            for activity in item["activities"]:
                if activity not in index["activities"]:
                    index["activities"][activity] = {"count": 0}
                index["activities"][activity]["count"] += 1

        year = str(item["year"])
        if year not in index["years"]:
            index["years"][year] = {"count": 0, "size_mb": 0, "countries": []}
        index["years"][year]["count"] += 1
        index["years"][year]["size_mb"] += item["size_mb"]
        if item["country"] and item["country"] not in index["years"][year]["countries"]:
            index["years"][year]["countries"].append(item["country"])

        index["files"].append({
            "filename": item["filename"],
            "path": folder_map.get(item["id"], ""),
            "date": item["date"].strftime("%Y-%m-%d"),
            "city": item["city"],
            "country": item["country"],
            "type": item["type"],
            "size_mb": item["size_mb"],
        })

    index_path = download_path / "library_index.json"
    index_path.write_text(json.dumps(index, indent=2, default=str))
    print("   Index saved to library_index.json")


def create_by_location_symlinks(download_path, processed_media, folder_map):
    """Create _by_location/ symlink structure."""
    print("\nCreating location-based symlinks...")

    by_location = download_path / "_by_location"
    by_location.mkdir(exist_ok=True)

    locations = defaultdict(lambda: defaultdict(set))

    for item in processed_media:
        if item["country"]:
            folder_path = folder_map.get(item["id"])
            if folder_path:
                city = item["city"] or "Other"
                locations[item["country"]][city].add(folder_path)

    for country, cities in locations.items():
        country_dir = by_location / country
        country_dir.mkdir(exist_ok=True)

        for city, folder_paths in cities.items():
            city_dir = country_dir / city
            city_dir.mkdir(exist_ok=True)

            for folder_path in folder_paths:
                source = download_path / folder_path
                link_name = folder_path.replace("/", "_")
                link_path = city_dir / link_name

                if not link_path.exists() and source.exists():
                    try:
                        rel_path = os.path.relpath(source, link_path.parent)
                        link_path.symlink_to(rel_path)
                    except Exception as e:
                        print(f"      Warning: Could not create symlink: {e}")

    print(f"   Created symlinks for {len(locations)} countries")
