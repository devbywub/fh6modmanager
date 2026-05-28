import csv
import hashlib
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union


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

    headers = ["save_name", "timestamp", "relative_path", "filename", "size_bytes", "sha256"]

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
                file_hash = ""
                try:
                    file_hash = compute_sha256(file_path)
                except Exception:
                    file_hash = ""
                writer.writerow([save_name, timestamp, rel_path, file, size, file_hash])

    return out_file


# --- NEW MOD OPERATIONS ENGINE ---


def load_manifest(mod_path: Path) -> Dict[str, Union[str, List[str]]]:
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

    if "id" not in data and "mod_id" not in data:
        data["id"] = sanitize_filename(data["name"])
    if "dependencies" not in data:
        data["dependencies"] = []
    if "incompatibilities" not in data:
        data["incompatibilities"] = []
    if "min_game_version" not in data:
        data["min_game_version"] = ""

    data["dependencies"] = normalize_manifest_list(data.get("dependencies"))
    data["incompatibilities"] = normalize_manifest_list(data.get("incompatibilities"))

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


def normalize_manifest_list(value: Union[List[str], str, None]) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def compute_sha256(file_path: Path) -> str:
    hash_obj = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 64), b""):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()


def build_mod_file_index(mod_path: Path) -> List[str]:
    files_index = []
    for root, _, files in os.walk(mod_path):
        for file in files:
            if file == "manifest.json":
                continue
            source_file = Path(root) / file
            rel_to_mod = source_file.relative_to(mod_path).as_posix()
            files_index.append(rel_to_mod)
    return sorted(set(files_index))


def load_baseline_manifest(csv_path: Path) -> Dict[str, Dict[str, Union[str, int]]]:
    if not csv_path.exists():
        raise FileNotFoundError("Baseline manifest file is missing.")

    entries: Dict[str, Dict[str, Union[str, int]]] = {}
    with open(csv_path, "r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            rel_path = row.get("relative_path")
            if not rel_path:
                continue
            size_raw = row.get("size_bytes", "0")
            try:
                size_value = int(size_raw)
            except Exception:
                size_value = 0
            entries[rel_path] = {
                "size_bytes": size_value,
                "sha256": row.get("sha256", ""),
            }
    return entries


def normalize_version(value: str) -> Tuple[int, ...]:
    if not value:
        return tuple()
    parts = re.split(r"[^\d]+", value)
    numbers = [int(part) for part in parts if part.isdigit()]
    return tuple(numbers)


def is_version_at_least(current_version: str, minimum_version: str) -> bool:
    if not minimum_version:
        return True
    current = list(normalize_version(current_version))
    minimum = list(normalize_version(minimum_version))
    if not current:
        return False
    max_len = max(len(current), len(minimum))
    current.extend([0] * (max_len - len(current)))
    minimum.extend([0] * (max_len - len(minimum)))
    return tuple(current) >= tuple(minimum)
