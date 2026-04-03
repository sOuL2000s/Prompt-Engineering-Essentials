import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import os
import sys

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
            "bg": "#f9f9f9",
            "fg": "#202020",
            "frame_bg": "#ffffff",
            "entry_bg": "#ffffff",
            "button_bg": "#0078d4",
            "button_fg": "#ffffff",
            "log_bg": "#ffffff",
            "log_fg": "#333333",
            "accent": "#0078d4",
            "border": "#dddddd"
        },
        "dark": {
            "bg": "#1e1e1e",
            "fg": "#e0e0e0",
            "frame_bg": "#2d2d2d",
            "entry_bg": "#3d3d3d",
            "button_bg": "#0078d4",
            "button_fg": "#ffffff",
            "log_bg": "#121212",
            "log_fg": "#cccccc",
            "accent": "#47a1ff",
            "border": "#444444"
        }
    }

    def __init__(self, master):
        self.master = master
        master.title("Project File Combiner")
        
        self.current_theme = "light"
        self.colors = self.THEMES[self.current_theme]

        # Modern sizing
        master.geometry("1000x950") 
        master.resizable(True, True)
        master.configure(bg=self.colors["bg"])

        # Variables
        self.root_dir_var = tk.StringVar(value=os.getcwd()) # Default to current dir
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

        self.create_widgets()

    def setup_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.apply_theme_styles()

    def apply_theme_styles(self):
        c = self.colors
        self.style.configure("TFrame", background=c["bg"])
        self.style.configure("TLabelframe", background=c["bg"], foreground=c["fg"])
        self.style.configure("TLabelframe.Label", background=c["bg"], foreground=c["accent"], font=('Segoe UI Semibold', 10))
        self.style.configure("TLabel", background=c["bg"], foreground=c["fg"], font=('Segoe UI', 9))
        self.style.configure("TEntry", fieldbackground=c["entry_bg"], foreground=c["fg"], insertcolor=c["fg"])
        self.style.configure('Browse.TButton', font=('Segoe UI', 9), padding=5)
        self.style.map('Browse.TButton',
            background=[('active', c["accent"]), ('!disabled', c["frame_bg"])],
            foreground=[('active', '#ffffff'), ('!disabled', c["fg"])]
        )
        self.style.configure("TSeparator", background=c["border"])

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
        self.footer_frame.configure(bg=c["bg"])
        self.search_results_listbox.configure(bg=c["log_bg"], fg=c["log_fg"], selectbackground=c["accent"])
        self.result_container.configure(highlightbackground=c["border"], bg=c["log_bg"])
        self.status_text.configure(bg=c["log_bg"], fg=c["log_fg"])
        self.combine_button.configure(bg=c["button_bg"], fg=c["button_fg"])
        self.theme_btn.configure(text="🌙 Dark Mode" if self.current_theme == "light" else "☀️ Light Mode", 
                                 bg=c["frame_bg"], fg=c["fg"])

    def create_widgets(self):
        self.setup_styles()
        c = self.colors
        
        # Main Layout
        self.main_container = tk.Frame(self.master, bg=c["bg"], padx=25, pady=10)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # Header
        self.header_frame = tk.Frame(self.main_container, bg=c["bg"])
        self.header_frame.pack(fill=tk.X, pady=(0, 10))
        
        title_lbl = tk.Label(self.header_frame, text="Project File Combiner", 
                            font=('Segoe UI Semibold', 16), bg=c["bg"], fg=c["accent"])
        title_lbl.pack(side=tk.LEFT)
        
        self.theme_btn = tk.Button(self.header_frame, text="🌙 Dark Mode" if self.current_theme == "light" else "☀️ Light Mode",
                                  command=self.toggle_theme, relief=tk.FLAT, cursor="hand2",
                                  bg=c["frame_bg"], fg=c["fg"], font=('Segoe UI', 9))
        self.theme_btn.pack(side=tk.RIGHT)

        # --- Section 1: Configuration ---
        config_frame = ttk.LabelFrame(self.main_container, text=" Configuration ", padding=(15, 10))
        config_frame.pack(fill=tk.X, pady=(0, 10))
        config_frame.columnconfigure(1, weight=1)

        ttk.Label(config_frame, text="Project Root:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(config_frame, textvariable=self.root_dir_var).grid(row=0, column=1, pady=5, padx=(10, 5), sticky=tk.EW)
        ttk.Button(config_frame, text="Browse", style='Browse.TButton', command=self.browse_root_dir, width=12).grid(row=0, column=2, pady=5)

        ttk.Label(config_frame, text="Output Path:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(config_frame, textvariable=self.output_full_path_var).grid(row=1, column=1, pady=5, padx=(10, 5), sticky=tk.EW)
        ttk.Button(config_frame, text="Browse", style='Browse.TButton', command=self.browse_output_file, width=12).grid(row=1, column=2, pady=5)

        # --- Section 2: Filters ---
        filters_frame = ttk.LabelFrame(self.main_container, text=" Inclusion & Exclusion Filters ", padding=(15, 10))
        filters_frame.pack(fill=tk.X, pady=10)
        filters_frame.columnconfigure(1, weight=1)

        # Inclusions
        ttk.Label(filters_frame, text="Include Dirs:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(filters_frame, textvariable=self.included_dirs_var).grid(row=0, column=1, pady=2, padx=(10, 5), sticky=tk.EW)
        ttk.Button(filters_frame, text="+ Directory", style='Browse.TButton', command=self.browse_included_dirs, width=12).grid(row=0, column=2, pady=2)

        ttk.Label(filters_frame, text="Include Files:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(filters_frame, textvariable=self.included_files_var).grid(row=1, column=1, pady=2, padx=(10, 5), sticky=tk.EW)
        ttk.Button(filters_frame, text="+ File", style='Browse.TButton', command=self.browse_included_files, width=12).grid(row=1, column=2, pady=2)

        ttk.Separator(filters_frame, orient='horizontal').grid(row=2, column=0, columnspan=3, sticky='ew', pady=12)

        # Exclusions
        ttk.Label(filters_frame, text="Exclude Dirs:").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(filters_frame, textvariable=self.excluded_dirs_var).grid(row=3, column=1, pady=2, padx=(10, 5), sticky=tk.EW)
        ttk.Button(filters_frame, text="+ Directory", style='Browse.TButton', command=self.browse_excluded_dirs, width=12).grid(row=3, column=2, pady=2)

        ttk.Label(filters_frame, text="Exclude Files:").grid(row=4, column=0, sticky=tk.W, pady=2)
        ttk.Entry(filters_frame, textvariable=self.excluded_files_var).grid(row=4, column=1, pady=2, padx=(10, 5), sticky=tk.EW)
        ttk.Button(filters_frame, text="+ File", style='Browse.TButton', command=self.browse_excluded_files, width=12).grid(row=4, column=2, pady=2)

        # --- Section 3: Search ---
        search_frame = ttk.LabelFrame(self.main_container, text=" Content-Based File Search ", padding=(15, 10))
        search_frame.pack(fill=tk.X, pady=10)
        search_frame.columnconfigure(1, weight=1)

        ttk.Label(search_frame, text="Search Query:").grid(row=0, column=0, sticky=tk.W)
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_query_var)
        self.search_entry.grid(row=0, column=1, padx=(10, 5), sticky=tk.EW)
        ttk.Button(search_frame, text="Run Search", style='Browse.TButton', command=self.perform_search, width=12).grid(row=0, column=2)

        self.result_container = tk.Frame(search_frame, bg=c["log_bg"], bd=1, highlightthickness=1, highlightbackground=c["border"])
        self.result_container.grid(row=1, column=0, columnspan=3, sticky=tk.NSEW, pady=(10, 5))
        
        self.search_results_listbox = tk.Listbox(self.result_container, selectmode=tk.MULTIPLE, height=5, 
                                                font=('Consolas', 9), bd=0, highlightthickness=0,
                                                bg=c["log_bg"], fg=c["log_fg"], selectbackground=c["accent"])
        self.search_results_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(self.result_container, orient=tk.VERTICAL, command=self.search_results_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.search_results_listbox.config(yscrollcommand=scrollbar.set)

        ttk.Button(search_frame, text="Add Selected to Inclusion List", style='Browse.TButton', 
                   command=self.add_search_results_to_included).grid(row=2, column=0, columnspan=3, pady=(5,0))

        # --- Section 4: Action & Log ---
        self.footer_frame = tk.Frame(self.main_container, bg=c["bg"])
        self.footer_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.combine_button = tk.Button(self.footer_frame, text="COMBINE ALL SELECTED FILES", command=self.start_combination, 
                                        font=('Segoe UI Semibold', 11), bg=c["button_bg"], fg=c["button_fg"], 
                                        activebackground=c["accent"], activeforeground='white',
                                        relief=tk.FLAT, cursor="hand2", padx=30, pady=10)
        self.combine_button.pack(pady=(0, 15))

        ttk.Label(self.footer_frame, text="Execution Log", font=('Segoe UI Semibold', 10)).pack(anchor=tk.W, pady=(5,2))
        self.status_text = scrolledtext.ScrolledText(self.footer_frame, wrap=tk.WORD, height=10, 
                                                     font=('Consolas', 9), bg=c["log_bg"], fg=c["log_fg"],
                                                     relief=tk.FLAT, bd=0)
        self.status_text.pack(fill=tk.BOTH, expand=True)
        self.status_text.config(state=tk.DISABLED)

    def update_status_message(self, message):
        """Appends a message to the status log and scrolls to the end."""
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.yview(tk.END) # Auto-scroll to bottom
        self.status_text.config(state=tk.DISABLED)
        self.master.update_idletasks() # Refresh the GUI immediately

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

    def perform_search(self):
        """Searches through file contents in root_dir for the keyword."""
        query = self.search_query_var.get().strip()
        root_dir = self.root_dir_var.get()
        
        if not query:
            messagebox.showwarning("Search", "Please enter a search keyword.")
            return
        if not os.path.isdir(root_dir):
            messagebox.showerror("Error", "Invalid root directory for search.")
            return

        self.update_status_message(f"Searching for '{query}' in {root_dir}...")
        self.search_results_listbox.delete(0, tk.END)
        
        # Get exclusions to avoid searching unwanted dirs
        excluded_dirs = [d.strip() for d in self.excluded_dirs_var.get().split(',') if d.strip()]
        excluded_dirs_set = set(excluded_dirs)

        matches = []
        try:
            for dp, dn, filenames in os.walk(root_dir):
                dn[:] = [d for d in dn if d not in excluded_dirs_set]
                for f in filenames:
                    fp = os.path.join(dp, f)
                    try:
                        with open(fp, 'r', encoding='utf-8', errors='ignore') as file:
                            if query.lower() in file.read().lower():
                                matches.append(os.path.abspath(fp))
                    except Exception:
                        continue
            
            if matches:
                for match in matches:
                    self.search_results_listbox.insert(tk.END, match)
                self.update_status_message(f"Found {len(matches)} files containing '{query}'.")
            else:
                self.update_status_message(f"No matches found for '{query}'.")
                messagebox.showinfo("Search", "No matches found.")
        except Exception as e:
            self.update_status_message(f"Search error: {e}")

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
        """Triggers the file combination process."""
        # Clear previous log
        self.status_text.config(state=tk.NORMAL)
        self.status_text.delete(1.0, tk.END) 
        self.status_text.config(state=tk.DISABLED)
        self.update_status_message("Starting file combination process...")

        root_dir = self.root_dir_var.get()
        output_full_path = self.output_full_path_var.get()
        
        excluded_dirs_str = self.excluded_dirs_var.get()
        excluded_files_str = self.excluded_files_var.get()
        
        included_dirs_str = self.included_dirs_var.get() # NEW
        included_files_str = self.included_files_var.get() # NEW

        # Convert comma-separated strings to lists, stripping whitespace
        excluded_dirs = [d.strip() for d in excluded_dirs_str.split(',') if d.strip()]
        excluded_files = [f.strip() for f in excluded_files_str.split(',') if f.strip()]
        
        included_dirs = [d.strip() for d in included_dirs_str.split(',') if d.strip()] # NEW
        included_files = [f.strip() for f in included_files_str.split(',') if f.strip()] # NEW

        if not root_dir:
            messagebox.showerror("Error", "Please select a project root directory.")
            self.update_status_message("Error: Project root directory not selected.")
            return

        if not output_full_path:
            messagebox.showerror("Error", "Please specify an output file path.")
            self.update_status_message("Error: Output file path not specified.")
            return
        
        # Disable button during processing
        self.combine_button.config(state=tk.DISABLED, text="PROCESSING...", bg=self.colors["border"])
        
        # Run the core logic
        try:
            success = combine_files_to_single_file_gui(
                root_dir, 
                output_full_path, 
                excluded_dirs, 
                excluded_files, 
                included_dirs,  # Pass new parameters
                included_files, # Pass new parameters
                self.update_status_message
            )

            if success:
                messagebox.showinfo("Success", f"Files combined successfully into:\n{output_full_path}")
            else:
                messagebox.showerror("Failed", "File combination failed. Check the log for details.")
        except Exception as e:
            messagebox.showerror("Unexpected Error", f"An unexpected error occurred: {e}")
            self.update_status_message(f"An unexpected error occurred: {e}")
        finally:
            # Re-enable button
            self.combine_button.config(state=tk.NORMAL, text="COMBINE ALL SELECTED FILES", bg=self.colors["button_bg"])


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