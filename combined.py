import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os
import sys

# --- Core Logic (unchanged, still uses the lists passed) ---
def combine_files_to_single_file_gui(root_dir, output_full_path, excluded_dirs_list, excluded_files_list, status_callback):
    """
    Combines the content of all files in a directory into a single file,
    excluding specified directories and files, and provides status updates via a callback.

    Args:
        root_dir (str): The root directory of the project.
        output_full_path (str): The full path including filename for the output file.
        excluded_dirs_list (list): A list of directory names to exclude.
        excluded_files_list (list): A list of filenames to exclude.
        status_callback (callable): A function to call with status messages.
    """
    combined_content = []

    status_callback(f"Starting to combine files from: {root_dir}")
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

    try:
        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Modify dirnames in-place to skip excluded directories
            # Filter based on basename, as excluded_dirs_list contains only names
            dirnames[:] = [d for d in dirnames if d not in excluded_dirs_list]

            for filename in filenames:
                # Filter based on basename, as excluded_files_list contains only names
                if filename in excluded_files_list:
                    status_callback(f"Skipping excluded file: {os.path.join(dirpath, filename)}")
                    continue

                file_path = os.path.join(dirpath, filename)
                # Make path relative to root_dir for the header
                relative_file_path = os.path.relpath(file_path, root_dir)

                # Skip symbolic links to avoid infinite loops or errors
                if os.path.islink(file_path):
                    status_callback(f"Skipping symbolic link: {relative_file_path}")
                    continue

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
    def __init__(self, master):
        self.master = master
        master.title("Project File Combiner")
        
        # Set a default size for the window, allowing resizing
        master.geometry("900x650") # Slightly wider to accommodate new buttons
        master.resizable(True, True)

        # Variables
        self.root_dir_var = tk.StringVar(value=os.getcwd()) # Default to current dir
        self.output_full_path_var = tk.StringVar(value=os.path.join(os.getcwd(), "combined_project_files.txt"))
        self.excluded_dirs_var = tk.StringVar(
            value="node_modules, .git, .vscode, .idea, dist, build, venv, __pycache__, .DS_Store"
        )
        self.excluded_files_var = tk.StringVar(
            value="package-lock.json, yarn.lock, bun.lockb, .env, .DS_Store, Thumbs.db, pyproject.toml"
        )

        self.create_widgets()

    def create_widgets(self):
        # Frame for inputs
        input_frame = tk.Frame(self.master, padx=10, pady=10)
        input_frame.pack(fill=tk.X)

        # Configure grid column weights so the Entry fields expand
        input_frame.grid_columnconfigure(1, weight=1)

        # Project Root Directory
        tk.Label(input_frame, text="1. Project Root Directory:").grid(row=0, column=0, sticky=tk.W, pady=2)
        tk.Entry(input_frame, textvariable=self.root_dir_var, width=70).grid(row=0, column=1, pady=2, padx=5, sticky=tk.EW)
        tk.Button(input_frame, text="Browse...", command=self.browse_root_dir).grid(row=0, column=2, pady=2, padx=5)

        # Output File Location
        tk.Label(input_frame, text="2. Output File Path:").grid(row=1, column=0, sticky=tk.W, pady=2)
        tk.Entry(input_frame, textvariable=self.output_full_path_var, width=70).grid(row=1, column=1, pady=2, padx=5, sticky=tk.EW)
        tk.Button(input_frame, text="Browse...", command=self.browse_output_file).grid(row=1, column=2, pady=2, padx=5)

        # Excluded Directories
        tk.Label(input_frame, text="3. Exclude Directories (comma-separated):").grid(row=2, column=0, sticky=tk.W, pady=2)
        entry_excluded_dirs = tk.Entry(input_frame, textvariable=self.excluded_dirs_var, width=70)
        entry_excluded_dirs.grid(row=2, column=1, pady=2, padx=5, sticky=tk.EW)
        tk.Button(input_frame, text="Add Dir...", command=self.browse_excluded_dirs).grid(row=2, column=2, pady=2, padx=5)
        # Added a helpful label
        tk.Label(input_frame, text="e.g., node_modules, .git", fg="gray").grid(row=2, column=3, sticky=tk.W, padx=5)


        # Excluded Files
        tk.Label(input_frame, text="4. Exclude Files (comma-separated):").grid(row=3, column=0, sticky=tk.W, pady=2)
        entry_excluded_files = tk.Entry(input_frame, textvariable=self.excluded_files_var, width=70)
        entry_excluded_files.grid(row=3, column=1, pady=2, padx=5, sticky=tk.EW)
        tk.Button(input_frame, text="Add File...", command=self.browse_excluded_files).grid(row=3, column=2, pady=2, padx=5)
        # Added a helpful label
        tk.Label(input_frame, text="e.g., package-lock.json, .env", fg="gray").grid(row=3, column=3, sticky=tk.W, padx=5)


        # Combine Button
        self.combine_button = tk.Button(self.master, text="Combine Files", command=self.start_combination, 
                                        font=('Arial', 12, 'bold'), bg='lightblue', fg='black')
        self.combine_button.pack(pady=15)

        # Status Output
        tk.Label(self.master, text="Status/Log:").pack(anchor=tk.W, padx=10, pady=(0,5))
        self.status_text = scrolledtext.ScrolledText(self.master, wrap=tk.WORD, height=15)
        self.status_text.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        self.status_text.config(state=tk.DISABLED) # Make it read-only

    def update_status_message(self, message):
        """Appends a message to the status log and scrolls to the end."""
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.yview(tk.END) # Auto-scroll to bottom
        self.status_text.config(state=tk.DISABLED)
        self.master.update_idletasks() # Refresh the GUI immediately

    def _add_to_comma_separated_list(self, current_var, new_items):
        """Helper to add new items to a comma-separated StringVar, handling duplicates."""
        current_list = [item.strip() for item in current_var.get().split(',') if item.strip()]
        for item in new_items:
            if item not in current_list:
                current_list.append(item)
        # Sort for consistent display and re-join
        current_var.set(', '.join(sorted(current_list)))

    def browse_root_dir(self):
        """Opens a directory dialog for selecting the project root."""
        directory = filedialog.askdirectory(
            initialdir=self.root_dir_var.get() if os.path.isdir(self.root_dir_var.get()) else os.getcwd(),
            title="Select Project Root Directory"
        )
        if directory:
            self.root_dir_var.set(directory)

    def browse_output_file(self):
        """Opens a file save dialog for specifying the output file."""
        # Get default filename from current output path variable
        current_output_path = self.output_full_path_var.get()
        default_filename = os.path.basename(current_output_path)
        default_initialdir = os.path.dirname(current_output_path)
        
        # Ensure default_initialdir is a valid directory, otherwise use CWD
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
            title="Select Directory to Exclude"
        )
        if selected_path:
            dir_name = os.path.basename(selected_path)
            self._add_to_comma_separated_list(self.excluded_dirs_var, [dir_name])
            self.update_status_message(f"Added directory '{dir_name}' to exclusion list.")

    def browse_excluded_files(self):
        """Opens a file dialog to select files to exclude."""
        root_dir = self.root_dir_var.get()
        initial_dir = root_dir if os.path.isdir(root_dir) else os.getcwd()
        selected_paths = filedialog.askopenfilenames(
            initialdir=initial_dir,
            title="Select Files to Exclude"
        )
        if selected_paths:
            file_names = [os.path.basename(p) for p in selected_paths]
            self._add_to_comma_separated_list(self.excluded_files_var, file_names)
            self.update_status_message(f"Added files {', '.join(file_names)} to exclusion list.")

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

        # Convert comma-separated strings to lists, stripping whitespace
        excluded_dirs = [d.strip() for d in excluded_dirs_str.split(',') if d.strip()]
        excluded_files = [f.strip() for f in excluded_files_str.split(',') if f.strip()]

        if not root_dir:
            messagebox.showerror("Error", "Please select a project root directory.")
            self.update_status_message("Error: Project root directory not selected.")
            return

        if not output_full_path:
            messagebox.showerror("Error", "Please specify an output file path.")
            self.update_status_message("Error: Output file path not specified.")
            return
        
        # Disable button during processing
        self.combine_button.config(state=tk.DISABLED, text="Processing...")
        
        # Run the core logic
        try:
            success = combine_files_to_single_file_gui(
                root_dir, 
                output_full_path, 
                excluded_dirs, 
                excluded_files, 
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
            self.combine_button.config(state=tk.NORMAL, text="Combine Files")


if __name__ == "__main__":
    root = tk.Tk()
    app = FileCombinerApp(root)
    root.mainloop()
