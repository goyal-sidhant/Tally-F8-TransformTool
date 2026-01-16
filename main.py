"""
GST Compliance Data Transformation Tool
Main Application Entry Point

A PyQt5 Windows application for transforming Tally ERP GST data exports
into structured formats suitable for GST compliance and ITC analysis.

Author: Sidhant
Version: 2.0
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QMessageBox, QProgressDialog, QFileDialog, QStatusBar, QInputDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon

import pandas as pd
from typing import List, Tuple, Dict, Any

from core.processor import GSTProcessor, ProcessingResult
from core.config_manager import ConfigManager
from ui.files_tab import FilesTab
from ui.columns_tab import ColumnsTab
from ui.tax_config_tab import TaxConfigTab
from ui.gst_tab import GSTTab
from ui.non_gst_tab import NonGSTTab
from utils.excel_handler import ExcelReader, ExcelWriter
from utils.helpers import get_source_name


class ProcessingThread(QThread):
    """Background thread for processing data"""

    progress_updated = pyqtSignal(int, str)
    processing_complete = pyqtSignal(object)
    processing_error = pyqtSignal(str)

    def __init__(self, processor: GSTProcessor, sources: List[Tuple[pd.DataFrame, str]]):
        super().__init__()
        self.processor = processor
        self.sources = sources

    def run(self):
        try:
            self.progress_updated.emit(10, "Starting processing...")
            result = self.processor.process_multiple_sources(self.sources)
            self.progress_updated.emit(100, "Processing complete!")
            self.processing_complete.emit(result)
        except Exception as e:
            self.processing_error.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()

        self.config_manager = ConfigManager()
        self.processing_result = None
        self._scanned_column_data = []  # Store column data from scanning

        self._init_ui()
        self._setup_connections()
        self._load_config()

    def _init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("GST Compliance Tool - Tally F8 Transformer v2.0")
        self.setMinimumSize(1200, 800)

        # Central widget with tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Tab 1: Files
        self.files_tab = FilesTab()
        self.tabs.addTab(self.files_tab, "1. Files")

        # Tab 2: Columns
        self.columns_tab = ColumnsTab()
        self.tabs.addTab(self.columns_tab, "2. Columns")

        # Tab 3: Tax Config
        self.tax_config_tab = TaxConfigTab()
        self.tabs.addTab(self.tax_config_tab, "3. Tax Config")

        # Tab 4: GST Transactions
        self.gst_tab = GSTTab()
        self.tabs.addTab(self.gst_tab, "GST Transactions")

        # Tab 5: Non-GST Transactions
        self.non_gst_tab = NonGSTTab()
        self.tabs.addTab(self.non_gst_tab, "Non-GST Transactions")

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Add files to begin")

        # Menu bar
        self._create_menu()

    def _create_menu(self):
        """Create menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        export_action = file_menu.addAction("Export Complete Report")
        export_action.triggered.connect(self._export_complete)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

        # Config menu
        config_menu = menubar.addMenu("Configuration")

        save_config = config_menu.addAction("Save Configuration")
        save_config.triggered.connect(self._save_config)

        load_config = config_menu.addAction("Load Configuration")
        load_config.triggered.connect(self._load_config_dialog)

        config_menu.addSeparator()

        reset_config = config_menu.addAction("Reset to Defaults")
        reset_config.triggered.connect(self._reset_config)

        # Help menu
        help_menu = menubar.addMenu("Help")

        about_action = help_menu.addAction("About")
        about_action.triggered.connect(self._show_about)

    def _setup_connections(self):
        """Set up signal connections"""
        # Files tab signals
        self.files_tab.files_changed.connect(self._on_files_changed)
        self.files_tab.process_requested.connect(self._process_data)
        self.files_tab.export_requested.connect(self._export_complete)

        # Columns tab signals
        self.columns_tab.column_marked.connect(self._on_column_marked)
        self.columns_tab.process_requested.connect(self._process_data)
        self.columns_tab.export_requested.connect(self._export_complete)

        # Tax config tab signals
        self.tax_config_tab.config_changed.connect(self._on_config_changed)
        self.tax_config_tab.process_requested.connect(self._process_data)
        self.tax_config_tab.export_requested.connect(self._export_complete)

    def _load_config(self):
        """Load configuration into UI"""
        # Load exclusion list into columns tab
        self.columns_tab.set_exclusion_list(
            self.config_manager.current_config.exclusion_list
        )

    def _on_files_changed(self):
        """Handle file selection changes - scan columns"""
        self._scan_columns()

    def _scan_columns(self):
        """Scan columns from all selected files/sheets"""
        from PyQt5.QtWidgets import QApplication

        sources = self.files_tab.get_selected_sources()
        if not sources:
            self.columns_tab.set_columns([], preserve_user_types=True)
            self.tax_config_tab.set_tax_marked_columns([])
            return

        self.status_bar.showMessage("Scanning columns...")
        QApplication.processEvents()

        # Collect column data with sums and sheet tracking
        column_stats = {}  # col_name -> {'sum': float, 'count': int, 'sheets': set, ...}
        row_counts = {}  # filepath -> {sheet: row_count}

        standard_cols = ['Date', 'Particulars', 'Voucher No.', 'Voucher Type', 'Type',
                        'Vch No.', 'Ref No.', 'GSTIN', 'Party Name']

        for filepath, sheet_name in sources:
            QApplication.processEvents()

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
                columns_to_check = []
                if 'Particulars' in headers:
                    columns_to_check.append('Particulars')
                for col in headers[:3]:
                    if col not in columns_to_check:
                        columns_to_check.append(col)

                def is_not_grand_total(row):
                    for col in columns_to_check:
                        val = row.get(col, '')
                        if pd.notna(val) and 'GRAND TOTAL' in str(val).upper():
                            return False
                    return True

                mask = data.apply(is_not_grand_total, axis=1)
                data = data[mask]

                # Store row count
                if filepath not in row_counts:
                    row_counts[filepath] = {}
                row_counts[filepath][sheet_name] = len(data)

                # Get short sheet identifier
                short_filename = os.path.basename(filepath)
                sheet_id = f"{short_filename} | {sheet_name}"

                # Collect stats for each column
                for col in headers:
                    if col not in column_stats:
                        column_stats[col] = {
                            'sum': 0,
                            'count': 0,
                            'numeric_count': 0,
                            'total_non_null': 0,
                            'sheets': set()
                        }

                    column_stats[col]['sheets'].add(sheet_id)

                    try:
                        numeric_values = pd.to_numeric(data[col], errors='coerce')
                        valid_sum = numeric_values.sum()
                        valid_count = numeric_values.notna().sum()
                        total_non_null = data[col].notna().sum()

                        if valid_count > 0:
                            column_stats[col]['sum'] += valid_sum if pd.notna(valid_sum) else 0

                        column_stats[col]['numeric_count'] += valid_count
                        column_stats[col]['total_non_null'] += total_non_null

                    except Exception:
                        pass

                    column_stats[col]['count'] += len(data)

            except Exception as e:
                print(f"Error scanning {filepath}/{sheet_name}: {e}")

        if not column_stats:
            self.status_bar.showMessage("No columns found")
            return

        # Update row counts in files tab
        self.files_tab.set_row_counts(row_counts)

        # Determine is_numeric for each column (80% threshold)
        for col_name, stats in column_stats.items():
            total_non_null = stats.get('total_non_null', 0)
            numeric_count = stats.get('numeric_count', 0)

            if total_non_null > 0:
                numeric_ratio = numeric_count / total_non_null
                stats['is_numeric'] = numeric_ratio >= 0.8
            else:
                stats['is_numeric'] = False

        # Get configured tax columns and exclusion list
        tax_column_names = self.config_manager.get_all_tax_column_names()
        exclusion_list = self.columns_tab.get_exclusion_list()

        # Auto-exclude column names
        auto_exclude_names = ['value', 'gross total', 'gstin/uin', 'gstin', 'uin']

        # Build column data
        column_data = []
        auto_excluded_cols = []

        for col_name, stats in sorted(column_stats.items()):
            col_name_lower = col_name.lower().strip()

            # Determine type
            if col_name in tax_column_names:
                col_type = 'Tax'
            elif col_name in exclusion_list:
                col_type = 'Excluded'
            elif col_name in standard_cols:
                col_type = 'Standard'
            elif not stats['is_numeric']:
                col_type = 'Excluded'
                if col_name not in exclusion_list:
                    auto_excluded_cols.append(f"{col_name} (text)")
                    self.columns_tab.add_column(col_name, 'Excluded')
            elif col_name_lower in auto_exclude_names:
                col_type = 'Excluded'
                if col_name not in exclusion_list:
                    auto_excluded_cols.append(f"{col_name} (auto)")
                    self.columns_tab.add_column(col_name, 'Excluded')
            else:
                col_type = 'Taxable'

            sheets_list = sorted(list(stats.get('sheets', set())))

            column_data.append({
                'name': col_name,
                'type': col_type,
                'sum': stats['sum'] if stats['is_numeric'] else None,
                'is_numeric': stats['is_numeric'],
                'sheets': sheets_list
            })

        self._scanned_column_data = column_data
        self.columns_tab.set_columns(column_data, preserve_user_types=True)

        # Update tax config with Tax-marked columns
        tax_marked = self.columns_tab.get_tax_columns()
        self.tax_config_tab.set_tax_marked_columns(tax_marked)

        total_rows = sum(sum(sheets.values()) for sheets in row_counts.values())
        self.status_bar.showMessage(f"Scanned {len(column_data)} columns, {total_rows:,} rows")

    def _on_column_marked(self, col_name: str, mark_type: str):
        """Handle column marking from columns tab"""
        # Update tax config with current Tax-marked columns
        tax_marked = self.columns_tab.get_tax_columns()
        self.tax_config_tab.set_tax_marked_columns(tax_marked)

    def _on_config_changed(self):
        """Handle config changes in tax config tab"""
        # Mark config as changed for save prompt
        pass

    def _process_data(self):
        """Process selected files and sheets"""
        sources = self.files_tab.get_selected_sources()

        if not sources:
            QMessageBox.warning(self, "Warning", "No files selected. Please add files first.")
            return

        # Show progress dialog
        progress = QProgressDialog("Processing data...", "Cancel", 0, 100, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        try:
            # Load data from sources
            progress.setLabelText("Loading files...")
            progress.setValue(5)

            loaded_sources = []
            for filepath, sheet_name in sources:
                if progress.wasCanceled():
                    return

                try:
                    df = ExcelReader.read_sheet(filepath, sheet_name)
                    # Validate that the DataFrame has data
                    if df is None or len(df) == 0:
                        QMessageBox.warning(
                            self, "Warning",
                            f"Sheet '{sheet_name}' in {filepath} is empty. Skipping."
                        )
                        continue
                    source_name = get_source_name(filepath, sheet_name)
                    loaded_sources.append((df, source_name))
                except Exception as e:
                    QMessageBox.warning(
                        self, "Warning",
                        f"Could not load {filepath} / {sheet_name}:\n{str(e)}"
                    )

            if not loaded_sources:
                progress.close()
                QMessageBox.warning(self, "Warning", "No valid data loaded.")
                return

            progress.setLabelText("Processing transactions...")
            progress.setValue(20)

            # Get tax configuration from tax config tab
            tax_config = self.tax_config_tab.get_config()
            self.config_manager.set_tax_config(tax_config)

            # Get exclusion list from columns tab
            exclusion_list = self.columns_tab.get_exclusion_list()
            self.config_manager.set_exclusion_list(exclusion_list)

            # Get tax-marked columns
            tax_marked_columns = self.columns_tab.get_tax_columns()

            # Standard columns to exclude from taxable value calculation
            standard_columns = ['Date', 'Particulars', 'Voucher No.', 'Voucher Type', 'Type',
                                'Vch No.', 'Ref No.', 'GSTIN', 'Party Name', 'GSTIN/UIN']

            # Create processor
            tax_config_df = self.config_manager.get_tax_config_df()
            processor = GSTProcessor(tax_config_df, exclusion_list, tax_marked_columns, standard_columns)

            # Process data
            progress.setValue(40)
            result = processor.process_multiple_sources(loaded_sources)

            progress.setValue(80)

            # Store result
            self.processing_result = result

            # Update UI
            self.gst_tab.set_data(result.gst_data)
            self.non_gst_tab.set_data(result.non_gst_data)

            progress.setValue(100)
            progress.close()

            # Show warnings if any
            if result.warnings:
                warning_text = "\n".join(result.warnings)
                QMessageBox.warning(
                    self, "Processing Warnings",
                    f"Processing completed with warnings:\n\n{warning_text}"
                )

            # Show summary
            gst_count = len(result.gst_data) if result.gst_data is not None else 0
            non_gst_count = len(result.non_gst_data) if result.non_gst_data is not None else 0

            self.status_bar.showMessage(
                f"Processing complete: {gst_count} GST, {non_gst_count} Non-GST transactions"
            )

            # Switch to GST tab
            self.tabs.setCurrentIndex(3)

            QMessageBox.information(
                self, "Success",
                f"Processing complete!\n\n"
                f"GST Transactions: {gst_count:,}\n"
                f"Non-GST Transactions: {non_gst_count:,}"
            )

        except Exception as e:
            progress.close()
            QMessageBox.critical(
                self, "Error",
                f"Processing failed:\n\n{str(e)}"
            )

    def _export_complete(self):
        """Export complete report with all 4 sheets"""
        if self.processing_result is None:
            QMessageBox.warning(
                self, "Warning",
                "No data to export. Please process data first."
            )
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Complete Report",
            "GST_Compliance_Report.xlsx",
            "Excel Files (*.xlsx)"
        )

        if not filepath:
            return

        try:
            # Get data
            gst_data = self.processing_result.gst_data
            non_gst_data = self.processing_result.non_gst_data
            metadata = self.processing_result.metadata

            # Get config
            tax_config = self.config_manager.current_config.tax_config
            exclusion_list = self.config_manager.current_config.exclusion_list

            # Get column types and stats
            column_types = self.columns_tab.get_column_types()
            column_stats = {}
            for col_data in self._scanned_column_data:
                name = col_data.get('name', '')
                column_stats[name] = {
                    'type': col_data.get('type', ''),
                    'sum': col_data.get('sum', 0),
                    'is_numeric': col_data.get('is_numeric', False)
                }

            # Write output
            ExcelWriter.write_output(
                filepath=filepath,
                gst_data=gst_data,
                non_gst_data=non_gst_data,
                metadata=metadata,
                tax_config=tax_config,
                exclusion_list=exclusion_list,
                column_types=column_types,
                column_stats=column_stats
            )

            QMessageBox.information(
                self, "Success",
                f"Report exported successfully to:\n{filepath}"
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Error",
                f"Export failed:\n\n{str(e)}"
            )

    def _save_config(self):
        """Save current configuration"""
        # Update config manager with current values
        self.config_manager.set_tax_config(self.tax_config_tab.get_config())
        self.config_manager.set_exclusion_list(self.columns_tab.get_exclusion_list())

        client_name, ok = QInputDialog.getText(
            self, "Save Configuration",
            "Enter client name:",
            text=self.config_manager.current_config.client_name
        )

        if ok and client_name:
            filename = self.config_manager.save_config(client_name)
            QMessageBox.information(
                self, "Success",
                f"Configuration saved as:\n{filename}"
            )

    def _load_config_dialog(self):
        """Load a saved configuration"""
        configs = self.config_manager.list_configs()

        if not configs:
            QMessageBox.information(self, "Info", "No saved configurations found.")
            return

        config_name, ok = QInputDialog.getItem(
            self, "Load Configuration",
            "Select configuration:",
            configs, 0, False
        )

        if ok and config_name:
            if self.config_manager.load_config(config_name + '.json'):
                self._load_config()

                # Also update tax config tab if we have tax columns
                tax_marked = self.columns_tab.get_tax_columns()
                if tax_marked:
                    self.tax_config_tab.set_tax_marked_columns(tax_marked)
                    self.tax_config_tab.set_config(
                        self.config_manager.current_config.tax_config
                    )

                QMessageBox.information(
                    self, "Success",
                    f"Configuration loaded: {config_name}"
                )
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
            QMessageBox.information(self, "Success", "Configuration reset to defaults.")

    def _show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self, "About GST Compliance Tool",
            "<h2>GST Compliance Tool</h2>"
            "<p>Version 2.0</p>"
            "<p>A tool for transforming Tally ERP GST data exports "
            "into structured formats suitable for GST compliance and ITC analysis.</p>"
            "<p><b>What's New in v2.0:</b></p>"
            "<ul>"
            "<li>Redesigned UI with separate tabs</li>"
            "<li>Improved file management with row counts</li>"
            "<li>Side-by-side Column and Exclusion lists</li>"
            "<li>Simplified Tax Config showing only marked columns</li>"
            "<li>Auto-assign tax types from column names</li>"
            "</ul>"
            "<p><b>Author:</b> Sidhant</p>"
            "<p><b>Built with:</b> Python, PyQt5</p>"
        )

    def closeEvent(self, event):
        """Handle window close"""
        if self.config_manager.has_changes():
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved configuration changes.\nDo you want to save before exiting?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )

            if reply == QMessageBox.Save:
                self._save_config()
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    """Main entry point"""
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle('Fusion')

    # Create and show main window
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
