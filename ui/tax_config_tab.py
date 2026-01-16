"""
Tax Config Tab UI Component
Handles tax column mapping with simplified design showing only Tax-marked columns.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QComboBox, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QBrush

from typing import List, Dict
import re


class TaxConfigTab(QWidget):
    """Tab 3: Tax Column Mapping"""

    config_changed = pyqtSignal()
    process_requested = pyqtSignal()
    export_requested = pyqtSignal()

    # Standard tax rates
    TAX_RATES = ['Generic', '0%', '0.05%', '0.1%', '0.125%', '0.25%',
                 '1.5%', '2.5%', '3%', '5%', '6%', '7.5%', '9%',
                 '12%', '14%', '18%', '28%']

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tax_columns = []  # List of Tax-marked column names
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Header with title and status
        header_layout = QHBoxLayout()

        title = QLabel("Tax Column Mapping")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.lbl_status = QLabel("Status: 0/0 assigned")
        self.lbl_status.setStyleSheet(
            "font-weight: bold; color: #C65911; padding: 5px; "
            "background-color: #F0F0F0; border-radius: 3px;"
        )
        header_layout.addWidget(self.lbl_status)

        layout.addLayout(header_layout)

        # Info text
        info = QLabel(
            "Tax-marked columns from the Columns tab appear here.\n"
            "Assign each to its Tax Type and Rate for proper processing."
        )
        info.setStyleSheet("color: gray; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Table for tax column mapping
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(['Source Column', 'Tax Type', 'Rate', 'Maps To'])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)

        # Placeholder when no tax columns
        self.placeholder = QLabel(
            "No tax columns marked yet.\n\n"
            "Go to the Columns tab and mark columns as Tax,\n"
            "then return here to configure the mapping."
        )
        self.placeholder.setStyleSheet("color: gray; padding: 40px; font-size: 12px;")
        self.placeholder.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.placeholder)

        # Auto-assign button
        btn_layout = QHBoxLayout()

        self.btn_auto_assign = QPushButton("Auto-assign by Name")
        self.btn_auto_assign.setToolTip(
            "Automatically detect Tax Type and Rate from column names.\n"
            "Works for columns like 'CGST @ 9%', 'SGST 5%', 'IGST @ 18%', etc."
        )
        self.btn_auto_assign.clicked.connect(self._auto_assign)
        btn_layout.addWidget(self.btn_auto_assign)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        # Action buttons
        action_layout = QHBoxLayout()

        self.btn_process = QPushButton("Process Data")
        self.btn_process.setStyleSheet(
            "background-color: #4472C4; color: white; font-weight: bold; padding: 10px 20px;"
        )
        self.btn_process.clicked.connect(lambda: self.process_requested.emit())
        action_layout.addWidget(self.btn_process)

        self.btn_export = QPushButton("Export to Excel")
        self.btn_export.setStyleSheet(
            "background-color: #70AD47; color: white; font-weight: bold; padding: 10px 20px;"
        )
        self.btn_export.clicked.connect(lambda: self.export_requested.emit())
        action_layout.addWidget(self.btn_export)

        action_layout.addStretch()
        layout.addLayout(action_layout)

        self._update_visibility()

    def set_tax_marked_columns(self, columns: List[str]):
        """Set columns that are marked as Tax in Column List"""
        self._tax_columns = sorted(columns)
        self._rebuild_table()
        self._update_visibility()
        self._update_status()

    def _rebuild_table(self):
        """Rebuild the table with current tax columns"""
        # Save current mappings
        current_mappings = {}
        for row in range(self.table.rowCount()):
            col_name_item = self.table.item(row, 0)
            type_combo = self.table.cellWidget(row, 1)
            rate_combo = self.table.cellWidget(row, 2)

            if col_name_item and type_combo and rate_combo:
                col_name = col_name_item.text()
                current_mappings[col_name] = {
                    'type': type_combo.currentText(),
                    'rate': rate_combo.currentText()
                }

        # Clear and rebuild
        self.table.setRowCount(0)

        for col_name in self._tax_columns:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Source Column
            name_item = QTableWidgetItem(col_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, name_item)

            # Tax Type dropdown
            type_combo = QComboBox()
            type_combo.addItems(['CGST', 'SGST', 'IGST', 'CESS'])
            type_combo.currentTextChanged.connect(lambda: self._on_mapping_changed())
            self.table.setCellWidget(row, 1, type_combo)

            # Rate dropdown
            rate_combo = QComboBox()
            rate_combo.addItems(self.TAX_RATES)
            rate_combo.currentTextChanged.connect(lambda: self._on_mapping_changed())
            self.table.setCellWidget(row, 2, rate_combo)

            # Maps To (preview)
            maps_to = QTableWidgetItem("")
            maps_to.setFlags(maps_to.flags() & ~Qt.ItemIsEditable)
            maps_to.setForeground(QBrush(QColor('#4472C4')))
            self.table.setItem(row, 3, maps_to)

            # Restore previous mapping if exists
            if col_name in current_mappings:
                type_combo.setCurrentText(current_mappings[col_name]['type'])
                rate_combo.setCurrentText(current_mappings[col_name]['rate'])
            else:
                # Try to auto-detect from name
                detected = self._detect_type_and_rate(col_name)
                if detected:
                    type_combo.setCurrentText(detected['type'])
                    rate_combo.setCurrentText(detected['rate'])

            self._update_maps_to(row)

    def _detect_type_and_rate(self, col_name: str) -> Dict:
        """Try to detect tax type and rate from column name"""
        col_upper = col_name.upper()

        # Detect type
        tax_type = None
        if 'CGST' in col_upper or 'CENTRAL' in col_upper:
            tax_type = 'CGST'
        elif 'SGST' in col_upper or 'STATE' in col_upper:
            tax_type = 'SGST'
        elif 'IGST' in col_upper or 'INTEGRATED' in col_upper:
            tax_type = 'IGST'
        elif 'CESS' in col_upper:
            tax_type = 'CESS'

        if not tax_type:
            return None

        # Detect rate - look for patterns like @9%, 9%, @ 9, etc.
        rate_match = re.search(r'@?\s*(\d+(?:\.\d+)?)\s*%?', col_name)
        if rate_match:
            rate_val = rate_match.group(1)
            # Handle decimal rates (0.05 -> 0.05%)
            rate = f"{rate_val}%"
            if rate in self.TAX_RATES:
                return {'type': tax_type, 'rate': rate}

            # Try without decimal for whole numbers
            try:
                rate_num = float(rate_val)
                if rate_num == int(rate_num):
                    rate = f"{int(rate_num)}%"
                    if rate in self.TAX_RATES:
                        return {'type': tax_type, 'rate': rate}
            except ValueError:
                pass

        # If type found but no rate, use Generic
        return {'type': tax_type, 'rate': 'Generic'}

    def _on_mapping_changed(self):
        """Handle mapping change"""
        # Update all Maps To columns
        for row in range(self.table.rowCount()):
            self._update_maps_to(row)

        self._update_status()
        self.config_changed.emit()

    def _update_maps_to(self, row: int):
        """Update the Maps To preview for a row"""
        type_combo = self.table.cellWidget(row, 1)
        rate_combo = self.table.cellWidget(row, 2)
        maps_to = self.table.item(row, 3)

        if type_combo and rate_combo and maps_to:
            tax_type = type_combo.currentText()
            rate = rate_combo.currentText()

            if rate == 'Generic':
                preview = f"→ {tax_type}_Generic"
            else:
                preview = f"→ {tax_type}_{rate}"

            maps_to.setText(preview)

    def _update_visibility(self):
        """Show/hide table vs placeholder"""
        has_columns = len(self._tax_columns) > 0
        self.table.setVisible(has_columns)
        self.placeholder.setVisible(not has_columns)
        self.btn_auto_assign.setEnabled(has_columns)

    def _update_status(self):
        """Update status label"""
        total = len(self._tax_columns)
        assigned = 0

        for row in range(self.table.rowCount()):
            type_combo = self.table.cellWidget(row, 1)
            rate_combo = self.table.cellWidget(row, 2)

            if type_combo and rate_combo:
                if type_combo.currentText() and rate_combo.currentText():
                    assigned += 1

        if total == 0:
            status_text = "No tax columns marked"
            color = "#C65911"  # Orange
        elif assigned < total:
            status_text = f"Status: {assigned}/{total} assigned"
            color = "#4472C4"  # Blue
        else:
            status_text = f"Status: {total}/{total} assigned ✓"
            color = "#70AD47"  # Green

        self.lbl_status.setText(status_text)
        self.lbl_status.setStyleSheet(
            f"font-weight: bold; color: {color}; padding: 5px; "
            "background-color: #F0F0F0; border-radius: 3px;"
        )

    def _auto_assign(self):
        """Auto-assign tax type and rate based on column names"""
        assigned_count = 0

        for row in range(self.table.rowCount()):
            col_name_item = self.table.item(row, 0)
            type_combo = self.table.cellWidget(row, 1)
            rate_combo = self.table.cellWidget(row, 2)

            if col_name_item and type_combo and rate_combo:
                col_name = col_name_item.text()
                detected = self._detect_type_and_rate(col_name)

                if detected:
                    type_combo.setCurrentText(detected['type'])
                    rate_combo.setCurrentText(detected['rate'])
                    assigned_count += 1

        self._update_status()

        if assigned_count > 0:
            QMessageBox.information(self, "Auto-assign Complete",
                f"Auto-assigned {assigned_count} columns based on naming patterns.\n\n"
                "Please review the assignments and adjust if needed.")
        else:
            QMessageBox.information(self, "Auto-assign",
                "Could not auto-detect types/rates from column names.\n"
                "Please assign manually using the dropdowns.")

    def get_config(self) -> List[Dict]:
        """Get tax configuration as list of dicts"""
        config = []

        for row in range(self.table.rowCount()):
            col_name_item = self.table.item(row, 0)
            type_combo = self.table.cellWidget(row, 1)
            rate_combo = self.table.cellWidget(row, 2)

            if col_name_item and type_combo and rate_combo:
                config.append({
                    'TaxType': type_combo.currentText(),
                    'TaxRate': rate_combo.currentText(),
                    'ColumnNames': col_name_item.text(),
                    'Delimiter': ','
                })

        return config

    def set_config(self, tax_config: List[Dict]):
        """Load tax configuration"""
        # Build lookup from column name to config
        config_lookup = {}
        for cfg in tax_config:
            col_names = cfg.get('ColumnNames', '')
            delimiter = cfg.get('Delimiter', ',')
            for col in col_names.split(delimiter):
                col = col.strip()
                if col:
                    config_lookup[col] = {
                        'type': cfg.get('TaxType', 'CGST'),
                        'rate': cfg.get('TaxRate', 'Generic')
                    }

        # Apply to table
        for row in range(self.table.rowCount()):
            col_name_item = self.table.item(row, 0)
            type_combo = self.table.cellWidget(row, 1)
            rate_combo = self.table.cellWidget(row, 2)

            if col_name_item and type_combo and rate_combo:
                col_name = col_name_item.text()
                if col_name in config_lookup:
                    type_combo.setCurrentText(config_lookup[col_name]['type'])
                    rate_combo.setCurrentText(config_lookup[col_name]['rate'])

        self._update_status()

    def get_tax_column_mapping(self) -> Dict[str, Dict]:
        """Get mapping of column name to tax type/rate"""
        mapping = {}

        for row in range(self.table.rowCount()):
            col_name_item = self.table.item(row, 0)
            type_combo = self.table.cellWidget(row, 1)
            rate_combo = self.table.cellWidget(row, 2)

            if col_name_item and type_combo and rate_combo:
                mapping[col_name_item.text()] = {
                    'type': type_combo.currentText(),
                    'rate': rate_combo.currentText()
                }

        return mapping
