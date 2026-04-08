import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import os
import sys
import threading
from pathlib import Path

# --- Core Logic (now with optional include functionality) ---
def combine_files_to_single_file_gui(root_dir, output_full_path, 
                                     excluded_dirs_list, excluded_files_list,
                                     included_dirs_list, included_files_list, # New parameters
                                     status_callback):
    """
    Combines the content of all files in a directory into a single file,
    optionally including only specified directories/files, or excluding specified
    directories and files, and provides status updates via a callback.

    Args:
        root_dir (str): The root directory of the project.
        output_full_path (str): The full path including filename for the output file.
        excluded_dirs_list (list): A list of directory names to exclude (ignored if include lists are used).
        excluded_files_list (list): A list of filenames to exclude (ignored if include lists are used).
        included_dirs_list (list): A list of directory names to explicitly include.
        included_files_list (list): A list of filenames to explicitly include.
        status_callback (callable): A function to call with status messages.
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

                if use_include_mode:
                    # If specific files are included, only take those
                    if included_files_set:
                        if filename in included_files_set or abs_file_path in included_files_set:
                            files_to_process.append(filename)
                        # We removed the log here to prevent UI lag
                    # If no specific files but included_dirs are defined, take all files in an included/relevant dir
                    elif included_dirs_set:
                        files_to_process.append(filename)
                else: 
                    # Not in include mode, all non-excluded files are included
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

        # 3. Footer Section (Fixed at bottom)
        self.footer_outer = tk.Frame(self.master, bg=c["bg"], padx=30, pady=20)
        self.footer_outer.grid(row=2, column=0, sticky="ew")
        
        self.combine_button = tk.Button(self.footer_outer, text="START MERGING PROJECT FILES", command=self.start_combination, 
                                        font=('Segoe UI Bold', 12), bg=c["button_bg"], fg=c["button_fg"], 
                                        activebackground=c["accent"], activeforeground='white',
                                        relief=tk.FLAT, cursor="hand2", pady=15)
        self.combine_button.pack(fill=tk.X, pady=(0, 20))

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
            self.update_status_message(f"Source and destination updated to: {directory}")

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

    def _is_binary(self, file_path):
        """Checks if a file is likely binary by looking for null bytes in first 1024 bytes."""
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                return b'\x00' in chunk
        except Exception:
            return True

    def perform_search(self):
        """Searches through file contents in root_dir for the keyword using Pathlib."""
        query = self.search_query_var.get().strip().lower()
        root_path = Path(self.root_dir_var.get())
        
        if not query:
            messagebox.showwarning("Search", "Please enter a search keyword.")
            return
        if not root_path.is_dir():
            messagebox.showerror("Error", "Invalid root directory for search.")
            return

        self.update_status_message(f"Searching for '{query}' in {root_path}...")
        self.search_results_listbox.delete(0, tk.END)
        
        excluded_dirs = set(d.strip() for d in self.excluded_dirs_var.get().split(',') if d.strip())

        def search_worker():
            matches = []
            try:
                for file_path in root_path.rglob('*'):
                    if not file_path.is_file():
                        continue
                    
                    # Check if any parent dir is excluded
                    if any(part in excluded_dirs for part in file_path.parts):
                        continue

                    if self._is_binary(file_path):
                        continue

                    try:
                        if query in file_path.read_text(encoding='utf-8', errors='ignore').lower():
                            matches.append(str(file_path.absolute()))
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

    def start_combination(self):
        """Triggers the file combination process in a background thread."""
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

        try:
            success = combine_files_to_single_file_gui(
                root_dir, 
                output_full_path, 
                excluded_dirs, 
                excluded_files, 
                included_dirs, 
                included_files,
                self.update_status_message
            )

            def finalize():
                if success:
                    messagebox.showinfo("Success", f"Files combined successfully into:\n{output_full_path}")
                else:
                    messagebox.showerror("Failed", "File combination failed. Check the log for details.")
                self.combine_button.config(state=tk.NORMAL, text="COMBINE ALL SELECTED FILES", bg=self.colors["button_bg"])

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