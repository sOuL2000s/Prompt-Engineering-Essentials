import tkinter as tk
from tkinter import filedialog, messagebox
import os

def split_text_file(input_file, output_prefix="output", lines_per_file=500):
    """
    Divides a text file into smaller files, each with a specified number of lines
    and a part number header at the top.
    """
    try:
        # The fix is here: specify 'encoding="utf-8"'
        with open(input_file, 'r', encoding="utf-8") as infile:
            lines = infile.readlines()
            total_lines = len(lines)
            
            # Calculate the number of files needed
            num_files = (total_lines + lines_per_file - 1) // lines_per_file

            # Create a directory to store the output files
            output_dir = f"{output_prefix}_split_files"
            os.makedirs(output_dir, exist_ok=True)
            
            print(f"Total lines found: {total_lines}")
            print(f"Splitting into {num_files} files in the '{output_dir}' directory.")
            print("-" * 30)

            for i in range(num_files):
                start_index = i * lines_per_file
                end_index = min((i + 1) * lines_per_file, total_lines)
                
                # Create the output filename inside the new directory
                output_file = os.path.join(output_dir, f"{output_prefix}_{i+1}.txt")
                
                # And here: specify 'encoding="utf-8"' for the output files as well
                with open(output_file, 'w', encoding="utf-8") as outfile:
                    # Write the part number header
                    header = f"--- Part {i+1}/{num_files} ---\n"
                    outfile.write(header)
                    
                    # Write the lines from the original file
                    outfile.writelines(lines[start_index:end_index])
                
                print(f"Created file: {output_file} with lines from {start_index + 1} to {end_index}")
            
            messagebox.showinfo("Success", f"File splitting complete!\nCheck the '{output_dir}' folder.")

    except FileNotFoundError:
        messagebox.showerror("Error", f"The file '{input_file}' was not found.")
    except Exception as e:
        # This will now catch the UnicodeDecodeError and display the specific error
        messagebox.showerror("An Error Occurred", f"An unexpected error occurred: {e}")

# --- GUI CODE ---
def browse_and_split():
    """
    Opens a file dialog for the user to select a text file and then calls the
    splitting function.
    """
    root.withdraw()
    
    file_path = filedialog.askopenfilename(
        title="Select a Text File to Split",
        filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
    )
    
    if file_path:
        filename = os.path.basename(file_path)
        filename_prefix = os.path.splitext(filename)[0]
        split_text_file(file_path, output_prefix=filename_prefix, lines_per_file=500)
    else:
        messagebox.showinfo("Cancelled", "File selection was cancelled.")
    
    root.destroy()

root = tk.Tk()
root.title("Text File Splitter")
browse_button = tk.Button(root, text="Browse for a File to Split", command=browse_and_split)
browse_button.pack(padx=20, pady=20)
root.mainloop()