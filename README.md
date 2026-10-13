# Garmin Device Backup Utility 🏃💨

A lightweight, reusable, cross-platform backup tool for Garmin smartwatches (Forerunner, Fenix, Epix, Venu, Instinct) and Edge cycling computers.

## ✨ Features

- **Automatic Device Detection**: Automatically discovers mounted Garmin drives across **Windows** (e.g. `D:\GARMIN`), **macOS** (`/Volumes/GARMIN`), and **Linux** (`/media/...`).
- **Device Metadata Extraction**: Automatically parses device model (e.g., `Forerunner 55`), Unit ID, and firmware version directly from `GarminDevice.xml`.
- **Fast Incremental Sync**: Only copies new or modified files to save time and flash wear.
- **Selective Backup**:
  - **Includes**: Activity logs (`.fit`), sport profiles (`Sports/`), watch settings (`Settings/`), workouts (`Workouts/`), personal records (`Records/`), totals, and Connect IQ app data (`APPS/`).
  - **Excludes by default**: Temporary caches, event crash dumps, and multi-megabyte language translation files (unless `--full` is specified).
- **Activity Summary**: Displays a clean table of newly synced workouts (Sport, Distance, Duration, Heart Rate, Date) if `fitparse` is installed.
- **Zip Archiving**: Optional `--zip` flag packages backups into timestamped `.zip` archives.
- **Zero Required Dependencies**: Runs using standard Python 3.8+ library. Optional `fitparse` enables activity metric summaries.

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.8 or higher.
- *(Optional)* `fitparse` for activity breakdown:
  ```bash
  pip install fitparse
  ```

### 2. Basic Usage

Plug in your Garmin device via USB and run:

```bash
# Auto-detects connected Garmin and backs up to ~/GarminBackups
python garmin_backup.py
```

### 3. Windows PowerShell / macOS / Linux Shortcuts
- **Windows**:
  ```powershell
  .\backup.ps1
  ```
- **macOS / Linux**:
  ```bash
  chmod +x backup.sh
  ./backup.sh
  ```

---

## 🛠️ CLI Options

```text
usage: garmin_backup.py [-h] [-s SOURCE] [-d DESTINATION] [--zip] [--full]

options:
  -h, --help            Show help message and exit
  -s, --source SOURCE   Path to mounted Garmin drive or GARMIN folder (auto-detected if omitted)
  -d, --destination DESTINATION
                        Destination directory for backups (default: ~/GarminBackups)
  --zip                 Create a timestamped compressed .zip archive of the backup
  --full                Back up all contents including language packs and system caches
```

### Examples

**Custom destination directory:**
```bash
python garmin_backup.py -d "D:\Backups\Garmin"
```

**Explicit source mount:**
```bash
python garmin_backup.py -s "D:\GARMIN" -d "C:\Users\username\GarminBackups"
```

**Create a compressed snapshot archive:**
```bash
python garmin_backup.py --zip
```

---

## 📁 Backup Structure

Backups are organized by device model and unique Unit ID:

```text
GarminBackups/
└── Forerunner_55_3520175632/
    ├── backup_manifest.json     # Metadata, sync timestamp, file counts
    ├── GarminDevice.xml         # Full hardware & capability specification
    ├── Device.fit               # Device identity FIT binary
    ├── Activity/                # All recorded runs, rides, and walks (.fit)
    ├── Settings/                # Watch preferences and settings
    ├── Sports/                  # Screen layouts and sport profiles
    ├── Workouts/                # Custom and structured interval workouts
    ├── Records/                 # Personal records and PR benchmarks
    ├── Totals/                  # Lifetime mileage totals
    └── APPS/                    # Connect IQ watch faces, widgets, and apps
```

---

## ⏰ Automated Backups on USB Plug-in (Windows)

To automate backups every time you plug in your watch on Windows:
1. Open **Task Scheduler** (`taskschd.msc`).
2. Create a task triggered by Event ID `20001` or `20003` under `Microsoft-Windows-DriverFrameworks-UserMode/Operational`.
3. Set the action to run:
   ```powershell
   python.exe "C:\path\to\garmin_backup.py"
   ```

---

## 📄 License

MIT License. Free to use and modify.
