"""
Setup Tab UI Component
Handles file selection, column configuration, and tax/exclusion settings.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QLabel, QListWidget, QListWidgetItem, QAbstractItemView,
    QSplitter, QMessageBox, QInputDialog, QComboBox, QLineEdit,
    QCheckBox, QScrollArea, QFrame, QDialog, QDialogButtonBox,
    QListView
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QBrush, QFont, QStandardItemModel, QStandardItem

from typing import List, Dict, Tuple, Optional, Set
import os
import pandas as pd


class MultiSelectComboBox(QComboBox):
    """ComboBox that allows multiple selection via checkboxes"""
    
    selection_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setPlaceholderText("Select columns...")
        
        self._model = QStandardItemModel(self)
        self.setModel(self._model)
        
        self._model.itemChanged.connect(self._on_item_changed)
        self._all_items = []  # All possible items
        self._disabled_items = set()  # Items disabled (used elsewhere)
    
    def set_items(self, items: List[str], disabled: Set[str] = None):
        """Set available items, optionally disabling some"""
        self._all_items = items
        self._disabled_items = disabled or set()
        self._rebuild_model()
    
    def _rebuild_model(self):
        """Rebuild the model with current items and disabled state"""
        # Remember current selection
        current_selected = self.get_selected()
        
        self._model.blockSignals(True)
        self._model.clear()
        
        for item_text in self._all_items:
            item = QStandardItem(item_text)
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            
            if item_text in self._disabled_items:
                item.setFlags(Qt.ItemIsUserCheckable)  # Remove enabled flag
                item.setCheckState(Qt.Unchecked)
                item.setForeground(QBrush(QColor('#999999')))
            else:
                # Restore previous selection if applicable
                if item_text in current_selected:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
            
            self._model.appendRow(item)
        
        self._model.blockSignals(False)
        self._update_display()
    
    def _on_item_changed(self, item):
        """Handle item check state change"""
        self._update_display()
        self.selection_changed.emit()
    
    def _update_display(self):
        """Update the display text to show selected items"""
        selected = self.get_selected()
        if selected:
            self.lineEdit().setText(", ".join(selected))
        else:
            self.lineEdit().setText("")
    
    def get_selected(self) -> List[str]:
        """Get list of selected items"""
        selected = []
        for i in range(self._model.rowCount()):
            item = self._model.item(i)
            if item and item.checkState() == Qt.Checked:
                selected.append(item.text())
        return selected
    
    def set_selected(self, items: List[str]):
        """Set selected items"""
        self._model.blockSignals(True)
        for i in range(self._model.rowCount()):
            item = self._model.item(i)
            if item:
                if item.text() in items and item.text() not in self._disabled_items:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)
        self._model.blockSignals(False)
        self._update_display()
    
    def disable_items(self, items: Set[str]):
        """Disable specific items (used elsewhere)"""
        self._disabled_items = items
        self._rebuild_model()


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
    """Widget for displaying columns with type and sum"""
    
    column_marked = pyqtSignal(str, str)  # column_name, mark_type ('Tax', 'Excluded', 'Clear')
    
    def __init__(self, parent=None):
        super().__init__("Column List", parent)
        self.columns = {}  # col_name -> {'type': str, 'sum': float/None, 'is_numeric': bool}
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Legend
        legend = QLabel("Legend: [T]=Tax  [E]=Excluded  [S]=Standard  [ ]=Taxable (contributes to value)")
        legend.setStyleSheet("color: gray; font-size: 10px;")
        legend.setWordWrap(True)
        layout.addWidget(legend)
        
        # Column table
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(['Column Name', 'Type', 'Sum'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        self.btn_mark_tax = QPushButton("Mark as Tax")
        self.btn_mark_tax.clicked.connect(lambda: self._mark_selected('Tax'))
        btn_layout.addWidget(self.btn_mark_tax)
        
        self.btn_mark_exclude = QPushButton("Mark as Exclude")
        self.btn_mark_exclude.clicked.connect(lambda: self._mark_selected('Excluded'))
        btn_layout.addWidget(self.btn_mark_exclude)
        
        self.btn_clear_mark = QPushButton("Clear Mark")
        self.btn_clear_mark.clicked.connect(lambda: self._mark_selected('Taxable'))
        btn_layout.addWidget(self.btn_clear_mark)
        
        layout.addLayout(btn_layout)
    
    def set_columns(self, column_data: List[Dict]):
        """
        Set columns with their data.
        column_data: List of {'name': str, 'type': str, 'sum': float/None, 'is_numeric': bool}
        """
        self.columns.clear()
        self.table.setRowCount(0)
        
        for col_info in column_data:
            name = col_info['name']
            self.columns[name] = col_info
            self._add_column_row(col_info)
    
    def _add_column_row(self, col_info: Dict):
        """Add a column row to the table"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        name = col_info['name']
        col_type = col_info['type']
        col_sum = col_info.get('sum')
        is_numeric = col_info.get('is_numeric', False)
        
        # Type prefix
        prefix_map = {'Tax': '[T]', 'Excluded': '[E]', 'Standard': '[S]', 'Taxable': '[ ]'}
        prefix = prefix_map.get(col_type, '[ ]')
        
        # Column name with prefix
        name_item = QTableWidgetItem(f"{prefix} {name}")
        name_item.setData(Qt.UserRole, name)
        
        # Type
        type_item = QTableWidgetItem(col_type)
        
        # Sum
        if is_numeric and col_sum is not None:
            sum_item = QTableWidgetItem(f"{col_sum:,.2f}")
            sum_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        else:
            sum_item = QTableWidgetItem("Text" if not is_numeric else "-")
            sum_item.setTextAlignment(Qt.AlignCenter)
        
        # Color coding
        colors = {
            'Tax': QColor('#C6EFCE'),
            'Excluded': QColor('#FFEB9C'),
            'Standard': QColor('#DDEBF7'),
            'Taxable': QColor('#FFFFFF')
        }
        bg_color = colors.get(col_type, QColor('#FFFFFF'))
        
        for item in [name_item, type_item, sum_item]:
            item.setBackground(QBrush(bg_color))
        
        self.table.setItem(row, 0, name_item)
        self.table.setItem(row, 1, type_item)
        self.table.setItem(row, 2, sum_item)
    
    def _mark_selected(self, mark_type: str):
        """Mark selected columns with given type"""
        selected_rows = self.table.selectionModel().selectedRows()
        
        for index in selected_rows:
            row = index.row()
            name_item = self.table.item(row, 0)
            if name_item:
                col_name = name_item.data(Qt.UserRole)
                if col_name in self.columns:
                    # Don't change Standard columns
                    if self.columns[col_name]['type'] == 'Standard':
                        continue
                    
                    self.columns[col_name]['type'] = mark_type
                    self.column_marked.emit(col_name, mark_type)
        
        self._refresh_table()
    
    def _refresh_table(self):
        """Refresh table display"""
        self.table.setRowCount(0)
        for name, info in self.columns.items():
            self._add_column_row({'name': name, **info})
    
    def get_excluded_columns(self) -> List[str]:
        """Get list of excluded column names"""
        return [col for col, info in self.columns.items() if info['type'] == 'Excluded']
    
    def get_tax_columns(self) -> List[str]:
        """Get list of tax column names"""
        return [col for col, info in self.columns.items() if info['type'] == 'Tax']
    
    def get_column_types(self) -> Dict[str, str]:
        """Get dict of column name -> type"""
        return {col: info['type'] for col, info in self.columns.items()}
    
    def get_all_columns(self) -> List[str]:
        """Get all column names"""
        return list(self.columns.keys())


class TaxConfigWidget(QGroupBox):
    """Widget for editing tax configuration with multi-select dropdowns"""
    
    config_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__("Tax Configuration", parent)
        self._available_columns = []
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
    
    def set_available_columns(self, columns: List[str]):
        """Set available columns for selection"""
        self._available_columns = columns
        self._update_column_dropdowns()
    
    def _get_used_columns(self, exclude_row: int = -1) -> Set[str]:
        """Get set of columns already used in other rows"""
        used = set()
        for row in range(self.table.rowCount()):
            if row == exclude_row:
                continue
            
            combo = self.table.cellWidget(row, 2)
            if combo and isinstance(combo, MultiSelectComboBox):
                used.update(combo.get_selected())
        
        return used
    
    def _update_column_dropdowns(self):
        """Update all column dropdowns with current available/used columns"""
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 2)
            if combo and isinstance(combo, MultiSelectComboBox):
                used = self._get_used_columns(exclude_row=row)
                combo.set_items(self._available_columns, disabled=used)
    
    def set_config(self, tax_config: List[Dict]):
        """Set tax configuration data"""
        self.table.setRowCount(0)
        
        for row_data in tax_config:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # TaxType combo
            type_combo = QComboBox()
            type_combo.addItems(['CGST', 'SGST', 'IGST', 'CESS'])
            type_combo.setCurrentText(row_data.get('TaxType', 'CGST'))
            self.table.setCellWidget(row, 0, type_combo)
            
            # TaxRate
            self.table.setItem(row, 1, QTableWidgetItem(row_data.get('TaxRate', '')))
            
            # ColumnNames - MultiSelect ComboBox (empty by default)
            col_combo = MultiSelectComboBox()
            col_combo.set_items(self._available_columns)
            col_combo.selection_changed.connect(self._on_column_selection_changed)
            self.table.setCellWidget(row, 2, col_combo)
            
            # Delimiter
            self.table.setItem(row, 3, QTableWidgetItem(row_data.get('Delimiter', ',')))
        
        self._update_column_dropdowns()
    
    def _on_column_selection_changed(self):
        """Handle column selection change in any row"""
        self._update_column_dropdowns()
        self.config_changed.emit()
    
    def get_config(self) -> List[Dict]:
        """Get tax configuration data"""
        config = []
        for row in range(self.table.rowCount()):
            type_combo = self.table.cellWidget(row, 0)
            col_combo = self.table.cellWidget(row, 2)
            
            tax_type = type_combo.currentText() if type_combo else ''
            col_names = ", ".join(col_combo.get_selected()) if col_combo else ''
            
            config.append({
                'TaxType': tax_type,
                'TaxRate': self.table.item(row, 1).text() if self.table.item(row, 1) else '',
                'ColumnNames': col_names,
                'Delimiter': self.table.item(row, 3).text() if self.table.item(row, 3) else ','
            })
        return config
    
    def _add_row(self):
        """Add a new row"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # TaxType combo
        type_combo = QComboBox()
        type_combo.addItems(['CGST', 'SGST', 'IGST', 'CESS'])
        self.table.setCellWidget(row, 0, type_combo)
        
        # TaxRate - empty
        self.table.setItem(row, 1, QTableWidgetItem(''))
        
        # ColumnNames - empty MultiSelect
        col_combo = MultiSelectComboBox()
        used = self._get_used_columns()
        col_combo.set_items(self._available_columns, disabled=used)
        col_combo.selection_changed.connect(self._on_column_selection_changed)
        self.table.setCellWidget(row, 2, col_combo)
        
        # Delimiter
        self.table.setItem(row, 3, QTableWidgetItem(','))
        
        self.config_changed.emit()
    
    def _delete_row(self):
        """Delete selected row"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)
            self._update_column_dropdowns()
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
    
    def add_column(self, column_name: str):
        """Add a column to exclusion list if not already present"""
        existing = self.get_list()
        if column_name not in existing:
            self.list_widget.addItem(column_name)
            self.list_changed.emit()
    
    def remove_column(self, column_name: str):
        """Remove a column from exclusion list"""
        for i in range(self.list_widget.count()):
            if self.list_widget.item(i).text() == column_name:
                self.list_widget.takeItem(i)
                self.list_changed.emit()
                break
    
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
    export_requested = pyqtSignal()   # Emitted when Export button clicked
    
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self._scanned_column_data = []  # Store full column data from scanning
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
        self.column_list.column_marked.connect(self._on_column_marked)
        top_splitter.addWidget(self.column_list)
        
        top_splitter.setSizes([400, 400])
        layout.addWidget(top_splitter)
        
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
        
        self.btn_export = QPushButton("Export to Excel")
        self.btn_export.setStyleSheet("background-color: #70AD47; color: white; font-weight: bold; padding: 10px;")
        self.btn_export.clicked.connect(self._on_export_clicked)
        btn_layout.addWidget(self.btn_export)
        
        btn_layout.addStretch()
        
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
        """Handle file selection changes - auto scan columns"""
        self._scan_columns()
    
    def _scan_columns(self):
        """Scan columns from all selected files/sheets"""
        from utils.excel_handler import ExcelReader
        
        sources = self.file_selector.get_selected_sources()
        if not sources:
            self.column_list.set_columns([])
            self.tax_config.set_available_columns([])
            return
        
        # Collect column data with sums
        column_stats = {}  # col_name -> {'sum': float, 'count': int, 'is_numeric': bool}
        
        standard_cols = ['Date', 'Particulars', 'Voucher No.', 'Voucher Type', 'Type', 
                        'Vch No.', 'Ref No.', 'GSTIN', 'Party Name']
        
        for filepath, sheet_name in sources:
            try:
                df = ExcelReader.read_sheet(filepath, sheet_name)
                
                # Find header row
                header_row_idx = -1
                for idx in range(min(20, len(df))):
                    row = df.iloc[idx]
                    first_three = [str(val).strip() if pd.notna(val) else '' for val in row.iloc[:3]]
                    if 'Date' in first_three and 'Particulars' in first_three:
                        header_row_idx = idx
                        break
                
                if header_row_idx < 0:
                    continue
                
                # Get headers and data
                headers = df.iloc[header_row_idx].tolist()
                headers = [str(h).strip() if pd.notna(h) else f'Column_{i}' 
                           for i, h in enumerate(headers)]
                
                data = df.iloc[header_row_idx + 1:].copy()
                data.columns = headers
                
                # Remove Grand Total rows
                first_col = headers[0]
                mask = data[first_col].apply(lambda x: 
                    'GRAND TOTAL' not in str(x).upper() if pd.notna(x) else True)
                data = data[mask]
                
                # Collect stats for each column
                for col in headers:
                    if col not in column_stats:
                        column_stats[col] = {'sum': 0, 'count': 0, 'is_numeric': True, 'numeric_count': 0}
                    
                    try:
                        numeric_values = pd.to_numeric(data[col], errors='coerce')
                        valid_sum = numeric_values.sum()
                        valid_count = numeric_values.notna().sum()
                        
                        if valid_count > 0:
                            column_stats[col]['sum'] += valid_sum if pd.notna(valid_sum) else 0
                            column_stats[col]['numeric_count'] += valid_count
                        
                        # Check if majority is numeric
                        total_non_null = data[col].notna().sum()
                        if total_non_null > 0 and valid_count / total_non_null < 0.5:
                            column_stats[col]['is_numeric'] = False
                            
                    except Exception:
                        column_stats[col]['is_numeric'] = False
                    
                    column_stats[col]['count'] += len(data)
                    
            except Exception as e:
                print(f"Error scanning {filepath}/{sheet_name}: {e}")
        
        if not column_stats:
            return
        
        # Get configured tax columns and exclusion list
        tax_column_names = self.config_manager.get_all_tax_column_names()
        exclusion_list = self.exclusion_list.get_list()
        
        # Build column data
        column_data = []
        for col_name, stats in sorted(column_stats.items()):
            # Determine type
            if col_name in tax_column_names:
                col_type = 'Tax'
            elif col_name in exclusion_list:
                col_type = 'Excluded'
            elif col_name in standard_cols:
                col_type = 'Standard'
            else:
                col_type = 'Taxable'
            
            column_data.append({
                'name': col_name,
                'type': col_type,
                'sum': stats['sum'] if stats['is_numeric'] else None,
                'is_numeric': stats['is_numeric']
            })
        
        self._scanned_column_data = column_data
        self.column_list.set_columns(column_data)
        
        # Update tax config available columns
        all_col_names = [c['name'] for c in column_data]
        self.tax_config.set_available_columns(all_col_names)
    
    def _on_column_marked(self, col_name: str, mark_type: str):
        """Handle column marking from column list"""
        if mark_type == 'Excluded':
            self.exclusion_list.add_column(col_name)
        elif mark_type in ('Taxable', 'Tax'):
            self.exclusion_list.remove_column(col_name)
    
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
    
    def _on_export_clicked(self):
        """Handle export button click"""
        self.export_requested.emit()
    
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
    
    def get_scanned_column_data(self) -> List[Dict]:
        """Get full column data from last scan"""
        return self._scanned_column_data
