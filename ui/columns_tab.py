"""
Columns Tab UI Component
Handles column configuration with Column List on left and Exclusion List on right.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QListWidget, QListWidgetItem, QLineEdit, QSplitter,
    QFrame, QMessageBox, QInputDialog
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QBrush, QFont

from typing import List, Dict, Set


class ColumnsTab(QWidget):
    """Tab 2: Column List + Exclusion List"""

    column_marked = pyqtSignal(str, str)  # column_name, mark_type ('Tax', 'Excluded', 'Taxable')
    process_requested = pyqtSignal()
    export_requested = pyqtSignal()
    prev_tab_requested = pyqtSignal()  # Emitted when Previous button clicked
    next_tab_requested = pyqtSignal()  # Emitted when Next button clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.columns = {}  # col_name -> {'type': str, 'sum': float/None, 'is_numeric': bool, 'sheets': list}
        self._all_column_data = []
        self._current_sort = ('name', True)  # (field, ascending)
        self._user_type_overrides = {}  # Preserve user markings across rescans
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Main content splitter
        splitter = QSplitter(Qt.Horizontal)

        # Left side: Column List
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Column List header
        header_layout = QHBoxLayout()
        col_title = QLabel("Column List")
        col_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        header_layout.addWidget(col_title)

        header_layout.addStretch()

        self.btn_auto_detect = QPushButton("Auto-detect Tax")
        self.btn_auto_detect.setToolTip("Automatically mark columns containing CGST, SGST, IGST, CESS as Tax")
        self.btn_auto_detect.clicked.connect(self._auto_detect_tax_columns)
        header_layout.addWidget(self.btn_auto_detect)

        left_layout.addLayout(header_layout)

        # Legend
        legend = QLabel("Legend: [T]=Tax  [E]=Excluded  [S]=Standard  [ ]=Taxable")
        legend.setStyleSheet("color: gray; font-size: 10px;")
        left_layout.addWidget(legend)

        # Search and sort row
        search_layout = QHBoxLayout()

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search columns...")
        self.txt_search.textChanged.connect(self._apply_filter)
        search_layout.addWidget(self.txt_search)

        self.btn_clear_search = QPushButton("×")
        self.btn_clear_search.setMaximumWidth(25)
        self.btn_clear_search.clicked.connect(lambda: self.txt_search.clear())
        search_layout.addWidget(self.btn_clear_search)

        search_layout.addWidget(QLabel("Sort:"))

        self.btn_sort_name = QPushButton("Name ↑")
        self.btn_sort_name.setMaximumWidth(70)
        self.btn_sort_name.clicked.connect(lambda: self._toggle_sort('name'))
        search_layout.addWidget(self.btn_sort_name)

        self.btn_sort_type = QPushButton("Type")
        self.btn_sort_type.setMaximumWidth(60)
        self.btn_sort_type.clicked.connect(lambda: self._toggle_sort('type'))
        search_layout.addWidget(self.btn_sort_type)

        self.btn_sort_sum = QPushButton("Sum")
        self.btn_sort_sum.setMaximumWidth(60)
        self.btn_sort_sum.clicked.connect(lambda: self._toggle_sort('sum'))
        search_layout.addWidget(self.btn_sort_sum)

        left_layout.addLayout(search_layout)

        # Column table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['Column Name', 'Type', 'Sum', 'Sh'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        left_layout.addWidget(self.table)

        # Mark buttons
        mark_layout = QHBoxLayout()

        self.btn_mark_tax = QPushButton("Mark as Tax")
        self.btn_mark_tax.clicked.connect(lambda: self._mark_selected('Tax'))
        mark_layout.addWidget(self.btn_mark_tax)

        self.btn_mark_exclude = QPushButton("Mark as Exclude")
        self.btn_mark_exclude.clicked.connect(lambda: self._mark_selected('Excluded'))
        mark_layout.addWidget(self.btn_mark_exclude)

        self.btn_clear_mark = QPushButton("Clear Mark")
        self.btn_clear_mark.clicked.connect(lambda: self._mark_selected('Taxable'))
        mark_layout.addWidget(self.btn_clear_mark)

        mark_layout.addStretch()
        left_layout.addLayout(mark_layout)

        splitter.addWidget(left_widget)

        # Right side: Exclusion List
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        excl_title = QLabel("Exclusion List")
        excl_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        right_layout.addWidget(excl_title)

        excl_info = QLabel("Columns excluded from taxable value calculation")
        excl_info.setStyleSheet("color: gray; font-size: 10px;")
        excl_info.setWordWrap(True)
        right_layout.addWidget(excl_info)

        self.exclusion_list = QListWidget()
        self.exclusion_list.setAlternatingRowColors(True)
        right_layout.addWidget(self.exclusion_list)

        # Add/Remove buttons for exclusion
        excl_btn_layout = QHBoxLayout()

        self.txt_add_excl = QLineEdit()
        self.txt_add_excl.setPlaceholderText("Add column...")
        excl_btn_layout.addWidget(self.txt_add_excl)

        self.btn_add_excl = QPushButton("Add")
        self.btn_add_excl.clicked.connect(self._add_exclusion)
        excl_btn_layout.addWidget(self.btn_add_excl)

        right_layout.addLayout(excl_btn_layout)

        self.btn_remove_excl = QPushButton("Remove Selected")
        self.btn_remove_excl.clicked.connect(self._remove_exclusion)
        right_layout.addWidget(self.btn_remove_excl)

        # Auto-excluded count
        self.lbl_auto_excluded = QLabel("Auto-excluded: 0")
        self.lbl_auto_excluded.setStyleSheet("color: gray; font-size: 10px;")
        right_layout.addWidget(self.lbl_auto_excluded)

        splitter.addWidget(right_widget)

        # Set splitter proportions (70% columns, 30% exclusions)
        splitter.setSizes([700, 300])

        layout.addWidget(splitter)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        # Action buttons
        btn_layout = QHBoxLayout()

        # Previous button
        self.btn_prev = QPushButton("← Previous")
        self.btn_prev.setStyleSheet(
            "background-color: #5B9BD5; color: white; font-weight: bold; padding: 10px 20px;"
        )
        self.btn_prev.clicked.connect(lambda: self.prev_tab_requested.emit())
        btn_layout.addWidget(self.btn_prev)

        # Center spacer
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

        # Center spacer
        btn_layout.addStretch()

        # Next button
        self.btn_next = QPushButton("Next →")
        self.btn_next.setStyleSheet(
            "background-color: #5B9BD5; color: white; font-weight: bold; padding: 10px 20px;"
        )
        self.btn_next.clicked.connect(lambda: self.next_tab_requested.emit())
        btn_layout.addWidget(self.btn_next)

        layout.addLayout(btn_layout)

    def _auto_detect_tax_columns(self):
        """Automatically detect and mark tax columns based on common patterns"""
        tax_patterns = ['CGST', 'SGST', 'IGST', 'CESS', 'GST @', 'GST@',
                        'Central GST', 'State GST', 'Integrated GST', 'Compensation Cess']

        marked_count = 0
        for col_name in self.columns.keys():
            # Skip Standard columns
            if self.columns[col_name]['type'] == 'Standard':
                continue

            # Check if column name contains any tax pattern
            col_upper = col_name.upper()
            for pattern in tax_patterns:
                if pattern.upper() in col_upper:
                    if self.columns[col_name]['type'] != 'Tax':
                        self.columns[col_name]['type'] = 'Tax'
                        self._user_type_overrides[col_name] = 'Tax'

                        # Update _all_column_data too
                        for col_data in self._all_column_data:
                            if col_data['name'] == col_name:
                                col_data['type'] = 'Tax'
                                break

                        self.column_marked.emit(col_name, 'Tax')
                        marked_count += 1
                    break

        self._apply_filter()

        if marked_count > 0:
            QMessageBox.information(self, "Auto-detect Complete",
                f"Marked {marked_count} columns as Tax based on naming patterns.\n\n"
                "Patterns detected: CGST, SGST, IGST, CESS, GST @, etc.")
        else:
            QMessageBox.information(self, "Auto-detect Complete",
                "No additional tax columns detected.\n\n"
                "You can manually mark columns using 'Mark as Tax' button.")

    def _toggle_sort(self, field: str):
        """Toggle sort on a field"""
        current_field, ascending = self._current_sort

        if current_field == field:
            ascending = not ascending
        else:
            ascending = True

        self._current_sort = (field, ascending)
        self._update_sort_buttons()
        self._apply_filter()

    def _update_sort_buttons(self):
        """Update sort button labels"""
        field, ascending = self._current_sort
        arrow = "↑" if ascending else "↓"

        self.btn_sort_name.setText("Name" + (f" {arrow}" if field == 'name' else ""))
        self.btn_sort_type.setText("Type" + (f" {arrow}" if field == 'type' else ""))
        self.btn_sort_sum.setText("Sum" + (f" {arrow}" if field == 'sum' else ""))

    def _apply_filter(self):
        """Apply search filter and sort to the table"""
        search_text = self.txt_search.text().lower().strip()
        field, ascending = self._current_sort

        # Filter columns
        if search_text:
            filtered = [c for c in self._all_column_data if search_text in c['name'].lower()]
        else:
            filtered = self._all_column_data.copy()

        # Sort columns
        if field == 'name':
            filtered.sort(key=lambda x: x['name'].lower(), reverse=not ascending)
        elif field == 'type':
            type_order = {'Tax': 0, 'Excluded': 1, 'Standard': 2, 'Taxable': 3}
            filtered.sort(key=lambda x: (type_order.get(x['type'], 99), x['name'].lower()),
                         reverse=not ascending)
        elif field == 'sum':
            def sum_key(x):
                if x.get('is_numeric') and x.get('sum') is not None:
                    return (0, -x['sum'] if ascending else x['sum'])
                return (1, x['name'].lower())
            filtered.sort(key=sum_key, reverse=not ascending)

        # Update table
        self.table.setRowCount(0)
        for col_info in filtered:
            self._add_column_row(col_info)

    def _add_column_row(self, col_info: Dict):
        """Add a column row to the table"""
        row = self.table.rowCount()
        self.table.insertRow(row)

        name = col_info['name']
        col_type = col_info['type']
        col_sum = col_info.get('sum')
        is_numeric = col_info.get('is_numeric', False)
        sheets = col_info.get('sheets', [])

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

        # Sheet count with tooltip
        sheet_count = len(sheets) if sheets else 0
        sheet_item = QTableWidgetItem(str(sheet_count) if sheet_count > 0 else "-")
        sheet_item.setTextAlignment(Qt.AlignCenter)

        if sheets:
            tooltip = "Found in:\n" + "\n".join(f"  • {s}" for s in sheets)
            sheet_item.setToolTip(tooltip)
            name_item.setToolTip(f"{name}\n\n{tooltip}")

        # Color coding
        colors = {
            'Tax': QColor('#C6EFCE'),
            'Excluded': QColor('#FFEB9C'),
            'Standard': QColor('#DDEBF7'),
            'Taxable': QColor('#FFFFFF')
        }
        bg_color = colors.get(col_type, QColor('#FFFFFF'))

        for item in [name_item, type_item, sum_item, sheet_item]:
            item.setBackground(QBrush(bg_color))

        self.table.setItem(row, 0, name_item)
        self.table.setItem(row, 1, type_item)
        self.table.setItem(row, 2, sum_item)
        self.table.setItem(row, 3, sheet_item)

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

                    old_type = self.columns[col_name]['type']
                    self.columns[col_name]['type'] = mark_type
                    self._user_type_overrides[col_name] = mark_type

                    # Update _all_column_data too
                    for col_data in self._all_column_data:
                        if col_data['name'] == col_name:
                            col_data['type'] = mark_type
                            break

                    # Handle exclusion list sync
                    if mark_type == 'Excluded':
                        self._add_to_exclusion_list(col_name)
                    elif old_type == 'Excluded':
                        self._remove_from_exclusion_list(col_name)

                    self.column_marked.emit(col_name, mark_type)

        self._apply_filter()

    def _add_to_exclusion_list(self, col_name: str):
        """Add column to exclusion list widget (case-insensitive duplicate check)"""
        items = [self.exclusion_list.item(i).text()
                 for i in range(self.exclusion_list.count())]
        # Case-insensitive check to avoid duplicates like "Discount" and "discount"
        items_lower = [item.lower() for item in items]
        if col_name.lower() not in items_lower:
            self.exclusion_list.addItem(col_name)

    def _remove_from_exclusion_list(self, col_name: str):
        """Remove column from exclusion list widget"""
        for i in range(self.exclusion_list.count()):
            if self.exclusion_list.item(i).text() == col_name:
                self.exclusion_list.takeItem(i)
                break

    def _add_exclusion(self):
        """Add item to exclusion list (case-insensitive duplicate check)"""
        text = self.txt_add_excl.text().strip()
        if text:
            items = [self.exclusion_list.item(i).text()
                     for i in range(self.exclusion_list.count())]
            items_lower = [item.lower() for item in items]
            if text.lower() not in items_lower:
                self.exclusion_list.addItem(text)
                self.txt_add_excl.clear()

    def _remove_exclusion(self):
        """Remove selected item from exclusion list"""
        current_row = self.exclusion_list.currentRow()
        if current_row >= 0:
            item = self.exclusion_list.takeItem(current_row)
            col_name = item.text()

            # Also update column type if it exists
            if col_name in self.columns and self.columns[col_name]['type'] == 'Excluded':
                self.columns[col_name]['type'] = 'Taxable'
                self._user_type_overrides[col_name] = 'Taxable'

                for col_data in self._all_column_data:
                    if col_data['name'] == col_name:
                        col_data['type'] = 'Taxable'
                        break

                self._apply_filter()
                self.column_marked.emit(col_name, 'Taxable')

    def set_columns(self, column_data: List[Dict], preserve_user_types: bool = True):
        """
        Set columns with their data.
        column_data: List of {'name': str, 'type': str, 'sum': float/None, 'is_numeric': bool, 'sheets': list}
        """
        self.columns.clear()
        self._all_column_data = []

        for col_info in column_data:
            name = col_info['name']

            # Apply user override if exists and should preserve
            if preserve_user_types and name in self._user_type_overrides:
                col_info = col_info.copy()
                col_info['type'] = self._user_type_overrides[name]

            self.columns[name] = col_info
            self._all_column_data.append(col_info)

        self._apply_filter()

    def set_exclusion_list(self, exclusion_list: List[str]):
        """Set exclusion list items"""
        self.exclusion_list.clear()
        for item in exclusion_list:
            self.exclusion_list.addItem(item)

    def get_exclusion_list(self) -> List[str]:
        """Get exclusion list items"""
        return [self.exclusion_list.item(i).text()
                for i in range(self.exclusion_list.count())]

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

    def get_scanned_column_data(self) -> List[Dict]:
        """Get full column data from last scan"""
        return self._all_column_data

    def add_column(self, col_name: str, col_type: str = 'Excluded'):
        """Add a column with specified type"""
        if col_type == 'Excluded':
            self._add_to_exclusion_list(col_name)
        elif col_type == 'Tax':
            # Mark as Tax in internal tracking
            if col_name in self.columns:
                self.columns[col_name]['type'] = 'Tax'
                self._user_type_overrides[col_name] = 'Tax'
                self.column_marked.emit(col_name, 'Tax')
        elif col_type == 'Taxable':
            # Mark as Taxable (clear exclusion)
            if col_name in self.columns:
                self.columns[col_name]['type'] = 'Taxable'
                self._user_type_overrides[col_name] = 'Taxable'
                self._remove_from_exclusion_list(col_name)
                self.column_marked.emit(col_name, 'Taxable')
