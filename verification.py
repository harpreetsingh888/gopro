"""Download verification and non-source quality logging."""

import json
from datetime import datetime


def verify_downloads(download_path, processed_media, folder_map):
    """Verify all files have been downloaded correctly.

    Returns:
        tuple: (verification_dict, list_of_retry_ids)
    """
    print("\nVerifying downloads...")

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
        folder = download_path / folder_path_str
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

            if actual_size == 0:
                verification["zero_size"].append({
                    "filename": item["filename"],
                    "path": str(folder_path_str),
                    "id": item["id"],
                })
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

    total_issues = len(verification["missing"]) + len(verification["size_mismatch"]) + len(verification["zero_size"])
    verification["total_issues"] = total_issues
    verification["success_rate"] = round(verification["verified"] / len(processed_media) * 100, 1) if processed_media else 0

    # Save verification report
    report_path = download_path / "verification_report.json"
    report_path.write_text(json.dumps(verification, indent=2, default=str))

    # Create failed_downloads.txt with browser URLs
    all_failed = verification["missing"] + verification["zero_size"] + verification["size_mismatch"]
    if all_failed:
        failed_txt_path = download_path / "failed_downloads.txt"
        with open(failed_txt_path, 'w') as f:
            f.write("# GoPro Failed Downloads\n")
            f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Total Failed: {len(all_failed)}\n")
            f.write("#\n")
            f.write("# Format: MEDIA_ID | FILENAME | DATE | FOLDER_PATH | BROWSER_URL\n")
            f.write("# You can open the URL in browser to verify/download manually\n")
            f.write("# Use the MEDIA_ID to retry specific files with: ./download.sh --retry ID1,ID2,ID3\n")
            f.write("#" + "=" * 80 + "\n\n")

            for item in all_failed:
                media_id = item["id"]
                filename = item["filename"]
                date = item.get("date", "unknown")
                path = item.get("path", "unknown")
                browser_url = f"https://gopro.com/media-library/{media_id}/"

                f.write(f"{media_id} | {filename} | {date} | {path}\n")
                f.write(f"  -> {browser_url}\n\n")

        # Also create retry IDs file
        retry_ids_path = download_path / "retry_ids.txt"
        with open(retry_ids_path, 'w') as f:
            f.write("# Media IDs for retry - copy these to retry specific files\n")
            f.write("# Usage: export RETRY_IDS='id1,id2,id3' && ./download.sh\n\n")
            ids = [item["id"] for item in all_failed]
            f.write(",".join(ids) + "\n")

        print(f"\nFailed downloads saved to: failed_downloads.txt")
        print("   (Contains browser URLs for manual verification)")
        print("Retry IDs saved to: retry_ids.txt")

    # Print summary
    print(f"\n{'=' * 50}")
    print("VERIFICATION REPORT")
    print(f"{'=' * 50}")
    print(f"   Total Expected:  {verification['total_expected']}")
    print(f"   Verified:        {verification['verified']}")
    print(f"   Missing:         {len(verification['missing'])}")
    print(f"   Size Mismatch:   {len(verification['size_mismatch'])}")
    print(f"   Zero Size:       {len(verification['zero_size'])}")
    print(f"   Success Rate:    {verification['success_rate']}%")

    if verification["missing"]:
        print(f"\nMissing Files ({len(verification['missing'])}):")
        for item in verification["missing"][:10]:
            print(f"   - {item['path']}/{item['filename']}")
        if len(verification["missing"]) > 10:
            print(f"   ... and {len(verification['missing']) - 10} more")

    if verification["zero_size"]:
        print(f"\nZero-Size Files (failed downloads):")
        for item in verification["zero_size"][:10]:
            print(f"   - {item['path']}/{item['filename']}")
        if len(verification["zero_size"]) > 10:
            print(f"   ... and {len(verification['zero_size']) - 10} more")

    if verification["size_mismatch"]:
        print(f"\nSize Mismatches:")
        for item in verification["size_mismatch"][:5]:
            print(f"   - {item['filename']}: expected {item['expected_mb']}MB, got {item['actual_mb']}MB ({item['diff_pct']}% diff)")

    print(f"\nFull report saved to: verification_report.json")

    # Return list of items that need re-download
    retry_items = [item["id"] for item in verification["missing"] + verification["zero_size"]]

    return verification, retry_items


def save_non_source_log(download_path, non_source_downloads):
    """Save log of files not downloaded in source quality."""
    if not non_source_downloads:
        return

    log_path = download_path / "non_source_quality.txt"
    with open(log_path, 'w') as f:
        f.write("# Files NOT Downloaded in Source Quality\n")
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Total: {len(non_source_downloads)}\n")
        f.write("#\n")
        f.write("# These files were downloaded in a lower quality because source was unavailable.\n")
        f.write("# You can try downloading them manually from the browser URLs below.\n")
        f.write("#" + "=" * 80 + "\n\n")

        for item in non_source_downloads:
            f.write(f"File: {item['filename']}\n")
            f.write(f"  Path: {item['folder_path']}\n")
            f.write(f"  Downloaded Quality: {item['downloaded_quality']}\n")
            f.write("  Available Qualities:\n")
            for q in item['available_qualities']:
                marker = " <- downloaded" if q['label'] == item['downloaded_quality'] else ""
                f.write(f"    - {q['label']}: {q.get('size_mb', 0)} MB{marker}\n")
            f.write(f"  Media ID: {item['media_id']}\n")
            f.write(f"  Browser URL: {item['browser_url']}\n")
            f.write("\n")

    # Also save as JSON
    json_path = download_path / "non_source_quality.json"
    json_path.write_text(json.dumps(non_source_downloads, indent=2, default=str))

    print(f"\n{len(non_source_downloads)} files downloaded in non-source quality")
    print("   See: non_source_quality.txt")
