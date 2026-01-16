"""
Files Tab UI Component
Handles file selection with visual gaps, row counts, and sheet tooltips.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QFileDialog,
    QLabel, QMessageBox, QFrame, QAbstractItemView, QDialog,
    QListWidget, QListWidgetItem, QDialogButtonBox, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QBrush, QFont

from typing import List, Dict, Tuple
import os
import glob


class FolderPreviewDialog(QDialog):
    """Dialog to preview files found in a folder before adding"""

    def __init__(self, files: List[str], folder_path: str, parent=None):
        super().__init__(parent)
        self.files = files
        self.selected_files = files.copy()
        self.setWindowTitle("Files Found in Folder")
        self.setMinimumSize(600, 400)
        self._init_ui(folder_path)

    def _init_ui(self, folder_path: str):
        layout = QVBoxLayout(self)

        # Header
        header = QLabel(f"Found {len(self.files)} Excel file(s) in:")
        header.setStyleSheet("font-weight: bold;")
        layout.addWidget(header)

        folder_label = QLabel(folder_path)
        folder_label.setStyleSheet("color: gray; font-size: 11px;")
        folder_label.setWordWrap(True)
        layout.addWidget(folder_label)

        # Select all checkbox
        self.chk_select_all = QCheckBox(f"Select All ({len(self.files)} files)")
        self.chk_select_all.setChecked(True)
        self.chk_select_all.stateChanged.connect(self._toggle_all)
        layout.addWidget(self.chk_select_all)

        # File list
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)

        for filepath in self.files:
            item = QListWidgetItem(os.path.basename(filepath))
            item.setToolTip(filepath)
            item.setData(Qt.UserRole, filepath)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.list_widget.addItem(item)

        self.list_widget.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.list_widget)

        # Button box
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _toggle_all(self, state):
        """Toggle all checkboxes"""
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setCheckState(Qt.Checked if state == Qt.Checked else Qt.Unchecked)
        self.list_widget.blockSignals(False)
        self._update_selected()

    def _on_item_changed(self, item):
        """Handle individual item check change"""
        self._update_selected()

    def _update_selected(self):
        """Update selected files list"""
        self.selected_files = []
        checked_count = 0
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                self.selected_files.append(item.data(Qt.UserRole))
                checked_count += 1

        # Update select all checkbox
        self.chk_select_all.blockSignals(True)
        if checked_count == 0:
            self.chk_select_all.setCheckState(Qt.Unchecked)
        elif checked_count == self.list_widget.count():
            self.chk_select_all.setCheckState(Qt.Checked)
        else:
            self.chk_select_all.setCheckState(Qt.PartiallyChecked)
        self.chk_select_all.blockSignals(False)

    def get_selected_files(self) -> List[str]:
        """Get list of selected files"""
        return self.selected_files


class FilesTab(QWidget):
    """Tab 1: File & Sheet Selection"""

    files_changed = pyqtSignal()  # Emitted when file selection changes
    process_requested = pyqtSignal()  # Emitted when Process button clicked
    export_requested = pyqtSignal()  # Emitted when Export button clicked
    next_tab_requested = pyqtSignal()  # Emitted when Next button clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.files = {}  # filepath -> {'sheets': [], 'selected': [], 'row_counts': {}}
        self._init_ui()

        # Enable drag and drop
        self.setAcceptDrops(True)

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Header with title and buttons
        header_layout = QHBoxLayout()

        title = QLabel("Files & Sheets")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.btn_add = QPushButton("Add Files...")
        self.btn_add.clicked.connect(self._add_files)
        header_layout.addWidget(self.btn_add)

        self.btn_add_folder = QPushButton("Add Folder...")
        self.btn_add_folder.setToolTip("Add all Excel files from a folder (including subfolders)")
        self.btn_add_folder.clicked.connect(self._add_folder)
        header_layout.addWidget(self.btn_add_folder)

        self.btn_clear = QPushButton("Clear All")
        self.btn_clear.clicked.connect(self._clear_all)
        header_layout.addWidget(self.btn_clear)

        layout.addLayout(header_layout)

        # Tree widget for files and sheets
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['File / Sheet', 'Sheets', 'Rows', ''])
        self.tree.setColumnCount(4)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setRootIsDecorated(True)
        self.tree.setIndentation(20)

        # Column widths
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        # Connect item changed signal for checkbox handling
        self.tree.itemChanged.connect(self._on_item_changed)

        layout.addWidget(self.tree)

        # Placeholder when empty
        self.placeholder = QLabel(
            "No files added.\n\n"
            "Click 'Add Files...' or drag & drop Excel files here.\n\n"
            "Supported formats: .xlsx, .xls"
        )
        self.placeholder.setStyleSheet("color: gray; padding: 40px; font-size: 12px;")
        self.placeholder.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.placeholder)

        # Total row count
        self.lbl_total = QLabel("Total: 0 rows")
        self.lbl_total.setStyleSheet("font-weight: bold; color: #4472C4; padding: 5px;")
        self.lbl_total.setAlignment(Qt.AlignRight)
        layout.addWidget(self.lbl_total)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        # Action buttons
        btn_layout = QHBoxLayout()

        # Left spacer for centering
        btn_layout.addStretch()

        self.btn_process = QPushButton("Process Data")
        self.btn_process.setStyleSheet(
            "background-color: #4472C4; color: white; font-weight: bold; padding: 10px 20px;"
        )
        self.btn_process.clicked.connect(lambda: self.process_requested.emit())
        btn_layout.addWidget(self.btn_process)

        self.btn_export = QPushButton("Export to Excel")
        self.btn_export.setStyleSheet(
            "background-color: #70AD47; color: white; font-weight: bold; padding: 10px 20px;"
        )
        self.btn_export.clicked.connect(lambda: self.export_requested.emit())
        btn_layout.addWidget(self.btn_export)

        # Right spacer for centering
        btn_layout.addStretch()

        # Next button
        self.btn_next = QPushButton("Next →")
        self.btn_next.setStyleSheet(
            "background-color: #5B9BD5; color: white; font-weight: bold; padding: 10px 20px;"
        )
        self.btn_next.clicked.connect(lambda: self.next_tab_requested.emit())
        btn_layout.addWidget(self.btn_next)

        layout.addLayout(btn_layout)

        self._update_placeholder()

    def dragEnterEvent(self, event):
        """Handle drag enter - accept if files are Excel files"""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                filepath = url.toLocalFile()
                if filepath.lower().endswith(('.xlsx', '.xls')):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event):
        """Handle drag move"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handle file drop"""
        files_to_add = []

        for url in event.mimeData().urls():
            filepath = url.toLocalFile()
            if filepath.lower().endswith(('.xlsx', '.xls')):
                files_to_add.append(filepath)

        if files_to_add:
            event.acceptProposedAction()
            self._add_files_from_list(files_to_add)
        else:
            event.ignore()

    def _add_files(self):
        """Open file dialog and add selected files"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Excel Files", "",
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )

        if files:
            self._add_files_from_list(files)

    def _add_folder(self):
        """Open folder dialog and add all Excel files from folder (including subfolders)"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select Folder with Excel Files", "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if not folder_path:
            return

        # Scan for Excel files recursively
        from PyQt5.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.WaitCursor)

        excel_files = []
        for ext in ['*.xlsx', '*.xls']:
            # Use recursive glob pattern
            pattern = os.path.join(folder_path, '**', ext)
            excel_files.extend(glob.glob(pattern, recursive=True))

        QApplication.restoreOverrideCursor()

        if not excel_files:
            QMessageBox.information(
                self, "No Files Found",
                f"No Excel files (.xlsx, .xls) found in:\n{folder_path}\n\n"
                "(Including all subfolders)"
            )
            return

        # Remove duplicates and sort
        excel_files = sorted(set(excel_files))

        # Filter out already added files
        new_files = [f for f in excel_files if f not in self.files]

        if not new_files:
            QMessageBox.information(
                self, "No New Files",
                f"All {len(excel_files)} Excel files from this folder are already added."
            )
            return

        # Show preview dialog
        dialog = FolderPreviewDialog(new_files, folder_path, self)
        if dialog.exec_() == QDialog.Accepted:
            selected = dialog.get_selected_files()
            if selected:
                self._add_files_from_list(selected)

    def _add_files_from_list(self, files: List[str]):
        """Add files from a list of filepaths"""
        from utils.excel_handler import ExcelReader
        from PyQt5.QtWidgets import QApplication

        added_count = 0
        for filepath in files:
            QApplication.processEvents()

            if filepath in self.files:
                continue  # Skip duplicates

            try:
                sheets = ExcelReader.get_sheet_names(filepath)
                self.files[filepath] = {
                    'sheets': sheets,
                    'selected': sheets.copy(),  # Select all by default
                    'row_counts': {}  # Will be populated during scan
                }
                added_count += 1
            except Exception as e:
                QMessageBox.warning(
                    self, "Error",
                    f"Could not read file:\n{filepath}\n\nError: {str(e)}"
                )

        if added_count > 0:
            self._rebuild_tree()
            self._update_placeholder()
            self.files_changed.emit()

    def _rebuild_tree(self):
        """Rebuild the tree widget from files data"""
        self.tree.blockSignals(True)
        self.tree.clear()

        for filepath, info in self.files.items():
            filename = os.path.basename(filepath)
            sheets = info['sheets']
            selected = info['selected']
            row_counts = info.get('row_counts', {})

            # Create file item
            file_item = QTreeWidgetItem()
            file_item.setText(0, filename)
            file_item.setToolTip(0, filepath)
            file_item.setData(0, Qt.UserRole, filepath)
            file_item.setData(0, Qt.UserRole + 1, 'file')

            # Sheet count with tooltip
            sheet_count = len(sheets)
            file_item.setText(1, str(sheet_count))

            # Build tooltip showing all sheets
            sheet_tooltip = f"{filename}\n\nSheets:\n" + "\n".join(f"  • {s}" for s in sheets)
            file_item.setToolTip(1, sheet_tooltip)

            # Total rows for file (sum of selected sheets)
            total_rows = sum(row_counts.get(s, 0) for s in selected)
            if total_rows > 0:
                file_item.setText(2, f"{total_rows:,}")

            # Remove button placeholder (handled via selection)
            btn_remove = QPushButton("×")
            btn_remove.setMaximumWidth(30)
            btn_remove.setStyleSheet("color: red; font-weight: bold;")
            btn_remove.clicked.connect(lambda checked, fp=filepath: self._remove_file(fp))

            self.tree.addTopLevelItem(file_item)
            self.tree.setItemWidget(file_item, 3, btn_remove)

            # Add sheet items if multiple sheets
            if len(sheets) > 1:
                for sheet in sheets:
                    sheet_item = QTreeWidgetItem(file_item)
                    sheet_item.setText(0, sheet)
                    sheet_item.setData(0, Qt.UserRole, filepath)
                    sheet_item.setData(0, Qt.UserRole + 1, 'sheet')
                    sheet_item.setData(0, Qt.UserRole + 2, sheet)

                    # Checkbox
                    sheet_item.setFlags(sheet_item.flags() | Qt.ItemIsUserCheckable)
                    if sheet in selected:
                        sheet_item.setCheckState(0, Qt.Checked)
                    else:
                        sheet_item.setCheckState(0, Qt.Unchecked)

                    # Row count
                    if sheet in row_counts:
                        sheet_item.setText(2, f"{row_counts[sheet]:,}")

                    # Indent styling
                    sheet_item.setForeground(0, QBrush(QColor('#666666')))

                file_item.setExpanded(True)

        self.tree.blockSignals(False)
        self._update_total_rows()

    def _on_item_changed(self, item, column):
        """Handle checkbox state changes"""
        if column != 0:
            return

        item_type = item.data(0, Qt.UserRole + 1)
        if item_type != 'sheet':
            return

        filepath = item.data(0, Qt.UserRole)
        sheet = item.data(0, Qt.UserRole + 2)

        if filepath not in self.files:
            return

        selected = self.files[filepath]['selected']

        if item.checkState(0) == Qt.Checked:
            if sheet not in selected:
                selected.append(sheet)
        else:
            if sheet in selected:
                selected.remove(sheet)

        self._update_total_rows()
        self.files_changed.emit()

    def _remove_file(self, filepath: str):
        """Remove a file from selection"""
        if filepath in self.files:
            del self.files[filepath]
            self._rebuild_tree()
            self._update_placeholder()
            self.files_changed.emit()

    def _clear_all(self):
        """Clear all files"""
        if not self.files:
            return

        reply = QMessageBox.question(
            self, "Confirm Clear",
            "Remove all files from the list?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.files.clear()
            self._rebuild_tree()
            self._update_placeholder()
            self.files_changed.emit()

    def _update_placeholder(self):
        """Show/hide placeholder based on file count"""
        has_files = len(self.files) > 0
        self.placeholder.setVisible(not has_files)
        self.tree.setVisible(has_files)
        self.lbl_total.setVisible(has_files)

    def _update_total_rows(self):
        """Update total row count label"""
        total = 0
        for filepath, info in self.files.items():
            row_counts = info.get('row_counts', {})
            for sheet in info['selected']:
                total += row_counts.get(sheet, 0)

        self.lbl_total.setText(f"Total: {total:,} rows")

    def set_row_counts(self, row_counts: Dict[str, Dict[str, int]]):
        """
        Set row counts for sheets.
        row_counts: {filepath: {sheet_name: row_count}}
        """
        for filepath, counts in row_counts.items():
            if filepath in self.files:
                self.files[filepath]['row_counts'] = counts

        self._rebuild_tree()

    def get_selected_sources(self) -> List[Tuple[str, str]]:
        """Get list of (filepath, sheet_name) tuples for selected sheets"""
        sources = []
        for filepath, info in self.files.items():
            for sheet in info['selected']:
                sources.append((filepath, sheet))
        return sources

    def get_all_files(self) -> Dict:
        """Get all files data"""
        return self.files.copy()

    def clear(self):
        """Clear all files"""
        self.files.clear()
        self._rebuild_tree()
        self._update_placeholder()
        self.files_changed.emit()
