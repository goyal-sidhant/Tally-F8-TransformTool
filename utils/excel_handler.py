"""
Excel Handler
Utilities for reading and writing Excel files.
"""

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.utils import get_column_letter
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import os


class ExcelReader:
    """Handles reading Excel files and extracting sheet data"""
    
    SUPPORTED_EXTENSIONS = ['.xlsx', '.xls']
    
    @staticmethod
    def is_supported(filepath: str) -> bool:
        """Check if file extension is supported"""
        ext = os.path.splitext(filepath)[1].lower()
        return ext in ExcelReader.SUPPORTED_EXTENSIONS
    
    @staticmethod
    def get_sheet_names(filepath: str) -> List[str]:
        """Get list of sheet names from Excel file"""
        try:
            xl = pd.ExcelFile(filepath)
            return xl.sheet_names
        except Exception as e:
            raise ValueError(f"Error reading file: {str(e)}")
    
    @staticmethod
    def read_sheet(filepath: str, sheet_name: str) -> pd.DataFrame:
        """Read a specific sheet from Excel file"""
        try:
            # Read without headers (we'll detect them later)
            df = pd.read_excel(filepath, sheet_name=sheet_name, header=None)
            return df
        except Exception as e:
            raise ValueError(f"Error reading sheet '{sheet_name}': {str(e)}")
    
    @staticmethod
    def read_multiple_sheets(filepath: str, sheet_names: List[str]) -> Dict[str, pd.DataFrame]:
        """Read multiple sheets from Excel file"""
        result = {}
        for sheet_name in sheet_names:
            try:
                df = ExcelReader.read_sheet(filepath, sheet_name)
                result[sheet_name] = df
            except Exception as e:
                result[sheet_name] = None
        return result
    
    @staticmethod
    def get_all_columns(sources: List[Tuple[str, str, pd.DataFrame]]) -> List[str]:
        """
        Get union of all columns from all sources.
        sources: List of (filepath, sheet_name, dataframe) tuples
        Returns unique column names.
        """
        all_columns = set()
        
        for filepath, sheet_name, df in sources:
            if df is not None and len(df) > 0:
                # Try to find header row and get column names
                try:
                    # Look for header row with Date and Particulars
                    for idx in range(min(20, len(df))):
                        row = df.iloc[idx]
                        first_three = [str(val).strip() if pd.notna(val) else '' for val in row.iloc[:3]]
                        if 'Date' in first_three and 'Particulars' in first_three:
                            headers = df.iloc[idx].tolist()
                            headers = [str(h).strip() if pd.notna(h) else f'Column_{i}' 
                                       for i, h in enumerate(headers)]
                            all_columns.update(headers)
                            break
                except Exception:
                    pass
        
        return sorted(list(all_columns))


class ExcelWriter:
    """Handles writing processed data to Excel files"""
    
    # Styling constants
    HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
    TAX_COL_FILL = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    EXCLUDE_COL_FILL = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    BORDER = Border(
        left=Side(style='thin', color='B4B4B4'),
        right=Side(style='thin', color='B4B4B4'),
        top=Side(style='thin', color='B4B4B4'),
        bottom=Side(style='thin', color='B4B4B4')
    )
    
    @staticmethod
    def write_output(
        filepath: str,
        gst_data: pd.DataFrame,
        non_gst_data: pd.DataFrame,
        metadata: Dict[str, Any],
        tax_config: List[Dict],
        exclusion_list: List[str],
        column_types: Dict[str, str]
    ):
        """
        Write complete output to Excel file with 4 sheets.
        
        Args:
            filepath: Output file path
            gst_data: GST transactions DataFrame
            non_gst_data: Non-GST transactions DataFrame
            metadata: Processing metadata
            tax_config: Tax configuration list
            exclusion_list: Exclusion column list
            column_types: Dict mapping column names to their types
        """
        wb = Workbook()
        
        # Sheet 1: Metadata
        ws_meta = wb.active
        ws_meta.title = "Metadata"
        ExcelWriter._write_metadata_sheet(ws_meta, metadata, column_types)
        
        # Sheet 2: Configuration
        ws_config = wb.create_sheet("Configuration")
        ExcelWriter._write_config_sheet(ws_config, tax_config, exclusion_list)
        
        # Sheet 3: GST Transactions
        ws_gst = wb.create_sheet("GST Transactions")
        ExcelWriter._write_data_sheet(ws_gst, gst_data, "GST")
        
        # Sheet 4: Non-GST Transactions
        ws_non_gst = wb.create_sheet("Non-GST Transactions")
        ExcelWriter._write_data_sheet(ws_non_gst, non_gst_data, "Non-GST")
        
        # Save
        wb.save(filepath)
    
    @staticmethod
    def _write_metadata_sheet(ws, metadata: Dict[str, Any], column_types: Dict[str, str]):
        """Write metadata sheet"""
        # Title
        ws['A1'] = "GST Compliance Tool - Processing Report"
        ws['A1'].font = Font(bold=True, size=14)
        ws.merge_cells('A1:D1')
        
        # Processing info
        ws['A3'] = "Processing Date:"
        ws['B3'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        ws['A4'] = "Total Sources:"
        ws['B4'] = metadata.get('total_sources', 0)
        
        ws['A5'] = "Total GST Rows:"
        ws['B5'] = metadata.get('total_gst_rows', 0)
        
        ws['A6'] = "Total Non-GST Rows:"
        ws['B6'] = metadata.get('total_non_gst_rows', 0)
        
        # Source files table
        ws['A8'] = "Source Files Summary"
        ws['A8'].font = Font(bold=True, size=12)
        
        headers = ['Source File', 'Sheet', 'Original Rows', 'GST Rows', 'Non-GST Rows', 'Status']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=9, column=col, value=header)
            cell.fill = ExcelWriter.HEADER_FILL
            cell.font = ExcelWriter.HEADER_FONT
            cell.border = ExcelWriter.BORDER
        
        row = 10
        sources = metadata.get('sources', [])
        for source in sources:
            source_name = source.get('source', '')
            parts = source_name.split(' | ')
            file_name = parts[0] if parts else source_name
            sheet_name = parts[1] if len(parts) > 1 else ''
            
            ws.cell(row=row, column=1, value=file_name).border = ExcelWriter.BORDER
            ws.cell(row=row, column=2, value=sheet_name).border = ExcelWriter.BORDER
            ws.cell(row=row, column=3, value=source.get('original_rows', 0)).border = ExcelWriter.BORDER
            ws.cell(row=row, column=4, value=source.get('gst_rows', 0)).border = ExcelWriter.BORDER
            ws.cell(row=row, column=5, value=source.get('non_gst_rows', 0)).border = ExcelWriter.BORDER
            
            error = source.get('error')
            status = 'Error: ' + error if error else 'Success'
            ws.cell(row=row, column=6, value=status).border = ExcelWriter.BORDER
            
            row += 1
        
        # Totals row
        ws.cell(row=row, column=1, value="TOTAL").font = Font(bold=True)
        ws.cell(row=row, column=3, value=sum(s.get('original_rows', 0) for s in sources)).font = Font(bold=True)
        ws.cell(row=row, column=4, value=metadata.get('total_gst_rows', 0)).font = Font(bold=True)
        ws.cell(row=row, column=5, value=metadata.get('total_non_gst_rows', 0)).font = Font(bold=True)
        
        # Column types table
        row += 3
        ws.cell(row=row, column=1, value="Column Configuration").font = Font(bold=True, size=12)
        row += 1
        
        col_headers = ['Column Name', 'Type']
        for col, header in enumerate(col_headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.fill = ExcelWriter.HEADER_FILL
            cell.font = ExcelWriter.HEADER_FONT
            cell.border = ExcelWriter.BORDER
        
        row += 1
        for col_name, col_type in sorted(column_types.items()):
            cell1 = ws.cell(row=row, column=1, value=col_name)
            cell2 = ws.cell(row=row, column=2, value=col_type)
            cell1.border = ExcelWriter.BORDER
            cell2.border = ExcelWriter.BORDER
            
            # Color code based on type
            if 'Tax' in col_type:
                cell1.fill = ExcelWriter.TAX_COL_FILL
                cell2.fill = ExcelWriter.TAX_COL_FILL
            elif col_type == 'Excluded':
                cell1.fill = ExcelWriter.EXCLUDE_COL_FILL
                cell2.fill = ExcelWriter.EXCLUDE_COL_FILL
            
            row += 1
        
        # Adjust column widths
        ws.column_dimensions['A'].width = 40
        ws.column_dimensions['B'].width = 25
        ws.column_dimensions['C'].width = 15
        ws.column_dimensions['D'].width = 15
        ws.column_dimensions['E'].width = 15
        ws.column_dimensions['F'].width = 20
    
    @staticmethod
    def _write_config_sheet(ws, tax_config: List[Dict], exclusion_list: List[str]):
        """Write configuration sheet"""
        # Tax Config table
        ws['A1'] = "Tax Configuration"
        ws['A1'].font = Font(bold=True, size=12)
        
        tax_headers = ['TaxType', 'TaxRate', 'ColumnNames', 'Delimiter']
        for col, header in enumerate(tax_headers, 1):
            cell = ws.cell(row=2, column=col, value=header)
            cell.fill = ExcelWriter.HEADER_FILL
            cell.font = ExcelWriter.HEADER_FONT
            cell.border = ExcelWriter.BORDER
        
        for row_idx, config_row in enumerate(tax_config, 3):
            for col_idx, header in enumerate(tax_headers, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=config_row.get(header, ''))
                cell.border = ExcelWriter.BORDER
        
        # Exclusion List table (to the right)
        ws['F1'] = "Exclusion List"
        ws['F1'].font = Font(bold=True, size=12)
        
        cell = ws.cell(row=2, column=6, value="ExcludeColumn")
        cell.fill = ExcelWriter.HEADER_FILL
        cell.font = ExcelWriter.HEADER_FONT
        cell.border = ExcelWriter.BORDER
        
        for row_idx, excl_col in enumerate(exclusion_list, 3):
            cell = ws.cell(row=row_idx, column=6, value=excl_col)
            cell.border = ExcelWriter.BORDER
        
        # Adjust column widths
        ws.column_dimensions['A'].width = 12
        ws.column_dimensions['B'].width = 12
        ws.column_dimensions['C'].width = 50
        ws.column_dimensions['D'].width = 12
        ws.column_dimensions['F'].width = 20
    
    @staticmethod
    def _write_data_sheet(ws, df: pd.DataFrame, sheet_type: str):
        """Write data sheet with proper formatting"""
        if df is None or len(df) == 0:
            ws['A1'] = f"No {sheet_type} transactions found"
            return
        
        # Write headers
        for col_idx, col_name in enumerate(df.columns, 1):
            cell = ws.cell(row=1, column=col_idx, value=col_name)
            cell.fill = ExcelWriter.HEADER_FILL
            cell.font = ExcelWriter.HEADER_FONT
            cell.border = ExcelWriter.BORDER
            cell.alignment = Alignment(horizontal='center', wrap_text=True)
        
        # Write data
        for row_idx, row in enumerate(df.itertuples(index=False), 2):
            for col_idx, value in enumerate(row, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.border = ExcelWriter.BORDER
                
                # Format numbers
                if isinstance(value, (int, float)) and not pd.isna(value):
                    cell.number_format = '#,##0.00'
        
        # Auto-adjust column widths (with max limit)
        for col_idx, col_name in enumerate(df.columns, 1):
            max_length = len(str(col_name))
            for row_idx in range(2, min(102, len(df) + 2)):  # Sample first 100 rows
                cell_value = ws.cell(row=row_idx, column=col_idx).value
                if cell_value:
                    max_length = max(max_length, len(str(cell_value)))
            
            adjusted_width = min(max_length + 2, 50)  # Max width of 50
            ws.column_dimensions[get_column_letter(col_idx)].width = adjusted_width
        
        # Freeze header row
        ws.freeze_panes = 'A2'
        
        # Add auto filter
        ws.auto_filter.ref = ws.dimensions


class ExcelExporter:
    """Simplified exporter for quick exports"""
    
    @staticmethod
    def quick_export(df: pd.DataFrame, filepath: str, sheet_name: str = "Data"):
        """Quick export DataFrame to Excel"""
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    @staticmethod
    def export_multiple_sheets(sheets: Dict[str, pd.DataFrame], filepath: str):
        """Export multiple DataFrames to different sheets"""
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            for sheet_name, df in sheets.items():
                if df is not None and len(df) > 0:
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
