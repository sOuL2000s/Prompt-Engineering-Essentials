import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import os
import sys
import threading
import json
from pathlib import Path
try:
    import pathspec
except ImportError:
    pathspec = None

# --- Core Logic (now with optional include functionality) ---
def generate_directory_tree(root_dir, excluded_dirs, excluded_files, 
                            included_dirs, included_files, gitignore_spec=None):
    """
    Generates a visual text-based directory tree of the project, respecting 
    exclusions, inclusions, and gitignore rules.
    """
    use_include_mode = bool(included_dirs or included_files)
    excluded_dirs_set = set(excluded_dirs)
    excluded_files_set = set(f.strip() for f in excluded_files)
    included_dirs_set = set(included_dirs)
    included_files_set = set(f.strip() for f in included_files)

    tree_lines = [f"{os.path.basename(root_dir)}/"]
    
    def _walk_tree(current_dir, prefix=""):
        try:
            # Sorting items keeps the tree output deterministic
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
                # Directory filtering
                if gitignore_spec and gitignore_spec.match_file(os.path.normpath(rel_path)):
                    continue
                if item in excluded_dirs_set:
                    continue
                
                # Include Mode logic for Directory Traversal
                if use_include_mode and included_dirs_set:
                    segments = rel_path.split(os.sep)
                    if not any(seg in included_dirs_set for seg in segments):
                        continue
                
                valid_items.append((item, True))
            else:
                # File filtering
                if item in excluded_files_set or abs_path in excluded_files_set:
                    continue
                if gitignore_spec and gitignore_spec.match_file(os.path.normpath(rel_path)):
                    continue
                
                # Include Mode logic for Files
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

def combine_files_to_single_file_gui(root_dir, output_full_path, 
                                     excluded_dirs_list, excluded_files_list,
                                     included_dirs_list, included_files_list,
                                     status_callback, gitignore_spec=None,
                                     manual_selection_map=None):
    """
    Combines the content of all files in a directory into a single file.

    Args:
        ...
        manual_selection_map (dict): Optional mapping of absolute file path to boolean (True = include).
    """
    combined_content = []

    status_callback(f"Starting to combine files from: {root_dir}")

    # Determine if "include mode" is active
    use_include_mode = bool(included_dirs_list or included_files_list)

    if use_include_mode:
        status_callback(f"Running in INCLUDE MODE (Exclusions still apply).")
        if included_dirs_list:
            status_callback(f"Including directories: {', '.join(included_dirs_list)}")
        if included_files_list:
            status_callback(f"Including files: {', '.join(included_files_list)}")
    else:
        status_callback(f"Running in EXCLUDE MODE.")
    
    status_callback(f"Excluding directories: {', '.join(excluded_dirs_list)}")
    status_callback(f"Excluding files: {', '.join(excluded_files_list)}")

    # 0. Generate Directory Tree Header
    status_callback("Generating project directory tree header...")
    tree_header = generate_directory_tree(
        root_dir, excluded_dirs_list, excluded_files_list, 
        included_dirs_list, included_files_list, gitignore_spec
    )
    combined_content.append("================================================================\n")
    combined_content.append("PROJECT STRUCTURE (TREE VIEW)\n")
    combined_content.append("================================================================\n\n")
    combined_content.append(tree_header)
    combined_content.append("\n\n================================================================\n")
    combined_content.append("FILE CONTENTS\n")
    combined_content.append("================================================================\n")

    # Basic validation
    if not os.path.isdir(root_dir):
        status_callback(f"Error: Project root directory not found or is not a directory: {root_dir}")
        return False
    
    # Ensure the output directory exists
    output_dir = os.path.dirname(output_full_path)
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            status_callback(f"Created output directory: {output_dir}")
        except OSError as e:
            status_callback(f"Error creating output directory {output_dir}: {e}")
            return False

    # Convert lists to sets for faster lookups
    excluded_dirs_set = set(excluded_dirs_list)
    excluded_files_set = set(f.strip() for f in excluded_files_list)
    included_dirs_set = set(included_dirs_list)
    # Ensure items in included_files_set are stripped and absolute where possible
    included_files_set = set(f.strip() for f in included_files_list)

    try:
        for dirpath, dirnames, filenames in os.walk(root_dir):
            relative_dirpath = os.path.relpath(dirpath, root_dir)

            # --- 0. Apply Gitignore Patterns (Directories) ---
            if gitignore_spec:
                dirnames[:] = [d for d in dirnames if not gitignore_spec.match_file(os.path.normpath(os.path.join(relative_dirpath, d)))]

            # --- 1. Apply Exclusions for Directories (Always) ---
            dirnames[:] = [d for d in dirnames if d not in excluded_dirs_set]

            # --- 2. Apply Include Mode Filtering (Directory Traversal) ---
            if use_include_mode:
                # Determine if the current directory `dirpath` (and its files/subdirs) should be considered *at all*
                should_process_this_dir_based_on_included_dirs = True 
                
                if included_dirs_set: # User has specified specific directories to include
                    if dirpath == root_dir:
                        should_process_this_dir_based_on_included_dirs = True
                    else:
                        # Check if this directory, or any of its ancestors (relative to root), matches an included directory basename.
                        relative_path_segments = relative_dirpath.split(os.sep)
                        if not any(seg in included_dirs_set for seg in relative_path_segments):
                            should_process_this_dir_based_on_included_dirs = False

                if not should_process_this_dir_based_on_included_dirs:
                    # If this directory is not relevant based on `included_dirs_set`, prune its subdirectories
                    # and skip processing any files in it.
                    dirnames[:] = [] 
                    continue         

            # --- 3. Filter Files for Processing ---
            files_to_process = []
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                relative_file_path = os.path.join(relative_dirpath, filename)
                abs_file_path = os.path.abspath(file_path)
                
                # Skip symbolic links
                if os.path.islink(file_path):
                    continue

                # Skip explicitly excluded files (Always)
                if filename in excluded_files_set or abs_file_path in excluded_files_set:
                    continue

                # Gitignore check for files
                if gitignore_spec and gitignore_spec.match_file(os.path.normpath(relative_file_path)):
                    continue

                if use_include_mode:
                    # If specific files are included, only take those
                    if included_files_set:
                        if filename in included_files_set or abs_file_path in included_files_set:
                            # Apply manual checklist override if present
                            if manual_selection_map is None or manual_selection_map.get(abs_file_path, True):
                                files_to_process.append(filename)
                    # If no specific files but included_dirs are defined, take all files in an included/relevant dir
                    elif included_dirs_set:
                        if manual_selection_map is None or manual_selection_map.get(abs_file_path, True):
                            files_to_process.append(filename)
                else: 
                    # Not in include mode, all non-excluded files are included
                    if manual_selection_map is None or manual_selection_map.get(abs_file_path, True):
                        files_to_process.append(filename)

            # --- Process the filtered files ---
            for filename in files_to_process:
                file_path = os.path.join(dirpath, filename)
                relative_file_path = os.path.relpath(file_path, root_dir)

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    combined_content.append(f"\n--- START FILE: {relative_file_path} ---\n\n")
                    combined_content.append(content)
                    combined_content.append(f"\n\n--- END FILE: {relative_file_path} ---\n")
                    status_callback(f"Included file: {relative_file_path}")
                except UnicodeDecodeError:
                    status_callback(f"Skipping binary or undecodable file (UnicodeDecodeError): {relative_file_path}")
                except Exception as e:
                    status_callback(f"Error reading file {relative_file_path}: {e}")

        with open(output_full_path, 'w', encoding='utf-8') as outfile:
            outfile.write("".join(combined_content))
        status_callback(f"\nSuccessfully combined all files into: {output_full_path}")
        return True
    except Exception as e:
        status_callback(f"An unexpected error occurred during file combination: {e}")
        return False

# --- GUI Application ---
CONFIG_FILE = "last_session.json"

class FileCombinerApp:
    THEMES = {
        "light": {
            "bg": "#f3f4f6",
            "fg": "#111827",
            "frame_bg": "#ffffff",
            "entry_bg": "#f9fafb",
            "button_bg": "#2563eb",
            "button_fg": "#ffffff",
            "log_bg": "#ffffff",
            "log_fg": "#374151",
            "accent": "#2563eb",
            "border": "#e5e7eb",
            "secondary_fg": "#6b7280"
        },
        "dark": {
            "bg": "#0f172a",
            "fg": "#f8fafc",
            "frame_bg": "#1e293b",
            "entry_bg": "#0f172a",
            "button_bg": "#3b82f6",
            "button_fg": "#ffffff",
            "log_bg": "#020617",
            "log_fg": "#cbd5e1",
            "accent": "#60a5fa",
            "border": "#334155",
            "secondary_fg": "#94a3b8"
        }
    }

    def __init__(self, master):
        self.master = master
        master.title("Project File Combiner Pro")
        
        self.current_theme = "dark" # Start with dark mode as it looks more modern
        self.colors = self.THEMES[self.current_theme]
        
        # File preview state
        self.preview_files = {} # abs_path: bool (True = checked)

        # Sizing and Window Setup
        master.geometry("1000x850")
        master.minsize(900, 700)
        master.configure(bg=self.colors["bg"])

        # Variables
        self.root_dir_var = tk.StringVar(value=os.getcwd())
        self.output_full_path_var = tk.StringVar(value=os.path.join(os.getcwd(), "combined_project_files.txt"))
        
        # Excluded items
        self.excluded_dirs_var = tk.StringVar(
            value="node_modules, .git, .vscode, .idea, dist, build, venv, __pycache__, .DS_Store"
        )
        self.excluded_files_var = tk.StringVar(
            value="package-lock.json, yarn.lock, bun.lockb, .DS_Store, Thumbs.db, pyproject.toml, combined_project_files.txt"
        )

        # Included items
        self.included_dirs_var = tk.StringVar(value="")
        self.included_files_var = tk.StringVar(value="")

        # Search variables
        self.search_query_var = tk.StringVar(value="")

        self.setup_styles()
        self.create_widgets()

        # Load persisted settings from previous session
        self.load_config()

        # Setup auto-save on window close
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Check for pathspec dependency
        if not pathspec:
            self.update_status_message("⚠️  Note: 'pathspec' library is missing. .gitignore files will be ignored.")
            self.update_status_message("👉 To enable .gitignore support, run: pip install pathspec")
        else:
            self.update_status_message("✅ 'pathspec' detected. .gitignore support is active.")

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.apply_theme_styles()

    def apply_theme_styles(self):
        c = self.colors
        # Common widget styles
        self.style.configure("TFrame", background=c["bg"])
        self.style.configure("Card.TFrame", background=c["frame_bg"], relief="flat", borderwidth=0)
        self.style.configure("TLabel", background=c["bg"], foreground=c["fg"], font=('Segoe UI', 10))
        self.style.configure("Card.TLabel", background=c["frame_bg"], foreground=c["fg"], font=('Segoe UI', 10))
        self.style.configure("Header.TLabel", background=c["frame_bg"], foreground=c["accent"], font=('Segoe UI Bold', 9))
        self.style.configure("SmallHeader.TLabel", background=c["frame_bg"], foreground=c["fg"], font=('Segoe UI Bold', 8))
        self.style.configure("TEntry", fieldbackground=c["entry_bg"], foreground=c["fg"], 
                             insertcolor=c["fg"], bordercolor=c["border"], lightcolor=c["border"], darkcolor=c["border"])
        
        # Action Button (Primary)
        self.style.configure("Action.TButton", font=('Segoe UI Semibold', 10), padding=(15, 8), borderwidth=0)
        self.style.map("Action.TButton",
            background=[('pressed', c["accent"]), ('active', c["accent"]), ('!disabled', c["button_bg"])],
            foreground=[('active', '#ffffff'), ('!disabled', '#ffffff')]
        )
        
        # Browse Button (Secondary)
        self.style.configure('Browse.TButton', font=('Segoe UI', 9), padding=(10, 5), borderwidth=1)
        self.style.map('Browse.TButton',
            background=[('active', c["border"]), ('!disabled', c["frame_bg"])],
            foreground=[('active', c["fg"]), ('!disabled', c["fg"])],
            bordercolor=[('!disabled', c["border"])]
        )

        # Tabs
        self.style.configure("TNotebook", background=c["bg"], borderwidth=0, tabmargins=[2, 5, 2, 0])
        self.style.configure("TNotebook.Tab", background=c["frame_bg"], foreground=c["fg"], padding=(20, 10), font=('Segoe UI Semibold', 9), borderwidth=0)
        self.style.map("TNotebook.Tab",
            background=[("selected", c["accent"]), ("active", c["border"])],
            foreground=[("selected", "#ffffff"), ("active", c["fg"])]
        )

        # Treeview Styling
        self.style.configure("Treeview", background=c["log_bg"], foreground=c["log_fg"], 
                             fieldbackground=c["log_bg"], borderwidth=0, font=('Segoe UI', 9))
        self.style.configure("Treeview.Heading", background=c["frame_bg"], foreground=c["fg"], font=('Segoe UI Semibold', 9))
        self.style.map("Treeview", background=[('selected', c["accent"])], foreground=[('selected', '#ffffff')])

        # Specific styling for inner frames of notebook
        self.style.configure("Tab.TFrame", background=c["frame_bg"])

    def toggle_theme(self):
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.colors = self.THEMES[self.current_theme]
        self.master.configure(bg=self.colors["bg"])
        self.apply_theme_styles()
        self.refresh_ui_colors()

    def refresh_ui_colors(self):
        c = self.colors
        # Update Treeview headers manual background if needed (some systems don't update headings automatically)
        self.tree_container.configure(highlightbackground=c["border"], bg=c["log_bg"])
        # Update Standard Frames and Canvas
        self.main_container.configure(bg=c["bg"])
        self.header_frame.configure(bg=c["bg"])
        self.title_container.configure(bg=c["bg"])
        self.footer_outer.configure(bg=c["bg"])
        self.log_label_frame.configure(bg=c["bg"])
        self.canvas.configure(bg=c["bg"])
        self.config_card.configure(bg=c["frame_bg"], highlightbackground=c["border"])
        self.result_container.configure(highlightbackground=c["border"], bg=c["log_bg"])

        # Update Standard Labels
        self.title_lbl.configure(bg=c["bg"], fg=c["accent"])
        self.subtitle_lbl.configure(bg=c["bg"], fg=c["secondary_fg"])
        
        # Update Log Label (ttk widget needs manual background update for specific cases)
        self.log_label_text.configure(background=c["bg"], foreground=c["secondary_fg"])
        
        # Update Listbox and Text Area
        self.search_results_listbox.configure(bg=c["log_bg"], fg=c["log_fg"], 
                                              selectbackground=c["accent"], borderwidth=0)
        self.status_text.configure(bg=c["log_bg"], fg=c["log_fg"], 
                                   highlightbackground=c["border"], insertbackground=c["fg"])
        
        # Update Buttons
        self.combine_button.configure(bg=c["button_bg"], fg=c["button_fg"], 
                                        activebackground=c["accent"])
        self.copy_button.configure(bg=c["frame_bg"], fg=c["fg"], 
                                     activebackground=c["border"], highlightbackground=c["border"])
        self.theme_btn.configure(text="🌙 Dark Mode" if self.current_theme == "light" else "☀️ Light Mode", 
                                 bg=c["frame_bg"], fg=c["fg"], activebackground=c["border"])
        
    def create_widgets(self):
        c = self.colors
        
        # Main Layout: 3 Vertical Sections (Header, Content, Footer)
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(1, weight=1) # Content expands

        # 1. Header Section
        self.header_frame = tk.Frame(self.master, bg=c["bg"], padx=30, pady=20)
        self.header_frame.grid(row=0, column=0, sticky="ew")
        
        self.title_container = tk.Frame(self.header_frame, bg=c["bg"])
        self.title_container.pack(side=tk.LEFT)

        self.title_lbl = tk.Label(self.title_container, text="Project Combiner", 
                            font=('Segoe UI Semibold', 22), bg=c["bg"], fg=c["accent"])
        self.title_lbl.pack(anchor=tk.W)
        
        self.subtitle_lbl = tk.Label(self.title_container, text="Consolidate your codebase into a single document for analysis.", 
                               font=('Segoe UI', 10), bg=c["bg"], fg=c["secondary_fg"])
        self.subtitle_lbl.pack(anchor=tk.W)
        
        self.theme_btn = tk.Button(self.header_frame, text="🌙 Dark Mode" if self.current_theme == "light" else "☀️ Light Mode",
                                  command=self.toggle_theme, relief=tk.FLAT, cursor="hand2",
                                  bg=c["frame_bg"], fg=c["fg"], font=('Segoe UI Semibold', 9),
                                  padx=15, pady=8)
        self.theme_btn.pack(side=tk.RIGHT)

        # 2. Main Scrollable Content Area
        self.canvas = tk.Canvas(self.master, bg=c["bg"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.master, orient="vertical", command=self.canvas.yview)
        self.main_container = tk.Frame(self.canvas, bg=c["bg"], padx=30)

        # Create the window item and store its ID for configuration
        self.canvas_frame_id = self.canvas.create_window((0, 0), window=self.main_container, anchor="nw")

        # Ensure the scrollregion is updated when the inner frame changes size
        self.main_container.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        
        # Fix: Bind to Canvas configuration rather than Master to prevent layout oscillation/blinking.
        # This ensures the interior frame width matches the canvas available space.
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_frame_id, width=e.width))
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.scrollbar.grid(row=1, column=1, sticky="ns")

        # Configuration Card
        self.config_card = tk.Frame(self.main_container, bg=c["frame_bg"], padx=20, pady=20, 
                              highlightthickness=1, highlightbackground=c["border"])
        self.config_card.pack(fill=tk.X, pady=(0, 20))
        self.config_card.columnconfigure(1, weight=1)

        self.config_title_lbl = ttk.Label(self.config_card, text="PROJECT CONFIGURATION", style="Header.TLabel")
        self.config_title_lbl.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0,15))

        ttk.Label(self.config_card, text="Root Directory", style="Card.TLabel").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(self.config_card, textvariable=self.root_dir_var).grid(row=1, column=1, pady=5, padx=15, sticky=tk.EW)
        ttk.Button(self.config_card, text="Change", style='Browse.TButton', command=self.browse_root_dir).grid(row=1, column=2, pady=5)

        ttk.Label(self.config_card, text="Output File", style="Card.TLabel").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(self.config_card, textvariable=self.output_full_path_var).grid(row=2, column=1, pady=5, padx=15, sticky=tk.EW)
        ttk.Button(self.config_card, text="Save As", style='Browse.TButton', command=self.browse_output_file).grid(row=2, column=2, pady=5)

        # Tabbed Control Area
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill=tk.X, pady=(0, 20))

        # Tab 1: Filters (Exclusions/Inclusions)
        filter_tab = ttk.Frame(self.notebook, padding=20, style="Tab.TFrame")
        self.notebook.add(filter_tab, text=" Filters & Rules ")
        filter_tab.columnconfigure(1, weight=1)

        # Section Headers in Tabs
        ttk.Label(filter_tab, text="EXCLUSIONS (SKIP THESE)", style="SmallHeader.TLabel").grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        
        ttk.Label(filter_tab, text="Directories:", style="Card.TLabel").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(filter_tab, textvariable=self.excluded_dirs_var).grid(row=1, column=1, pady=5, padx=(10, 10), sticky=tk.EW)
        ttk.Button(filter_tab, text="+ Dir", style='Browse.TButton', command=self.browse_excluded_dirs).grid(row=1, column=2, pady=5)

        ttk.Label(filter_tab, text="Files:", style="Card.TLabel").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(filter_tab, textvariable=self.excluded_files_var).grid(row=2, column=1, pady=5, padx=(10, 10), sticky=tk.EW)
        ttk.Button(filter_tab, text="+ File", style='Browse.TButton', command=self.browse_excluded_files).grid(row=2, column=2, pady=5)

        ttk.Separator(filter_tab, orient='horizontal').grid(row=3, column=0, columnspan=3, sticky="ew", pady=15)

        ttk.Label(filter_tab, text="INCLUSIONS (ONLY THESE)", style="SmallHeader.TLabel").grid(row=4, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))

        ttk.Label(filter_tab, text="Directories:", style="Card.TLabel").grid(row=5, column=0, sticky=tk.W, pady=5)
        ttk.Entry(filter_tab, textvariable=self.included_dirs_var).grid(row=5, column=1, pady=5, padx=(10, 10), sticky=tk.EW)
        ttk.Button(filter_tab, text="+ Dir", style='Browse.TButton', command=self.browse_included_dirs).grid(row=5, column=2, pady=5)

        ttk.Label(filter_tab, text="Files:", style="Card.TLabel").grid(row=6, column=0, sticky=tk.W, pady=5)
        ttk.Entry(filter_tab, textvariable=self.included_files_var).grid(row=6, column=1, pady=5, padx=(10, 10), sticky=tk.EW)
        ttk.Button(filter_tab, text="+ File", style='Browse.TButton', command=self.browse_included_files).grid(row=6, column=2, pady=5)

        # Tab 2: Smart Search
        search_tab = ttk.Frame(self.notebook, padding=20, style="Tab.TFrame")
        self.notebook.add(search_tab, text=" Smart Search & Pick ")
        search_tab.columnconfigure(1, weight=1)
        search_tab.rowconfigure(2, weight=1)

        ttk.Label(search_tab, text="Keyword:", style="Card.TLabel").grid(row=0, column=0, sticky=tk.W)
        self.search_entry = ttk.Entry(search_tab, textvariable=self.search_query_var)
        self.search_entry.grid(row=0, column=1, padx=15, sticky=tk.EW)
        self.search_entry.bind('<Return>', lambda e: self.perform_search())
        ttk.Button(search_tab, text="Search Files", style='Action.TButton', command=self.perform_search).grid(row=0, column=2)

        self.result_container = tk.Frame(search_tab, bg=c["log_bg"], bd=1, highlightthickness=1, highlightbackground=c["border"])
        self.result_container.grid(row=1, column=0, columnspan=3, sticky=tk.NSEW, pady=15)
        
        self.search_results_listbox = tk.Listbox(self.result_container, selectmode=tk.MULTIPLE, height=6, 
                                                font=('Consolas', 10), bd=0, highlightthickness=0,
                                                bg=c["log_bg"], fg=c["log_fg"], selectbackground=c["accent"])
        self.search_results_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        sl = ttk.Scrollbar(self.result_container, orient=tk.VERTICAL, command=self.search_results_listbox.yview)
        sl.pack(side=tk.RIGHT, fill=tk.Y)
        self.search_results_listbox.config(yscrollcommand=sl.set)

        ttk.Button(search_tab, text="Add Selection to Inclusion List", style='Browse.TButton', 
                   command=self.add_search_results_to_included).grid(row=2, column=0, columnspan=3, sticky=tk.E)

        # Tab 3: Interactive Preview (The Checklist)
        preview_tab = ttk.Frame(self.notebook, padding=20, style="Tab.TFrame")
        self.notebook.add(preview_tab, text=" File Checklist (Scan) ")
        preview_tab.columnconfigure(0, weight=1)
        preview_tab.rowconfigure(1, weight=1)

        preview_header_frame = tk.Frame(preview_tab, bg=c["frame_bg"])
        preview_header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(preview_header_frame, text="Select specific files to include in the merge:", 
                  style="Card.TLabel").pack(side=tk.LEFT)
        
        self.scan_button = ttk.Button(preview_header_frame, text="Scan Project", 
                                     style='Action.TButton', command=self.perform_scan)
        self.scan_button.pack(side=tk.RIGHT)

        # Treeview for checklist
        self.tree_container = tk.Frame(preview_tab, bg=c["log_bg"], bd=1, highlightthickness=1, highlightbackground=c["border"])
        self.tree_container.grid(row=1, column=0, sticky="nsew")
        
        self.tree = ttk.Treeview(self.tree_container, columns=("Include", "Path"), show="headings", style="Treeview")
        self.tree.heading("Include", text="[X]")
        self.tree.heading("Path", text="Relative File Path")
        self.tree.column("Include", width=50, stretch=False, anchor="center")
        self.tree.column("Path", width=600, stretch=True)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tree_scroll = ttk.Scrollbar(self.tree_container, orient=tk.VERTICAL, command=self.tree.yview)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)

        # 3. Footer Section (Fixed at bottom)
        self.footer_outer = tk.Frame(self.master, bg=c["bg"], padx=30, pady=20)
        self.footer_outer.grid(row=2, column=0, sticky="ew")
        
        self.combine_button = tk.Button(self.footer_outer, text="START MERGING PROJECT FILES", command=self.start_combination, 
                                        font=('Segoe UI Bold', 12), bg=c["button_bg"], fg=c["button_fg"], 
                                        activebackground=c["accent"], activeforeground='white',
                                        relief=tk.FLAT, cursor="hand2", pady=15)
        self.combine_button.pack(fill=tk.X, pady=(0, 10))

        self.copy_button = tk.Button(self.footer_outer, text="📋 COPY MERGED RESULT TO CLIPBOARD", 
                                       command=self.copy_to_clipboard, 
                                       font=('Segoe UI Semibold', 10), bg=c["frame_bg"], fg=c["fg"], 
                                       activebackground=c["border"], relief=tk.FLAT, cursor="hand2", 
                                       pady=10, state=tk.DISABLED)
        self.copy_button.pack(fill=tk.X, pady=(0, 20))

        self.log_label_frame = tk.Frame(self.footer_outer, bg=c["bg"])
        self.log_label_frame.pack(fill=tk.X, pady=(0, 5))
        self.log_label_text = ttk.Label(self.log_label_frame, text="Activity Log", font=('Segoe UI Semibold', 9), foreground=c["secondary_fg"])
        self.log_label_text.pack(side=tk.LEFT)
        
        self.status_text = scrolledtext.ScrolledText(self.footer_outer, wrap=tk.WORD, height=6, 
                                                     font=('Consolas', 9), bg=c["log_bg"], fg=c["log_fg"],
                                                     relief=tk.FLAT, bd=1, highlightthickness=1, 
                                                     highlightbackground=c["border"])
        self.status_text.pack(fill=tk.X)
        self.status_text.config(state=tk.DISABLED)

        # Mousewheel scrolling for canvas
        self.master.bind_all("<MouseWheel>", self._on_mousewheel)

    def load_config(self):
        """Loads configuration from a JSON file."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.root_dir_var.set(config.get("root_dir", os.getcwd()))
                    self.output_full_path_var.set(config.get("output_path", os.path.join(os.getcwd(), "combined_project_files.txt")))
                    self.excluded_dirs_var.set(config.get("excluded_dirs", "node_modules, .git, .vscode, .idea, dist, build, venv, __pycache__, .DS_Store"))
                    self.excluded_files_var.set(config.get("excluded_files", "package-lock.json, yarn.lock, bun.lockb, .DS_Store, Thumbs.db, pyproject.toml, combined_project_files.txt"))
                    self.included_dirs_var.set(config.get("included_dirs", ""))
                    self.included_files_var.set(config.get("included_files", ""))
                    
                    # Apply saved theme
                    saved_theme = config.get("theme", "dark")
                    if saved_theme != self.current_theme:
                        self.current_theme = saved_theme
                        self.colors = self.THEMES[self.current_theme]
                        self.apply_theme_styles()
                        self.refresh_ui_colors()
                        
                self.update_status_message(f"✅ Last session configuration restored.")
            except Exception as e:
                self.update_status_message(f"⚠️ Failed to load session config: {e}")

    def save_config(self):
        """Saves current configuration to a JSON file."""
        config = {
            "root_dir": self.root_dir_var.get(),
            "output_path": self.output_full_path_var.get(),
            "excluded_dirs": self.excluded_dirs_var.get(),
            "excluded_files": self.excluded_files_var.get(),
            "included_dirs": self.included_dirs_var.get(),
            "included_files": self.included_files_var.get(),
            "theme": self.current_theme
        }
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def on_closing(self):
        """Called when the window is closed."""
        self.save_config()
        self.master.destroy()

    def update_status_message(self, message):
        """Schedules a log update on the main thread."""
        self.master.after(0, self._safe_update_log, message)

    def _safe_update_log(self, message):
        """Appends a message to the status log and scrolls to the end safely."""
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)

    def _on_mousewheel(self, event):
        """Allows scrolling the canvas with the mouse wheel."""
        # Fix for some systems where event.delta is different
        if event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")

    def _add_to_comma_separated_list(self, current_var, new_items):
        """Helper to add new items to a comma-separated StringVar, handling duplicates."""
        raw_val = current_var.get()
        if ', ' in raw_val:
            current_list = [item.strip() for item in raw_val.split(', ') if item.strip()]
        else:
            current_list = [item.strip() for item in raw_val.split(',') if item.strip()]

        for item in new_items:
            if item not in current_list:
                current_list.append(item)
        
        current_var.set(', '.join(sorted(current_list)))

    def browse_root_dir(self):
        """Opens a directory dialog for selecting the project root."""
        directory = filedialog.askdirectory(
            initialdir=self.root_dir_var.get() if os.path.isdir(self.root_dir_var.get()) else os.getcwd(),
            title="Select Project Root Directory"
        )
        if directory:
            self.root_dir_var.set(directory)
            # Automatically update output path to the same directory
            new_output_path = os.path.join(directory, "combined_project_files.txt")
            self.output_full_path_var.set(new_output_path)
            
            msg = f"Source updated to: {directory}"
            if os.path.exists(os.path.join(directory, '.gitignore')):
                if pathspec:
                    msg += " (Found .gitignore - filtering active)"
                else:
                    msg += " (Found .gitignore - filtering DISABLED. Install pathspec to enable.)"
            self.update_status_message(msg)

    def browse_output_file(self):
        """Opens a file save dialog for specifying the output file."""
        current_output_path = self.output_full_path_var.get()
        default_filename = os.path.basename(current_output_path)
        default_initialdir = os.path.dirname(current_output_path)
        
        if not os.path.isdir(default_initialdir):
            default_initialdir = os.getcwd()

        file_path = filedialog.asksaveasfilename(
            initialdir=default_initialdir,
            initialfile=default_filename,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Save Combined File As"
        )
        if file_path:
            self.output_full_path_var.set(file_path)

    def browse_excluded_dirs(self):
        """Opens a directory dialog to select directories to exclude."""
        root_dir = self.root_dir_var.get()
        initial_dir = root_dir if os.path.isdir(root_dir) else os.getcwd()
        selected_path = filedialog.askdirectory(
            initialdir=initial_dir,
            title="Select Directory to Exclude (by basename)"
        )
        if selected_path:
            dir_name = os.path.basename(selected_path)
            self._add_to_comma_separated_list(self.excluded_dirs_var, [dir_name])
            self.update_status_message(f"Added directory '{dir_name}' to EXCLUSION list.")

    def browse_excluded_files(self):
        """Opens a file dialog to select files to exclude (supports full paths)."""
        root_dir = self.root_dir_var.get()
        initial_dir = root_dir if os.path.isdir(root_dir) else os.getcwd()
        selected_paths = filedialog.askopenfilenames(
            initialdir=initial_dir,
            title="Select Files to Exclude"
        )
        if selected_paths:
            abs_paths = [os.path.abspath(p) for p in selected_paths]
            self._add_to_comma_separated_list(self.excluded_files_var, abs_paths)
            self.update_status_message(f"Added {len(abs_paths)} files to EXCLUSION list.")

    def browse_included_dirs(self): # NEW
        """Opens a directory dialog to select directories to include."""
        root_dir = self.root_dir_var.get()
        initial_dir = root_dir if os.path.isdir(root_dir) else os.getcwd()
        selected_path = filedialog.askdirectory(
            initialdir=initial_dir,
            title="Select Directory to Include (by basename)"
        )
        if selected_path:
            dir_name = os.path.basename(selected_path)
            self._add_to_comma_separated_list(self.included_dirs_var, [dir_name])
            self.update_status_message(f"Added directory '{dir_name}' to INCLUSION list.")

    def browse_included_files(self):
        """Opens a file dialog to select files to include (uses full paths)."""
        root_dir = self.root_dir_var.get()
        initial_dir = root_dir if os.path.isdir(root_dir) else os.getcwd()
        selected_paths = filedialog.askopenfilenames(
            initialdir=initial_dir,
            title="Select Files to Include"
        )
        if selected_paths:
            # Use absolute paths for more precision as requested
            abs_paths = [os.path.abspath(p) for p in selected_paths]
            self._add_to_comma_separated_list(self.included_files_var, abs_paths)
            self.update_status_message(f"Added {len(abs_paths)} files to INCLUSION list.")

    def copy_to_clipboard(self):
        """Reads the output file and copies its content to the system clipboard."""
        output_path = self.output_full_path_var.get()
        if not os.path.exists(output_path):
            messagebox.showerror("Error", "Output file not found. Please merge files first.")
            return
        
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            self.master.clipboard_clear()
            self.master.clipboard_append(content)
            self.update_status_message("✅ Project content copied to clipboard!")
            messagebox.showinfo("Clipboard", "Success! Merged project content has been copied to your clipboard.")
        except Exception as e:
            self.update_status_message(f"❌ Failed to copy to clipboard: {e}")
            messagebox.showerror("Error", f"Failed to copy to clipboard: {e}")

    def _is_binary(self, file_path):
        """Checks if a file is likely binary by looking for null bytes in first 1024 bytes."""
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                return b'\x00' in chunk
        except Exception:
            return True

    def perform_search(self):
        """Highly optimized search using os.walk and directory pruning."""
        query = self.search_query_var.get().strip().lower()
        root_dir = self.root_dir_var.get()
        
        if not query:
            messagebox.showwarning("Search", "Please enter a search keyword.")
            return
        if not os.path.isdir(root_dir):
            messagebox.showerror("Error", "Invalid root directory for search.")
            return

        self.update_status_message(f"Searching for '{query}'... (Fast Scan Mode)")
        self.search_results_listbox.delete(0, tk.END)
        
        # Prepare exclusions as sets for O(1) lookups
        excluded_dirs = set(d.strip() for d in self.excluded_dirs_var.get().split(',') if d.strip())
        excluded_files = set(f.strip() for f in self.excluded_files_var.get().split(',') if f.strip())
        gitignore_spec = self._load_gitignore_spec(root_dir)

        def search_worker():
            matches = []
            try:
                for dirpath, dirnames, filenames in os.walk(root_dir):
                    relative_dirpath = os.path.relpath(dirpath, root_dir)

                    # Gitignore pruning
                    if gitignore_spec:
                        dirnames[:] = [d for d in dirnames if not gitignore_spec.match_file(os.path.normpath(os.path.join(relative_dirpath, d)))]

                    # CRITICAL OPTIMIZATION: Prune directories in-place.
                    # This prevents os.walk from even entering excluded folders like node_modules.
                    dirnames[:] = [d for d in dirnames if d not in excluded_dirs]
                    
                    for filename in filenames:
                        file_path = os.path.join(dirpath, filename)
                        relative_file_path = os.path.relpath(file_path, root_dir)
                        abs_path = os.path.abspath(file_path)

                        if filename in excluded_files or abs_path in excluded_files:
                            continue
                        
                        if gitignore_spec and gitignore_spec.match_file(os.path.normpath(relative_file_path)):
                            continue
                        
                        # Skip known binary files to speed up
                        if self._is_binary(file_path):
                            continue

                        try:
                            # Read with errors='ignore' for speed and to avoid crashes on non-utf8 text
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                if query in f.read().lower():
                                    matches.append(abs_path)
                        except Exception:
                            continue
                
                def update_ui():
                    if matches:
                        for match in matches:
                            self.search_results_listbox.insert(tk.END, match)
                        self.update_status_message(f"Found {len(matches)} files containing '{query}'.")
                    else:
                        self.update_status_message(f"No matches found for '{query}'.")
                        messagebox.showinfo("Search", "No matches found.")
                
                self.master.after(0, update_ui)
            except Exception as e:
                self.master.after(0, lambda: self.update_status_message(f"Search error: {e}"))

        threading.Thread(target=search_worker, daemon=True).start()

    def add_search_results_to_included(self):
        """Adds selected items from the search listbox to the inclusion list."""
        selected_indices = self.search_results_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Inclusion", "No search results selected.")
            return
        
        selected_paths = [self.search_results_listbox.get(i) for i in selected_indices]
        self._add_to_comma_separated_list(self.included_files_var, selected_paths)
        self.update_status_message(f"Added {len(selected_paths)} selected files to INCLUSION list.")

    def perform_scan(self):
        """Scans project based on current rules and populates the checklist."""
        root_dir = self.root_dir_var.get().strip()
        if not os.path.isdir(root_dir):
            messagebox.showerror("Error", "Invalid root directory.")
            return

        self.update_status_message("Scanning project for checklist...")
        self.scan_button.config(state=tk.DISABLED, text="Scanning...")
        
        # Clear current tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.preview_files = {}

        def scan_worker():
            excluded_dirs = set(d.strip() for d in self.excluded_dirs_var.get().split(',') if d.strip())
            excluded_files = set(f.strip() for f in self.excluded_files_var.get().split(',') if f.strip())
            included_dirs = set(d.strip() for d in self.included_dirs_var.get().split(',') if d.strip())
            included_files = set(f.strip() for f in self.included_files_var.get().split(',') if f.strip())
            use_include_mode = bool(included_dirs or included_files)
            
            gitignore_spec = self._load_gitignore_spec(root_dir)
            found_items = []

            for dirpath, dirnames, filenames in os.walk(root_dir):
                rel_dir = os.path.relpath(dirpath, root_dir)
                
                # Pruning
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
                    
                    if f in excluded_files or abs_path in excluded_files: continue
                    if gitignore_spec and gitignore_spec.match_file(os.path.normpath(rel_path)): continue
                    if self._is_binary(abs_path): continue

                    include = True
                    if use_include_mode:
                        include = False
                        if included_files and (f in included_files or abs_path in included_files):
                            include = True
                        elif included_dirs:
                            include = True # Parent dir check already passed if we got here
                    
                    if include:
                        found_items.append((rel_path, abs_path))

            def update_ui():
                for rel, abs_p in found_items:
                    self.preview_files[abs_p] = True
                    self.tree.insert("", tk.END, values=("☑", rel), tags=(abs_p,))
                
                self.scan_button.config(state=tk.NORMAL, text="Scan Project")
                self.update_status_message(f"Scan complete. Found {len(found_items)} files.")
            
            self.master.after(0, update_ui)

        threading.Thread(target=scan_worker, daemon=True).start()

    def on_tree_click(self, event):
        """Handles checkbox toggling in the Treeview."""
        item_id = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        
        if item_id and column == "#1": # Clicking the 'Include' column
            tags = self.tree.item(item_id, "tags")
            if not tags: return
            abs_path = tags[0]
            
            # Toggle state
            is_checked = not self.preview_files.get(abs_path, True)
            self.preview_files[abs_path] = is_checked
            
            # Update UI
            new_val = "☑" if is_checked else "☐"
            current_values = list(self.tree.item(item_id, "values"))
            current_values[0] = new_val
            self.tree.item(item_id, values=tuple(current_values))

    def _load_gitignore_spec(self, root_dir):
        """Attempts to load .gitignore patterns from root directory."""
        if not pathspec:
            return None
        
        gitignore_path = os.path.join(root_dir, '.gitignore')
        if os.path.exists(gitignore_path):
            try:
                with open(gitignore_path, 'r', encoding='utf-8') as f:
                    spec = pathspec.PathSpec.from_lines('gitwildmatch', f)
                return spec
            except Exception as e:
                self.update_status_message(f"Warning: Failed to parse .gitignore: {e}")
        return None

    def start_combination(self):
        """Triggers the file combination process in a background thread."""
        self.save_config() # Auto-save current settings before starting
        root_dir = self.root_dir_var.get().strip()
        output_full_path = self.output_full_path_var.get().strip()

        if not root_dir or not os.path.isdir(root_dir):
            messagebox.showerror("Config Error", "Please select a valid project root directory.")
            return

        if not output_full_path:
            messagebox.showerror("Config Error", "Please specify a destination file path.")
            return

        # Clear previous log
        self.status_text.config(state=tk.NORMAL)
        self.status_text.delete(1.0, tk.END) 
        self.status_text.config(state=tk.DISABLED)
        self.update_status_message(">>> Initialization complete. Starting worker thread...")

        # Visual Feedback
        self.combine_button.config(state=tk.DISABLED, text="⌛ PROCESSING FILES...", bg=self.colors["border"])
        self.copy_button.config(state=tk.DISABLED)
        
        # Run in background
        thread = threading.Thread(target=self._run_combination_logic)
        thread.daemon = True
        thread.start()

    def _run_combination_logic(self):
        """Background logic for file combination."""
        root_dir = self.root_dir_var.get()
        output_full_path = self.output_full_path_var.get()
        
        excluded_dirs = [d.strip() for d in self.excluded_dirs_var.get().split(',') if d.strip()]
        excluded_files = [f.strip() for f in self.excluded_files_var.get().split(',') if f.strip()]
        included_dirs = [d.strip() for d in self.included_dirs_var.get().split(',') if d.strip()]
        included_files = [f.strip() for f in self.included_files_var.get().split(',') if f.strip()]

        gitignore_spec = self._load_gitignore_spec(root_dir)
        if gitignore_spec:
            self.update_status_message(">>> Applied .gitignore patterns for filtering.")

        try:
            # Pass the manual selection map (from the Checklist tab) if it's been populated
            manual_map = self.preview_files if self.preview_files else None
            
            success = combine_files_to_single_file_gui(
                root_dir, 
                output_full_path, 
                excluded_dirs, 
                excluded_files, 
                included_dirs, 
                included_files,
                self.update_status_message,
                gitignore_spec=gitignore_spec,
                manual_selection_map=manual_map
            )

            def finalize():
                if success:
                    self.copy_button.config(state=tk.NORMAL)
                    messagebox.showinfo("Success", f"Files combined successfully into:\n{output_full_path}")
                else:
                    messagebox.showerror("Failed", "File combination failed. Check the log for details.")
                self.combine_button.config(state=tk.NORMAL, text="START MERGING PROJECT FILES", bg=self.colors["button_bg"])

            self.master.after(0, finalize)
        except Exception as e:
            def handle_error():
                messagebox.showerror("Unexpected Error", f"An unexpected error occurred: {e}")
                self.update_status_message(f"An unexpected error occurred: {e}")
                self.combine_button.config(state=tk.NORMAL, text="COMBINE ALL SELECTED FILES", bg=self.colors["button_bg"])
            self.master.after(0, handle_error)


if __name__ == "__main__":
    # Enable High DPI awareness on Windows
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = tk.Tk()
    # Set a minimum window size to ensure UI remains usable
    root.minsize(800, 600)
    app = FileCombinerApp(root)
    root.mainloop()