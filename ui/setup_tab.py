"""
Setup Tab UI Component
Handles file selection, column configuration, and tax/exclusion settings.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QLabel, QListWidget, QListWidgetItem, QAbstractItemView,
    QSplitter, QMessageBox, QInputDialog, QComboBox, QLineEdit,
    QCheckBox, QScrollArea, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QBrush, QFont

from typing import List, Dict, Tuple, Optional, Callable
import os


class FileSheetSelector(QGroupBox):
    """Widget for selecting files and their sheets"""
    
    files_changed = pyqtSignal()  # Emitted when file selection changes
    
    def __init__(self, parent=None):
        super().__init__("File & Sheet Selection", parent)
        self.files = {}  # filepath -> {'sheets': [], 'selected': []}
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Add file button
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("Add File(s)...")
        self.btn_add.clicked.connect(self._add_files)
        btn_layout.addWidget(self.btn_add)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Scroll area for file list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(150)
        
        self.file_container = QWidget()
        self.file_layout = QVBoxLayout(self.file_container)
        self.file_layout.setAlignment(Qt.AlignTop)
        
        scroll.setWidget(self.file_container)
        layout.addWidget(scroll)
        
        # Placeholder label
        self.placeholder = QLabel("No files added. Click 'Add File(s)...' to begin.")
        self.placeholder.setStyleSheet("color: gray; padding: 20px;")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.file_layout.addWidget(self.placeholder)
    
    def _add_files(self):
        """Open file dialog and add selected files"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Excel Files", "",
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        
        if not files:
            return
        
        from utils.excel_handler import ExcelReader
        
        for filepath in files:
            if filepath in self.files:
                continue  # Skip duplicates
            
            try:
                sheets = ExcelReader.get_sheet_names(filepath)
                self.files[filepath] = {
                    'sheets': sheets,
                    'selected': sheets.copy()  # Select all by default
                }
                self._add_file_widget(filepath)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not read file:\n{filepath}\n\nError: {str(e)}")
        
        self._update_placeholder()
        self.files_changed.emit()
    
    def _add_file_widget(self, filepath: str):
        """Add a widget for a file with its sheet checkboxes"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        frame.setProperty('filepath', filepath)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Header with filename and remove button
        header_layout = QHBoxLayout()
        filename = os.path.basename(filepath)
        lbl = QLabel(f"<b>{filename}</b>")
        lbl.setToolTip(filepath)
        header_layout.addWidget(lbl)
        header_layout.addStretch()
        
        btn_remove = QPushButton("Remove")
        btn_remove.setMaximumWidth(70)
        btn_remove.clicked.connect(lambda: self._remove_file(filepath, frame))
        header_layout.addWidget(btn_remove)
        
        layout.addLayout(header_layout)
        
        # Sheet checkboxes
        sheet_layout = QHBoxLayout()
        for sheet in self.files[filepath]['sheets']:
            cb = QCheckBox(sheet)
            cb.setChecked(True)
            cb.stateChanged.connect(lambda state, f=filepath, s=sheet: self._sheet_toggled(f, s, state))
            sheet_layout.addWidget(cb)
        sheet_layout.addStretch()
        
        layout.addLayout(sheet_layout)
        
        self.file_layout.addWidget(frame)
    
    def _remove_file(self, filepath: str, frame: QFrame):
        """Remove a file from selection"""
        if filepath in self.files:
            del self.files[filepath]
        
        frame.setParent(None)
        frame.deleteLater()
        
        self._update_placeholder()
        self.files_changed.emit()
    
    def _sheet_toggled(self, filepath: str, sheet: str, state: int):
        """Handle sheet checkbox toggle"""
        if filepath not in self.files:
            return
        
        selected = self.files[filepath]['selected']
        if state == Qt.Checked:
            if sheet not in selected:
                selected.append(sheet)
        else:
            if sheet in selected:
                selected.remove(sheet)
        
        self.files_changed.emit()
    
    def _update_placeholder(self):
        """Show/hide placeholder based on file count"""
        self.placeholder.setVisible(len(self.files) == 0)
    
    def get_selected_sources(self) -> List[Tuple[str, str]]:
        """Get list of (filepath, sheet_name) tuples for selected sheets"""
        sources = []
        for filepath, info in self.files.items():
            for sheet in info['selected']:
                sources.append((filepath, sheet))
        return sources
    
    def clear(self):
        """Clear all files"""
        self.files.clear()
        
        # Remove all file widgets
        while self.file_layout.count() > 1:  # Keep placeholder
            item = self.file_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        
        self._update_placeholder()
        self.files_changed.emit()


class ColumnListWidget(QGroupBox):
    """Widget for displaying and categorizing columns"""
    
    def __init__(self, parent=None):
        super().__init__("Column List", parent)
        self.columns = {}  # col_name -> {'type': str, 'mapping': str}
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Legend
        legend = QLabel("Legend: [T] Tax  [E] Excluded  [ ] Taxable")
        legend.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(legend)
        
        # Column list
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        layout.addWidget(self.list_widget)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        self.btn_mark_tax = QPushButton("Mark as Tax")
        self.btn_mark_tax.clicked.connect(self._mark_as_tax)
        btn_layout.addWidget(self.btn_mark_tax)
        
        self.btn_mark_exclude = QPushButton("Mark as Exclude")
        self.btn_mark_exclude.clicked.connect(self._mark_as_exclude)
        btn_layout.addWidget(self.btn_mark_exclude)
        
        self.btn_clear_mark = QPushButton("Clear Mark")
        self.btn_clear_mark.clicked.connect(self._clear_mark)
        btn_layout.addWidget(self.btn_clear_mark)
        
        layout.addLayout(btn_layout)
    
    def set_columns(self, columns: List[str], tax_columns: List[str], exclusion_list: List[str]):
        """Set columns and their types"""
        self.columns.clear()
        self.list_widget.clear()
        
        standard_cols = ['Date', 'Particulars', 'Voucher No.', 'Voucher Type', 'Type', 
                        'Vch No.', 'Ref No.', 'GSTIN', 'Party Name']
        
        for col in columns:
            if col in tax_columns:
                col_type = 'Tax'
            elif col in exclusion_list:
                col_type = 'Excluded'
            elif col in standard_cols:
                col_type = 'Standard'
            else:
                col_type = 'Taxable'
            
            self.columns[col] = {'type': col_type, 'mapping': ''}
            self._add_column_item(col, col_type)
    
    def _add_column_item(self, col_name: str, col_type: str):
        """Add a column item to the list"""
        prefix_map = {'Tax': '[T]', 'Excluded': '[E]', 'Standard': '[S]', 'Taxable': '[ ]'}
        prefix = prefix_map.get(col_type, '[ ]')
        
        item = QListWidgetItem(f"{prefix} {col_name}")
        item.setData(Qt.UserRole, col_name)
        
        # Color coding
        colors = {
            'Tax': QColor('#C6EFCE'),
            'Excluded': QColor('#FFEB9C'),
            'Standard': QColor('#DDEBF7'),
            'Taxable': QColor('#FFFFFF')
        }
        item.setBackground(QBrush(colors.get(col_type, QColor('#FFFFFF'))))
        
        self.list_widget.addItem(item)
    
    def _mark_as_tax(self):
        """Mark selected columns as tax columns"""
        # This would require additional dialog for tax type/rate
        # For now, just mark the type
        for item in self.list_widget.selectedItems():
            col_name = item.data(Qt.UserRole)
            self.columns[col_name]['type'] = 'Tax'
        
        self._refresh_list()
    
    def _mark_as_exclude(self):
        """Mark selected columns as excluded"""
        for item in self.list_widget.selectedItems():
            col_name = item.data(Qt.UserRole)
            self.columns[col_name]['type'] = 'Excluded'
        
        self._refresh_list()
    
    def _clear_mark(self):
        """Clear marks from selected columns"""
        for item in self.list_widget.selectedItems():
            col_name = item.data(Qt.UserRole)
            self.columns[col_name]['type'] = 'Taxable'
        
        self._refresh_list()
    
    def _refresh_list(self):
        """Refresh the list display"""
        self.list_widget.clear()
        for col_name, info in self.columns.items():
            self._add_column_item(col_name, info['type'])
    
    def get_excluded_columns(self) -> List[str]:
        """Get list of excluded column names"""
        return [col for col, info in self.columns.items() if info['type'] == 'Excluded']
    
    def get_column_types(self) -> Dict[str, str]:
        """Get dict of column name -> type"""
        return {col: info['type'] for col, info in self.columns.items()}


class TaxConfigWidget(QGroupBox):
    """Widget for editing tax configuration"""
    
    config_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__("Tax Configuration", parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['TaxType', 'TaxRate', 'ColumnNames', 'Delimiter'])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_add = QPushButton("Add Row")
        self.btn_add.clicked.connect(self._add_row)
        btn_layout.addWidget(self.btn_add)
        
        self.btn_delete = QPushButton("Delete Row")
        self.btn_delete.clicked.connect(self._delete_row)
        btn_layout.addWidget(self.btn_delete)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
    
    def set_config(self, tax_config: List[Dict]):
        """Set tax configuration data"""
        self.table.setRowCount(0)
        
        for row_data in tax_config:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            self.table.setItem(row, 0, QTableWidgetItem(row_data.get('TaxType', '')))
            self.table.setItem(row, 1, QTableWidgetItem(row_data.get('TaxRate', '')))
            self.table.setItem(row, 2, QTableWidgetItem(row_data.get('ColumnNames', '')))
            self.table.setItem(row, 3, QTableWidgetItem(row_data.get('Delimiter', ',')))
    
    def get_config(self) -> List[Dict]:
        """Get tax configuration data"""
        config = []
        for row in range(self.table.rowCount()):
            config.append({
                'TaxType': self.table.item(row, 0).text() if self.table.item(row, 0) else '',
                'TaxRate': self.table.item(row, 1).text() if self.table.item(row, 1) else '',
                'ColumnNames': self.table.item(row, 2).text() if self.table.item(row, 2) else '',
                'Delimiter': self.table.item(row, 3).text() if self.table.item(row, 3) else ','
            })
        return config
    
    def _add_row(self):
        """Add a new row"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Default values
        type_combo = QComboBox()
        type_combo.addItems(['CGST', 'SGST', 'IGST', 'CESS'])
        self.table.setCellWidget(row, 0, type_combo)
        
        self.table.setItem(row, 1, QTableWidgetItem(''))
        self.table.setItem(row, 2, QTableWidgetItem(''))
        self.table.setItem(row, 3, QTableWidgetItem(','))
        
        self.config_changed.emit()
    
    def _delete_row(self):
        """Delete selected row"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)
            self.config_changed.emit()


class ExclusionListWidget(QGroupBox):
    """Widget for editing exclusion list"""
    
    list_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__("Exclusion List", parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # List
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        
        # Add row
        add_layout = QHBoxLayout()
        self.txt_new = QLineEdit()
        self.txt_new.setPlaceholderText("Column name to exclude...")
        add_layout.addWidget(self.txt_new)
        
        self.btn_add = QPushButton("Add")
        self.btn_add.clicked.connect(self._add_item)
        add_layout.addWidget(self.btn_add)
        
        layout.addLayout(add_layout)
        
        # Delete button
        self.btn_delete = QPushButton("Delete Selected")
        self.btn_delete.clicked.connect(self._delete_item)
        layout.addWidget(self.btn_delete)
    
    def set_list(self, exclusion_list: List[str]):
        """Set exclusion list data"""
        self.list_widget.clear()
        for item in exclusion_list:
            self.list_widget.addItem(item)
    
    def get_list(self) -> List[str]:
        """Get exclusion list data"""
        items = []
        for i in range(self.list_widget.count()):
            items.append(self.list_widget.item(i).text())
        return items
    
    def _add_item(self):
        """Add new exclusion item"""
        text = self.txt_new.text().strip()
        if text:
            self.list_widget.addItem(text)
            self.txt_new.clear()
            self.list_changed.emit()
    
    def _delete_item(self):
        """Delete selected item"""
        current_row = self.list_widget.currentRow()
        if current_row >= 0:
            self.list_widget.takeItem(current_row)
            self.list_changed.emit()


class SetupTab(QWidget):
    """Main Setup Tab widget"""
    
    process_requested = pyqtSignal()  # Emitted when Process button clicked
    
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self._init_ui()
        self._load_config()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Top splitter: File selection and Column list
        top_splitter = QSplitter(Qt.Horizontal)
        
        # File selector
        self.file_selector = FileSheetSelector()
        self.file_selector.files_changed.connect(self._on_files_changed)
        top_splitter.addWidget(self.file_selector)
        
        # Column list
        self.column_list = ColumnListWidget()
        top_splitter.addWidget(self.column_list)
        
        top_splitter.setSizes([400, 300])
        layout.addWidget(top_splitter)
        
        # Scan button
        self.btn_scan = QPushButton("Scan Columns from Selected Files")
        self.btn_scan.clicked.connect(self._scan_columns)
        layout.addWidget(self.btn_scan)
        
        # Bottom splitter: Tax config and Exclusion list
        bottom_splitter = QSplitter(Qt.Horizontal)
        
        # Tax config
        self.tax_config = TaxConfigWidget()
        bottom_splitter.addWidget(self.tax_config)
        
        # Exclusion list
        self.exclusion_list = ExclusionListWidget()
        bottom_splitter.addWidget(self.exclusion_list)
        
        bottom_splitter.setSizes([500, 200])
        layout.addWidget(bottom_splitter)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        self.btn_process = QPushButton("Process Data")
        self.btn_process.setStyleSheet("background-color: #4472C4; color: white; font-weight: bold; padding: 10px;")
        self.btn_process.clicked.connect(self._on_process_clicked)
        btn_layout.addWidget(self.btn_process)
        
        btn_layout.addStretch()
        
        self.btn_export_config = QPushButton("Export to Excel")
        self.btn_export_config.clicked.connect(self._export_config)
        btn_layout.addWidget(self.btn_export_config)
        
        self.btn_save_config = QPushButton("Save Config")
        self.btn_save_config.clicked.connect(self._save_config)
        btn_layout.addWidget(self.btn_save_config)
        
        self.btn_load_config = QPushButton("Load Config")
        self.btn_load_config.clicked.connect(self._load_config_dialog)
        btn_layout.addWidget(self.btn_load_config)
        
        self.btn_reset = QPushButton("Reset to Defaults")
        self.btn_reset.clicked.connect(self._reset_config)
        btn_layout.addWidget(self.btn_reset)
        
        layout.addLayout(btn_layout)
    
    def _load_config(self):
        """Load configuration into UI"""
        self.tax_config.set_config(self.config_manager.current_config.tax_config)
        self.exclusion_list.set_list(self.config_manager.current_config.exclusion_list)
    
    def _on_files_changed(self):
        """Handle file selection changes"""
        # Could auto-scan columns here if desired
        pass
    
    def _scan_columns(self):
        """Scan columns from all selected files/sheets"""
        from utils.excel_handler import ExcelReader
        
        sources = self.file_selector.get_selected_sources()
        if not sources:
            QMessageBox.information(self, "Info", "No files selected. Please add files first.")
            return
        
        all_columns = set()
        
        for filepath, sheet_name in sources:
            try:
                df = ExcelReader.read_sheet(filepath, sheet_name)
                
                # Find header row
                for idx in range(min(20, len(df))):
                    row = df.iloc[idx]
                    first_three = [str(val).strip() if val is not None else '' for val in row.iloc[:3].tolist()]
                    if 'Date' in first_three and 'Particulars' in first_three:
                        headers = df.iloc[idx].tolist()
                        headers = [str(h).strip() if h is not None else f'Column_{i}' 
                                   for i, h in enumerate(headers)]
                        all_columns.update(headers)
                        break
            except Exception as e:
                print(f"Error scanning {filepath}/{sheet_name}: {e}")
        
        if not all_columns:
            QMessageBox.warning(self, "Warning", "Could not find valid headers in selected files.")
            return
        
        # Update column list
        tax_columns = self.config_manager.get_all_tax_column_names()
        exclusion_list = self.exclusion_list.get_list()
        
        self.column_list.set_columns(sorted(all_columns), tax_columns, exclusion_list)
        
        QMessageBox.information(self, "Success", f"Found {len(all_columns)} unique columns.")
    
    def _on_process_clicked(self):
        """Handle process button click"""
        sources = self.file_selector.get_selected_sources()
        if not sources:
            QMessageBox.warning(self, "Warning", "No files selected. Please add files first.")
            return
        
        # Update config manager with current UI values
        self.config_manager.set_tax_config(self.tax_config.get_config())
        self.config_manager.set_exclusion_list(self.exclusion_list.get_list())
        
        self.process_requested.emit()
    
    def _export_config(self):
        """Export current configuration to Excel - this will be handled by main window"""
        # This is a placeholder - the actual export happens after processing
        QMessageBox.information(self, "Info", 
            "To export, first process the data using 'Process Data' button.\n"
            "Then use the export buttons in the GST/Non-GST tabs.")
    
    def _save_config(self):
        """Save current configuration"""
        # Update config manager
        self.config_manager.set_tax_config(self.tax_config.get_config())
        self.config_manager.set_exclusion_list(self.exclusion_list.get_list())
        
        # Ask for client name
        client_name, ok = QInputDialog.getText(
            self, "Save Configuration", 
            "Enter client name:",
            text=self.config_manager.current_config.client_name
        )
        
        if ok and client_name:
            filename = self.config_manager.save_config(client_name)
            QMessageBox.information(self, "Success", f"Configuration saved as:\n{filename}")
    
    def _load_config_dialog(self):
        """Show dialog to load a saved configuration"""
        configs = self.config_manager.list_configs()
        
        if not configs:
            QMessageBox.information(self, "Info", "No saved configurations found.")
            return
        
        config_name, ok = QInputDialog.getItem(
            self, "Load Configuration",
            "Select configuration to load:",
            configs, 0, False
        )
        
        if ok and config_name:
            if self.config_manager.load_config(config_name + '.json'):
                self._load_config()
                QMessageBox.information(self, "Success", f"Configuration loaded: {config_name}")
            else:
                QMessageBox.warning(self, "Error", "Could not load configuration.")
    
    def _reset_config(self):
        """Reset to default configuration"""
        reply = QMessageBox.question(
            self, "Confirm Reset",
            "Reset all settings to defaults?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.config_manager.reset_to_defaults()
            self._load_config()
    
    def get_selected_sources(self) -> List[Tuple[str, str]]:
        """Get list of selected (filepath, sheet_name) tuples"""
        return self.file_selector.get_selected_sources()
    
    def get_column_types(self) -> Dict[str, str]:
        """Get column type mappings"""
        return self.column_list.get_column_types()
