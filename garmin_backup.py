#!/usr/bin/env python3
"""
Garmin Device Backup Utility
============================
A reusable, cross-platform backup tool for Garmin smartwatches and cycling computers.
Supports incremental backups, zip archiving, device auto-detection, and activity summaries.

Author: David.B (davbod)
"""

import argparse
import datetime
import hashlib
import json
import os
import platform
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Categories of Garmin directories to back up
CRITICAL_FOLDERS = [
    "Activity",      # All recorded workouts, runs, rides (.fit)
    "Settings",      # User configuration and watch settings (.fit)
    "Sports",        # Custom sport profiles and data screens (.fit)
    "Workouts",      # Custom and structured interval workouts (.fit)
    "Records",       # Personal records (PRs, longest runs, fastest times)
    "Totals",        # Lifetime mileage, activity totals
    "Goals",         # Fitness goals
    "Schedule",      # Training calendars
    "PaceBands",     # PacePro pacing strategies
    "Sleep",         # Sleep score and sleep tracking data
    "Monitor",       # Daily health tracking (steps, heart rate, stress)
    "APPS",          # Connect IQ apps, data fields, watch faces, settings (.SET)
    "Courses",       # Navigation courses (.fit)
    "Locations",     # Saved waypoints and locations
    "Points",        # Custom POIs
]

# Files in the root directory to back up
ROOT_FILES = [
    "GarminDevice.xml",
    "Device.fit",
]

# Folders skipped by default (temporary caches, duplicate translations)
DEFAULT_IGNORES = [
    "Text",          # Translation files (.ln4) taking significant space
    "ExtData",       # Temporary satellite cache and font bundles
    "Debug",         # Crash/KPI dumps
    "TempFIT",       # Temporary upload files
    "EVNTLOGS",      # Event logs
    "REMOTESW",      # Firmware update staging binaries
]


def find_garmin_mount() -> Optional[Path]:
    """Auto-detect mounted Garmin device across Windows, macOS, and Linux."""
    system = platform.system()

    if system == "Windows":
        # Check all available drive letters
        import string
        for letter in string.ascii_uppercase:
            drive_root = Path(f"{letter}:\\")
            if not drive_root.exists():
                continue
            # Look for Garmin folder
            garmin_dir = drive_root / "GARMIN"
            if (garmin_dir / "GarminDevice.xml").exists():
                return garmin_dir
            if (drive_root / "GarminDevice.xml").exists():
                return drive_root

    elif system == "Darwin":  # macOS
        volumes = Path("/Volumes")
        if volumes.exists():
            for vol in volumes.iterdir():
                if (vol / "GARMIN" / "GarminDevice.xml").exists():
                    return vol / "GARMIN"
                if (vol / "GarminDevice.xml").exists():
                    return vol

    elif system == "Linux":
        # Check standard user media mounts
        search_roots = [
            Path("/media"),
            Path("/run/media"),
            Path("/mnt"),
        ]
        for base in search_roots:
            if not base.exists():
                continue
            for root, dirs, _ in os.walk(base):
                p = Path(root)
                if (p / "GarminDevice.xml").exists():
                    return p
                if (p / "GARMIN" / "GarminDevice.xml").exists():
                    return p / "GARMIN"

    return None


def parse_device_info(garmin_dir: Path) -> Dict[str, str]:
    """Extract device model name, unit ID, and software version from GarminDevice.xml."""
    xml_path = garmin_dir / "GarminDevice.xml"
    info = {
        "model": "Unknown Garmin Device",
        "unit_id": "Unknown",
        "software_version": "Unknown",
        "part_number": "Unknown",
    }

    if not xml_path.exists():
        return info

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Helper to find tag ignoring XML namespaces
        def find_tag(element, tag_name):
            for elem in element.iter():
                if elem.tag.endswith(tag_name) or elem.tag == tag_name:
                    return elem
            return None

        model_elem = find_tag(root, "Model")
        if model_elem is not None:
            desc = find_tag(model_elem, "Description")
            if desc is not None and desc.text:
                info["model"] = desc.text.strip()
            part = find_tag(model_elem, "PartNumber")
            if part is not None and part.text:
                info["part_number"] = part.text.strip()
            sw = find_tag(model_elem, "SoftwareVersion")
            if sw is not None and sw.text:
                info["software_version"] = sw.text.strip()

        id_elem = find_tag(root, "Id")
        if id_elem is not None and id_elem.text:
            info["unit_id"] = id_elem.text.strip()

    except Exception as e:
        info["error"] = str(e)

    return info


def sanitize_filename(name: str) -> str:
    """Sanitize string for use in folder/archive names."""
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name).strip("_")


def format_bytes(size: int) -> str:
    """Format bytes into human-readable representation."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024.0
    return f"{size:.1f} TB"


def copy_incremental(src_dir: Path, dst_dir: Path, full_backup: bool = False) -> Tuple[int, int, List[str]]:
    """
    Perform an incremental copy of Garmin data folders to destination.
    Returns: (copied_count, total_bytes_copied, list_of_new_activities)
    """
    copied_count = 0
    total_bytes = 0
    new_activities = []

    # Copy selected root files
    dst_dir.mkdir(parents=True, exist_ok=True)
    for root_file in ROOT_FILES:
        s_file = src_dir / root_file
        if s_file.exists() and s_file.is_file():
            d_file = dst_dir / root_file
            if should_copy(s_file, d_file):
                shutil.copy2(s_file, d_file)
                copied_count += 1
                total_bytes += s_file.stat().st_size

    # Traverse subdirectories
    for item in src_dir.iterdir():
        if not item.is_dir():
            continue

        folder_name = item.name
        if not full_backup:
            if folder_name in DEFAULT_IGNORES:
                continue
            # Back up only recognized critical folders if not full backup
            if folder_name not in CRITICAL_FOLDERS and not folder_name.startswith("Activity"):
                continue

        target_sub = dst_dir / folder_name
        target_sub.mkdir(parents=True, exist_ok=True)

        for root, dirs, files in os.walk(item):
            rel_path = Path(root).relative_to(src_dir)
            current_target = dst_dir / rel_path
            current_target.mkdir(parents=True, exist_ok=True)

            for f in files:
                s_path = Path(root) / f
                d_path = current_target / f

                if should_copy(s_path, d_path):
                    shutil.copy2(s_path, d_path)
                    copied_count += 1
                    file_size = s_path.stat().st_size
                    total_bytes += file_size
                    if folder_name.lower() == "activity" and f.lower().endswith(".fit"):
                        new_activities.append(f)

    return copied_count, total_bytes, new_activities


def should_copy(src: Path, dst: Path) -> bool:
    """Check if destination is missing or source has different size/newer mtime."""
    if not dst.exists():
        return True
    s_stat = src.stat()
    d_stat = dst.stat()
    if s_stat.st_size != d_stat.st_size:
        return True
    # If source is newer by more than 2 seconds (FAT filesystem timestamp resolution)
    if (s_stat.st_mtime - d_stat.st_mtime) > 2.0:
        return True
    return False


def summarize_activities(activity_dir: Path, activity_files: List[str]):
    """Summarize newly backed up activities if fitparse is available."""
    if not activity_files:
        return

    try:
        import fitparse
    except ImportError:
        print("\n  [Tip] Install 'fitparse' (`pip install fitparse`) for automatic workout stat summaries.")
        return

    print("\n  Activity Summary (New Activities):")
    print("  " + "-" * 75)
    print(f"  {'File':<25} {'Sport':<12} {'Distance':<10} {'Duration':<10} {'Avg HR':<8} {'Date'}")
    print("  " + "-" * 75)

    for fname in sorted(activity_files)[-10:]:  # Show up to 10 latest
        fpath = activity_dir / fname
        try:
            fit = fitparse.FitFile(str(fpath))
            sessions = list(fit.get_messages("session"))
            if sessions:
                s = sessions[0]
                sport = str(s.get_value("sport") or "Unknown").capitalize()
                dist_m = s.get_value("total_distance") or 0
                dist_km = f"{dist_m / 1000:.2f} km" if dist_m else "--"
                elapsed_s = s.get_value("total_timer_time") or s.get_value("total_elapsed_time") or 0
                dur_m = f"{elapsed_s / 60:.1f} min" if elapsed_s else "--"
                avg_hr = str(s.get_value("avg_heart_rate") or "--")
                start_dt = str(s.get_value("start_time") or "")[:10]
                print(f"  {fname:<25} {sport:<12} {dist_km:<10} {dur_m:<10} {avg_hr:<8} {start_dt}")
        except Exception:
            continue
    print("  " + "-" * 75)


def create_zip_archive(source_dir: Path, zip_output_path: Path):
    """Bundle backed up directory into a compressed zip file."""
    base_name = str(zip_output_path.with_suffix(""))
    shutil.make_archive(base_name, "zip", source_dir)


def main():
    parser = argparse.ArgumentParser(
        description="Garmin Device Reusable Backup Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect watch and backup to default folder (~/GarminBackups)
  python garmin_backup.py

  # Specify custom Garmin path and output directory
  python garmin_backup.py -s D:\\GARMIN -d C:\\Backups\\Garmin

  # Create a compressed timestamped ZIP archive
  python garmin_backup.py --zip

  # Complete backup including language files and diagnostics
  python garmin_backup.py --full
        """
    )
    parser.add_argument(
        "-s", "--source",
        type=Path,
        help="Path to mounted Garmin drive or GARMIN folder (auto-detected if omitted)",
    )
    parser.add_argument(
        "-d", "--destination",
        type=Path,
        default=Path.home() / "GarminBackups",
        help="Destination directory for backups (default: ~/GarminBackups)",
    )
    parser.add_argument(
        "--zip",
        action="store_true",
        help="Create a timestamped compressed .zip archive of the backup",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Back up all contents including language packs and system caches",
    )

    args = parser.parse_args()

    print("=" * 70)
    print(" Garmin Device Backup Utility")
    print("=" * 70)

    # 1. Detect / validate source
    src_dir = args.source
    if not src_dir:
        print("[*] Searching for connected Garmin device...")
        src_dir = find_garmin_mount()
        if not src_dir:
            print("[!] Error: No connected Garmin device detected.")
            print("    Please connect your watch via USB or specify the path with -s/--source.")
            sys.exit(1)
    else:
        # Check if user specified root of drive instead of GARMIN subfolder
        if (src_dir / "GARMIN").exists():
            src_dir = src_dir / "GARMIN"

    if not (src_dir / "GarminDevice.xml").exists() and not (src_dir / "Device.fit").exists():
        print(f"[!] Warning: '{src_dir}' does not appear to be a standard Garmin device folder.")

    # 2. Extract Device Info
    info = parse_device_info(src_dir)
    model = info.get("model", "Garmin Device")
    unit_id = info.get("unit_id", "Unknown")
    sw_ver = info.get("software_version", "Unknown")

    print(f"[+] Device Detected: {model}")
    print(f"    - Unit ID:        {unit_id}")
    print(f"    - Software Ver:   {sw_ver}")
    print(f"    - Source Path:    {src_dir}")

    # 3. Setup Destination Directory
    clean_model_name = sanitize_filename(model)
    target_backup_dir = args.destination / f"{clean_model_name}_{unit_id}"
    print(f"[+] Backup Target:   {target_backup_dir}")

    # 4. Perform Backup
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[*] Starting incremental sync at {timestamp}...")
    copied_count, total_bytes, new_activities = copy_incremental(
        src_dir, target_backup_dir, full_backup=args.full
    )

    print(f"[+] Backup complete:")
    print(f"    - Files synced:   {copied_count}")
    print(f"    - Data copied:    {format_bytes(total_bytes)}")
    print(f"    - Total directory: {format_bytes(sum(f.stat().st_size for f in target_backup_dir.rglob('*') if f.is_file()))}")

    # 5. Write Manifest
    manifest = {
        "timestamp": timestamp,
        "device": info,
        "files_copied": copied_count,
        "bytes_copied": total_bytes,
        "destination": str(target_backup_dir.resolve()),
    }
    manifest_file = target_backup_dir / "backup_manifest.json"
    with open(manifest_file, "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2)

    # 6. Parse Activity Summaries
    if new_activities:
        summarize_activities(target_backup_dir / "Activity", new_activities)

    # 7. Optional ZIP Archive
    if args.zip:
        time_tag = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_filename = f"{clean_model_name}_{unit_id}_{time_tag}.zip"
        zip_path = args.destination / zip_filename
        print(f"[*] Compressing backup archive to: {zip_path}...")
        create_zip_archive(target_backup_dir, zip_path)
        print(f"[+] Archive created successfully ({format_bytes(zip_path.stat().st_size)})")

    print("\n[OK] Done!")


if __name__ == "__main__":
    main()
