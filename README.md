# 🏎️ Forza Horizon 6 Mod Manager (FH6MM)

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-ff007f.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-white.svg)](https://opensource.org/licenses/MIT)
[![Platform support](https://img.shields.io/badge/platform-Windows%20|%20Linux-blue.svg)]()

An elegant, lightweight, and non-destructive desktop application to install, manage, and toggle modifications for **Forza Horizon 6**. 

FH6MM establishes a **secure cryptographic-like baseline registry** of your unmodded clean game install immediately. When you toggle modifications, the manager keeps a safety net: backing up original game file structures dynamically before overwrite, and automatically surgical-cleaning mod footprints when disabled.

---

## ✨ Features

- **🚀 First-Launch Baseline Isolation:** Detects fresh setups. Prompts for your unmodded root folder and structures a dynamic mapping layout.
- **📦 Universal Manifest Integration:** Parses standardized, developer-friendly `manifest.json` files visually directly on the GUI.
- **💾 Smart Backup & Overwrite Engine:** If a mod changes `/media/sound/radio.pck` or a simple `test.txt`, FH6MM clones the original to `/fh6mm/replacedmainfiles/<mod>/originals/` dynamically before applying modifications.
- **🔄 Zero-Trace Disable & Cleanup:** Toggling a mod off automatically deletes mod-only additions, restores original game files, and runs directory sweeps to remove empty folders.
- **⚔️ Conflict Detection & Priority:** Detects overlapping files between mods, shows priority, and blocks unsafe activations.
- **🧩 Profiles:** Save and apply mod sets (Offline, Visual, Performance, etc.) with one click.
- **🧷 Dependencies & Compatibility:** Supports dependencies, incompatibilities, and minimum game version checks.
- **🛠️ Integrity & Repair Mode:** Hash-based integrity verification with automatic repair using backups.
- **🧾 Audit Logs:** Full history of import/enable/rollback/delete actions with export support.
- **🌐 Mod Catalog & Updates:** Remote catalog search, checksum validation, and update flow for installed mods.
- **📊 UX Improvements:** Real activation progress bar and file replacement previews before applying.

---

## 📜 Manifest Extensions

Optional fields supported in `manifest.json`:

- `id` or `mod_id` (stable identifier)
- `dependencies` (list or comma-separated string)
- `incompatibilities` (list or comma-separated string)
- `min_game_version` (minimum game version required)

## 📂 System Storage Architecture

The manager uses a central working directory to store logs, settings, baseline CSV mappings, and backups:

* **Windows:** `C:\fh6mm\` (or your primary OS drive)
* **Linux/macOS:** `/fh6mm/`

### File Directory Breakdown:
```text
/fh6mm/
│
├── settings.json                       <-- Global parameters & mod registry tracking
├── logs/
│   └── actions.log                      <-- Audit log history
├── backups/
│   └── clean_manifest.csv              <-- Master list of unmodded baseline files
├── catalog_cache.json                  <-- Cached remote catalog
│
├── mods/                               <-- Isolated managed directory copies of imported mods
│   └── <mod_id>/
│       ├── manifest.json
│       └── [mod files...]
│
└── replacedmainfiles/
    └── <mod_id>/
        └── originals/                  <-- Dynamic backups of original overwritten game files
```

## 📦 Packaging (Windows)

Build a standalone executable with PyInstaller:

```powershell
.\build_windows.ps1
```

Create an installer with Inno Setup:

```text
installer.iss
```

## ⚠️ LEGAL DISCLAIMER & TERMS OF USE

**BY DOWNLOADING, RUNNING, OR USING THIS SOFTWARE (FORZA HORIZON 6 MOD MANAGER / FH6MM), YOU AGREE TO THE FOLLOWING TERMS. IF YOU DO NOT AGREE, DELETE THIS SOFTWARE IMMEDIATELY.**

### 1. No Affiliation or Corporate Endorsement
This software is an unofficial, community-developed, open-source utility. It is **NOT** affiliated with, authorized, maintained, sponsored, or endorsed by:
* **Microsoft Corporation**
* **Playground Games**
* **Turn 10 Studios**
* **Xbox Game Studios**
* Or any of their parent companies, subsidiaries, or affiliates. 

All product names, logos, brands, trademarks, and registered trademarks (including "Forza Horizon", "Forza Horizon 6", "Playground Games", and associated media) are properties of their respective owners. Their use in this project does not imply endorsement or ownership.

### 2. Risk of Account Suspension & Multi-Player Bans
Modifying game files of any title published by Xbox Game Studios is a direct violation of the **Microsoft Services Agreement**, **Xbox Game Studios Terms of Use**, and the **Forza Code of Conduct**. 
* Using this software to apply modifications may result in anti-cheat detection systems flagging your game instance.
* This can lead to punitive actions, including but not limited to: **permanent account bans, suspension of multiplayer match access, deletion of leaderboard rankings, console hardware bans, or Steam/Xbox profile restrictions.**
* **The developer of this software takes ZERO responsibility** for any actions taken against your accounts, hardware, or profiles by Microsoft, Playground Games, Valve (Steam), or Xbox Live. **YOU MOD AT YOUR OWN RISK.**

### 3. "AS-IS" Warranty & Software Disclaimer
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NONINFRINGEMENT. 

IN NO EVENT SHALL THE AUTHORS, DEVELOPERS, OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT, OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

### 4. Technical and Data Risks
While this tool includes automatic backup scripts, file operations carry inherent risks. The developer is **not liable** for:
* Loss of game progress, corrupted save files, or corrupted game installations.
* System operating failures, hardware damage, or blue screens (BSODs) resulting from file read/write permissions issues.
* The content, stability, or potential malware hidden inside external third-party mods you choose to import using this tool.

### 5. Indemnification
By using this software, you agree to defend, indemnify, and hold harmless the developer(s) of this project from and against any and all claims, damages, obligations, losses, liabilities, costs, debts, and expenses (including but not limited to attorney's fees) arising from your use of the software, your violation of these terms, or your violation of any third-party rights (such as Microsoft's EULA).
