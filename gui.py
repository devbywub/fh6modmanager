import json
import os
import shutil
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# Import backend methods
from tools.tool import (
    clean_empty_directories,
    export_directory_to_csv,
    load_manifest,
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
            ]:
                directory.mkdir(parents=True, exist_ok=True)

            if not self.settings_file.exists():
                self.first_run = True
                self.settings_data = {
                    "a": "omni",
                    "game_path": "",
                    "clean_manifest_generated": False,
                    "date_registered": "",
                    "mods": {},  # Maps sanitized name -> data registry states
                }
                self.save_settings()
            else:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    self.settings_data = json.load(f)

                # Ensure required configuration structure is present
                if "a" not in self.settings_data:
                    self.settings_data["a"] = "omni"
                if "mods" not in self.settings_data:
                    self.settings_data["mods"] = {}
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

        # Split Pane: Left Tree List, Right Details Layout
        panes = tk.PanedWindow(
            self.work_space, orient="horizontal", bg="#131419", sashwidth=4
        )
        panes.pack(fill="both", expand=True)

        # Left list module
        left_frame = ttk.LabelFrame(panes, text=" Configured Mods ")
        self.mod_tree = ttk.Treeview(
            left_frame, columns=("state", "name", "version"), show="headings"
        )
        self.mod_tree.heading("state", text="Status")
        self.mod_tree.heading("name", text="Mod Title")
        self.mod_tree.heading("version", text="Version")

        self.mod_tree.column("state", width=80, anchor="center")
        self.mod_tree.column("name", width=200, anchor="w")
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
        for mod_id, data in stored_mods.items():
            status = "🟢 Enabled" if data.get("enabled", False) else "🔴 Disabled"
            name = data.get("name", "Unknown Mod")
            version = data.get("version", "1.0.0")
            self.mod_tree.insert("", "end", iid=mod_id, values=(status, name, version))

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

    # --- ACTION MANAGEMENT ENGINE ---

    def import_mod_directory(self):
        """Imports an extracted mod folder to `/fh6mm/mods/` after validation."""
        selected_dir = filedialog.askdirectory(
            title="Import Extracted Mod (Contains manifest.json)"
        )
        if not selected_dir:
            return

        selected_path = Path(selected_dir)

        try:
            # Parse external JSON schema structure validation
            manifest_info = load_manifest(selected_path)
            mod_title = manifest_info["name"]
            mod_id = sanitize_filename(f"{mod_title}_{manifest_info['version']}")

            # Prevent clashes inside management registry
            if mod_id in self.settings_data["mods"]:
                messagebox.showerror(
                    "Conflict", "This mod version has already been imported."
                )
                return

            # Prepare to copy to management cache directory
            mod_dest_dir = self.mods_store_dir / mod_id
            if mod_dest_dir.exists():
                shutil.rmtree(mod_dest_dir)

            # Copy all files from the extracted mod folder
            shutil.copytree(selected_path, mod_dest_dir)

            # Register database variables inside settings.json
            self.settings_data["mods"][mod_id] = {
                "name": mod_title,
                "version": manifest_info["version"],
                "author": manifest_info["author"],
                "description": manifest_info["description"],
                "enabled": False,
                "backed_up_files_index": [],  # Track list of original game files replaced
            }
            self.save_settings()

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

    def enable_mod(self, mod_id: str):
        """Copies mod files into the target directories and backs up overwritten files."""
        mod_info = self.settings_data["mods"].get(mod_id)
        if not mod_info:
            return

        game_dir = Path(self.settings_data["game_path"])
        mod_source = self.mods_store_dir / mod_id
        backup_origin_root = self.originals_backup_dir / mod_id / "originals"

        backup_origin_root.mkdir(parents=True, exist_ok=True)
        replaced_index = []

        try:
            # Traverse and deploy mod files (skip manifest.json)
            for root, _, files in os.walk(mod_source):
                for file in files:
                    if file == "manifest.json":
                        continue

                    source_file = Path(root) / file
                    # Relative directory calculation
                    rel_to_mod = source_file.relative_to(mod_source)
                    target_file = game_dir / rel_to_mod

                    # Setup folder paths automatically
                    target_file.parent.mkdir(parents=True, exist_ok=True)

                    # Manage File Overwrites (Backup Original)
                    if target_file.exists():
                        backup_target = backup_origin_root / rel_to_mod
                        backup_target.parent.mkdir(parents=True, exist_ok=True)

                        # Copy original file to safe backup location
                        shutil.copy2(target_file, backup_target)
                        replaced_index.append(rel_to_mod.as_posix())

                    # Deploy Mod file
                    shutil.copy2(source_file, target_file)

            # Update Registry Values
            mod_info["enabled"] = True
            mod_info["backed_up_files_index"] = replaced_index
            self.save_settings()

            messagebox.showinfo(
                "Mod Enabled",
                f"Mod successfully compiled inside game folders:\n{mod_info['name']}",
            )
            self.refresh_mods_list()
            self.show_mod_details(mod_id, mod_info)

        except Exception as e:
            messagebox.showerror("Execution Error", f"Failed applying mods: {e}")

    def disable_mod(self, mod_id: str):
        """Removes enabled mod files from the game folder and restores backed up original files."""
        mod_info = self.settings_data["mods"].get(mod_id)
        if not mod_info:
            return

        game_dir = Path(self.settings_data["game_path"])
        mod_source = self.mods_store_dir / mod_id
        backup_origin_root = self.originals_backup_dir / mod_id / "originals"

        try:
            # Traverse mod structure to target files for cleanup
            for root, _, files in os.walk(mod_source):
                for file in files:
                    if file == "manifest.json":
                        continue

                    source_file = Path(root) / file
                    rel_to_mod = source_file.relative_to(mod_source)
                    target_file = game_dir / rel_to_mod

                    # If this file replaced an original, restore the original
                    backup_file = backup_origin_root / rel_to_mod
                    if backup_file.exists():
                        shutil.copy2(backup_file, target_file)
                    else:
                        # If it did not replace an original, simply delete the mod file
                        if target_file.exists():
                            target_file.unlink()

            # Clean up empty folders left in game directories
            clean_empty_directories(game_dir)

            # Clean cache directory backups
            if backup_origin_root.parent.exists():
                shutil.rmtree(backup_origin_root.parent)

            # Record state
            mod_info["enabled"] = False
            mod_info["backed_up_files_index"] = []
            self.save_settings()

            messagebox.showinfo(
                "Mod Rollback",
                f"Mod successfully uninstalled and original game files restored:\n{mod_info['name']}",
            )
            self.refresh_mods_list()
            self.show_mod_details(mod_id, mod_info)

        except Exception as e:
            messagebox.showerror("Rollback Error", f"Failed disabling mod safely: {e}")

    def delete_mod_from_system(self, mod_id: str):
        """Fully purges configured mods. Automatically disables active instances first."""
        mod_info = self.settings_data["mods"].get(mod_id)
        if not mod_info:
            return

        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete and purge '{mod_info['name']}'?\n"
            "This action is permanent.",
        )
        if not confirm:
            return

        # Disable mod first if it is active
        if mod_info.get("enabled", False):
            self.disable_mod(mod_id)

        try:
            # Remove stored copies
            local_store = self.mods_store_dir / mod_id
            if local_store.exists():
                shutil.rmtree(local_store)

            # Remove record entries from settings.json
            del self.settings_data["mods"][mod_id]
            self.save_settings()

            messagebox.showinfo("Purged", "Mod successfully deleted.")
            self.refresh_mods_list()
            self.show_no_selection_details()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to complete purge: {e}")


if __name__ == "__main__":
    root = tk.Tk()
    app = ModManagerGUI(root)
    root.mainloop()
