import sys
import os
import math
import datetime
import threading
import pandas as pd
import psutil
import numpy as np

# PyQt5 imports
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTableWidget, QTableWidgetItem,
    QProgressBar, QTabWidget, QFileDialog, QMessageBox, QHeaderView,
    QTreeWidget, QTreeWidgetItem, QStyleFactory, QSizePolicy
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QTimer # Added QTimer for potential future use, not critical for this fix
from PyQt5.QtGui import QIcon, QColor

# Matplotlib integration for PyQt5
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# Ensure matplotlib uses a non-interactive backend by default for GUI
plt.switch_backend('Agg')

# --- Helper Function ---
def bytes_to_human_readable(num_bytes, suffix="B"):
    """
    Converts bytes to human-readable format (e.g., KB, MB, GB, TB).
    Handles potentially negative numbers gracefully.
    """
    if num_bytes == 0:
        return f"0 {suffix}"
    
    sign = -1 if num_bytes < 0 else 1
    abs_num_bytes = abs(num_bytes)
    
    if abs_num_bytes < 1: 
        return f"{num_bytes:.2f} {suffix}"

    unit_idx = int(math.floor(math.log(abs_num_bytes, 1024)))
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    
    if unit_idx >= len(units):
        unit_idx = len(units) - 1

    p = 1024 ** unit_idx
    value = (abs_num_bytes / p) * sign
    
    return f"{value:.2f} {units[unit_idx]}"

# --- Worker Threads for long-running tasks ---

class DiskScanWorker(QObject):
    finished = pyqtSignal(pd.DataFrame)
    error = pyqtSignal(str)

    def run(self):
        try:
            partitions = psutil.disk_partitions(all=False)
            disk_data = []

            for p in partitions:
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    
                    volume_name = "N/A"
                    if sys.platform == "win32":
                        try:
                            import win32api
                            volume_name = win32api.GetVolumeInformation(p.mountpoint)[0]
                            if not volume_name:
                                volume_name = p.mountpoint.strip(':\\')
                        except ImportError:
                            volume_name = "Install 'pywin32' for volume names"
                        except Exception as e:
                            volume_name = f"Error: {e}"

                    disk_info = {
                        "Device": p.device,
                        "Mountpoint": p.mountpoint,
                        "Filesystem Type": p.fstype,
                        "Opts": p.opts,
                        "Volume Name": volume_name,
                        "Total Size (Bytes)": usage.total,
                        "Used Space (Bytes)": usage.used,
                        "Free Space (Bytes)": usage.free,
                        "Used (%)": usage.percent,
                        "Total Size (Human)": bytes_to_human_readable(usage.total),
                        "Used Space (Human)": bytes_to_human_readable(usage.used),
                        "Free Space (Human)": bytes_to_human_readable(usage.free),
                    }
                    disk_data.append(disk_info)
                except Exception as e:
                    disk_data.append({
                        "Device": p.device, "Mountpoint": p.mountpoint, "Filesystem Type": p.fstype, "Opts": p.opts,
                        "Volume Name": "N/A", "Total Size (Bytes)": 0, "Used Space (Bytes)": 0, "Free Space (Bytes)": 0,
                        "Used (%)": 0.0, "Total Size (Human)": "N/A", "Used Space (Human)": "N/A", "Free Space (Human)": "N/A"
                    })
            self.finished.emit(pd.DataFrame(disk_data))
        except Exception as e:
            self.error.emit(f"Error during disk scan: {e}")

class FileFolderScanWorker(QObject):
    finished = pyqtSignal(pd.DataFrame, pd.DataFrame, str) # df_files, df_folders, scan_path
    progress = pyqtSignal(int, str) # percentage, message
    error = pyqtSignal(str)

    def __init__(self, path):
        super().__init__()
        self.path = os.path.abspath(path) # Ensure absolute path for consistency
        self._is_cancelled = False
        self.total_scanned_items = 0 # Track items for progress update
        self.progress_update_interval = 1000 # Update every N items

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        if not os.path.isdir(self.path):
            self.error.emit(f"Error: '{self.path}' is not a valid directory.")
            return

        file_details = []
        folder_direct_file_sizes = {} # Stores sum of files *directly* in a folder
        all_scanned_paths = set() # Keep track of all folders encountered

        self.progress.emit(0, "Starting scan...")
        
        def onerror_callback(e):
            # We skip printing these to avoid flooding the UI, but they are implicitly handled
            # by try-except blocks during os.stat if needed.
            pass

        for root, dirs, files in os.walk(self.path, onerror=onerror_callback):
            if self._is_cancelled:
                self.error.emit("Scan cancelled by user.")
                return

            all_scanned_paths.add(root)
            folder_direct_file_sizes[root] = folder_direct_file_sizes.get(root, 0) # Initialize or get current direct size

            self.total_scanned_items += len(dirs) # Count directories in progress
            
            for file_name in files:
                if self._is_cancelled:
                    self.error.emit("Scan cancelled by user.")
                    return
                
                self.total_scanned_items += 1
                file_path = os.path.join(root, file_name)
                try:
                    stat_info = os.stat(file_path)
                    file_size = stat_info.st_size
                    folder_direct_file_sizes[root] += file_size # Add to current folder's direct file size sum

                    _, file_extension = os.path.splitext(file_name)
                    
                    file_details.append({
                        "Path": file_path,
                        "Name": file_name,
                        "Size (Bytes)": file_size,
                        "Size (Human)": bytes_to_human_readable(file_size),
                        "Type": "File",
                        "Extension": file_extension.lower(),
                        "Parent Folder": root,
                        "Created": datetime.datetime.fromtimestamp(stat_info.st_ctime),
                        "Modified": datetime.datetime.fromtimestamp(stat_info.st_mtime),
                        "Accessed": datetime.datetime.fromtimestamp(stat_info.st_atime),
                    })
                except FileNotFoundError:
                    pass
                except PermissionError:
                    pass 
                except Exception as e:
                    # self.error.emit(f"Error processing file {file_path}: {e}. Skipping.") # Too verbose for GUI
                    pass
            
            # Update progress periodically
            if self.total_scanned_items % self.progress_update_interval == 0:
                # Use a dummy percentage (e.g., 1% to 90%) for the scan phase
                self.progress.emit(min(int(self.total_scanned_items / 10000), 90), 
                                   f"Scanning: {self.total_scanned_items} items processed...")

        self.progress.emit(90, "Finished file scan, now aggregating folder sizes...")

        df_files = pd.DataFrame(file_details)
        
        # --- Optimized Folder Aggregate Size Calculation ---
        
        # Ensure all parent paths up to the scan_path are in all_scanned_paths
        # This is crucial for correct aggregation, even if they have no direct files
        for path in list(all_scanned_paths):
            p = os.path.dirname(path)
            while p and p != self.path and p.startswith(self.path):
                all_scanned_paths.add(p)
                p = os.path.dirname(p)
        
        if self.path not in all_scanned_paths:
            all_scanned_paths.add(self.path)

        # Initialize aggregate sizes with direct file sizes (0 if no direct files)
        folder_aggregate_sizes = {path: folder_direct_file_sizes.get(path, 0) for path in all_scanned_paths}

        # Sort paths from deepest to shallowest to ensure children are processed before parents
        sorted_paths_for_aggregation = sorted(list(all_scanned_paths), key=lambda x: (x.count(os.sep), x), reverse=True)

        # Propagate sizes upwards
        for path in sorted_paths_for_aggregation:
            if self._is_cancelled:
                self.error.emit("Scan cancelled by user during aggregation.")
                return
            
            # If current path is not the very top level of the scan
            if path != self.path:
                parent_path = os.path.dirname(path)
                if parent_path in folder_aggregate_sizes: # Ensure parent is also a relevant scanned folder
                    folder_aggregate_sizes[parent_path] += folder_aggregate_sizes[path]

        self.progress.emit(99, "Generating folder DataFrame...")

        folder_data = []
        for path, size in folder_aggregate_sizes.items():
            folder_name = os.path.basename(path) 
            if not folder_name:
                folder_name = path # For root path like C:\
            
            # Only include folders within the original scan path's hierarchy
            if path == self.path or path.startswith(self.path + os.sep):
                folder_data.append({
                    "Path": path,
                    "Name": folder_name,
                    "Size (Bytes)": size,
                    "Size (Human)": bytes_to_human_readable(size),
                    "Type": "Directory",
                    "Parent Folder": os.path.dirname(path) if path != self.path else None,
                })
        df_folders = pd.DataFrame(folder_data)
        
        self.progress.emit(100, "Scan complete.")
        self.finished.emit(df_files, df_folders, self.path)

# --- Matplotlib Canvas Widget ---
class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor='#202020') # Dark background
        self.axes = self.fig.add_subplot(111)
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.updateGeometry()
        
        # Set default text/label colors for dark theme
        self.axes.tick_params(axis='x', colors='lightgrey')
        self.axes.tick_params(axis='y', colors='lightgrey')
        self.axes.yaxis.label.set_color('lightgrey')
        self.axes.xaxis.label.set_color('lightgrey')
        self.axes.title.set_color('white')
        self.fig.tight_layout() # Ensure labels fit

# --- Main GUI Window ---

class StorageAnalyzerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced System Storage Analyzer")
        self.setGeometry(100, 100, 1200, 800)
        
        self.df_disk_info = pd.DataFrame()
        self.df_files_details = pd.DataFrame()
        self.df_folders_details = pd.DataFrame()
        self.current_scan_path = "" # Stores the root path of the *last successful* scan

        self.setup_ui()
        self.apply_stylesheet()
        
        # QThread is the recommended way to handle threads in PyQt for better signal/slot integration
        self.disk_scan_thread_obj = threading.Thread() # Placeholder for actual thread
        self.file_folder_scan_thread_obj = threading.Thread() # Placeholder for actual thread
        self.file_folder_scan_worker = None # Keep reference to worker to cancel

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # --- Disk Partitions Tab ---
        self.disk_tab = QWidget()
        self.tab_widget.addTab(self.disk_tab, "Disk Partitions")
        self.setup_disk_tab()

        # --- Directory Scanner Tab ---
        self.scanner_tab = QWidget()
        self.tab_widget.addTab(self.scanner_tab, "Directory Scanner")
        self.setup_scanner_tab()

        # --- Folder Tree Explorer Tab ---
        self.explorer_tab = QWidget()
        self.tab_widget.addTab(self.explorer_tab, "Folder Tree Explorer")
        self.setup_explorer_tab()
        
        self.tab_widget.currentChanged.connect(self.on_tab_change)

    def apply_stylesheet(self):
        # A simple dark theme stylesheet (QSS)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2e2e2e;
                color: #ffffff;
            }
            QTabWidget::pane { /* The tab widget frame */
                border: 1px solid #424242;
                background-color: #2e2e2e;
            }
            QTabWidget::tab-bar {
                left: 5px; /* move to the right by 5px */
            }
            QTabBar::tab {
                background: #3a3a3a;
                border: 1px solid #424242;
                border-bottom-color: #2e2e2e; /* same as pane color */
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                min-width: 8ex;
                padding: 5px;
                color: #cccccc;
            }
            QTabBar::tab:selected {
                background: #2e2e2e;
                border-color: #424242;
                border-bottom-color: #2e2e2e; /* same as pane color */
                color: #ffffff;
                font-weight: bold;
            }
            QTableWidget, QTreeWidget {
                background-color: #3a3a3a;
                color: #ffffff;
                border: 1px solid #555555;
                gridline-color: #424242;
                selection-background-color: #5b5b5b;
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #4a4a4a;
                color: #ffffff;
                padding: 4px;
                border: 1px solid #555555;
            }
            QPushButton {
                background-color: #4a4a4a;
                color: #ffffff;
                border: 1px solid #5b5b5b;
                padding: 5px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5b5b5b;
            }
            QPushButton:pressed {
                background-color: #6a6a6a;
            }
            QLineEdit {
                background-color: #3a3a3a;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 5px;
                border-radius: 4px;
            }
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 5px;
                text-align: center;
                background-color: #3a3a3a;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #007acc; /* A nice blue */
                border-radius: 5px;
            }
            QLabel {
                color: #ffffff;
            }
            QGroupBox {
                border: 1px solid #555555;
                border-radius: 5px;
                margin-top: 1ex; /* leave space at the top for the title */
                color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center; /* position at top center */
                padding: 0 3px;
                background-color: #2e2e2e; /* same as window background */
            }
        """)

        # Set default Matplotlib colors for dark theme
        plt.rcParams.update({
            "text.color": "lightgrey",
            "axes.labelcolor": "lightgrey",
            "xtick.color": "lightgrey",
            "ytick.color": "lightgrey",
            "axes.edgecolor": "#555555",
            "figure.facecolor": "#2e2e2e",
            "axes.facecolor": "#3a3a3a",
            "grid.color": "#4a4a4a"
        })

    def setup_disk_tab(self):
        layout = QVBoxLayout(self.disk_tab)

        # Table for disk info
        self.disk_table = QTableWidget()
        self.disk_table.setColumnCount(9) # Adjust to match new columns if any
        headers = ["Mountpoint", "Volume Name", "Filesystem Type", "Device", "Opts",
                   "Total Size", "Used Space", "Free Space", "Used (%)"]
        self.disk_table.setHorizontalHeaderLabels(headers)
        self.disk_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch) # Auto-resize columns
        self.disk_table.setEditTriggers(QTableWidget.NoEditTriggers) # Make table read-only
        layout.addWidget(self.disk_table)

        # Charts for disk info
        charts_layout = QHBoxLayout()
        self.disk_chart1 = MplCanvas(self, width=6, height=4)
        self.disk_chart2 = MplCanvas(self, width=6, height=4)
        self.disk_chart3 = MplCanvas(self, width=6, height=4) # New: Overall Pie
        self.disk_chart4 = MplCanvas(self, width=6, height=4) # New: Stacked bar
        
        charts_layout.addWidget(self.disk_chart1)
        charts_layout.addWidget(self.disk_chart2)
        charts_layout.addWidget(self.disk_chart3)
        charts_layout.addWidget(self.disk_chart4)
        
        layout.addLayout(charts_layout)

        # Refresh button
        refresh_button = QPushButton("Refresh Disk Info")
        refresh_button.clicked.connect(self.refresh_disk_info)
        layout.addWidget(refresh_button)
        
        self.refresh_disk_info() # Load data on startup

    def setup_scanner_tab(self):
        layout = QVBoxLayout(self.scanner_tab)

        # Path selection
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Enter directory path to scan...")
        self.path_input.setText(os.path.expanduser("~")) # Default to user home directory
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_directory)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_button)
        layout.addLayout(path_layout)

        # Scan and Save buttons
        button_layout = QHBoxLayout()
        self.scan_button = QPushButton("Start Scan")
        self.scan_button.clicked.connect(self.start_file_folder_scan)
        self.cancel_scan_button = QPushButton("Cancel Scan")
        self.cancel_scan_button.clicked.connect(self.cancel_file_folder_scan)
        self.cancel_scan_button.setEnabled(False) # Disable initially
        self.save_files_csv_button = QPushButton("Save All File Details to CSV")
        self.save_files_csv_button.clicked.connect(self.save_files_csv)
        self.save_folders_csv_button = QPushButton("Save All Folder Details to CSV")
        self.save_folders_csv_button.clicked.connect(self.save_folders_csv)
        
        button_layout.addWidget(self.scan_button)
        button_layout.addWidget(self.cancel_scan_button)
        button_layout.addStretch() # Push buttons to left
        button_layout.addWidget(self.save_files_csv_button)
        button_layout.addWidget(self.save_folders_csv_button)
        layout.addLayout(button_layout)

        # Progress bar and status label
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.status_label = QLabel("Ready to scan a directory.")
        layout.addWidget(self.status_label)

        # Summaries (Top Files/Folders)
        summary_layout = QHBoxLayout()
        
        # Top Files Table
        top_files_group = QVBoxLayout()
        top_files_group.addWidget(QLabel("Top 10 Largest Files:"))
        self.top_files_table = QTableWidget()
        self.top_files_table.setColumnCount(4)
        self.top_files_table.setHorizontalHeaderLabels(["Name", "Size", "Modified", "Extension"])
        self.top_files_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.top_files_table.setEditTriggers(QTableWidget.NoEditTriggers)
        top_files_group.addWidget(self.top_files_table)
        summary_layout.addLayout(top_files_group)

        # Top Folders Table
        top_folders_group = QVBoxLayout()
        top_folders_group.addWidget(QLabel("Top 10 Largest Folders:"))
        self.top_folders_table = QTableWidget()
        self.top_folders_table.setColumnCount(2)
        self.top_folders_table.setHorizontalHeaderLabels(["Name", "Size"])
        self.top_folders_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.top_folders_table.setEditTriggers(QTableWidget.NoEditTriggers)
        top_folders_group.addWidget(self.top_folders_table)
        summary_layout.addLayout(top_folders_group)
        
        layout.addLayout(summary_layout)

        # Charts for file/folder scan
        scan_charts_layout = QHBoxLayout()
        self.file_chart1 = MplCanvas(self, width=6, height=4) # Top N Files
        self.file_chart2 = MplCanvas(self, width=6, height=4) # Top N Folders
        self.file_chart3 = MplCanvas(self, width=6, height=4) # File Type Distribution
        
        scan_charts_layout.addWidget(self.file_chart1)
        scan_charts_layout.addWidget(self.file_chart2)
        scan_charts_layout.addWidget(self.file_chart3)
        layout.addLayout(scan_charts_layout)

    def setup_explorer_tab(self):
        layout = QVBoxLayout(self.explorer_tab)
        
        self.explorer_path_label = QLabel("Current Path: ")
        layout.addWidget(self.explorer_path_label)

        # Tree widget for hierarchical view
        self.folder_tree = QTreeWidget()
        self.folder_tree.setColumnCount(3)
        self.folder_tree.setHeaderLabels(["Name", "Type", "Size"]) # Corrected line!
        self.folder_tree.header().setSectionResizeMode(0, QHeaderView.Stretch) # Name column stretches
        self.folder_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.folder_tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.folder_tree.setEditTriggers(QTableWidget.NoEditTriggers)
        self.folder_tree.setContextMenuPolicy(Qt.CustomContextMenu) # Enable context menu
        # self.folder_tree.customContextMenuRequested.connect(self.show_context_menu) # Connect later if implementing context menu
        self.folder_tree.itemDoubleClicked.connect(self.explore_tree_item)
        layout.addWidget(self.folder_tree)
        
        self.explorer_refresh_button = QPushButton("Refresh Explorer View")
        self.explorer_refresh_button.clicked.connect(self.populate_explorer_tree)
        self.explorer_refresh_button.setEnabled(False) # Enable after scan
        layout.addWidget(self.explorer_refresh_button)

    def on_tab_change(self, index):
        # Refresh the explorer view if switching to it, only if data is available
        if self.tab_widget.tabText(index) == "Folder Tree Explorer" and not self.df_folders_details.empty:
            self.populate_explorer_tree()
        # Optionally, clear charts/tables if switching away from scanner to save resources
        # Or simply update relevant tab on demand.

    # --- Disk Tab Logic ---
    def refresh_disk_info(self):
        self.disk_table.setRowCount(0) # Clear table
        self.clear_all_disk_charts()
        
        self.disk_scan_thread_obj = threading.Thread(target=self._run_disk_scan_worker)
        self.disk_scan_thread_obj.daemon = True # Allow app to close even if thread is running
        self.disk_scan_thread_obj.start()
        
        # You could disable the refresh button here and re-enable in update_disk_tab
        # refresh_button = self.findChild(QPushButton, "Refresh Disk Info") # Requires object name
        # if refresh_button: refresh_button.setEnabled(False)

    def _run_disk_scan_worker(self):
        worker = DiskScanWorker()
        worker.finished.connect(self.update_disk_tab)
        worker.error.connect(self.show_error_message)
        
        # We're already in a thread here if this is called from main thread, 
        # but worker.run() should still be called to perform the work.
        # This setup effectively runs the worker's logic in the calling thread (which is a new thread created by self.disk_scan_thread_obj).
        worker.run()


    def update_disk_tab(self, df):
        self.df_disk_info = df
        if self.df_disk_info.empty:
            QMessageBox.information(self, "No Disk Data", "Could not retrieve any disk partition information.")
            return

        # Populate Table
        self.disk_table.setRowCount(len(df))
        for row_idx, (index, row) in enumerate(df.iterrows()):
            self.disk_table.setItem(row_idx, 0, QTableWidgetItem(row["Mountpoint"]))
            self.disk_table.setItem(row_idx, 1, QTableWidgetItem(row["Volume Name"]))
            self.disk_table.setItem(row_idx, 2, QTableWidgetItem(row["Filesystem Type"]))
            self.disk_table.setItem(row_idx, 3, QTableWidgetItem(row["Device"]))
            self.disk_table.setItem(row_idx, 4, QTableWidgetItem(row["Opts"]))
            self.disk_table.setItem(row_idx, 5, QTableWidgetItem(row["Total Size (Human)"]))
            self.disk_table.setItem(row_idx, 6, QTableWidgetItem(row["Used Space (Human)"]))
            self.disk_table.setItem(row_idx, 7, QTableWidgetItem(row["Free Space (Human)"]))
            self.disk_table.setItem(row_idx, 8, QTableWidgetItem(f"{row['Used (%)']:.2f}%"))
            
            # Align numeric data right
            for col in [5, 6, 7, 8]:
                self.disk_table.item(row_idx, col).setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)

        # Plot Charts
        self.plot_disk_charts(df)
        
        # Re-enable refresh button if it was disabled
        # refresh_button = self.findChild(QPushButton, "Refresh Disk Info")
        # if refresh_button: refresh_button.setEnabled(True)

    def plot_disk_charts(self, df):
        plot_df = df[df["Total Size (Bytes)"] > 0].copy()
        if plot_df.empty:
            # self.status_label.setText("No usable disk data for plotting.") # Not for disk tab
            self.clear_all_disk_charts()
            return
            
        labels = plot_df["Mountpoint"].tolist()
        if sys.platform == "win32":
            display_labels = [f"{row['Volume Name']} ({row['Mountpoint']})" if row['Volume Name'] != 'N/A' and row['Volume Name'] not in row['Mountpoint'] else row['Mountpoint'] for index, row in plot_df.iterrows()]
        else:
            display_labels = labels

        total_gb = plot_df["Total Size (Bytes)"] / (1024**3)
        used_gb = plot_df["Used Space (Bytes)"] / (1024**3)
        free_gb = plot_df["Free Space (Bytes)"] / (1024**3)
        used_percent = plot_df["Used (%)"]

        # Chart 1: Bar Chart - Total, Used, Free Space (GB)
        self.clear_chart(self.disk_chart1)
        ax = self.disk_chart1.axes
        bar_width = 0.25
        r1 = np.arange(len(labels))
        r2 = [x + bar_width for x in r1]
        r3 = [x + bar_width for x in r2]
        ax.bar(r1, total_gb, color='skyblue', width=bar_width, edgecolor='grey', label='Total (GB)')
        ax.bar(r2, used_gb, color='lightcoral', width=bar_width, edgecolor='grey', label='Used (GB)')
        ax.bar(r3, free_gb, color='lightgreen', width=bar_width, edgecolor='grey', label='Free (GB)')
        ax.set_xlabel('Drive', fontweight='bold')
        ax.set_ylabel('Size (GB)', fontweight='bold')
        ax.set_title('Disk Space Overview', fontweight='bold', color='white')
        ax.set_xticks([r + bar_width for r in range(len(labels))]) # SET TICKS FIRST
        ax.set_xticklabels(display_labels, rotation=45, ha='right') # THEN SET LABELS WITH PROPERTIES
        ax.legend()
        ax.grid(axis='y', linestyle='--', alpha=0.7)
        self.disk_chart1.draw()

        # Chart 2: Horizontal Bar Chart - Usage Percentage
        self.clear_chart(self.disk_chart2)
        ax = self.disk_chart2.axes
        sorted_idx = np.argsort(used_percent)
        sorted_labels = [display_labels[i] for i in sorted_idx]
        sorted_used_percent = used_percent.iloc[sorted_idx]
        bars = ax.barh(sorted_labels, sorted_used_percent, color='teal')
        ax.set_xlabel('Usage (%)', fontweight='bold')
        ax.set_title('Disk Usage Percentage', fontweight='bold', color='white')
        ax.set_xlim(0, 100)
        ax.grid(axis='x', linestyle='--', alpha=0.7)
        for bar in bars:
            ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2, 
                    f'{bar.get_width():.1f}%', va='center', ha='left', fontsize=9, color='lightgrey')
        self.disk_chart2.draw()

        # Chart 3: Pie Chart - Overall System Usage
        self.clear_chart(self.disk_chart3)
        ax = self.disk_chart3.axes
        total_system_used = plot_df["Used Space (Bytes)"].sum()
        total_system_free = plot_df["Free Space (Bytes)"].sum()
        total_system_size = total_system_used + total_system_free
        if total_system_size > 0:
            overall_labels = ['Total Used', 'Total Free']
            overall_sizes = [total_system_used, total_system_free]
            overall_colors = ['lightcoral', 'lightgreen']
            
            def autopct_format_bytes(pct, allvals):
                absolute = int(np.round(pct/100.*np.sum(allvals)))
                return f"{pct:.1f}%\n({bytes_to_human_readable(absolute)})"

            ax.pie(overall_sizes, labels=overall_labels, colors=overall_colors, 
                   autopct=lambda pct: autopct_format_bytes(pct, overall_sizes),
                   startangle=90, wedgeprops={'edgecolor': 'black', 'linewidth': 0.5},
                   textprops={'color': 'white'})
            ax.set_title('Overall System Storage', fontweight='bold', color='white')
            ax.axis('equal')
        self.disk_chart3.draw()

        # Chart 4: Stacked Bar Chart - Individual Drive Usage (Used vs Free)
        self.clear_chart(self.disk_chart4)
        ax = self.disk_chart4.axes
        ax.bar(display_labels, used_gb, color='lightcoral', label='Used (GB)', edgecolor='grey')
        ax.bar(display_labels, free_gb, bottom=used_gb, color='lightgreen', label='Free (GB)', edgecolor='grey')
        ax.set_xlabel('Drive', fontweight='bold')
        ax.set_ylabel('Size (GB)', fontweight='bold')
        ax.set_title('Individual Drive Usage', fontweight='bold', color='white')
        ax.set_xticks(np.arange(len(display_labels))) # SET NUMERICAL TICKS FIRST
        ax.set_xticklabels(display_labels, rotation=45, ha='right') # THEN SET LABELS WITH PROPERTIES
        ax.legend()
        ax.grid(axis='y', linestyle='--', alpha=0.7)
        self.disk_chart4.draw()

    def clear_chart(self, canvas):
        canvas.axes.clear()
        canvas.axes.set_facecolor('#3a3a3a') # Keep dark background for axes
        canvas.fig.patch.set_facecolor('#2e2e2e') # Keep dark background for figure
        canvas.draw()
        
    def clear_all_disk_charts(self):
        self.clear_chart(self.disk_chart1)
        self.clear_chart(self.disk_chart2)
        self.clear_chart(self.disk_chart3)
        self.clear_chart(self.disk_chart4)

    # --- Scanner Tab Logic ---
    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory to Scan")
        if directory:
            self.path_input.setText(directory)

    def start_file_folder_scan(self):
        path_to_scan = self.path_input.text()
        if not path_to_scan or not os.path.isdir(path_to_scan):
            QMessageBox.warning(self, "Invalid Path", "Please enter a valid directory path.")
            return

        # Check for C:\ drive on Windows
        if sys.platform == "win32" and os.path.abspath(path_to_scan).lower() == 'c:\\':
            reply = QMessageBox.question(self, 'Warning', 
                                         "Scanning the entire C: drive can take an extremely long time and may encounter many permission errors.\n\nAre you sure you want to proceed?", 
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                self.status_label.setText("C: drive scan cancelled.")
                return
        
        # Clear previous data and reset UI
        self.df_files_details = pd.DataFrame() 
        self.df_folders_details = pd.DataFrame()
        self.current_scan_path = ""
        self.status_label.setText("Scan started...")
        self.progress_bar.setValue(0)
        self.scan_button.setEnabled(False)
        self.cancel_scan_button.setEnabled(True)
        self.save_files_csv_button.setEnabled(False)
        self.save_folders_csv_button.setEnabled(False)
        self.explorer_refresh_button.setEnabled(False) # Disable until scan is done

        self.clear_table(self.top_files_table)
        self.clear_table(self.top_folders_table)
        self.clear_chart(self.file_chart1)
        self.clear_chart(self.file_chart2)
        self.clear_chart(self.file_chart3)
        
        # Create worker and thread
        self.file_folder_scan_worker = FileFolderScanWorker(path_to_scan)
        self.file_folder_scan_thread_obj = threading.Thread(target=self.file_folder_scan_worker.run)
        self.file_folder_scan_thread_obj.daemon = True
        
        # Connect signals from worker to slots in GUI
        self.file_folder_scan_worker.finished.connect(self.update_scanner_tab_on_completion)
        self.file_folder_scan_worker.progress.connect(self.update_scan_progress)
        self.file_folder_scan_worker.error.connect(self.show_error_message)
        
        self.file_folder_scan_thread_obj.start()


    def cancel_file_folder_scan(self):
        if self.file_folder_scan_worker:
            self.file_folder_scan_worker.cancel()
            self.status_label.setText("Scan cancellation requested. Please wait...")
            self.cancel_scan_button.setEnabled(False) # Prevent multiple clicks

    def update_scan_progress(self, percentage, message):
        self.progress_bar.setValue(percentage)
        self.status_label.setText(message)

    def update_scanner_tab_on_completion(self, df_files, df_folders, scan_path):
        self.df_files_details = df_files
        self.df_folders_details = df_folders
        self.current_scan_path = scan_path

        self.scan_button.setEnabled(True)
        self.cancel_scan_button.setEnabled(False)
        
        self.progress_bar.setValue(100) # Ensure 100% on successful completion

        if self.df_files_details.empty and self.df_folders_details.empty:
            self.status_label.setText(f"Scan complete. No files or folders found in {scan_path} or accessible.")
            self.save_files_csv_button.setEnabled(False)
            self.save_folders_csv_button.setEnabled(False)
            self.explorer_refresh_button.setEnabled(False)
            return

        self.status_label.setText(f"Scan of {scan_path} completed. {len(self.df_files_details)} files and {len(self.df_folders_details)} folders found.")
        self.save_files_csv_button.setEnabled(True)
        self.save_folders_csv_button.setEnabled(True)
        self.explorer_refresh_button.setEnabled(True)

        # Populate Top Files Table
        if not self.df_files_details.empty:
            df_top_files = self.df_files_details.nlargest(10, "Size (Bytes)")
            self.top_files_table.setRowCount(len(df_top_files))
            for row_idx, (index, row) in enumerate(df_top_files.iterrows()):
                self.top_files_table.setItem(row_idx, 0, QTableWidgetItem(row["Name"]))
                self.top_files_table.setItem(row_idx, 1, QTableWidgetItem(row["Size (Human)"]))
                self.top_files_table.setItem(row_idx, 2, QTableWidgetItem(str(row["Modified"].strftime('%Y-%m-%d %H:%M'))))
                self.top_files_table.setItem(row_idx, 3, QTableWidgetItem(row["Extension"]))
                self.top_files_table.item(row_idx, 1).setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
        else:
            self.clear_table(self.top_files_table)

        # Populate Top Folders Table
        if not self.df_folders_details.empty:
            df_top_folders = self.df_folders_details.nlargest(10, "Size (Bytes)")
            self.top_folders_table.setRowCount(len(df_top_folders))
            for row_idx, (index, row) in enumerate(df_top_folders.iterrows()):
                self.top_folders_table.setItem(row_idx, 0, QTableWidgetItem(row["Name"]))
                self.top_folders_table.setItem(row_idx, 1, QTableWidgetItem(row["Size (Human)"]))
                self.top_folders_table.item(row_idx, 1).setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
        else:
            self.clear_table(self.top_folders_table)
        
        self.plot_file_folder_charts(self.df_files_details, self.df_folders_details)
        
        # If the explorer tab is current and data is ready, populate it
        if self.tab_widget.tabText(self.tab_widget.currentIndex()) == "Folder Tree Explorer":
            self.populate_explorer_tree()


    def plot_file_folder_charts(self, df_files, df_folders, top_n=10):
        # Clear previous charts
        self.clear_chart(self.file_chart1)
        self.clear_chart(self.file_chart2)
        self.clear_chart(self.file_chart3)

        # Plot 1: Top N Largest Files
        if not df_files.empty:
            df_top_files = df_files.nlargest(top_n, "Size (Bytes)").sort_values("Size (Bytes)", ascending=True)
            if not df_top_files.empty:
                ax = self.file_chart1.axes
                labels = df_top_files["Name"]
                sizes_mb = df_top_files["Size (Bytes)"] / (1024**2)
                bars = ax.barh(labels, sizes_mb, color='darkred')
                ax.set_xlabel('Size (MB)', fontweight='bold')
                ax.set_title(f'Top {top_n} Largest Files', fontweight='bold', color='white')
                ax.grid(axis='x', linestyle='--', alpha=0.7)
                for index, value in enumerate(df_top_files["Size (Bytes)"]):
                    ax.text(sizes_mb.iloc[index] + max(sizes_mb.max() * 0.01, 0.1), index, 
                            bytes_to_human_readable(value), va='center', fontsize=9, color='lightgrey')
                if not sizes_mb.empty:
                    ax.set_xlim(0, sizes_mb.max() * 1.15)
                self.file_chart1.draw()

        # Plot 2: Top N Largest Folders
        if not df_folders.empty:
            # Exclude the root scan path itself from "Top N Largest Folders" if it makes sense, 
            # as it often contains everything. Or, just make sure to get top N from all.
            # Here, we will just take from all, as the aggregation should be correct.
            df_top_folders = df_folders.nlargest(top_n, "Size (Bytes)").sort_values("Size (Bytes)", ascending=True)
            if not df_top_folders.empty:
                ax = self.file_chart2.axes
                labels = df_top_folders["Name"]
                sizes_mb = df_top_folders["Size (Bytes)"] / (1024**2)
                bars = ax.barh(labels, sizes_mb, color='darkblue')
                ax.set_xlabel('Size (MB)', fontweight='bold')
                ax.set_title(f'Top {top_n} Largest Folders', fontweight='bold', color='white')
                ax.grid(axis='x', linestyle='--', alpha=0.7)
                for index, value in enumerate(df_top_folders["Size (Bytes)"]):
                    ax.text(sizes_mb.iloc[index] + max(sizes_mb.max() * 0.01, 0.1), index, 
                            bytes_to_human_readable(value), va='center', fontsize=9, color='lightgrey')
                if not sizes_mb.empty:
                    ax.set_xlim(0, sizes_mb.max() * 1.15)
                self.file_chart2.draw()

        # Plot 3: File Type Distribution
        if not df_files.empty:
            df_extensions = df_files[df_files["Extension"] != ''].copy() 
            if not df_extensions.empty:
                extension_sizes = df_extensions.groupby('Extension')['Size (Bytes)'].sum().nlargest(top_n-1)
                other_size = df_extensions['Size (Bytes)'].sum() - extension_sizes.sum()
                if other_size > 0:
                    extension_sizes['.other'] = other_size
                extension_sizes = extension_sizes[extension_sizes > 0]

                if not extension_sizes.empty:
                    ax = self.file_chart3.axes
                    
                    def autopct_format(pct, allvals):
                        absolute = int(np.round(pct/100.*np.sum(allvals)))
                        return f'{pct:.1f}%\n({bytes_to_human_readable(absolute)})'

                    ax.pie(extension_sizes, labels=extension_sizes.index, 
                           autopct=lambda pct: autopct_format(pct, extension_sizes.values), 
                           startangle=90,
                           wedgeprops={'edgecolor': 'black', 'linewidth': 0.5}, pctdistance=0.85,
                           textprops={'color': 'white'})
                    ax.set_title('File Type Distribution by Size', fontweight='bold', color='white')
                    ax.axis('equal') 
                    self.file_chart3.draw()

    def save_files_csv(self):
        if self.df_files_details.empty:
            QMessageBox.warning(self, "No Data", "No file details to save. Please run a scan first.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Save File Details", "file_details.csv", "CSV Files (*.csv)")
        if file_path:
            try:
                self.df_files_details.to_csv(file_path, index=False)
                QMessageBox.information(self, "Save Success", f"File details saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save file details: {e}")

    def save_folders_csv(self):
        if self.df_folders_details.empty:
            QMessageBox.warning(self, "No Data", "No folder details to save. Please run a scan first.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Folder Details", "folder_details.csv", "CSV Files (*.csv)")
        if file_path:
            try:
                self.df_folders_details.to_csv(file_path, index=False)
                QMessageBox.information(self, "Save Success", f"Folder details saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save folder details: {e}")

    # --- Explorer Tab Logic ---
    def populate_explorer_tree(self):
        self.folder_tree.clear() # Clear existing items
        
        if not self.current_scan_path:
            self.explorer_path_label.setText("Current Path: No directory scanned yet.")
            return

        self.explorer_path_label.setText(f"Current Path: {self.current_scan_path}")

        if self.df_folders_details.empty and self.df_files_details.empty:
            root_item = QTreeWidgetItem(["No data available for this path.", "", ""])
            self.folder_tree.addTopLevelItem(root_item)
            return

        # Find the root item (initial_scan_path) in df_folders_details
        root_folder_data = self.df_folders_details[self.df_folders_details["Path"] == self.current_scan_path]
        if root_folder_data.empty:
            # This can happen if the scan_path itself has 0 size or was inaccessible
            root_tree_item = QTreeWidgetItem([os.path.basename(self.current_scan_path), "Folder", "0 B"])
            root_tree_item.setData(0, Qt.UserRole, self.current_scan_path)
            root_tree_item.setData(1, Qt.UserRole, "Folder")
            self.folder_tree.addTopLevelItem(root_tree_item)
            # No children to add, as no data was found
            return
        
        root_row = root_folder_data.iloc[0]
        root_name = root_row["Name"]
        root_size_human = root_row["Size (Human)"]
        
        root_tree_item = QTreeWidgetItem([root_name, "Folder", root_size_human])
        root_tree_item.setData(0, Qt.UserRole, self.current_scan_path) # Store full path
        root_tree_item.setData(1, Qt.UserRole, "Folder") # Store type
        
        self.folder_tree.addTopLevelItem(root_tree_item)
        self.add_children_to_tree_item(root_tree_item, self.current_scan_path)
        root_tree_item.setExpanded(True) # Expand the root by default

    def add_children_to_tree_item(self, parent_tree_item, parent_path):
        # Add subfolders
        subfolders = self.df_folders_details[self.df_folders_details["Parent Folder"] == parent_path].copy()
        # Filter out self-reference if present (e.g., if parent_path == df_folders_details["Path"])
        subfolders = subfolders[subfolders["Path"] != parent_path]
        subfolders = subfolders.sort_values(by="Size (Bytes)", ascending=False) # Sort by size

        for idx, row in subfolders.iterrows():
            item = QTreeWidgetItem([row["Name"], "Folder", row["Size (Human)"]])
            item.setData(0, Qt.UserRole, row["Path"]) # Store full path
            item.setData(1, Qt.UserRole, "Folder") # Store type
            parent_tree_item.addChild(item)
            # Add a dummy child to make the folder expandable, and lazy-load
            # Check if this subfolder *actually* has children before adding "Loading..."
            has_children = not self.df_folders_details[self.df_folders_details["Parent Folder"] == row["Path"]].empty or \
                           not self.df_files_details[self.df_files_details["Parent Folder"] == row["Path"]].empty
            if has_children:
                item.addChild(QTreeWidgetItem(["Loading...", "", ""])) 

        # Add files directly in this folder
        files_in_folder = self.df_files_details[self.df_files_details["Parent Folder"] == parent_path].copy()
        files_in_folder = files_in_folder.sort_values(by="Size (Bytes)", ascending=False)
        
        for idx, row in files_in_folder.iterrows():
            item = QTreeWidgetItem([row["Name"], "File", row["Size (Human)"]])
            item.setData(0, Qt.UserRole, row["Path"])
            item.setData(1, Qt.UserRole, "File")
            parent_tree_item.addChild(item)

    def explore_tree_item(self, item, column):
        path = item.data(0, Qt.UserRole)
        item_type = item.data(1, Qt.UserRole)

        if item_type == "Folder":
            if item.childCount() == 1 and item.child(0).text(0) == "Loading...": # If dummy child exists, replace it
                item.removeChild(item.child(0))
                self.add_children_to_tree_item(item, path)
            item.setExpanded(not item.isExpanded()) # Toggle expansion
            self.explorer_path_label.setText(f"Current Path: {path}") # Update current path label
        elif item_type == "File":
            # Optional: Open file with default viewer (platform dependent)
            try:
                if sys.platform == "win32":
                    os.startfile(path)
                elif sys.platform == "darwin": # macOS
                    os.system(f"open \"{path}\"")
                else: # Linux
                    os.system(f"xdg-open \"{path}\"")
                # print(f"Opening file: {path}") # For debugging
            except Exception as e:
                QMessageBox.warning(self, "Open File Error", f"Could not open file '{path}': {e}")

    def clear_table(self, table_widget):
        table_widget.setRowCount(0)
        table_widget.clearContents()

    def show_error_message(self, message):
        QMessageBox.critical(self, "Error", message)
        self.status_label.setText(f"Error: {message}")
        self.scan_button.setEnabled(True)
        self.cancel_scan_button.setEnabled(False)
        self.progress_bar.setValue(0)
        self.save_files_csv_button.setEnabled(False)
        self.save_folders_csv_button.setEnabled(False)
        self.explorer_refresh_button.setEnabled(False)


if __name__ == "__main__":
    # Check for pywin32 on Windows for disk partition analysis
    if sys.platform == "win32":
        try:
            import win32api
        except ImportError:
            print("Warning: 'pywin32' not found. Volume names might not be displayed for Windows drives in partition view.")
            print("Install it with: pip install pywin32")

    app = QApplication(sys.argv)
    
    # Set a fusion style for a modern look (optional, but looks good with dark themes)
    app.setStyle(QStyleFactory.create("Fusion"))

    window = StorageAnalyzerApp()
    window.show()
    sys.exit(app.exec_())