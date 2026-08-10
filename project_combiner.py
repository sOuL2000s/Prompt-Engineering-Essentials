import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import os
import sys
import threading
import json
from pathlib import Path
import re
import hashlib
from datetime import datetime
import tempfile

try:
    import pathspec
except ImportError:
    pathspec = None

# =============================================================================
# CORE LOGIC
# =============================================================================

def generate_directory_tree(root_dir, excluded_dirs, excluded_files,
                            included_dirs, included_files, gitignore_spec=None):
    """Generates a visual text-based directory tree of the project."""
    use_include_mode = bool(included_dirs or included_files)
    excluded_dirs_set = set(excluded_dirs)
    excluded_files_set = set(f.strip() for f in excluded_files)
    included_dirs_set = set(included_dirs)
    included_files_set = set(f.strip() for f in included_files)

    tree_lines = [f"{os.path.basename(root_dir)}/"]

    def _walk_tree(current_dir, prefix=""):
        try:
            items = sorted(os.listdir(current_dir))
        except PermissionError:
            return

        valid_items = []
        for item in items:
            item_path = os.path.join(current_dir, item)
            rel_path = os.path.relpath(item_path, root_dir)
            abs_path = os.path.abspath(item_path)

            if os.path.islink(item_path):
                continue

            if os.path.isdir(item_path):
                if gitignore_spec and gitignore_spec.match_file(os.path.normpath(rel_path)):
                    continue
                if item in excluded_dirs_set:
                    continue
                if use_include_mode and included_dirs_set:
                    segments = rel_path.split(os.sep)
                    if not any(seg in included_dirs_set for seg in segments):
                        continue
                valid_items.append((item, True))
            else:
                if item in excluded_files_set or abs_path in excluded_files_set:
                    continue
                if gitignore_spec and gitignore_spec.match_file(os.path.normpath(rel_path)):
                    continue
                if use_include_mode:
                    if included_files_set:
                        if not (item in included_files_set or abs_path in included_files_set):
                            continue
                    elif included_dirs_set:
                        segments = rel_path.split(os.sep)
                        if not any(seg in included_dirs_set for seg in segments[:-1]):
                            continue
                valid_items.append((item, False))

        for i, (name, is_dir) in enumerate(valid_items):
            is_last = (i == len(valid_items) - 1)
            connector = "└── " if is_last else "├── "
            tree_lines.append(f"{prefix}{connector}{name}{'/' if is_dir else ''}")
            if is_dir:
                new_prefix = prefix + ("    " if is_last else "│   ")
                _walk_tree(os.path.join(current_dir, name), new_prefix)

    _walk_tree(root_dir)
    return "\n".join(tree_lines)

def get_file_stats(file_path):
    """Get file statistics: size, modified time, line count."""
    try:
        stat = os.stat(file_path)
        size = stat.st_size
        modified = datetime.fromtimestamp(stat.st_mtime)
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = sum(1 for _ in f)
        return size, modified, lines
    except Exception:
        return 0, datetime.now(), 0

def combine_files_to_single_file_gui(root_dir, output_full_path,
                                     excluded_dirs_list, excluded_files_list,
                                     included_dirs_list, included_files_list,
                                     status_callback, gitignore_spec=None,
                                     manual_selection_map=None, max_file_size=None,
                                     include_file_stats=False, sort_files=True):
    """
    Combines the content of all files in a directory into a single file.
    Enhanced with file stats, size limits, sorting, and duplicate detection.
    """
    combined_content = []
    processed_files = []
    duplicates = []
    file_hashes = {}
    total_size = 0

    status_callback(f"🚀 Starting file combination from: {root_dir}")

    use_include_mode = bool(included_dirs_list or included_files_list)

    if use_include_mode:
        status_callback(f"📋 Running in INCLUDE MODE (Exclusions still apply).")
        if included_dirs_list:
            status_callback(f"📁 Including directories: {', '.join(included_dirs_list)}")
        if included_files_list:
            status_callback(f"📄 Including files: {', '.join(included_files_list)}")
    else:
        status_callback(f"🚫 Running in EXCLUDE MODE.")

    if max_file_size:
        status_callback(f"📏 Max file size: {max_file_size} bytes")

    status_callback(f"🗑️ Excluding directories: {', '.join(excluded_dirs_list)}")
    status_callback(f"🗑️ Excluding files: {', '.join(excluded_files_list)}")

    # 0. Generate Directory Tree Header
    status_callback("🌳 Generating project directory tree header...")
    tree_header = generate_directory_tree(
        root_dir, excluded_dirs_list, excluded_files_list,
        included_dirs_list, included_files_list, gitignore_spec
    )

    combined_content.append("=" * 80 + "\n")
    combined_content.append("📁 PROJECT STRUCTURE (TREE VIEW)\n")
    combined_content.append("=" * 80 + "\n\n")
    combined_content.append(tree_header)
    combined_content.append("\n\n" + "=" * 80 + "\n")
    combined_content.append("📄 FILE CONTENTS\n")
    combined_content.append("=" * 80 + "\n")
    combined_content.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    combined_content.append(f"Root: {root_dir}\n")
    combined_content.append("=" * 80 + "\n")

    # Basic validation
    if not os.path.isdir(root_dir):
        status_callback(f"❌ Error: Project root directory not found: {root_dir}")
        return False

    output_dir = os.path.dirname(output_full_path)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            status_callback(f"📁 Created output directory: {output_dir}")
        except OSError as e:
            status_callback(f"❌ Error creating output directory {output_dir}: {e}")
            return False

    excluded_dirs_set = set(excluded_dirs_list)
    excluded_files_set = set(f.strip() for f in excluded_files_list)
    included_dirs_set = set(included_dirs_list)
    included_files_set = set(f.strip() for f in included_files_list)

    try:
        for dirpath, dirnames, filenames in os.walk(root_dir):
            relative_dirpath = os.path.relpath(dirpath, root_dir)

            if gitignore_spec:
                dirnames[:] = [d for d in dirnames if not gitignore_spec.match_file(os.path.normpath(os.path.join(relative_dirpath, d)))]

            dirnames[:] = [d for d in dirnames if d not in excluded_dirs_set]

            if use_include_mode:
                should_process_this_dir_based_on_included_dirs = True
                if included_dirs_set:
                    if dirpath == root_dir:
                        should_process_this_dir_based_on_included_dirs = True
                    else:
                        relative_path_segments = relative_dirpath.split(os.sep)
                        if not any(seg in included_dirs_set for seg in relative_path_segments):
                            should_process_this_dir_based_on_included_dirs = False
                if not should_process_this_dir_based_on_included_dirs:
                    dirnames[:] = []
                    continue

            files_to_process = []
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                relative_file_path = os.path.join(relative_dirpath, filename)
                abs_file_path = os.path.abspath(file_path)

                if os.path.islink(file_path):
                    continue
                if filename in excluded_files_set or abs_file_path in excluded_files_set:
                    continue
                if gitignore_spec and gitignore_spec.match_file(os.path.normpath(relative_file_path)):
                    continue

                # Check file size limit
                if max_file_size:
                    try:
                        file_size = os.path.getsize(file_path)
                        if file_size > max_file_size:
                            status_callback(f"⏭️ Skipping large file: {relative_file_path} ({file_size} bytes)")
                            continue
                    except Exception:
                        continue

                if use_include_mode:
                    if included_files_set:
                        if filename in included_files_set or abs_file_path in included_files_set:
                            if manual_selection_map is None or manual_selection_map.get(abs_file_path, True):
                                files_to_process.append((file_path, relative_file_path, abs_file_path))
                    elif included_dirs_set:
                        if manual_selection_map is None or manual_selection_map.get(abs_file_path, True):
                            files_to_process.append((file_path, relative_file_path, abs_file_path))
                else:
                    if manual_selection_map is None or manual_selection_map.get(abs_file_path, True):
                        files_to_process.append((file_path, relative_file_path, abs_file_path))

            # Sort files if requested
            if sort_files:
                files_to_process.sort(key=lambda x: x[1])  # Sort by relative path

            for file_path, relative_file_path, abs_file_path in files_to_process:
                processed_files.append(relative_file_path)

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()

                    # Calculate file hash for duplicate detection
                    content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
                    if content_hash in file_hashes:
                        duplicates.append((relative_file_path, file_hashes[content_hash]))
                    file_hashes[content_hash] = relative_file_path

                    total_size += len(content.encode('utf-8'))

                    # File header with stats
                    combined_content.append(f"\n--- START FILE: {relative_file_path} ---\n")

                    if include_file_stats:
                        size, modified, lines = get_file_stats(file_path)
                        combined_content.append(f"# Size: {size:,} bytes | Lines: {lines} | Modified: {modified.strftime('%Y-%m-%d %H:%M:%S')}\n")

                    combined_content.append(f"\n")
                    combined_content.append(content)
                    combined_content.append(f"\n--- END FILE: {relative_file_path} ---\n")

                    status_callback(f"✅ Included: {relative_file_path}")

                except UnicodeDecodeError:
                    status_callback(f"⚠️ Skipping binary/undecodable: {relative_file_path}")
                except Exception as e:
                    status_callback(f"❌ Error reading {relative_file_path}: {e}")

        # Add summary at the end
        combined_content.append("\n" + "=" * 80 + "\n")
        combined_content.append("📊 SUMMARY\n")
        combined_content.append("=" * 80 + "\n")
        combined_content.append(f"Total files processed: {len(processed_files)}\n")
        combined_content.append(f"Total size: {total_size:,} bytes\n")

        if duplicates:
            combined_content.append("\n⚠️ DUPLICATE FILES DETECTED:\n")
            for dup_file, original in duplicates:
                combined_content.append(f"  - {dup_file} (duplicate of {original})\n")

        combined_content.append("=" * 80 + "\n")

        with open(output_full_path, 'w', encoding='utf-8') as outfile:
            outfile.write("".join(combined_content))

        status_callback(f"✅ Successfully combined {len(processed_files)} files into: {output_full_path}")
        if duplicates:
            status_callback(f"⚠️ Found {len(duplicates)} duplicate files")
        return True

    except Exception as e:
        status_callback(f"❌ Unexpected error: {e}")
        return False


# =============================================================================
# CONFIGURATION MANAGER
# =============================================================================

CONFIG_FILE = "last_session.json"

class ConfigManager:
    @staticmethod
    def load():
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    @staticmethod
    def save(config):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    @staticmethod
    def reset():
        """Delete the config file to reset to defaults."""
        if os.path.exists(CONFIG_FILE):
            try:
                os.remove(CONFIG_FILE)
                return True
            except Exception as e:
                print(f"Error resetting config: {e}")
                return False
        return True


# =============================================================================
# GUI APPLICATION
# =============================================================================

class FileCombinerApp:
    THEMES = {
        "light": {
            "bg": "#f0f2f5",
            "fg": "#1a1a2e",
            "frame_bg": "#ffffff",
            "entry_bg": "#f8f9fa",
            "button_bg": "#4a6fa5",
            "button_fg": "#ffffff",
            "accent": "#4a6fa5",
            "accent_light": "#e8edf5",
            "border": "#d1d5db",
            "secondary_fg": "#6b7280",
            "success": "#22c55e",
            "warning": "#eab308",
            "danger": "#ef4444"
        },
        "dark": {
            "bg": "#0f172a",
            "fg": "#f1f5f9",
            "frame_bg": "#1e293b",
            "entry_bg": "#0f172a",
            "button_bg": "#3b82f6",
            "button_fg": "#ffffff",
            "accent": "#60a5fa",
            "accent_light": "#1e293b",
            "border": "#334155",
            "secondary_fg": "#94a3b8",
            "success": "#22c55e",
            "warning": "#eab308",
            "danger": "#ef4444"
        }
    }

    # Default configuration values
    DEFAULT_CONFIG = {
        "root_dir": os.getcwd(),
        "output_path": os.path.join(os.getcwd(), "combined_project_files.txt"),
        "excluded_dirs": "node_modules, .git, .vscode, .idea, dist, build, venv, __pycache__, .DS_Store",
        "excluded_files": "package-lock.json, yarn.lock, bun.lockb, .DS_Store, Thumbs.db, pyproject.toml, combined_project_files.txt",
        "included_dirs": "",
        "included_files": "",
        "theme": "dark"
    }

    def __init__(self, master):
        self.master = master
        master.title("📁 Project File Combiner Pro")
        master.geometry("1200x900")
        master.minsize(1000, 700)

        self.current_theme = "dark"
        self.colors = self.THEMES[self.current_theme]

        # App state
        self.preview_files = {}
        self.is_processing = False
        self.recent_projects = []

        # Variables
        self.root_dir_var = tk.StringVar(value=os.getcwd())
        self.output_full_path_var = tk.StringVar(value=os.path.join(os.getcwd(), "combined_project_files.txt"))

        self.excluded_dirs_var = tk.StringVar(
            value="node_modules, .git, .vscode, .idea, dist, build, venv, __pycache__, .DS_Store"
        )
        self.excluded_files_var = tk.StringVar(
            value="package-lock.json, yarn.lock, bun.lockb, .DS_Store, Thumbs.db, pyproject.toml, combined_project_files.txt"
        )
        self.included_dirs_var = tk.StringVar(value="")
        self.included_files_var = tk.StringVar(value="")

        # Advanced settings
        self.max_file_size_var = tk.IntVar(value=0)  # 0 = no limit
        self.include_stats_var = tk.BooleanVar(value=True)
        self.sort_files_var = tk.BooleanVar(value=True)
        self.detect_duplicates_var = tk.BooleanVar(value=True)

        self.search_query_var = tk.StringVar(value="")

        self.setup_styles()
        self.create_widgets()
        self.load_config()

        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

        if not pathspec:
            self.update_status_message("⚠️ 'pathspec' missing. .gitignore support disabled.")
            self.update_status_message("👉 Install: pip install pathspec")

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.apply_theme_styles()

    def apply_theme_styles(self):
        c = self.colors
        self.style.configure("TFrame", background=c["bg"])
        self.style.configure("TLabel", background=c["bg"], foreground=c["fg"], font=('Segoe UI', 10))
        self.style.configure("Header.TLabel", background=c["bg"], foreground=c["accent"], font=('Segoe UI Bold', 12))
        self.style.configure("Subtitle.TLabel", background=c["bg"], foreground=c["secondary_fg"], font=('Segoe UI', 9))
        self.style.configure("TEntry", fieldbackground=c["entry_bg"], foreground=c["fg"],
                             insertcolor=c["fg"], bordercolor=c["border"])
        self.style.configure("TNotebook", background=c["bg"], borderwidth=0)
        self.style.configure("TNotebook.Tab", background=c["frame_bg"], foreground=c["fg"],
                             padding=(20, 10), font=('Segoe UI Semibold', 9))
        self.style.map("TNotebook.Tab",
                       background=[("selected", c["accent"]), ("active", c["border"])],
                       foreground=[("selected", "#ffffff"), ("active", c["fg"])])
        self.style.configure("Treeview", background=c["frame_bg"], foreground=c["fg"],
                             fieldbackground=c["frame_bg"], font=('Segoe UI', 9))
        self.style.map("Treeview", background=[('selected', c["accent"])],
                       foreground=[('selected', '#ffffff')])

    def load_config(self):
        config = ConfigManager.load()
        if config:
            self.root_dir_var.set(config.get("root_dir", self.DEFAULT_CONFIG["root_dir"]))
            self.output_full_path_var.set(config.get("output_path", self.DEFAULT_CONFIG["output_path"]))
            self.excluded_dirs_var.set(config.get("excluded_dirs", self.DEFAULT_CONFIG["excluded_dirs"]))
            self.excluded_files_var.set(config.get("excluded_files", self.DEFAULT_CONFIG["excluded_files"]))
            self.included_dirs_var.set(config.get("included_dirs", self.DEFAULT_CONFIG["included_dirs"]))
            self.included_files_var.set(config.get("included_files", self.DEFAULT_CONFIG["included_files"]))
            self.recent_projects = config.get("recent_projects", [])

            saved_theme = config.get("theme", "dark")
            if saved_theme != self.current_theme:
                self.current_theme = saved_theme
                self.colors = self.THEMES[self.current_theme]
                self.apply_theme_styles()
                self.refresh_ui_colors()

            self.update_status_message("✅ Configuration loaded from previous session.")
        else:
            self.reset_to_defaults()
            self.update_status_message("✅ Using default configuration.")

    def save_config(self):
        config = {
            "root_dir": self.root_dir_var.get(),
            "output_path": self.output_full_path_var.get(),
            "excluded_dirs": self.excluded_dirs_var.get(),
            "excluded_files": self.excluded_files_var.get(),
            "included_dirs": self.included_dirs_var.get(),
            "included_files": self.included_files_var.get(),
            "theme": self.current_theme,
            "recent_projects": self.recent_projects[-5:] if self.recent_projects else []
        }
        ConfigManager.save(config)

    def reset_to_defaults(self):
        """Reset all settings to default values."""
        self.root_dir_var.set(self.DEFAULT_CONFIG["root_dir"])
        self.output_full_path_var.set(self.DEFAULT_CONFIG["output_path"])
        self.excluded_dirs_var.set(self.DEFAULT_CONFIG["excluded_dirs"])
        self.excluded_files_var.set(self.DEFAULT_CONFIG["excluded_files"])
        self.included_dirs_var.set(self.DEFAULT_CONFIG["included_dirs"])
        self.included_files_var.set(self.DEFAULT_CONFIG["included_files"])
        self.max_file_size_var.set(0)
        self.include_stats_var.set(True)
        self.sort_files_var.set(True)
        self.detect_duplicates_var.set(True)
        self.search_query_var.set("")
        self.preview_files = {}
        self.recent_projects = []

        # Clear tree view
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Clear search results
        self.search_results_listbox.delete(0, tk.END)

        # Delete config file
        ConfigManager.reset()

        self.update_status_message("🔄 Configuration reset to defaults!")

    def confirm_reset(self):
        """Show confirmation dialog before resetting."""
        result = messagebox.askyesno(
            "Reset Configuration",
            "⚠️ This will delete all saved settings and reset to defaults.\n\n"
            "This includes:\n"
            "• Project root path\n"
            "• Output file path\n"
            "• All exclusion/inclusion rules\n"
            "• Advanced settings\n\n"
            "Are you sure you want to continue?",
            icon=messagebox.WARNING
        )
        if result:
            self.reset_to_defaults()
            messagebox.showinfo("Reset Complete", "✅ All settings have been reset to default values.")

    def on_closing(self):
        self.save_config()
        self.master.destroy()

    def update_status_message(self, message):
        self.master.after(0, lambda: self._safe_update_log(message))

    def _safe_update_log(self, message):
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)

    def toggle_theme(self):
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.colors = self.THEMES[self.current_theme]
        self.master.configure(bg=self.colors["bg"])
        self.apply_theme_styles()
        self.refresh_ui_colors()

    def refresh_ui_colors(self):
        c = self.colors
        self.main_container.configure(bg=c["bg"])
        self.header_frame.configure(bg=c["bg"])
        self.title_container.configure(bg=c["bg"])
        self.footer_outer.configure(bg=c["bg"])
        self.log_frame.configure(bg=c["bg"])
        self.config_card.configure(bg=c["frame_bg"])
        self.notebook.configure(bg=c["bg"])
        self.status_text.configure(bg=c["frame_bg"], fg=c["fg"])
        self.combine_button.configure(bg=c["button_bg"], fg=c["button_fg"],
                                       activebackground=c["accent"])
        self.theme_btn.configure(text="🌙 Dark" if self.current_theme == "light" else "☀️ Light",
                                  bg=c["frame_bg"], fg=c["fg"])
        self.reset_btn.configure(bg=c["danger"], fg="#ffffff",
                                  activebackground=c["danger"])

    def create_widgets(self):
        c = self.colors
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(1, weight=1)

        # Header
        self.header_frame = tk.Frame(self.master, bg=c["bg"], padx=30, pady=15)
        self.header_frame.grid(row=0, column=0, sticky="ew")

        self.title_container = tk.Frame(self.header_frame, bg=c["bg"])
        self.title_container.pack(side=tk.LEFT)

        title_lbl = tk.Label(self.title_container, text="📁 Project Combiner Pro",
                             font=('Segoe UI Bold', 24), bg=c["bg"], fg=c["accent"])
        title_lbl.pack(anchor=tk.W)

        subtitle_lbl = tk.Label(self.title_container, text="Consolidate your entire codebase into a single, searchable document",
                                font=('Segoe UI', 10), bg=c["bg"], fg=c["secondary_fg"])
        subtitle_lbl.pack(anchor=tk.W)

        btn_frame = tk.Frame(self.header_frame, bg=c["bg"])
        btn_frame.pack(side=tk.RIGHT)

        # Reset Button (RED)
        self.reset_btn = tk.Button(btn_frame, text="🔄 Reset to Default", 
                                    command=self.confirm_reset,
                                    relief=tk.FLAT, cursor="hand2", 
                                    font=('Segoe UI', 9, 'bold'),
                                    bg=c["danger"], fg="#ffffff",
                                    activebackground=c["danger"],
                                    padx=15, pady=5)
        self.reset_btn.pack(side=tk.LEFT, padx=5)

        self.theme_btn = tk.Button(btn_frame, text="🌙 Dark", command=self.toggle_theme,
                                    relief=tk.FLAT, cursor="hand2", font=('Segoe UI', 9),
                                    bg=c["frame_bg"], fg=c["fg"], padx=15, pady=5)
        self.theme_btn.pack(side=tk.LEFT, padx=5)

        # Main content with scroll
        self.canvas = tk.Canvas(self.master, bg=c["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.master, orient="vertical", command=self.canvas.yview)
        self.main_container = tk.Frame(self.canvas, bg=c["bg"], padx=30, pady=20)

        self.canvas_frame_id = self.canvas.create_window((0, 0), window=self.main_container, anchor="nw")
        self.main_container.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_frame_id, width=e.width))
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")

        # Configuration Card
        self.config_card = tk.Frame(self.main_container, bg=c["frame_bg"], padx=25, pady=20, relief=tk.FLAT)
        self.config_card.pack(fill=tk.X, pady=(0, 20))
        self.config_card.columnconfigure(1, weight=1)

        header_lbl = ttk.Label(self.config_card, text="⚙️ CONFIGURATION", style="Header.TLabel")
        header_lbl.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 15))

        # Project Root
        ttk.Label(self.config_card, text="Project Root:").grid(row=1, column=0, sticky=tk.W, pady=5)
        root_entry = ttk.Entry(self.config_card, textvariable=self.root_dir_var)
        root_entry.grid(row=1, column=1, pady=5, padx=15, sticky=tk.EW)
        ttk.Button(self.config_card, text="Browse", command=self.browse_root_dir).grid(row=1, column=2, pady=5)

        # Output Path
        ttk.Label(self.config_card, text="Output File:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(self.config_card, textvariable=self.output_full_path_var).grid(row=2, column=1, pady=5, padx=15, sticky=tk.EW)
        ttk.Button(self.config_card, text="Browse", command=self.browse_output_file).grid(row=2, column=2, pady=5)

        # Notebook (Tabs)
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill=tk.X, pady=(0, 20))

        # Tab 1: Filters
        filter_tab = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(filter_tab, text="🔍 Filters & Rules")
        filter_tab.columnconfigure(1, weight=1)

        ttk.Label(filter_tab, text="EXCLUSIONS", style="Header.TLabel").grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        ttk.Label(filter_tab, text="Directories:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(filter_tab, textvariable=self.excluded_dirs_var).grid(row=1, column=1, pady=5, padx=10, sticky=tk.EW)
        ttk.Button(filter_tab, text="+ Dir", command=self.browse_excluded_dirs).grid(row=1, column=2, pady=5)

        ttk.Label(filter_tab, text="Files:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(filter_tab, textvariable=self.excluded_files_var).grid(row=2, column=1, pady=5, padx=10, sticky=tk.EW)
        ttk.Button(filter_tab, text="+ File", command=self.browse_excluded_files).grid(row=2, column=2, pady=5)

        ttk.Separator(filter_tab, orient='horizontal').grid(row=3, column=0, columnspan=3, sticky="ew", pady=15)

        ttk.Label(filter_tab, text="INCLUSIONS", style="Header.TLabel").grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        ttk.Label(filter_tab, text="Directories:").grid(row=5, column=0, sticky=tk.W, pady=5)
        ttk.Entry(filter_tab, textvariable=self.included_dirs_var).grid(row=5, column=1, pady=5, padx=10, sticky=tk.EW)
        ttk.Button(filter_tab, text="+ Dir", command=self.browse_included_dirs).grid(row=5, column=2, pady=5)

        ttk.Label(filter_tab, text="Files:").grid(row=6, column=0, sticky=tk.W, pady=5)
        ttk.Entry(filter_tab, textvariable=self.included_files_var).grid(row=6, column=1, pady=5, padx=10, sticky=tk.EW)
        ttk.Button(filter_tab, text="+ File", command=self.browse_included_files).grid(row=6, column=2, pady=5)

        # Tab 2: Advanced Settings
        advanced_tab = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(advanced_tab, text="⚡ Advanced")
        advanced_tab.columnconfigure(1, weight=1)

        ttk.Label(advanced_tab, text="FILE PROCESSING OPTIONS", style="Header.TLabel").grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 15))

        ttk.Label(advanced_tab, text="Max File Size (bytes, 0=no limit):").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(advanced_tab, textvariable=self.max_file_size_var, width=15).grid(row=1, column=1, sticky=tk.W, pady=5, padx=10)

        ttk.Label(advanced_tab, text="Include file statistics:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Checkbutton(advanced_tab, variable=self.include_stats_var).grid(row=2, column=1, sticky=tk.W, pady=5, padx=10)

        ttk.Label(advanced_tab, text="Sort files alphabetically:").grid(row=3, column=0, sticky=tk.W, pady=5)
        ttk.Checkbutton(advanced_tab, variable=self.sort_files_var).grid(row=3, column=1, sticky=tk.W, pady=5, padx=10)

        ttk.Label(advanced_tab, text="Detect duplicate files:").grid(row=4, column=0, sticky=tk.W, pady=5)
        ttk.Checkbutton(advanced_tab, variable=self.detect_duplicates_var).grid(row=4, column=1, sticky=tk.W, pady=5, padx=10)

        # Tab 3: Search
        search_tab = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(search_tab, text="🔎 Smart Search")
        search_tab.columnconfigure(1, weight=1)
        search_tab.rowconfigure(2, weight=1)

        ttk.Label(search_tab, text="Search for files containing:").grid(row=0, column=0, sticky=tk.W)
        self.search_entry = ttk.Entry(search_tab, textvariable=self.search_query_var)
        self.search_entry.grid(row=0, column=1, padx=15, sticky=tk.EW)
        self.search_entry.bind('<Return>', lambda e: self.perform_search())
        ttk.Button(search_tab, text="🔍 Search", command=self.perform_search).grid(row=0, column=2)

        self.result_container = tk.Frame(search_tab, bg=c["frame_bg"], bd=1)
        self.result_container.grid(row=1, column=0, columnspan=3, sticky=tk.NSEW, pady=15)

        self.search_results_listbox = tk.Listbox(self.result_container, selectmode=tk.MULTIPLE,
                                                  font=('Consolas', 10), bd=0, highlightthickness=0,
                                                  bg=c["frame_bg"], fg=c["fg"], selectbackground=c["accent"])
        self.search_results_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sl = ttk.Scrollbar(self.result_container, orient=tk.VERTICAL, command=self.search_results_listbox.yview)
        sl.pack(side=tk.RIGHT, fill=tk.Y)
        self.search_results_listbox.config(yscrollcommand=sl.set)

        ttk.Button(search_tab, text="➕ Add Selected to Inclusion List",
                   command=self.add_search_results_to_included).grid(row=2, column=0, columnspan=3, sticky=tk.E)

        # Tab 4: File Preview
        preview_tab = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(preview_tab, text="📋 File Checklist")
        preview_tab.columnconfigure(0, weight=1)
        preview_tab.rowconfigure(1, weight=1)

        preview_header = tk.Frame(preview_tab, bg=c["bg"])
        preview_header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(preview_header, text="Select specific files to include:").pack(side=tk.LEFT)
        ttk.Button(preview_header, text="🔄 Scan Project", command=self.perform_scan).pack(side=tk.RIGHT)

        tree_container = tk.Frame(preview_tab, bg=c["frame_bg"], bd=1)
        tree_container.grid(row=1, column=0, sticky="nsew")

        self.tree = ttk.Treeview(tree_container, columns=("Include", "Path", "Size"), show="headings")
        self.tree.heading("Include", text="✓")
        self.tree.heading("Path", text="File Path")
        self.tree.heading("Size", text="Size")
        self.tree.column("Include", width=50, stretch=False, anchor="center")
        self.tree.column("Path", width=500, stretch=True)
        self.tree.column("Size", width=100, stretch=False)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ts = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        ts.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=ts.set)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)

        # Footer
        self.footer_outer = tk.Frame(self.master, bg=c["bg"], padx=30, pady=20)
        self.footer_outer.grid(row=2, column=0, sticky="ew")

        button_row = tk.Frame(self.footer_outer, bg=c["bg"])
        button_row.pack(fill=tk.X, pady=(0, 15))

        self.combine_button = tk.Button(button_row, text="🚀 START MERGING", command=self.start_combination,
                                         font=('Segoe UI Bold', 13), bg=c["button_bg"], fg=c["button_fg"],
                                         activebackground=c["accent"], relief=tk.FLAT, cursor="hand2",
                                         padx=30, pady=15)
        self.combine_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        self.copy_button = tk.Button(button_row, text="📋 Copy to Clipboard", command=self.copy_to_clipboard,
                                      font=('Segoe UI', 10), bg=c["frame_bg"], fg=c["fg"],
                                      relief=tk.FLAT, cursor="hand2", padx=20, state=tk.DISABLED)
        self.copy_button.pack(side=tk.RIGHT)

        # Log
        self.log_frame = tk.Frame(self.footer_outer, bg=c["bg"])
        self.log_frame.pack(fill=tk.X)
        log_lbl = ttk.Label(self.log_frame, text="📋 Activity Log", style="Header.TLabel")
        log_lbl.pack(anchor=tk.W, pady=(0, 5))

        self.status_text = scrolledtext.ScrolledText(self.footer_outer, wrap=tk.WORD, height=8,
                                                      font=('Consolas', 9), bg=c["frame_bg"], fg=c["fg"],
                                                      relief=tk.FLAT, bd=1)
        self.status_text.pack(fill=tk.X)
        self.status_text.config(state=tk.DISABLED)

        # Mousewheel
        self.master.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        if event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")

    # --- Browse Methods ---
    def browse_root_dir(self):
        directory = filedialog.askdirectory(
            initialdir=self.root_dir_var.get() if os.path.isdir(self.root_dir_var.get()) else os.getcwd(),
            title="Select Project Root Directory"
        )
        if directory:
            self.root_dir_var.set(directory)
            new_output = os.path.join(directory, "combined_project_files.txt")
            self.output_full_path_var.set(new_output)
            self.update_status_message(f"📁 Project root set to: {directory}")

    def browse_output_file(self):
        current = self.output_full_path_var.get()
        default = os.path.basename(current)
        initialdir = os.path.dirname(current) or os.getcwd()
        file_path = filedialog.asksaveasfilename(
            initialdir=initialdir,
            initialfile=default,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Save Combined File As"
        )
        if file_path:
            self.output_full_path_var.set(file_path)

    def browse_excluded_dirs(self):
        root_dir = self.root_dir_var.get()
        initial_dir = root_dir if os.path.isdir(root_dir) else os.getcwd()
        selected = filedialog.askdirectory(initialdir=initial_dir, title="Select Directory to Exclude")
        if selected:
            dir_name = os.path.basename(selected)
            self._add_to_comma_separated_list(self.excluded_dirs_var, [dir_name])
            self.update_status_message(f"🗑️ Added directory '{dir_name}' to EXCLUSION list.")

    def browse_excluded_files(self):
        root_dir = self.root_dir_var.get()
        initial_dir = root_dir if os.path.isdir(root_dir) else os.getcwd()
        selected = filedialog.askopenfilenames(initialdir=initial_dir, title="Select Files to Exclude")
        if selected:
            abs_paths = [os.path.abspath(p) for p in selected]
            self._add_to_comma_separated_list(self.excluded_files_var, abs_paths)
            self.update_status_message(f"🗑️ Added {len(abs_paths)} files to EXCLUSION list.")

    def browse_included_dirs(self):
        root_dir = self.root_dir_var.get()
        initial_dir = root_dir if os.path.isdir(root_dir) else os.getcwd()
        selected = filedialog.askdirectory(initialdir=initial_dir, title="Select Directory to Include")
        if selected:
            dir_name = os.path.basename(selected)
            self._add_to_comma_separated_list(self.included_dirs_var, [dir_name])
            self.update_status_message(f"📁 Added directory '{dir_name}' to INCLUSION list.")

    def browse_included_files(self):
        root_dir = self.root_dir_var.get()
        initial_dir = root_dir if os.path.isdir(root_dir) else os.getcwd()
        selected = filedialog.askopenfilenames(initialdir=initial_dir, title="Select Files to Include")
        if selected:
            abs_paths = [os.path.abspath(p) for p in selected]
            self._add_to_comma_separated_list(self.included_files_var, abs_paths)
            self.update_status_message(f"📄 Added {len(abs_paths)} files to INCLUSION list.")

    def _add_to_comma_separated_list(self, var, new_items):
        raw = var.get()
        if ', ' in raw:
            current_list = [item.strip() for item in raw.split(', ') if item.strip()]
        else:
            current_list = [item.strip() for item in raw.split(',') if item.strip()]
        for item in new_items:
            if item not in current_list:
                current_list.append(item)
        var.set(', '.join(sorted(current_list)))

    # --- Search Methods ---
    def _is_binary(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                return b'\x00' in f.read(1024)
        except Exception:
            return True

    def perform_search(self):
        query = self.search_query_var.get().strip().lower()
        root_dir = self.root_dir_var.get()

        if not query:
            messagebox.showwarning("Search", "Please enter a search keyword.")
            return
        if not os.path.isdir(root_dir):
            messagebox.showerror("Error", "Invalid root directory.")
            return

        self.update_status_message(f"🔎 Searching for '{query}'...")
        self.search_results_listbox.delete(0, tk.END)

        excluded_dirs = set(d.strip() for d in self.excluded_dirs_var.get().split(',') if d.strip())
        excluded_files = set(f.strip() for f in self.excluded_files_var.get().split(',') if f.strip())
        gitignore_spec = self._load_gitignore_spec(root_dir)

        def search_worker():
            matches = []
            try:
                for dirpath, dirnames, filenames in os.walk(root_dir):
                    rel_dir = os.path.relpath(dirpath, root_dir)
                    if gitignore_spec:
                        dirnames[:] = [d for d in dirnames if not gitignore_spec.match_file(os.path.normpath(os.path.join(rel_dir, d)))]
                    dirnames[:] = [d for d in dirnames if d not in excluded_dirs]

                    for filename in filenames:
                        file_path = os.path.join(dirpath, filename)
                        rel_path = os.path.relpath(file_path, root_dir)
                        abs_path = os.path.abspath(file_path)

                        if filename in excluded_files or abs_path in excluded_files:
                            continue
                        if gitignore_spec and gitignore_spec.match_file(os.path.normpath(rel_path)):
                            continue
                        if self._is_binary(file_path):
                            continue

                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                if query in f.read().lower():
                                    matches.append(abs_path)
                        except Exception:
                            continue

                def update_ui():
                    if matches:
                        for match in matches:
                            self.search_results_listbox.insert(tk.END, match)
                        self.update_status_message(f"✅ Found {len(matches)} files containing '{query}'.")
                    else:
                        self.update_status_message(f"❌ No matches found for '{query}'.")
                        messagebox.showinfo("Search", "No matches found.")

                self.master.after(0, update_ui)
            except Exception as e:
                self.master.after(0, lambda: self.update_status_message(f"❌ Search error: {e}"))

        threading.Thread(target=search_worker, daemon=True).start()

    def add_search_results_to_included(self):
        selected = self.search_results_listbox.curselection()
        if not selected:
            messagebox.showwarning("Inclusion", "No search results selected.")
            return
        paths = [self.search_results_listbox.get(i) for i in selected]
        self._add_to_comma_separated_list(self.included_files_var, paths)
        self.update_status_message(f"➕ Added {len(paths)} selected files to INCLUSION list.")

    # --- Scan / Preview Methods ---
    def perform_scan(self):
        root_dir = self.root_dir_var.get().strip()
        if not os.path.isdir(root_dir):
            messagebox.showerror("Error", "Invalid root directory.")
            return

        self.update_status_message("🔄 Scanning project for file checklist...")
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.preview_files = {}

        excluded_dirs = set(d.strip() for d in self.excluded_dirs_var.get().split(',') if d.strip())
        excluded_files = set(f.strip() for f in self.excluded_files_var.get().split(',') if f.strip())
        included_dirs = set(d.strip() for d in self.included_dirs_var.get().split(',') if d.strip())
        included_files = set(f.strip() for f in self.included_files_var.get().split(',') if f.strip())
        use_include_mode = bool(included_dirs or included_files)
        gitignore_spec = self._load_gitignore_spec(root_dir)
        found_items = []

        for dirpath, dirnames, filenames in os.walk(root_dir):
            rel_dir = os.path.relpath(dirpath, root_dir)
            if gitignore_spec:
                dirnames[:] = [d for d in dirnames if not gitignore_spec.match_file(os.path.normpath(os.path.join(rel_dir, d)))]
            dirnames[:] = [d for d in dirnames if d not in excluded_dirs]

            if use_include_mode and included_dirs:
                if dirpath != root_dir:
                    segments = rel_dir.split(os.sep)
                    if not any(seg in included_dirs for seg in segments):
                        dirnames[:] = []
                        continue

            for f in filenames:
                abs_path = os.path.abspath(os.path.join(dirpath, f))
                rel_path = os.path.relpath(abs_path, root_dir)
                if f in excluded_files or abs_path in excluded_files:
                    continue
                if gitignore_spec and gitignore_spec.match_file(os.path.normpath(rel_path)):
                    continue
                if self._is_binary(abs_path):
                    continue

                include = True
                if use_include_mode:
                    include = False
                    if included_files and (f in included_files or abs_path in included_files):
                        include = True
                    elif included_dirs:
                        include = True

                if include:
                    size = os.path.getsize(abs_path) if os.path.exists(abs_path) else 0
                    found_items.append((rel_path, abs_path, size))

        for rel, abs_p, size in found_items:
            self.preview_files[abs_p] = True
            size_str = f"{size/1024:.1f}KB" if size < 1024*1024 else f"{size/(1024*1024):.1f}MB"
            self.tree.insert("", tk.END, values=("☑", rel, size_str), tags=(abs_p,))

        self.update_status_message(f"✅ Scan complete. Found {len(found_items)} files.")

    def on_tree_click(self, event):
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if item and column == "#1":
            tags = self.tree.item(item, "tags")
            if not tags:
                return
            abs_path = tags[0]
            is_checked = not self.preview_files.get(abs_path, True)
            self.preview_files[abs_path] = is_checked
            new_val = "☑" if is_checked else "☐"
            values = list(self.tree.item(item, "values"))
            values[0] = new_val
            self.tree.item(item, values=tuple(values))

    # --- Gitignore ---
    def _load_gitignore_spec(self, root_dir):
        if not pathspec:
            return None
        gitignore_path = os.path.join(root_dir, '.gitignore')
        if os.path.exists(gitignore_path):
            try:
                with open(gitignore_path, 'r', encoding='utf-8') as f:
                    return pathspec.PathSpec.from_lines('gitwildmatch', f)
            except Exception as e:
                self.update_status_message(f"⚠️ Failed to parse .gitignore: {e}")
        return None

    # --- Copy to Clipboard ---
    def copy_to_clipboard(self):
        output_path = self.output_full_path_var.get()
        if not os.path.exists(output_path):
            messagebox.showerror("Error", "Output file not found. Please merge files first.")
            return
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.master.clipboard_clear()
            self.master.clipboard_append(content)
            self.update_status_message("📋 Content copied to clipboard!")
            messagebox.showinfo("Clipboard", "✅ Merged content copied to clipboard!")
        except Exception as e:
            self.update_status_message(f"❌ Failed to copy: {e}")
            messagebox.showerror("Error", f"Failed to copy: {e}")

    # --- Start Combination ---
    def start_combination(self):
        if self.is_processing:
            return

        self.save_config()
        root_dir = self.root_dir_var.get().strip()
        output_full_path = self.output_full_path_var.get().strip()

        if not root_dir or not os.path.isdir(root_dir):
            messagebox.showerror("Config Error", "Please select a valid project root.")
            return

        if not output_full_path:
            messagebox.showerror("Config Error", "Please specify an output file path.")
            return

        self.status_text.config(state=tk.NORMAL)
        self.status_text.delete(1.0, tk.END)
        self.status_text.config(state=tk.DISABLED)

        self.is_processing = True
        self.combine_button.config(state=tk.DISABLED, text="⏳ PROCESSING...")
        self.copy_button.config(state=tk.DISABLED)

        self.update_status_message("🚀 Starting file combination process...")

        thread = threading.Thread(target=self._run_combination_logic, daemon=True)
        thread.start()

    def _run_combination_logic(self):
        root_dir = self.root_dir_var.get()
        output_full_path = self.output_full_path_var.get()

        excluded_dirs = [d.strip() for d in self.excluded_dirs_var.get().split(',') if d.strip()]
        excluded_files = [f.strip() for f in self.excluded_files_var.get().split(',') if f.strip()]
        included_dirs = [d.strip() for d in self.included_dirs_var.get().split(',') if d.strip()]
        included_files = [f.strip() for f in self.included_files_var.get().split(',') if f.strip()]

        gitignore_spec = self._load_gitignore_spec(root_dir)
        if gitignore_spec:
            self.update_status_message("📋 Applied .gitignore patterns for filtering.")

        max_size = self.max_file_size_var.get()
        if max_size:
            self.update_status_message(f"📏 Max file size: {max_size} bytes")

        manual_map = self.preview_files if self.preview_files else None

        success = combine_files_to_single_file_gui(
            root_dir, output_full_path,
            excluded_dirs, excluded_files,
            included_dirs, included_files,
            self.update_status_message,
            gitignore_spec=gitignore_spec,
            manual_selection_map=manual_map,
            max_file_size=max_size,
            include_file_stats=self.include_stats_var.get(),
            sort_files=self.sort_files_var.get()
        )

        def finalize():
            self.is_processing = False
            if success:
                self.copy_button.config(state=tk.NORMAL)
                messagebox.showinfo("Success", f"✅ Files combined successfully into:\n{output_full_path}")
            else:
                messagebox.showerror("Failed", "❌ File combination failed. Check log for details.")
            self.combine_button.config(state=tk.NORMAL, text="🚀 START MERGING")

        self.master.after(0, finalize)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = tk.Tk()
    root.minsize(900, 700)
    app = FileCombinerApp(root)
    root.mainloop()
