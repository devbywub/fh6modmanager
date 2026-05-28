from datetime import datetime
from pathlib import Path

from tools.ftexporter import export_directory_to_csv


def run_scanner(fh6path: str):
    print("--- First FH6 Scan ---")

    # 1. Ask user for inputs
    folder_input = input("1. Enter absolute folder path: ").strip()
    if not folder_input:
        target_dir = Path(fh6path)
    target_dir = Path(folder_input)

    if not target_dir.exists() or not target_dir.is_dir():
        print("[ERROR] Invalid directory path.")
        return

    save_name = "FH6_CleanSave"

    default_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    timestamp = input(
        f"3. Enter Timestamp [Press Enter for: '{default_time}']: "
    ).strip()
    if not timestamp:
        timestamp = default_time

    # 2. Call the tool method
    try:
        csv_file_result = export_directory_to_csv(
            target_path=target_dir, save_name=save_name, timestamp=timestamp
        )

        print("\n" + "=" * 50)
        print(f"[SUCCESS] CSV created successfully!")
        print(f"Path: {csv_file_result}")
        print("=" * 50)

    except Exception as e:
        print(f"\n[ERROR] An error occurred during export: {e}")


if __name__ == "__main__":
    run_scanner()
