"""
Helper Utilities
Common utility functions for the GST Tool.
"""

import os
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class FileInfo:
    """Information about a selected file"""
    filepath: str
    filename: str
    sheets: List[str]
    selected_sheets: List[str]
    
    @property
    def display_name(self) -> str:
        return self.filename


@dataclass 
class ColumnInfo:
    """Information about a column"""
    name: str
    col_type: str  # 'Tax', 'Excluded', 'Taxable', 'Standard'
    tax_mapping: Optional[str] = None  # e.g., 'CGST_9%' if it's a tax column
    
    @property
    def type_display(self) -> str:
        if self.col_type == 'Tax' and self.tax_mapping:
            return f"Tax ({self.tax_mapping})"
        return self.col_type


def get_source_name(filepath: str, sheet_name: str) -> str:
    """Generate source name in format 'filename.xlsx | SheetName'"""
    filename = os.path.basename(filepath)
    return f"{filename} | {sheet_name}"


def parse_source_name(source_name: str) -> Tuple[str, str]:
    """Parse source name back to filename and sheet name"""
    parts = source_name.split(' | ')
    if len(parts) >= 2:
        return parts[0], parts[1]
    return source_name, ''


def format_currency(value: float, symbol: str = "₹") -> str:
    """Format number as Indian currency"""
    if value < 0:
        return f"-{symbol}{abs(value):,.2f}"
    return f"{symbol}{value:,.2f}"


def format_indian_number(value: float) -> str:
    """Format number in Indian numbering system (lakhs, crores)"""
    if value < 0:
        return f"-{format_indian_number(abs(value))}"
    
    if value >= 10000000:  # 1 crore
        return f"{value/10000000:,.2f} Cr"
    elif value >= 100000:  # 1 lakh
        return f"{value/100000:,.2f} L"
    elif value >= 1000:
        return f"{value/1000:,.2f} K"
    else:
        return f"{value:,.2f}"


def classify_column(
    col_name: str, 
    tax_column_names: List[str], 
    exclusion_list: List[str],
    standard_columns: List[str] = None
) -> str:
    """
    Classify a column into its type.
    
    Args:
        col_name: Column name to classify
        tax_column_names: List of configured tax column names
        exclusion_list: List of excluded column names
        standard_columns: List of standard columns (Date, Particulars, etc.)
    
    Returns:
        Column type: 'Tax', 'Excluded', 'Standard', or 'Taxable'
    """
    if standard_columns is None:
        standard_columns = ['Date', 'Particulars', 'Voucher No.', 'Voucher Type', 'Type', 
                          'Vch No.', 'Ref No.', 'GSTIN', 'Party Name']
    
    if col_name in tax_column_names:
        return 'Tax'
    elif col_name in exclusion_list:
        return 'Excluded'
    elif col_name in standard_columns:
        return 'Standard'
    else:
        return 'Taxable'


def get_column_type_color(col_type: str) -> Tuple[str, str]:
    """
    Get background and foreground colors for column type.
    Returns (background_color, foreground_color) as hex strings.
    """
    colors = {
        'Tax': ('#C6EFCE', '#006100'),  # Light green, dark green
        'Excluded': ('#FFEB9C', '#9C5700'),  # Light orange, dark orange
        'Standard': ('#DDEBF7', '#1F4E79'),  # Light blue, dark blue
        'Taxable': ('#FFFFFF', '#000000'),  # White, black
    }
    return colors.get(col_type, ('#FFFFFF', '#000000'))


def validate_file(filepath: str) -> Tuple[bool, str]:
    """
    Validate if file exists and is a supported format.
    Returns (is_valid, error_message)
    """
    if not os.path.exists(filepath):
        return False, f"File not found: {filepath}"
    
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in ['.xlsx', '.xls']:
        return False, f"Unsupported file format: {ext}. Only .xlsx and .xls are supported."
    
    return True, ""


def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text with ellipsis if too long"""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def calculate_stats(gst_data, non_gst_data) -> Dict:
    """Calculate summary statistics from processed data"""
    stats = {
        'gst_count': len(gst_data) if gst_data is not None else 0,
        'non_gst_count': len(non_gst_data) if non_gst_data is not None else 0,
        'total_taxable_gst': 0,
        'total_tax_gst': 0,
        'total_taxable_non_gst': 0,
    }
    
    if gst_data is not None and len(gst_data) > 0:
        if 'Taxable Value' in gst_data.columns:
            stats['total_taxable_gst'] = gst_data['Taxable Value'].sum()
        
        tax_cols = ['Total CGST', 'Total SGST', 'Total IGST']
        for col in tax_cols:
            if col in gst_data.columns:
                stats['total_tax_gst'] += gst_data[col].sum()
    
    if non_gst_data is not None and len(non_gst_data) > 0:
        if 'Taxable Value' in non_gst_data.columns:
            stats['total_taxable_non_gst'] = non_gst_data['Taxable Value'].sum()
    
    return stats


class ProgressTracker:
    """Simple progress tracking utility"""
    
    def __init__(self, total: int, callback=None):
        """
        Initialize progress tracker.
        
        Args:
            total: Total number of items to process
            callback: Optional callback function(current, total, message)
        """
        self.total = total
        self.current = 0
        self.callback = callback
    
    def update(self, increment: int = 1, message: str = ""):
        """Update progress"""
        self.current += increment
        if self.callback:
            self.callback(self.current, self.total, message)
    
    def set_progress(self, current: int, message: str = ""):
        """Set absolute progress"""
        self.current = current
        if self.callback:
            self.callback(self.current, self.total, message)
    
    @property
    def percentage(self) -> float:
        """Get progress as percentage"""
        if self.total == 0:
            return 0
        return (self.current / self.total) * 100
