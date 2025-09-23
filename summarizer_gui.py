import os
import ast
import re
import tkinter as tk
from tkinter import filedialog, messagebox

# -------------------------
# Summarizers
# -------------------------
def summarize_python_code(filepath, code):
    try:
        tree = ast.parse(code)
    except Exception:
        return "⚠️ Could not parse (syntax error)"

    classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    funcs = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    imports = [
        node.names[0].name if isinstance(node, (ast.Import, ast.ImportFrom)) and node.names
        else str(node.module)
        for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    
    summary = []
    if imports: summary.append(f"Imports: {', '.join(set(imports))}")
    if classes: summary.append(f"Classes: {', '.join(classes)}")
    if funcs: summary.append(f"Functions: {', '.join(funcs)}")
    
    return "\n".join(summary) if summary else "No significant structures found."

def summarize_js_code(filepath, code):
    imports = re.findall(r"import .* from ['\"](.*)['\"]", code)
    funcs = re.findall(r"function (\w+)|(\w+) ?= ?\([^)]*\) ?=>", code)
    classes = re.findall(r"class (\w+)", code)

    funcs = [f[0] or f[1] for f in funcs]  # flatten regex results
    
    summary = []
    if imports: summary.append(f"Imports: {', '.join(set(imports))}")
    if classes: summary.append(f"Classes: {', '.join(classes)}")
    if funcs: summary.append(f"Functions: {', '.join(funcs)}")

    return "\n".join(summary) if summary else "No significant structures found."

def summarize_text(filepath, code):
    lines = code.splitlines()
    return f"Total lines: {len(lines)} | Approx size: {len(code)//1024} KB"

# -------------------------
# Main summarizer
# -------------------------
def summarize_file(filepath):
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        code = f.read()

    if filepath.endswith(".py"):
        return summarize_python_code(filepath, code)
    elif filepath.endswith((".js", ".ts", ".jsx", ".tsx")):
        return summarize_js_code(filepath, code)
    else:
        return summarize_text(filepath, code)

def generate_summary(project_dir, output_path):
    with open(output_path, "w", encoding="utf-8") as out:
        for root, dirs, files in os.walk(project_dir):
            # skip heavy/unnecessary dirs
            dirs[:] = [d for d in dirs if d not in ("node_modules", "__pycache__", ".git", "dist", "build")]

            for file in files:
                if file.startswith(".") or file.endswith((".lock", ".min.js")):
                    continue
                filepath = os.path.join(root, file)
                try:
                    summary = summarize_file(filepath)
                except Exception as e:
                    summary = f"⚠️ Error: {e}"
                out.write(f"\n📂 {filepath}\n{summary}\n{'-'*60}\n")
    return output_path

# -------------------------
# GUI app
# -------------------------
def main():
    root = tk.Tk()
    root.withdraw()  # hide main window

    # Ask for input folder
    folder = filedialog.askdirectory(title="Select your project folder to summarize")
    if not folder:
        messagebox.showinfo("Cancelled", "No project folder selected.")
        return

    # Ask for output folder
    out_folder = filedialog.askdirectory(title="Select output folder for summary file")
    if not out_folder:
        messagebox.showinfo("Cancelled", "No output folder selected.")
        return

    output_file = os.path.join(out_folder, "code_summary.txt")

    try:
        generate_summary(folder, output_file)
        messagebox.showinfo("Done ✅", f"Summary saved to:\n{output_file}")
    except Exception as e:
        messagebox.showerror("Error ❌", str(e))

if __name__ == "__main__":
    main()
