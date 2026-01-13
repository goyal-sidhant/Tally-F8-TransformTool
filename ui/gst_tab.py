"""
GST Transactions Tab UI Component
Displays processed GST transactions with summary statistics.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QFrame
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush, QFont

import pandas as pd
from typing import Optional


class StatsBar(QFrame):
    """Statistics bar showing summary information"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.StyledPanel)
        self.setStyleSheet("background-color: #F0F0F0; padding: 5px;")
        self._init_ui()
    
    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Records count
        self.lbl_records = QLabel("Records: 0")
        self.lbl_records.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(self.lbl_records)
        
        layout.addWidget(self._separator())
        
        # Total Taxable
        self.lbl_taxable = QLabel("Total Taxable: ₹0.00")
        layout.addWidget(self.lbl_taxable)
        
        layout.addWidget(self._separator())
        
        # Total Tax
        self.lbl_tax = QLabel("Total Tax: ₹0.00")
        layout.addWidget(self.lbl_tax)
        
        layout.addStretch()
    
    def _separator(self) -> QLabel:
        """Create a separator label"""
        sep = QLabel("|")
        sep.setStyleSheet("color: gray;")
        return sep
    
    def update_stats(self, record_count: int, total_taxable: float, total_tax: float):
        """Update statistics display"""
        self.lbl_records.setText(f"Records: {record_count:,}")
        self.lbl_taxable.setText(f"Total Taxable: ₹{total_taxable:,.2f}")
        self.lbl_tax.setText(f"Total Tax: ₹{total_tax:,.2f}")


class DataTableWidget(QTableWidget):
    """Enhanced table widget for displaying data"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.setStyleSheet("""
            QTableWidget {
                gridline-color: #D0D0D0;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #4472C4;
                color: white;
                padding: 5px;
                border: 1px solid #3060A0;
                font-weight: bold;
            }
        """)
        
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setDefaultSectionSize(25)
        self.setEditTriggers(QTableWidget.NoEditTriggers)  # Read-only
    
    def load_dataframe(self, df: pd.DataFrame):
        """Load data from DataFrame"""
        if df is None or len(df) == 0:
            self.clear()
            self.setRowCount(0)
            self.setColumnCount(0)
            return
        
        # Set dimensions
        self.setRowCount(len(df))
        self.setColumnCount(len(df.columns))
        self.setHorizontalHeaderLabels(df.columns.tolist())
        
        # Populate data
        for row_idx in range(len(df)):
            for col_idx, col_name in enumerate(df.columns):
                value = df.iloc[row_idx, col_idx]
                
                # Format value
                if pd.isna(value):
                    display_value = ""
                elif isinstance(value, (int, float)):
                    if col_name.startswith(('CGST_', 'SGST_', 'IGST_', 'Total ', 'Taxable')):
                        display_value = f"{value:,.2f}"
                    else:
                        display_value = str(value)
                else:
                    display_value = str(value)
                
                item = QTableWidgetItem(display_value)
                
                # Right-align numbers
                if isinstance(value, (int, float)) and not pd.isna(value):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
                # Color coding for tax columns
                if col_name.startswith(('CGST_', 'SGST_')):
                    item.setBackground(QBrush(QColor('#E2EFDA')))  # Light green
                elif col_name.startswith('IGST_'):
                    item.setBackground(QBrush(QColor('#DDEBF7')))  # Light blue
                elif col_name.startswith('Total '):
                    item.setBackground(QBrush(QColor('#FCE4D6')))  # Light orange
                
                self.setItem(row_idx, col_idx, item)
        
        # Adjust column widths
        self.resizeColumnsToContents()
        
        # Limit column widths
        for col in range(self.columnCount()):
            if self.columnWidth(col) > 200:
                self.setColumnWidth(col, 200)


class GSTTab(QWidget):
    """GST Transactions Tab"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = None
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Stats bar
        self.stats_bar = StatsBar()
        layout.addWidget(self.stats_bar)
        
        # Data table
        self.table = DataTableWidget()
        layout.addWidget(self.table)
        
        # Export button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_export = QPushButton("Export GST Transactions")
        self.btn_export.setStyleSheet("padding: 8px 20px;")
        self.btn_export.clicked.connect(self._export_data)
        btn_layout.addWidget(self.btn_export)
        
        layout.addLayout(btn_layout)
    
    def set_data(self, df: pd.DataFrame):
        """Set data and update display"""
        self.data = df
        
        if df is None or len(df) == 0:
            self.stats_bar.update_stats(0, 0, 0)
            self.table.load_dataframe(pd.DataFrame())
            return
        
        # Calculate stats
        record_count = len(df)
        
        total_taxable = 0
        if 'Taxable Value' in df.columns:
            total_taxable = df['Taxable Value'].sum()
        
        total_tax = 0
        for col in ['Total CGST', 'Total SGST', 'Total IGST']:
            if col in df.columns:
                total_tax += df[col].sum()
        
        # Update UI
        self.stats_bar.update_stats(record_count, total_taxable, total_tax)
        self.table.load_dataframe(df)
    
    def _export_data(self):
        """Export GST data to Excel"""
        if self.data is None or len(self.data) == 0:
            QMessageBox.warning(self, "Warning", "No data to export.")
            return
        
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export GST Transactions",
            "GST_Transactions.xlsx",
            "Excel Files (*.xlsx)"
        )
        
        if filepath:
            try:
                self.data.to_excel(filepath, index=False, sheet_name="GST Transactions")
                QMessageBox.information(self, "Success", f"Data exported to:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed:\n{str(e)}")
    
    def get_data(self) -> Optional[pd.DataFrame]:
        """Get current data"""
        return self.data
