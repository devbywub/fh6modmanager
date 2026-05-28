import csv
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set, Union


# Sanitization Helper
def sanitize_filename(name: str) -> str:
    """Removes invalid characters to make safe folder names."""
    return re.sub(r'[\\/*?:"<>| ]', "_", name)


def export_directory_to_csv(
    target_path: Union[str, Path],
    save_name: str,
    timestamp: Optional[str] = None,
    output_csv_path: Optional[Union[str, Path]] = None,
) -> Path:
    """Generates the secure clean game files baseline."""
    dir_path = Path(target_path).resolve()
    if not dir_path.exists() or not dir_path.is_dir():
        raise FileNotFoundError(f"Target path does not exist: {target_path}")

    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if output_csv_path is None:
        safe_save_name = sanitize_filename(save_name)
        out_file = Path.cwd() / f"{dir_path.name}_{safe_save_name}.csv"
    else:
        out_file = Path(output_csv_path).resolve()

    out_file.parent.mkdir(parents=True, exist_ok=True)

    headers = ["save_name", "timestamp", "relative_path", "filename", "size_bytes"]

    with open(out_file, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)

        for root, _, files in os.walk(dir_path):
            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(dir_path).as_posix()
                try:
                    size = file_path.stat().st_size
                except Exception:
                    size = 0
                writer.writerow([save_name, timestamp, rel_path, file, size])

    return out_file


# --- NEW MOD OPERATIONS ENGINE ---


def load_manifest(mod_path: Path) -> Dict[str, str]:
    """Validates and loads the JSON manifest file from target mod path."""
    manifest_path = mod_path / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("Format Error: 'manifest.json' is missing in mod root.")

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate Schema is present
    required_keys = ["name", "version", "author", "description"]
    for key in required_keys:
        if key not in data:
            data[key] = f"Unknown {key.capitalize()}"

    return data


def clean_empty_directories(path: Path):
    """Recursively removes empty directories to prevent game folder clutter."""
    if not path.is_dir():
        return

    # Checked child configurations nested
    for d in list(path.iterdir()):
        if d.is_dir():
            clean_empty_directories(d)

    # Try removing current if empty (skipping master folder path)
    try:
        if not any(path.iterdir()):
            path.rmdir()
    except Exception:
        pass
