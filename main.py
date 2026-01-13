"""
GST Compliance Data Transformation Tool
Main Application Entry Point

A PyQt5 Windows application for transforming Tally ERP GST data exports
into structured formats suitable for GST compliance and ITC analysis.

Author: Sidhant
Version: 1.0
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QMessageBox, QProgressDialog, QFileDialog, QStatusBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIcon

import pandas as pd
from typing import List, Tuple, Dict, Any

from core.processor import GSTProcessor, ProcessingResult
from core.config_manager import ConfigManager
from ui.setup_tab import SetupTab
from ui.gst_tab import GSTTab
from ui.non_gst_tab import NonGSTTab
from utils.excel_handler import ExcelReader, ExcelWriter
from utils.helpers import get_source_name


class ProcessingThread(QThread):
    """Background thread for processing data"""
    
    progress_updated = pyqtSignal(int, str)  # progress percentage, message
    processing_complete = pyqtSignal(object)  # ProcessingResult
    processing_error = pyqtSignal(str)  # error message
    
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
        
        self._init_ui()
        self._setup_connections()
    
    def _init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("GST Compliance Tool - Tally F8 Transformer")
        self.setMinimumSize(1200, 800)
        
        # Central widget with tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Setup tab
        self.setup_tab = SetupTab(self.config_manager)
        self.tabs.addTab(self.setup_tab, "Setup")
        
        # GST Transactions tab
        self.gst_tab = GSTTab()
        self.tabs.addTab(self.gst_tab, "GST Transactions")
        
        # Non-GST Transactions tab
        self.non_gst_tab = NonGSTTab()
        self.tabs.addTab(self.non_gst_tab, "Non-GST Transactions")
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
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
        load_config.triggered.connect(self._load_config)
        
        config_menu.addSeparator()
        
        reset_config = config_menu.addAction("Reset to Defaults")
        reset_config.triggered.connect(self._reset_config)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = help_menu.addAction("About")
        about_action.triggered.connect(self._show_about)
    
    def _setup_connections(self):
        """Set up signal connections"""
        self.setup_tab.process_requested.connect(self._process_data)
        self.setup_tab.export_requested.connect(self._export_complete)
    
    def _process_data(self):
        """Process selected files and sheets"""
        sources = self.setup_tab.get_selected_sources()
        
        if not sources:
            QMessageBox.warning(self, "Warning", "No files selected.")
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
            
            # Create processor
            tax_config_df = self.config_manager.get_tax_config_df()
            exclusion_list = self.config_manager.get_exclusion_list()
            
            processor = GSTProcessor(tax_config_df, exclusion_list)
            
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
                f"Processing complete: {gst_count} GST transactions, {non_gst_count} Non-GST transactions"
            )
            
            # Switch to GST tab
            self.tabs.setCurrentIndex(1)
            
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
            
            # Get column types
            column_types = self.setup_tab.get_column_types()
            
            # Write output
            ExcelWriter.write_output(
                filepath=filepath,
                gst_data=gst_data,
                non_gst_data=non_gst_data,
                metadata=metadata,
                tax_config=tax_config,
                exclusion_list=exclusion_list,
                column_types=column_types
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
        from PyQt5.QtWidgets import QInputDialog
        
        # Update config manager with current UI values
        self.config_manager.set_tax_config(self.setup_tab.tax_config.get_config())
        self.config_manager.set_exclusion_list(self.setup_tab.exclusion_list.get_list())
        
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
    
    def _load_config(self):
        """Load a saved configuration"""
        from PyQt5.QtWidgets import QInputDialog
        
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
                self.setup_tab._load_config()
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
            self.setup_tab._load_config()
            QMessageBox.information(self, "Success", "Configuration reset to defaults.")
    
    def _show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self, "About GST Compliance Tool",
            "<h2>GST Compliance Tool</h2>"
            "<p>Version 1.0</p>"
            "<p>A tool for transforming Tally ERP GST data exports "
            "into structured formats suitable for GST compliance and ITC analysis.</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Multiple file and sheet support</li>"
            "<li>Configuration-driven tax mapping</li>"
            "<li>Automatic GST/Non-GST separation</li>"
            "<li>Dual tax rate calculation</li>"
            "<li>Comprehensive Excel export</li>"
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
