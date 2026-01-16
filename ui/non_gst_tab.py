"""
Non-GST Transactions Tab UI Component
Displays processed Non-GST transactions with summary statistics.
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QFrame
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QBrush, QFont

import pandas as pd
from typing import Optional


class NonGSTStatsBar(QFrame):
    """Statistics bar for Non-GST transactions"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.StyledPanel)
        self.setStyleSheet("background-color: #FFF2CC; padding: 5px;")
        self._init_ui()
    
    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Records count
        self.lbl_records = QLabel("Records: 0")
        self.lbl_records.setFont(QFont("Arial", 10, QFont.Bold))
        layout.addWidget(self.lbl_records)
        
        layout.addWidget(self._separator())
        
        # Total Value
        self.lbl_value = QLabel("Total Value: ₹0.00")
        layout.addWidget(self.lbl_value)
        
        layout.addWidget(self._separator())
        
        # Info label
        self.lbl_info = QLabel("⚠ Review required for RCM/Exempt classification")
        self.lbl_info.setStyleSheet("color: #C65911;")
        layout.addWidget(self.lbl_info)
        
        layout.addStretch()
    
    def _separator(self) -> QLabel:
        """Create a separator label"""
        sep = QLabel("|")
        sep.setStyleSheet("color: gray;")
        return sep
    
    def update_stats(self, record_count: int, total_value: float):
        """Update statistics display"""
        self.lbl_records.setText(f"Records: {record_count:,}")
        self.lbl_value.setText(f"Total Value: ₹{total_value:,.2f}")


class NonGSTDataTableWidget(QTableWidget):
    """Enhanced table widget for Non-GST data"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlternatingRowColors(True)
        self.setStyleSheet("""
            QTableWidget {
                gridline-color: #D0D0D0;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #ED7D31;
                color: white;
                padding: 5px;
                border: 1px solid #C65911;
                font-weight: bold;
            }
        """)
        
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().setDefaultSectionSize(25)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
    
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
                    if col_name in ('Taxable Value',):
                        display_value = f"{value:,.2f}"
                    else:
                        display_value = str(value)
                else:
                    display_value = str(value)
                
                item = QTableWidgetItem(display_value)
                
                # Right-align numbers
                if isinstance(value, (int, float)) and not pd.isna(value):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
                # Highlight Review Required column
                if col_name == 'Review Required':
                    item.setBackground(QBrush(QColor('#FFEB9C')))  # Yellow
                    item.setFont(QFont("Arial", 10, QFont.Bold))
                
                # Highlight Transaction Type
                if col_name == 'Transaction Type':
                    item.setBackground(QBrush(QColor('#DDEBF7')))  # Light blue
                
                self.setItem(row_idx, col_idx, item)
        
        # Adjust column widths
        self.resizeColumnsToContents()
        
        # Limit column widths
        for col in range(self.columnCount()):
            if self.columnWidth(col) > 200:
                self.setColumnWidth(col, 200)


class NonGSTTab(QWidget):
    """Non-GST Transactions Tab"""

    prev_tab_requested = pyqtSignal()  # Emitted when Previous button clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = None
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Stats bar
        self.stats_bar = NonGSTStatsBar()
        layout.addWidget(self.stats_bar)
        
        # Data table
        self.table = NonGSTDataTableWidget()
        layout.addWidget(self.table)
        
        # Navigation and Export buttons
        btn_layout = QHBoxLayout()

        # Previous button
        self.btn_prev = QPushButton("← Previous")
        self.btn_prev.setStyleSheet(
            "background-color: #5B9BD5; color: white; font-weight: bold; padding: 10px 20px;"
        )
        self.btn_prev.clicked.connect(lambda: self.prev_tab_requested.emit())
        btn_layout.addWidget(self.btn_prev)

        btn_layout.addStretch()

        self.btn_export = QPushButton("Export Non-GST Transactions")
        self.btn_export.setStyleSheet(
            "background-color: #70AD47; color: white; font-weight: bold; padding: 10px 20px;"
        )
        self.btn_export.clicked.connect(self._export_data)
        btn_layout.addWidget(self.btn_export)

        btn_layout.addStretch()

        layout.addLayout(btn_layout)
    
    def set_data(self, df: pd.DataFrame):
        """Set data and update display"""
        self.data = df
        
        if df is None or len(df) == 0:
            self.stats_bar.update_stats(0, 0)
            self.table.load_dataframe(pd.DataFrame())
            return
        
        # Calculate stats
        record_count = len(df)
        
        total_value = 0
        if 'Taxable Value' in df.columns:
            total_value = df['Taxable Value'].sum()
        
        # Update UI
        self.stats_bar.update_stats(record_count, total_value)
        self.table.load_dataframe(df)
    
    def _export_data(self):
        """Export Non-GST data to Excel"""
        if self.data is None or len(self.data) == 0:
            QMessageBox.warning(self, "Warning", "No data to export.")
            return
        
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Non-GST Transactions",
            "NonGST_Transactions.xlsx",
            "Excel Files (*.xlsx)"
        )
        
        if filepath:
            try:
                self.data.to_excel(filepath, index=False, sheet_name="Non-GST Transactions")
                QMessageBox.information(self, "Success", f"Data exported to:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed:\n{str(e)}")
    
    def get_data(self) -> Optional[pd.DataFrame]:
        """Get current data"""
        return self.data
