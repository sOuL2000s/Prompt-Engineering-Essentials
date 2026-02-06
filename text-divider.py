import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import os
import threading

class TextDividerApp:
    def __init__(self, master):
        self.master = master
        master.title("ShipWale Text File Divider")
        master.geometry("600x450")
        
        # Variables
        self.input_file_path = tk.StringVar()
        self.lines_per_part = tk.IntVar(value=10000)
        self.output_prefix = tk.StringVar(value="split_part_")
        self.output_directory = tk.StringVar(value=os.getcwd())

        # Setup UI
        self._setup_input_frame(master)
        self._setup_output_frame(master)
        self._setup_log_area(master)

        self.btn_split = tk.Button(master, text="Start Splitting", command=self.start_split_thread, font=('Arial', 12, 'bold'))
        self.btn_split.pack(pady=10, padx=10, fill='x')

    def _setup_input_frame(self, master):
        input_frame = tk.LabelFrame(master, text="Input Configuration", padx=10, pady=10)
        input_frame.pack(padx=10, pady=5, fill="x")

        # 1. Input File Selection
        tk.Label(input_frame, text="Input File:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        tk.Entry(input_frame, textvariable=self.input_file_path, width=50).grid(row=0, column=1, padx=5, pady=5)
        tk.Button(input_frame, text="Browse", command=self.select_input_file).grid(row=0, column=2, padx=5, pady=5)

        # 2. Lines Per Part
        tk.Label(input_frame, text="Lines per Part:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        tk.Entry(input_frame, textvariable=self.lines_per_part, width=15).grid(row=1, column=1, sticky='w', padx=5, pady=5)

        # 3. Output Prefix
        tk.Label(input_frame, text="Output Prefix:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        tk.Entry(input_frame, textvariable=self.output_prefix, width=50).grid(row=2, column=1, padx=5, pady=5)

    def _setup_output_frame(self, master):
        output_frame = tk.LabelFrame(master, text="Output Directory", padx=10, pady=10)
        output_frame.pack(padx=10, pady=5, fill="x")

        # Output Directory Selection
        tk.Label(output_frame, text="Output Folder:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        tk.Entry(output_frame, textvariable=self.output_directory, width=50).grid(row=0, column=1, padx=5, pady=5)
        tk.Button(output_frame, text="Select Folder", command=self.select_output_directory).grid(row=0, column=2, padx=5, pady=5)

    def _setup_log_area(self, master):
        log_frame = tk.LabelFrame(master, text="Status Log", padx=5, pady=5)
        log_frame.pack(padx=10, pady=5, fill="both", expand=True)

        self.log_widget = scrolledtext.ScrolledText(log_frame, state='disabled', height=8, wrap='word', font=('Courier', 9))
        self.log_widget.pack(fill='both', expand=True)

    def log(self, message):
        """Updates the log text widget."""
        self.log_widget.configure(state='normal')
        self.log_widget.insert(tk.END, message + "\n")
        self.log_widget.configure(state='disabled')
        self.log_widget.see(tk.END) # Scroll to the bottom

    def select_input_file(self):
        """Opens a file dialog for selecting the input file."""
        fpath = filedialog.askopenfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if fpath:
            self.input_file_path.set(fpath)

    def select_output_directory(self):
        """Opens a directory dialog for selecting the output folder."""
        dpath = filedialog.askdirectory()
        if dpath:
            self.output_directory.set(dpath)

    def start_split_thread(self):
        """Starts the heavy splitting process in a separate thread to keep the GUI responsive."""
        
        # Disable button during processing
        self.btn_split.config(state=tk.DISABLED, text="Processing...")
        self.log_widget.delete('1.0', tk.END) # Clear previous log

        # Get values
        input_path = self.input_file_path.get()
        output_dir = self.output_directory.get()
        output_prefix = self.output_prefix.get()
        
        try:
            lines_per_part = self.lines_per_part.get()
            if lines_per_part <= 0:
                raise ValueError("Lines per part must be a positive integer.")
        except tk.TclError:
            messagebox.showerror("Input Error", "Lines per part must be an integer.")
            self.btn_split.config(state=tk.NORMAL, text="Start Splitting")
            return

        if not input_path or not os.path.exists(input_path):
            messagebox.showerror("Input Error", "Please select a valid input file.")
            self.btn_split.config(state=tk.NORMAL, text="Start Splitting")
            return
        
        if not output_dir or not os.path.isdir(output_dir):
            messagebox.showerror("Input Error", "Please select a valid output directory.")
            self.btn_split.config(state=tk.NORMAL, text="Start Splitting")
            return

        # Start the worker thread
        thread = threading.Thread(target=self.split_file_task, 
                                  args=(input_path, lines_per_part, output_prefix, output_dir))
        thread.start()

    def split_file_task(self, input_path, lines_per_part, output_prefix, output_dir):
        """
        Core logic to divide a text file into multiple parts.
        Runs in a separate thread.
        """
        current_part = 1
        line_count = 0
        output_handle = None
        
        self.log(f"--- Starting Split ---")
        self.log(f"Source: {input_path}")
        self.log(f"Chunk Size: {lines_per_part} lines.")
        self.log(f"Destination: {output_dir}")

        try:
            with open(input_path, 'r', encoding='utf-8') as infile:
                for line in infile:
                    
                    # Check if we need to open a new file (first line or reached limit)
                    if line_count == 0:
                        if output_handle is not None:
                            output_handle.close()
                        
                        output_filename = f"{output_prefix}{current_part}.txt"
                        full_output_path = os.path.join(output_dir, output_filename)
                        
                        self.log(f"Writing part {current_part} to: {output_filename}")
                        output_handle = open(full_output_path, 'w', encoding='utf-8')

                    # Write the line
                    output_handle.write(line)
                    line_count += 1

                    # Check if the current file part is full
                    if line_count >= lines_per_part:
                        line_count = 0
                        current_part += 1
                
                # Close the last file handle if it was open
                if output_handle:
                    output_handle.close()

            self.log(f"--- Process completed successfully. Total parts created: {current_part} ---")
            messagebox.showinfo("Success", f"File splitting completed. {current_part} parts created.")

        except FileNotFoundError:
            error_msg = f"Error: Input file '{input_path}' not found."
            self.log(error_msg)
            messagebox.showerror("File Error", error_msg)
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}"
            self.log(error_msg)
            messagebox.showerror("Processing Error", error_msg)
        finally:
            # Re-enable the button when done (using self.master.after to ensure GUI update runs on the main thread)
            self.master.after(0, lambda: self.btn_split.config(state=tk.NORMAL, text="Start Splitting"))


if __name__ == "__main__":
    root = tk.Tk()
    app = TextDividerApp(root)
    root.mainloop()