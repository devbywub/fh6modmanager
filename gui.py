import json
import os
import shutil
import sys
import tempfile
import tkinter as tk
import urllib.request
import zipfile
import ssl
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from urllib.parse import urlparse

# Import backend methods
from tools.tool import (
    build_mod_file_index,
    clean_empty_directories,
    compute_sha256,
    export_directory_to_csv,
    is_version_at_least,
    load_baseline_manifest,
    load_manifest,
    normalize_version,
    normalize_manifest_list,
    sanitize_filename,
)


def get_base_dir() -> Path:
    if sys.platform.startswith("win"):
        root = Path(os.path.splitdrive(os.getcwd())[0] + "/")
        return root / "fh6mm"
    return Path("/fh6mm")


class ModManagerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Forza Horizon 6 Mod Manager (FH6MM)")
        self.root.geometry("820x620")
        self.root.resizable(False, False)

        # Base system directories
        self.base_dir = get_base_dir()
        self.settings_file = self.base_dir / "settings.json"
        self.backup_dir = self.base_dir / "backups"
        self.manifest_file = self.backup_dir / "clean_manifest.csv"
        self.mods_store_dir = self.base_dir / "mods"
        self.originals_backup_dir = self.base_dir / "replacedmainfiles"
        self.logs_dir = self.base_dir / "logs"
        self.log_file = self.logs_dir / "actions.log"
        self.catalog_file = self.base_dir / "catalog_cache.json"
        self.catalog_entries = []
        self.catalog_max_bytes = 5 * 1024 * 1024
        self.download_max_bytes = 200 * 1024 * 1024
        self.zip_max_bytes = 500 * 1024 * 1024
        self.zip_max_files = 20000
        self.zip_max_ratio = 100

        # Initialize folders setup
        self.first_run = False
        self.settings_data = {}
        self.check_and_init_filesystem()

        # Styles Config
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self._configure_styles()

        # Layout Setup
        self.create_widgets()

    def check_and_init_filesystem(self):
        """Build and configure local database registers and verify configuration parameters."""
        try:
            for directory in [
                self.base_dir,
                self.backup_dir,
                self.mods_store_dir,
                self.originals_backup_dir,
                self.logs_dir,
            ]:
                directory.mkdir(parents=True, exist_ok=True)

            if not self.settings_file.exists():
                self.first_run = True
                self.settings_data = {
                    "a": "omni",
                    "game_path": "",
                    "game_version": "",
                    "clean_manifest_generated": False,
                    "date_registered": "",
                    "profiles": {},
                    "active_profile": "",
                    "catalog_url": "",
                    "catalog_last_updated": "",
                    "auto_update_catalog": False,
                    "mods": {},  # Maps sanitized name -> data registry states
                }
                self.save_settings()
            else:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    self.settings_data = json.load(f)

                # Ensure required configuration structure is present
                if "a" not in self.settings_data:
                    self.settings_data["a"] = "omni"
                if "game_version" not in self.settings_data:
                    self.settings_data["game_version"] = ""
                if "mods" not in self.settings_data:
                    self.settings_data["mods"] = {}
                if "profiles" not in self.settings_data:
                    self.settings_data["profiles"] = {}
                if "active_profile" not in self.settings_data:
                    self.settings_data["active_profile"] = ""
                if "catalog_url" not in self.settings_data:
                    self.settings_data["catalog_url"] = ""
                if "catalog_last_updated" not in self.settings_data:
                    self.settings_data["catalog_last_updated"] = ""
                if "auto_update_catalog" not in self.settings_data:
                    self.settings_data["auto_update_catalog"] = False
                self._normalize_mod_settings()
                self.save_settings()

        except PermissionError:
            messagebox.showerror(
                "Permissions Error",
                "Administrative rights are required to read/write under root directories. Please run this script as Administrator.",
            )
            sys.exit()

    def save_settings(self):
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(self.settings_data, f, indent=4)

    def _normalize_mod_settings(self):
        mods = self.settings_data.get("mods", {})
        existing_priorities = [
            data.get("priority")
            for data in mods.values()
            if isinstance(data.get("priority"), int)
        ]
        next_priority = max(existing_priorities, default=0) + 1
        for mod_id, data in mods.items():
            if "name" not in data:
                data["name"] = mod_id
            if "version" not in data:
                data["version"] = "1.0.0"
            if "author" not in data:
                data["author"] = "Unknown"
            if "description" not in data:
                data["description"] = ""
            if "enabled" not in data:
                data["enabled"] = False
            if "backed_up_files_index" not in data:
                data["backed_up_files_index"] = []
            if "backup_hashes" not in data:
                data["backup_hashes"] = {}
            if "file_index" not in data or not data.get("file_index"):
                mod_dir = self.mods_store_dir / mod_id
                if mod_dir.exists():
                    data["file_index"] = build_mod_file_index(mod_dir)
                else:
                    data["file_index"] = []
            if "manifest_id" not in data:
                data["manifest_id"] = sanitize_filename(data.get("name", mod_id))
            if "dependencies" not in data:
                data["dependencies"] = []
            data["dependencies"] = normalize_manifest_list(data.get("dependencies"))
            if "incompatibilities" not in data:
                data["incompatibilities"] = []
            data["incompatibilities"] = normalize_manifest_list(
                data.get("incompatibilities")
            )
            if "min_game_version" not in data:
                data["min_game_version"] = ""
            if not isinstance(data.get("priority"), int):
                data["priority"] = next_priority
                next_priority += 1

    def log_action(self, action: str, details=None):
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "details": details or {},
        }
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def _configure_styles(self):
        self.style.configure(".", background="#131419", foreground="#ffffff")
        self.style.configure(
            "TLabel",
            background="#131419",
            foreground="#ffffff",
            font=("Segoe UI", 9.5),
        )
        self.style.configure("TLabelframe", background="#131419", foreground="#ff007f")
        self.style.configure(
            "TLabelframe.Label",
            background="#131419",
            foreground="#ff007f",
            font=("Segoe UI", 11, "bold"),
        )
        self.style.configure(
            "TButton",
            font=("Segoe UI", 9, "bold"),
            background="#20222a",
            foreground="#ffffff",
        )
        self.style.map("TButton", background=[("active", "#ff007f")])

        # Style Treeview
        self.style.configure(
            "Treeview",
            background="#20222a",
            fieldbackground="#20222a",
            foreground="#ffffff",
        )

    def create_widgets(self):
        # 1. Header Banner
        banner = tk.Frame(self.root, bg="#ff007f", height=50)
        banner.pack(fill="x", side="top")
        lbl_banner = tk.Label(
            banner,
            text="FORZA HORIZON 6 MOD MANAGER",
            bg="#ff007f",
            fg="white",
            font=("Segoe UI Black", 14),
        )
        lbl_banner.pack(pady=10)

        # Main Layout Container
        self.work_space = tk.Frame(self.root, bg="#131419")
        self.work_space.pack(fill="both", expand=True, padx=20, pady=20)

        if not self.settings_data.get("clean_manifest_generated", False):
            self.show_registration_step()
        else:
            self.show_main_dashboard()

    # --- REGISTRATION INTERFACES ---

    def show_registration_step(self):
        """Show dynamic registration workspace if setup is incomplete."""
        for widget in self.work_space.winfo_children():
            widget.destroy()

        step_frame = ttk.LabelFrame(self.work_space, text=" System Setup Required ")
        step_frame.pack(fill="both", expand=True, padx=10, pady=10, ipady=15)

        msg = (
            "We detected that this is a clean workspace installation!\n\n"
            "To properly isolate and roll back files, FH6MM must index your original, unmodded files structure first.\n"
            "Please configure the path pointing into your main Forza Horizon 6 Game Folder below:"
        )

        ttk.Label(
            step_frame,
            text=msg,
            justify="left",
            font=("Segoe UI", 10),
            wraplength=700,
        ).pack(anchor="w", padx=20, pady=20)

        input_frame = tk.Frame(step_frame, bg="#131419")
        input_frame.pack(fill="x", padx=20, pady=10)

        self.ent_dir = ttk.Entry(input_frame, font=("Segoe UI", 10))
        self.ent_dir.pack(side="left", fill="x", expand=True, padx=(0, 10))

        btn_browse = ttk.Button(
            input_frame, text="Browse Folder", command=self.browse_for_game
        )
        btn_browse.pack(side="right")

        self.btn_register = tk.Button(
            step_frame,
            text="🔒 REGIONALIZE CLEAN BASELINE INSTANCE",
            bg="#28a745",
            fg="white",
            font=("Segoe UI", 11, "bold"),
            relief="flat",
            command=self.register_game_baseline,
        )
        self.btn_register.pack(fill="x", padx=20, pady=20, ipady=10)

    def browse_for_game(self):
        path = filedialog.askdirectory(title="Select folder containing FH6 game")
        if path:
            self.ent_dir.delete(0, tk.END)
            self.ent_dir.insert(0, path)

    def register_game_baseline(self):
        path_str = self.ent_dir.get().strip()
        if not path_str:
            messagebox.showerror("Error", "Please select a folder.")
            return

        game_dir = Path(path_str)
        if not game_dir.exists() or not game_dir.is_dir():
            messagebox.showerror("Error", "The folder path selected does not exist.")
            return

        self.btn_register.config(
            text="Parsing Game Tree Registry... Please Wait",
            state="disabled",
            bg="#555",
        )
        self.root.update()

        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            export_directory_to_csv(
                target_path=game_dir,
                save_name="FH6_Baseline_Unmodded",
                timestamp=now_str,
                output_csv_path=self.manifest_file,
            )

            self.settings_data["game_path"] = str(game_dir)
            self.settings_data["clean_manifest_generated"] = True
            self.settings_data["date_registered"] = now_str
            self.save_settings()
            self.log_action(
                "register_baseline",
                {"game_path": str(game_dir), "timestamp": now_str},
            )

            messagebox.showinfo(
                "Structure Registered",
                "Clean baseline indexed successfully! Loading Mod Manager.",
            )
            self.show_main_dashboard()

        except Exception as e:
            messagebox.showerror("Export Baseline Failed", f"Validation error: {e}")
            self.btn_register.config(
                text="🔒 REGIONALIZE CLEAN BASELINE INSTANCE",
                state="normal",
                bg="#28a745",
            )

    # --- MAIN MOD MANAGER WORKSPACE ---

    def show_main_dashboard(self):
        """Main interface displaying loaded mods, manifest details, and mod status toggle."""
        for widget in self.work_space.winfo_children():
            widget.destroy()

        # Top Panel (Status display)
        top_bar = tk.Frame(self.work_space, bg="#131419")
        top_bar.pack(fill="x", pady=(0, 10))

        ttk.Label(
            top_bar,
            text=f"📂 Active target Game Directory: {self.settings_data['game_path']}",
            font=("Segoe UI", 9, "italic"),
            foreground="#aaaaaa",
        ).pack(side="left")

        btn_import = ttk.Button(
            top_bar, text="➕ Import Mod Folder", command=self.import_mod_directory
        )
        btn_import.pack(side="right")

        utils_bar = tk.Frame(self.work_space, bg="#131419")
        utils_bar.pack(fill="x", pady=(0, 10))

        ttk.Label(utils_bar, text="Game Version:").pack(side="left")
        self.game_version_var = tk.StringVar(
            value=self.settings_data.get("game_version", "")
        )
        ttk.Entry(utils_bar, textvariable=self.game_version_var, width=12).pack(
            side="left", padx=(6, 12)
        )
        ttk.Button(
            utils_bar, text="Save Version", command=self.save_game_version
        ).pack(side="left", padx=(0, 18))

        ttk.Label(utils_bar, text="Profile:").pack(side="left")
        self.profile_var = tk.StringVar(
            value=self.settings_data.get("active_profile", "")
        )
        self.profile_combo = ttk.Combobox(
            utils_bar, textvariable=self.profile_var, state="readonly", width=18
        )
        self.refresh_profile_list()
        self.profile_combo.pack(side="left", padx=(6, 6))
        ttk.Button(utils_bar, text="Save Current", command=self.save_profile).pack(
            side="left"
        )
        ttk.Button(utils_bar, text="Apply", command=self.apply_selected_profile).pack(
            side="left", padx=(6, 18)
        )

        ttk.Button(utils_bar, text="Catalog", command=self.show_catalog_window).pack(
            side="right"
        )
        ttk.Button(utils_bar, text="Export Logs", command=self.export_logs).pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(utils_bar, text="Repair Mode", command=self.repair_installation).pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(
            utils_bar, text="Verify Integrity", command=self.verify_integrity
        ).pack(side="right", padx=(6, 0))

        # Split Pane: Left Tree List, Right Details Layout
        panes = tk.PanedWindow(
            self.work_space, orient="horizontal", bg="#131419", sashwidth=4
        )
        panes.pack(fill="both", expand=True)

        # Left list module
        left_frame = ttk.LabelFrame(panes, text=" Configured Mods ")
        self.mod_tree = ttk.Treeview(
            left_frame, columns=("state", "priority", "name", "version"), show="headings"
        )
        self.mod_tree.heading("state", text="Status")
        self.mod_tree.heading("priority", text="Priority")
        self.mod_tree.heading("name", text="Mod Title")
        self.mod_tree.heading("version", text="Version")

        self.mod_tree.column("state", width=80, anchor="center")
        self.mod_tree.column("priority", width=70, anchor="center")
        self.mod_tree.column("name", width=190, anchor="w")
        self.mod_tree.column("version", width=80, anchor="center")
        self.mod_tree.pack(fill="both", expand=True)

        self.mod_tree.bind("<<TreeviewSelect>>", self.on_mod_selected)
        panes.add(left_frame, minsize=380)

        # Right Dynamic Panel details
        self.details_frame = ttk.LabelFrame(panes, text=" Mod Manifest Details ")
        panes.add(self.details_frame, minsize=380)

        self.show_no_selection_details()
        self.refresh_mods_list()

    def show_no_selection_details(self):
        for widget in self.details_frame.winfo_children():
            widget.destroy()

        lbl_no_sel = ttk.Label(
            self.details_frame,
            text="Please select a Mod on the left\nto access options details.",
            justify="center",
            font=("Segoe UI", 10, "italic"),
            foreground="#888",
        )
        lbl_no_sel.pack(expand=True)

    def refresh_mods_list(self):
        # Clear existing items
        for item in self.mod_tree.get_children():
            self.mod_tree.delete(item)

        stored_mods = self.settings_data.get("mods", {})
        for mod_id, data in sorted(
            stored_mods.items(), key=lambda item: item[1].get("priority", 0)
        ):
            status = "🟢 Enabled" if data.get("enabled", False) else "🔴 Disabled"
            priority = data.get("priority", 0)
            name = data.get("name", "Unknown Mod")
            version = data.get("version", "1.0.0")
            self.mod_tree.insert(
                "", "end", iid=mod_id, values=(status, priority, name, version)
            )

    def on_mod_selected(self, event):
        selected_items = self.mod_tree.selection()
        if not selected_items:
            return

        mod_id = selected_items[0]
        data = self.settings_data["mods"].get(mod_id)
        if not data:
            return

        self.show_mod_details(mod_id, data)

    def show_mod_details(self, mod_id, data):
        """Dynamic configuration display logic on metadata loads."""
        for widget in self.details_frame.winfo_children():
            widget.destroy()

        content = tk.Frame(self.details_frame, bg="#131419")
        content.pack(fill="both", expand=True, padx=15, pady=15)

        # Metadata Layout labels
        ttk.Label(
            content,
            text=data.get("name"),
            font=("Segoe UI", 13, "bold"),
            wraplength=350,
        ).pack(anchor="w", pady=(0, 5))

        lbl_version = ttk.Label(
            content,
            text=f"Version:  {data.get('version')} | Author: {data.get('author')}",
            font=("Segoe UI", 9),
            foreground="#aaaaaa",
        )
        lbl_version.pack(anchor="w", pady=(0, 15))

        priority_frame = tk.Frame(content, bg="#131419")
        priority_frame.pack(anchor="w", pady=(0, 10), fill="x")
        ttk.Label(
            priority_frame,
            text=f"Priority: {data.get('priority', 0)}",
            font=("Segoe UI", 9),
            foreground="#aaaaaa",
        ).pack(side="left")
        tk.Button(
            priority_frame,
            text="▲",
            bg="#333",
            fg="white",
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            command=lambda: self.adjust_priority(mod_id, -1),
        ).pack(side="left", padx=(10, 4))
        tk.Button(
            priority_frame,
            text="▼",
            bg="#333",
            fg="white",
            font=("Segoe UI", 8, "bold"),
            relief="flat",
            command=lambda: self.adjust_priority(mod_id, 1),
        ).pack(side="left")

        # Description Panel
        desc_box = tk.Text(
            content,
            height=6,
            wrap="word",
            bg="#20222a",
            fg="#F1F1F1",
            relief="flat",
            font=("Segoe UI", 9),
        )
        desc_box.insert("1.0", data.get("description", "No description added."))
        desc_box.config(state="disabled")
        desc_box.pack(fill="x", pady=(0, 20))

        # Action Buttons
        is_enabled = data.get("enabled", False)
        if is_enabled:
            btn_toggle = tk.Button(
                content,
                text="🔴 Disable Mod",
                bg="#dc3545",
                fg="white",
                font=("Segoe UI", 10, "bold"),
                relief="flat",
                command=lambda: self.disable_mod(mod_id),
            )
        else:
            btn_toggle = tk.Button(
                content,
                text="🟢 Enable Mod",
                bg="#28a745",
                fg="white",
                font=("Segoe UI", 10, "bold"),
                relief="flat",
                command=lambda: self.enable_mod(mod_id),
            )

        btn_toggle.pack(fill="x", ipady=8, pady=(0, 10))

        # Delete from register path button (Force cleanup first)
        btn_delete = tk.Button(
            content,
            text="🗑️ Delete Mod",
            bg="#555",
            fg="white",
            font=("Segoe UI", 9),
            relief="flat",
            command=lambda: self.delete_mod_from_system(mod_id),
        )
        btn_delete.pack(fill="x", ipady=4)

    def refresh_profile_list(self):
        profiles = list(self.settings_data.get("profiles", {}).keys())
        if hasattr(self, "profile_combo"):
            self.profile_combo["values"] = profiles
            active = self.settings_data.get("active_profile", "")
            if active in profiles:
                self.profile_combo.set(active)
            elif profiles:
                self.profile_combo.set(profiles[0])

    def save_game_version(self):
        version = self.game_version_var.get().strip()
        self.settings_data["game_version"] = version
        self.save_settings()
        self.log_action("set_game_version", {"version": version})
        messagebox.showinfo("Saved", "Game version saved successfully.")

    def save_profile(self):
        profile_name = simpledialog.askstring(
            "Save Profile", "Enter a profile name (e.g. Offline, Visual, Performance):"
        )
        if not profile_name:
            return
        enabled_mods = [
            mod_id
            for mod_id, data in self.settings_data.get("mods", {}).items()
            if data.get("enabled")
        ]
        self.settings_data.setdefault("profiles", {})[profile_name] = enabled_mods
        self.settings_data["active_profile"] = profile_name
        self.save_settings()
        self.refresh_profile_list()
        self.log_action(
            "save_profile",
            {"profile": profile_name, "mods": enabled_mods},
        )
        messagebox.showinfo(
            "Profile Saved", f"Profile '{profile_name}' saved successfully."
        )

    def apply_selected_profile(self):
        profile_name = self.profile_var.get().strip()
        if not profile_name:
            messagebox.showerror("Profile", "Please select a profile to apply.")
            return
        self.apply_profile(profile_name)

    def apply_profile(self, profile_name: str):
        profiles = self.settings_data.get("profiles", {})
        if profile_name not in profiles:
            messagebox.showerror("Profile", "Selected profile does not exist.")
            return

        target_mods = set(profiles.get(profile_name, []))
        enabled_mods = {
            mod_id
            for mod_id, data in self.settings_data.get("mods", {}).items()
            if data.get("enabled")
        }

        to_disable = sorted(enabled_mods - target_mods)
        to_enable = sorted(target_mods - enabled_mods)

        confirm = messagebox.askyesno(
            "Apply Profile",
            f"Profile '{profile_name}' will enable {len(to_enable)} mods and "
            f"disable {len(to_disable)} mods. Continue?",
        )
        if not confirm:
            return

        for mod_id in to_disable:
            self.disable_mod(mod_id, silent=True)

        for mod_id in sorted(
            to_enable,
            key=lambda mid: self.settings_data["mods"].get(mid, {}).get("priority", 0),
        ):
            if not self.enable_mod(mod_id, silent=True, skip_preview=True):
                messagebox.showerror(
                    "Profile Apply",
                    f"Stopped enabling mods due to validation error on '{mod_id}'.",
                )
                return

        self.settings_data["active_profile"] = profile_name
        self.save_settings()
        self.refresh_mods_list()
        self.log_action(
            "apply_profile",
            {
                "profile": profile_name,
                "enabled": to_enable,
                "disabled": to_disable,
            },
        )
        messagebox.showinfo(
            "Profile Applied", f"Profile '{profile_name}' applied successfully."
        )

    def adjust_priority(self, mod_id: str, direction: int):
        mods = self.settings_data.get("mods", {})
        ordered = sorted(mods.items(), key=lambda item: item[1].get("priority", 0))
        ids = [mid for mid, _ in ordered]
        if mod_id not in ids:
            return
        current_index = ids.index(mod_id)
        target_index = current_index + direction
        if target_index < 0 or target_index >= len(ids):
            return

        current_id = ids[current_index]
        target_id = ids[target_index]
        current_priority = mods[current_id].get("priority", 0)
        target_priority = mods[target_id].get("priority", 0)
        mods[current_id]["priority"] = target_priority
        mods[target_id]["priority"] = current_priority
        self.save_settings()
        self.refresh_mods_list()
        self.show_mod_details(mod_id, mods[mod_id])

    def find_mod_ids_by_reference(self, reference: str):
        ref = reference.strip().lower()
        matches = []
        for mod_id, data in self.settings_data.get("mods", {}).items():
            name = str(data.get("name", "")).lower()
            manifest_id = str(data.get("manifest_id", "")).lower()
            if ref in {name, manifest_id}:
                matches.append(mod_id)
        return matches

    def validate_manifest_on_import(self, manifest_info) -> str:
        min_game_version = str(manifest_info.get("min_game_version", "")).strip()
        current_version = self.settings_data.get("game_version", "").strip()
        if min_game_version:
            if not current_version:
                return "Set a game version before importing mods with minimum version requirements."
            if not is_version_at_least(current_version, min_game_version):
                return (
                    f"Mod requires game version {min_game_version}, "
                    f"but current version is {current_version}."
                )

        for dependency in manifest_info.get("dependencies", []):
            if not self.find_mod_ids_by_reference(dependency):
                return f"Missing dependency: {dependency}"

        for incompatible in manifest_info.get("incompatibilities", []):
            if self.find_mod_ids_by_reference(incompatible):
                return f"Incompatible mod already installed: {incompatible}"

        return ""

    def validate_mod_for_enable(self, mod_id: str) -> str:
        mod_info = self.settings_data.get("mods", {}).get(mod_id, {})
        min_game_version = str(mod_info.get("min_game_version", "")).strip()
        current_version = self.settings_data.get("game_version", "").strip()
        if min_game_version:
            if not current_version:
                return "Set a game version before enabling this mod."
            if not is_version_at_least(current_version, min_game_version):
                return (
                    f"Mod requires game version {min_game_version}, "
                    f"but current version is {current_version}."
                )

        for dependency in mod_info.get("dependencies", []):
            matching_ids = self.find_mod_ids_by_reference(dependency)
            if not matching_ids:
                return f"Missing dependency: {dependency}"
            if not any(
                self.settings_data["mods"].get(mid, {}).get("enabled")
                for mid in matching_ids
            ):
                return f"Dependency not enabled: {dependency}"

        for incompatible in mod_info.get("incompatibilities", []):
            matching_ids = self.find_mod_ids_by_reference(incompatible)
            if any(
                self.settings_data["mods"].get(mid, {}).get("enabled")
                for mid in matching_ids
            ):
                return f"Incompatible enabled mod detected: {incompatible}"

        return ""

    def ensure_mod_file_index(self, mod_id: str, mod_info: dict) -> list:
        file_index = mod_info.get("file_index", [])
        if not file_index:
            mod_source = self.mods_store_dir / mod_id
            if mod_source.exists():
                file_index = build_mod_file_index(mod_source)
                mod_info["file_index"] = file_index
                self.save_settings()
        return file_index

    def start_progress(self, title: str, total: int):
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry("420x120")
        window.resizable(False, False)
        window.transient(self.root)
        window.grab_set()
        label_var = tk.StringVar(value=title)
        ttk.Label(window, textvariable=label_var).pack(pady=(10, 6))
        progress_bar = ttk.Progressbar(
            window, maximum=max(total, 1), length=360
        )
        progress_bar.pack(pady=6)
        return window, progress_bar, label_var

    def update_progress(self, progress_bar, label_var, value: int, message: str):
        progress_bar["value"] = value
        label_var.set(message)
        self.root.update()

    def finish_progress(self, window):
        if window and window.winfo_exists():
            window.destroy()

    def detect_mod_conflicts(self, mod_id: str, file_index: list) -> str:
        conflicts = []
        file_set = set(file_index)
        for other_id, data in self.settings_data.get("mods", {}).items():
            if other_id == mod_id or not data.get("enabled"):
                continue
            other_files = set(data.get("file_index", []))
            overlap = sorted(file_set & other_files)
            if overlap:
                conflicts.append(
                    {
                        "mod_id": other_id,
                        "name": data.get("name", other_id),
                        "priority": data.get("priority", 0),
                        "files": overlap,
                    }
                )

        if not conflicts:
            return ""

        lines = ["Conflicts detected with enabled mods:"]
        for conflict in conflicts:
            sample = ", ".join(conflict["files"][:5])
            suffix = "..." if len(conflict["files"]) > 5 else ""
            lines.append(
                f"- {conflict['name']} (priority {conflict['priority']}): "
                f"{len(conflict['files'])} files ({sample}{suffix})"
            )
        lines.append("Disable conflicting mods or adjust their priority before enabling.")
        return "\n".join(lines)

    def confirm_mod_activation(self, mod_id: str, file_index: list, game_dir: Path):
        overwrite_files = []
        new_files = []
        for rel_path in file_index:
            target = game_dir / rel_path
            if target.exists():
                overwrite_files.append(rel_path)
            else:
                new_files.append(rel_path)

        window = tk.Toplevel(self.root)
        window.title("Activation Preview")
        window.geometry("520x420")
        window.transient(self.root)
        window.grab_set()

        title = ttk.Label(
            window,
            text=f"Preview changes for {self.settings_data['mods'][mod_id]['name']}",
            font=("Segoe UI", 10, "bold"),
        )
        title.pack(pady=(10, 6))

        text_frame = tk.Frame(window)
        text_frame.pack(fill="both", expand=True, padx=10, pady=6)
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")

        text = tk.Text(text_frame, wrap="word", yscrollcommand=scrollbar.set)
        text.pack(fill="both", expand=True)
        scrollbar.config(command=text.yview)

        text.insert("end", f"Files to overwrite ({len(overwrite_files)}):\n")
        text.insert("end", "\n".join(overwrite_files) or "- None")
        text.insert("end", "\n\nFiles to add ({len(new_files)}):\n")
        text.insert("end", "\n".join(new_files) or "- None")
        text.config(state="disabled")

        result = {"confirm": False}

        def confirm():
            result["confirm"] = True
            window.destroy()

        def cancel():
            window.destroy()

        btn_frame = tk.Frame(window)
        btn_frame.pack(pady=10)
        tk.Button(
            btn_frame,
            text="Proceed",
            bg="#28a745",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            command=confirm,
        ).pack(side="left", padx=8)
        tk.Button(
            btn_frame,
            text="Cancel",
            bg="#555",
            fg="white",
            font=("Segoe UI", 9),
            relief="flat",
            command=cancel,
        ).pack(side="left", padx=8)

        self.root.wait_window(window)
        return result["confirm"]

    def export_logs(self):
        if not self.log_file.exists():
            messagebox.showerror("Export Logs", "No logs available to export.")
            return
        target = filedialog.asksaveasfilename(
            title="Export Logs",
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("All files", "*.*")],
        )
        if not target:
            return
        shutil.copy2(self.log_file, target)
        messagebox.showinfo("Logs Exported", f"Logs exported to:\n{target}")

    def verify_integrity(self):
        if not self.settings_data.get("game_path"):
            messagebox.showerror("Integrity Check", "Game path is not configured.")
            return
        try:
            baseline = load_baseline_manifest(self.manifest_file)
        except Exception as e:
            messagebox.showerror("Integrity Check", f"Failed loading baseline: {e}")
            return

        game_dir = Path(self.settings_data["game_path"])
        missing = []
        mismatched = []
        for rel_path, info in baseline.items():
            target = game_dir / rel_path
            if not target.exists():
                missing.append(rel_path)
                continue
            expected_hash = info.get("sha256", "")
            if expected_hash:
                try:
                    current_hash = compute_sha256(target)
                except Exception:
                    current_hash = ""
                if current_hash != expected_hash:
                    mismatched.append(rel_path)
            else:
                expected_size = info.get("size_bytes", 0)
                try:
                    size = target.stat().st_size
                except Exception:
                    size = -1
                if size != expected_size:
                    mismatched.append(rel_path)

        extras = []
        for root, _, files in os.walk(game_dir):
            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(game_dir).as_posix()
                if rel_path not in baseline:
                    extras.append(rel_path)

        backup_issues = []
        for mod_id, data in self.settings_data.get("mods", {}).items():
            backup_hashes = data.get("backup_hashes", {})
            backup_root = self.originals_backup_dir / mod_id / "originals"
            for rel_path, expected_hash in backup_hashes.items():
                backup_file = backup_root / rel_path
                if not backup_file.exists():
                    backup_issues.append(f"{mod_id}: missing backup {rel_path}")
                    continue
                if expected_hash:
                    try:
                        current_hash = compute_sha256(backup_file)
                    except Exception:
                        current_hash = ""
                    if current_hash != expected_hash:
                        backup_issues.append(f"{mod_id}: corrupted backup {rel_path}")

        report_lines = [
            f"Missing files: {len(missing)}",
            f"Mismatched files: {len(mismatched)}",
            f"Extra files: {len(extras)}",
            f"Backup issues: {len(backup_issues)}",
            "",
            "Sample missing files:",
            "\n".join(missing[:10]) or "- None",
            "",
            "Sample mismatched files:",
            "\n".join(mismatched[:10]) or "- None",
            "",
            "Sample extra files:",
            "\n".join(extras[:10]) or "- None",
            "",
            "Sample backup issues:",
            "\n".join(backup_issues[:10]) or "- None",
        ]

        self.log_action(
            "verify_integrity",
            {
                "missing": len(missing),
                "mismatched": len(mismatched),
                "extra": len(extras),
                "backup_issues": len(backup_issues),
            },
        )

        self.show_report_window("Integrity Report", "\n".join(report_lines))

    def repair_installation(self):
        if not self.settings_data.get("game_path"):
            messagebox.showerror("Repair Mode", "Game path is not configured.")
            return
        try:
            baseline = load_baseline_manifest(self.manifest_file)
        except Exception as e:
            messagebox.showerror("Repair Mode", f"Failed loading baseline: {e}")
            return

        game_dir = Path(self.settings_data["game_path"])
        backup_map = {}
        for mod_id in self.settings_data.get("mods", {}):
            backup_root = self.originals_backup_dir / mod_id / "originals"
            if not backup_root.exists():
                continue
            for root, _, files in os.walk(backup_root):
                for file in files:
                    backup_file = Path(root) / file
                    rel_path = backup_file.relative_to(backup_root).as_posix()
                    if rel_path not in backup_map:
                        backup_map[rel_path] = backup_file

        restored = []
        unresolved = []
        removed_extras = []
        progress_window, progress_bar, progress_label = self.start_progress(
            "Repairing Installation", len(baseline)
        )
        try:
            progress_count = 0
            for rel_path, info in baseline.items():
                target = game_dir / rel_path
                expected_hash = info.get("sha256", "")
                needs_restore = False
                if not target.exists():
                    needs_restore = True
                elif expected_hash:
                    try:
                        current_hash = compute_sha256(target)
                    except Exception:
                        current_hash = ""
                    if current_hash != expected_hash:
                        needs_restore = True
                else:
                    expected_size = info.get("size_bytes", 0)
                    try:
                        size = target.stat().st_size
                    except Exception:
                        size = -1
                    if size != expected_size:
                        needs_restore = True

                if needs_restore:
                    backup_file = backup_map.get(rel_path)
                    if backup_file and backup_file.exists():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(backup_file, target)
                        restored.append(rel_path)
                    else:
                        unresolved.append(rel_path)

                progress_count += 1
                self.update_progress(
                    progress_bar,
                    progress_label,
                    progress_count,
                    f"Checked {progress_count}/{len(baseline)} files",
                )

            for root, _, files in os.walk(game_dir):
                for file in files:
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(game_dir).as_posix()
                    if rel_path not in baseline:
                        try:
                            file_path.unlink()
                            removed_extras.append(rel_path)
                        except Exception:
                            pass

            clean_empty_directories(game_dir)

        finally:
            self.finish_progress(progress_window)

        self.log_action(
            "repair_installation",
            {
                "restored": len(restored),
                "unresolved": len(unresolved),
            },
        )

        report_lines = [
            f"Restored files: {len(restored)}",
            f"Unresolved files: {len(unresolved)}",
            f"Removed extra files: {len(removed_extras)}",
            "",
            "Sample restored files:",
            "\n".join(restored[:10]) or "- None",
            "",
            "Sample unresolved files:",
            "\n".join(unresolved[:10]) or "- None",
        ]
        self.show_report_window("Repair Report", "\n".join(report_lines))

    def show_report_window(self, title: str, content: str):
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry("560x420")
        window.transient(self.root)

        text_frame = tk.Frame(window)
        text_frame.pack(fill="both", expand=True, padx=10, pady=10)
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")

        text = tk.Text(text_frame, wrap="word", yscrollcommand=scrollbar.set)
        text.pack(fill="both", expand=True)
        scrollbar.config(command=text.yview)
        text.insert("end", content)
        text.config(state="disabled")

    def validate_https_url(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            return "Only valid https:// URLs are allowed."
        return ""

    def fetch_json_with_limits(self, url: str, max_bytes: int):
        context = ssl.create_default_context()
        with urllib.request.urlopen(url, timeout=15, context=context) as response:
            length = response.headers.get("Content-Length")
            try:
                length_value = int(length) if length else None
            except ValueError:
                length_value = None
            if length_value and length_value > max_bytes:
                raise ValueError("Remote payload exceeds size limit.")
            payload = response.read(max_bytes + 1)
            if len(payload) > max_bytes:
                raise ValueError("Remote payload exceeds size limit.")
            return json.loads(payload.decode("utf-8"))

    def download_with_limits(self, url: str, dest: Path, max_bytes: int):
        context = ssl.create_default_context()
        with urllib.request.urlopen(url, timeout=20, context=context) as response:
            length = response.headers.get("Content-Length")
            try:
                length_value = int(length) if length else None
            except ValueError:
                length_value = None
            if length_value and length_value > max_bytes:
                raise ValueError("Download exceeds allowed size.")
            total = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise ValueError("Download exceeds allowed size.")
                    f.write(chunk)

    def validate_zip_safety(self, zip_ref: zipfile.ZipFile):
        infos = zip_ref.infolist()
        if len(infos) > self.zip_max_files:
            raise ValueError("Archive contains too many files.")
        total_size = 0
        for info in infos:
            total_size += info.file_size
            if total_size > self.zip_max_bytes:
                raise ValueError("Archive is too large to extract safely.")
            if info.compress_size == 0 and info.file_size > 0:
                raise ValueError("Archive compression ratio is suspiciously high.")
            if info.compress_size:
                ratio = info.file_size / info.compress_size
                if ratio > self.zip_max_ratio:
                    raise ValueError("Archive compression ratio is suspiciously high.")

    def safe_extract_zip(self, zip_ref: zipfile.ZipFile, dest: Path):
        dest_path = dest.resolve()
        for info in zip_ref.infolist():
            target_path = (dest / info.filename).resolve()
            try:
                common_path = os.path.commonpath(
                    [str(dest_path), str(target_path)]
                )
            except ValueError:
                raise ValueError("Archive contains unsafe paths.") from None
            if common_path != str(dest_path):
                raise ValueError("Archive contains unsafe paths.")
        zip_ref.extractall(dest)

    def show_catalog_window(self):
        if hasattr(self, "catalog_window") and self.catalog_window.winfo_exists():
            self.catalog_window.lift()
            return

        self.catalog_window = tk.Toplevel(self.root)
        self.catalog_window.title("Mod Catalog")
        self.catalog_window.geometry("640x460")
        self.catalog_window.transient(self.root)

        header = tk.Frame(self.catalog_window)
        header.pack(fill="x", padx=10, pady=8)

        ttk.Label(header, text="Catalog URL:").pack(side="left")
        self.catalog_url_var = tk.StringVar(
            value=self.settings_data.get("catalog_url", "")
        )
        ttk.Entry(header, textvariable=self.catalog_url_var, width=45).pack(
            side="left", padx=(6, 8)
        )
        ttk.Button(header, text="Refresh", command=self.refresh_catalog).pack(
            side="left"
        )

        self.auto_update_var = tk.BooleanVar(
            value=self.settings_data.get("auto_update_catalog", False)
        )
        ttk.Checkbutton(
            header,
            text="Auto-update installed mods",
            variable=self.auto_update_var,
            command=self.toggle_auto_update,
        ).pack(side="right")

        self.catalog_tree = ttk.Treeview(
            self.catalog_window,
            columns=("name", "version", "author", "status"),
            show="headings",
        )
        self.catalog_tree.heading("name", text="Mod")
        self.catalog_tree.heading("version", text="Version")
        self.catalog_tree.heading("author", text="Author")
        self.catalog_tree.heading("status", text="Status")
        self.catalog_tree.column("name", width=230)
        self.catalog_tree.column("version", width=90, anchor="center")
        self.catalog_tree.column("author", width=130, anchor="center")
        self.catalog_tree.column("status", width=140, anchor="center")
        self.catalog_tree.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        btn_frame = tk.Frame(self.catalog_window)
        btn_frame.pack(pady=6)
        ttk.Button(
            btn_frame, text="Install / Update Selected", command=self.install_catalog_selection
        ).pack(side="left", padx=6)
        ttk.Button(
            btn_frame, text="Update All", command=self.update_all_catalog_updates
        ).pack(side="left", padx=6)

        self.load_catalog_cache()
        self.update_catalog_tree()

    def toggle_auto_update(self):
        self.settings_data["auto_update_catalog"] = bool(self.auto_update_var.get())
        self.save_settings()

    def load_catalog_cache(self):
        if not self.catalog_file.exists():
            return
        try:
            with open(self.catalog_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self.catalog_entries = data
        except Exception:
            self.catalog_entries = []

    def refresh_catalog(self):
        url = self.catalog_url_var.get().strip()
        if not url:
            messagebox.showerror("Catalog", "Please provide a catalog URL.")
            return
        url_error = self.validate_https_url(url)
        if url_error:
            messagebox.showerror("Catalog", url_error)
            return
        try:
            entries = self.fetch_catalog_entries(url)
        except Exception as e:
            messagebox.showerror("Catalog", f"Failed to fetch catalog: {e}")
            return

        self.catalog_entries = entries
        self.settings_data["catalog_url"] = url
        self.settings_data["catalog_last_updated"] = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        self.save_settings()
        with open(self.catalog_file, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2)

        self.log_action("refresh_catalog", {"count": len(entries), "url": url})
        self.update_catalog_tree()

        if self.auto_update_var.get():
            self.update_all_catalog_updates(auto_triggered=True)

    def fetch_catalog_entries(self, url: str):
        data = self.fetch_json_with_limits(url, self.catalog_max_bytes)

        entries = []
        if isinstance(data, dict):
            raw_entries = data.get("mods") or data.get("entries") or []
        elif isinstance(data, list):
            raw_entries = data
        else:
            raw_entries = []

        for entry in raw_entries:
            if not isinstance(entry, dict):
                continue
            normalized = {
                "id": entry.get("id") or entry.get("mod_id") or entry.get("name"),
                "name": entry.get("name", "Unknown Mod"),
                "version": entry.get("version", "1.0.0"),
                "author": entry.get("author", "Unknown"),
                "description": entry.get("description", ""),
                "download_url": entry.get("download_url", ""),
                "sha256": entry.get("sha256", ""),
            }
            entries.append(normalized)
        return entries

    def update_catalog_tree(self):
        if not hasattr(self, "catalog_tree"):
            return
        for item in self.catalog_tree.get_children():
            self.catalog_tree.delete(item)

        for index, entry in enumerate(self.catalog_entries):
            status = self.get_catalog_status(entry)
            self.catalog_tree.insert(
                "", "end", iid=str(index), values=(
                    entry.get("name"),
                    entry.get("version"),
                    entry.get("author"),
                    status,
                )
            )

    def get_catalog_status(self, entry: dict) -> str:
        entry_id = (entry.get("id") or entry.get("name") or "").strip()
        if not entry_id:
            return "Unknown"
        matching = self.find_mod_ids_by_reference(entry_id)
        if not matching:
            return "Not installed"

        newest = False
        for mod_id in matching:
            installed_version = str(self.settings_data["mods"][mod_id].get("version", ""))
            if self.is_version_newer(entry.get("version", ""), installed_version):
                newest = True
        return "Update available" if newest else "Installed"

    def is_version_newer(self, candidate: str, current: str) -> bool:
        return normalize_version(candidate) > normalize_version(current)

    def install_catalog_selection(self):
        if not hasattr(self, "catalog_tree"):
            return
        selection = self.catalog_tree.selection()
        if not selection:
            messagebox.showerror("Catalog", "Select a catalog entry first.")
            return
        entry_index = int(selection[0])
        if entry_index < 0 or entry_index >= len(self.catalog_entries):
            return
        entry = self.catalog_entries[entry_index]
        self.install_catalog_entry(entry)

    def update_all_catalog_updates(self, auto_triggered: bool = False):
        updates = [
            entry
            for entry in self.catalog_entries
            if self.get_catalog_status(entry) == "Update available"
        ]
        if not updates:
            if not auto_triggered:
                messagebox.showinfo("Catalog", "No updates available.")
            return
        if not auto_triggered:
            confirm = messagebox.askyesno(
                "Update All",
                f"Update {len(updates)} mods from the catalog?",
            )
            if not confirm:
                return
        for entry in updates:
            self.install_catalog_entry(entry, silent=auto_triggered)

    def install_catalog_entry(self, entry: dict, silent: bool = False):
        download_url = entry.get("download_url", "").strip()
        if not download_url:
            if not silent:
                messagebox.showerror("Catalog", "Selected entry has no download URL.")
            return
        url_error = self.validate_https_url(download_url)
        if url_error:
            if not silent:
                messagebox.showerror("Catalog", url_error)
            return

        entry_id = entry.get("id") or entry.get("name") or ""
        existing_mods = self.find_mod_ids_by_reference(entry_id)
        if existing_mods and not silent:
            confirm = messagebox.askyesno(
                "Update Mod",
                f"Update existing mod(s) for '{entry.get('name')}'?",
            )
            if not confirm:
                return

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                archive_path = temp_path / "mod_package"
                self.download_with_limits(
                    download_url, archive_path, self.download_max_bytes
                )

                expected_hash = entry.get("sha256", "")
                if expected_hash:
                    actual_hash = compute_sha256(archive_path)
                    if actual_hash != expected_hash:
                        if not silent:
                            messagebox.showerror(
                                "Catalog", "Checksum verification failed for download."
                            )
                        return

                if not zipfile.is_zipfile(archive_path):
                    if not silent:
                        messagebox.showerror(
                            "Catalog", "Download is not a valid zip archive."
                        )
                    return

                extract_dir = temp_path / "extracted"
                extract_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(archive_path, "r") as zip_ref:
                    self.validate_zip_safety(zip_ref)
                    self.safe_extract_zip(zip_ref, extract_dir)

                mod_root = self.find_manifest_root(extract_dir)
                if not mod_root:
                    if not silent:
                        messagebox.showerror(
                            "Catalog", "manifest.json not found in downloaded archive."
                        )
                    return

                for mod_id in existing_mods:
                    self.delete_mod_from_system(mod_id, prompt=False)

                self.import_mod_path(mod_root, source_label="catalog")
                self.log_action(
                    "install_catalog_mod",
                    {"name": entry.get("name"), "version": entry.get("version")},
                )
        except Exception as e:
            if not silent:
                messagebox.showerror("Catalog", f"Failed installing catalog mod: {e}")

    def find_manifest_root(self, search_dir: Path):
        manifest_paths = []
        for root, _, files in os.walk(search_dir):
            if "manifest.json" in files:
                manifest_paths.append(Path(root))
        if not manifest_paths:
            return None
        return manifest_paths[0]

    # --- ACTION MANAGEMENT ENGINE ---
    def import_mod_path(self, selected_path: Path, source_label: str = "manual"):
        try:
            manifest_info = load_manifest(selected_path)
            validation_error = self.validate_manifest_on_import(manifest_info)
            if validation_error:
                messagebox.showerror("Import Blocked", validation_error)
                return

            mod_title = str(manifest_info["name"])
            mod_id = sanitize_filename(f"{mod_title}_{manifest_info['version']}")

            if mod_id in self.settings_data["mods"]:
                messagebox.showerror(
                    "Conflict", "This mod version has already been imported."
                )
                return

            mod_dest_dir = self.mods_store_dir / mod_id
            if mod_dest_dir.exists():
                shutil.rmtree(mod_dest_dir)

            shutil.copytree(selected_path, mod_dest_dir)
            file_index = build_mod_file_index(mod_dest_dir)

            existing_priorities = [
                data.get("priority", 0)
                for data in self.settings_data["mods"].values()
                if isinstance(data.get("priority"), int)
            ]
            next_priority = max(existing_priorities, default=0) + 1

            manifest_id = manifest_info.get("id") or manifest_info.get("mod_id")
            if not manifest_id:
                manifest_id = mod_title
            manifest_id = sanitize_filename(str(manifest_id))

            self.settings_data["mods"][mod_id] = {
                "name": mod_title,
                "version": manifest_info["version"],
                "author": manifest_info["author"],
                "description": manifest_info["description"],
                "enabled": False,
                "backed_up_files_index": [],
                "backup_hashes": {},
                "file_index": file_index,
                "manifest_id": manifest_id,
                "dependencies": manifest_info.get("dependencies", []),
                "incompatibilities": manifest_info.get("incompatibilities", []),
                "min_game_version": manifest_info.get("min_game_version", ""),
                "priority": next_priority,
            }
            self.save_settings()

            self.log_action(
                "import_mod",
                {
                    "mod_id": mod_id,
                    "name": mod_title,
                    "version": manifest_info["version"],
                    "source": source_label,
                },
            )

            messagebox.showinfo(
                "Import Successful",
                f"Mod safely imported to library:\n'{mod_title}'",
            )
            self.refresh_mods_list()
            self.show_no_selection_details()

        except Exception as e:
            messagebox.showerror(
                "Import Failed",
                f"Validation failed on this folder structure:\n\n{str(e)}",
            )

    def import_mod_directory(self):
        """Imports an extracted mod folder to `/fh6mm/mods/` after validation."""
        selected_dir = filedialog.askdirectory(
            title="Import Extracted Mod (Contains manifest.json)"
        )
        if not selected_dir:
            return

        self.import_mod_path(Path(selected_dir))

    def enable_mod(self, mod_id: str, silent: bool = False, skip_preview: bool = False):
        """Copies mod files into the target directories and backs up overwritten files."""
        mod_info = self.settings_data["mods"].get(mod_id)
        if not mod_info:
            return False

        validation_error = self.validate_mod_for_enable(mod_id)
        if validation_error:
            if not silent:
                messagebox.showerror("Enable Blocked", validation_error)
            return False

        file_index = self.ensure_mod_file_index(mod_id, mod_info)
        conflict_report = self.detect_mod_conflicts(mod_id, file_index)
        if conflict_report:
            if not silent:
                messagebox.showerror("Conflict Detected", conflict_report)
            return False

        game_dir = Path(self.settings_data["game_path"])
        mod_source = self.mods_store_dir / mod_id
        backup_origin_root = self.originals_backup_dir / mod_id / "originals"

        if not skip_preview:
            if not self.confirm_mod_activation(mod_id, file_index, game_dir):
                return False

        backup_origin_root.mkdir(parents=True, exist_ok=True)
        replaced_index = []
        backup_hashes = {}
        progress_window, progress_bar, progress_label = self.start_progress(
            "Enabling Mod", len(file_index)
        )

        try:
            progress_count = 0
            for root, _, files in os.walk(mod_source):
                for file in files:
                    if file == "manifest.json":
                        continue

                    source_file = Path(root) / file
                    rel_to_mod = source_file.relative_to(mod_source)
                    target_file = game_dir / rel_to_mod
                    target_file.parent.mkdir(parents=True, exist_ok=True)

                    if target_file.exists():
                        backup_target = backup_origin_root / rel_to_mod
                        backup_target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(target_file, backup_target)
                        replaced_index.append(rel_to_mod.as_posix())
                        try:
                            backup_hashes[rel_to_mod.as_posix()] = compute_sha256(
                                backup_target
                            )
                        except Exception:
                            backup_hashes[rel_to_mod.as_posix()] = ""

                    shutil.copy2(source_file, target_file)

                    progress_count += 1
                    self.update_progress(
                        progress_bar,
                        progress_label,
                        progress_count,
                        f"Applied {progress_count}/{len(file_index)} files",
                    )

            mod_info["enabled"] = True
            mod_info["backed_up_files_index"] = replaced_index
            mod_info["backup_hashes"] = backup_hashes
            self.save_settings()
            self.log_action(
                "enable_mod",
                {"mod_id": mod_id, "name": mod_info.get("name"), "files": len(file_index)},
            )

            if not silent:
                messagebox.showinfo(
                    "Mod Enabled",
                    f"Mod successfully compiled inside game folders:\n{mod_info['name']}",
                )
            self.refresh_mods_list()
            self.show_mod_details(mod_id, mod_info)
            return True

        except Exception as e:
            if not silent:
                messagebox.showerror("Execution Error", f"Failed applying mods: {e}")
            return False
        finally:
            self.finish_progress(progress_window)

    def disable_mod(self, mod_id: str, silent: bool = False, purge_backups: bool = False):
        """Removes enabled mod files from the game folder and restores backed up original files."""
        mod_info = self.settings_data["mods"].get(mod_id)
        if not mod_info:
            return False

        game_dir = Path(self.settings_data["game_path"])
        mod_source = self.mods_store_dir / mod_id
        backup_origin_root = self.originals_backup_dir / mod_id / "originals"
        file_index = self.ensure_mod_file_index(mod_id, mod_info)
        progress_window, progress_bar, progress_label = self.start_progress(
            "Disabling Mod", len(file_index)
        )

        try:
            progress_count = 0
            for root, _, files in os.walk(mod_source):
                for file in files:
                    if file == "manifest.json":
                        continue

                    source_file = Path(root) / file
                    rel_to_mod = source_file.relative_to(mod_source)
                    target_file = game_dir / rel_to_mod

                    backup_file = backup_origin_root / rel_to_mod
                    if backup_file.exists():
                        shutil.copy2(backup_file, target_file)
                    else:
                        if target_file.exists():
                            target_file.unlink()

                    progress_count += 1
                    self.update_progress(
                        progress_bar,
                        progress_label,
                        progress_count,
                        f"Reverted {progress_count}/{len(file_index)} files",
                    )

            clean_empty_directories(game_dir)

            if purge_backups and backup_origin_root.parent.exists():
                shutil.rmtree(backup_origin_root.parent)
                mod_info["backed_up_files_index"] = []
                mod_info["backup_hashes"] = {}

            mod_info["enabled"] = False
            self.save_settings()
            self.log_action(
                "disable_mod",
                {"mod_id": mod_id, "name": mod_info.get("name"), "files": len(file_index)},
            )

            if not silent:
                messagebox.showinfo(
                    "Mod Rollback",
                    "Mod successfully uninstalled and original game files restored:\n"
                    f"{mod_info['name']}",
                )
            self.refresh_mods_list()
            self.show_mod_details(mod_id, mod_info)
            return True

        except Exception as e:
            if not silent:
                messagebox.showerror("Rollback Error", f"Failed disabling mod safely: {e}")
            return False
        finally:
            self.finish_progress(progress_window)

    def delete_mod_from_system(self, mod_id: str, prompt: bool = True):
        """Fully purges configured mods. Automatically disables active instances first."""
        mod_info = self.settings_data["mods"].get(mod_id)
        if not mod_info:
            return

        if prompt:
            confirm = messagebox.askyesno(
                "Confirm Delete",
                f"Are you sure you want to delete and purge '{mod_info['name']}'?\n"
                "This action is permanent.",
            )
            if not confirm:
                return

        # Disable mod first if it is active
        if mod_info.get("enabled", False):
            self.disable_mod(mod_id, silent=True, purge_backups=True)

        try:
            # Remove stored copies
            local_store = self.mods_store_dir / mod_id
            if local_store.exists():
                shutil.rmtree(local_store)

            backup_root = self.originals_backup_dir / mod_id
            if backup_root.exists():
                shutil.rmtree(backup_root)

            # Remove record entries from settings.json
            del self.settings_data["mods"][mod_id]
            self.save_settings()
            self.log_action(
                "delete_mod",
                {"mod_id": mod_id, "name": mod_info.get("name")},
            )

            if prompt:
                messagebox.showinfo("Purged", "Mod successfully deleted.")
            self.refresh_mods_list()
            self.show_no_selection_details()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to complete purge: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = ModManagerGUI(root)
    root.mainloop()
