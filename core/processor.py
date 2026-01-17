"""
Core GST Data Processor
Transforms Tally ERP GST exports into structured formats for compliance analysis.
Port of Power Query M Code solution to Python.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import re


@dataclass
class ProcessingResult:
    """Container for processing results"""
    gst_data: pd.DataFrame
    non_gst_data: pd.DataFrame
    metadata: Dict[str, Any]
    warnings: List[str]


class TaxColumnMapper:
    """Handles tax column mapping and transformation"""
    
    def __init__(self, tax_config: pd.DataFrame):
        self.tax_config = tax_config
        self._build_mapping()
    
    def _build_mapping(self):
        """Build mapping from actual column names to standardized names"""
        self.column_mapping = {}  # actual_col -> mapped_name
        self.mapped_to_actual = {}  # mapped_name -> [actual_cols]
        
        for _, row in self.tax_config.iterrows():
            tax_type = row['TaxType']
            tax_rate = str(row['TaxRate'])
            column_names = str(row['ColumnNames'])
            delimiter = str(row.get('Delimiter', ','))
            
            # Split column names
            actual_columns = [c.strip() for c in column_names.split(delimiter) if c.strip()]
            
            # Generate mapped name
            if tax_rate.upper() == 'GENERIC':
                mapped_name = f"{tax_type}_Generic"
            else:
                # Handle percentage formats
                clean_rate = tax_rate.replace('%', '')
                try:
                    num_rate = float(clean_rate)
                    # Convert decimal percentages (0.05 -> 5)
                    if 0 < num_rate < 1:
                        num_rate = num_rate * 100
                    # Round to 2 decimal places
                    num_rate = round(num_rate, 2)
                    # Format (remove decimals if whole number)
                    if num_rate == int(num_rate):
                        formatted_rate = str(int(num_rate))
                    else:
                        formatted_rate = str(num_rate)
                    mapped_name = f"{tax_type}_{formatted_rate}%"
                except ValueError:
                    mapped_name = f"{tax_type}_{tax_rate}"
            
            # Store mappings
            for col in actual_columns:
                self.column_mapping[col] = mapped_name
            
            if mapped_name not in self.mapped_to_actual:
                self.mapped_to_actual[mapped_name] = []
            self.mapped_to_actual[mapped_name].extend(actual_columns)
    
    def get_all_tax_columns(self) -> List[str]:
        """Get all possible tax column names from config"""
        return list(self.column_mapping.keys())
    
    def get_mapped_name(self, actual_col: str) -> Optional[str]:
        """Get standardized name for an actual column"""
        return self.column_mapping.get(actual_col)
    
    def get_existing_mappings(self, data_columns: List[str]) -> Dict[str, str]:
        """Get mappings only for columns that exist in data"""
        return {col: mapped for col, mapped in self.column_mapping.items() 
                if col in data_columns}


class GSTProcessor:
    """Main processor for GST data transformation"""

    # Standard columns that should never be included in taxable value calculations
    DEFAULT_STANDARD_COLUMNS = [
        'Date', 'Particulars', 'Voucher No.', 'Voucher Type', 'Type',
        'Vch No.', 'Ref No.', 'GSTIN', 'Party Name', 'GSTIN/UIN'
    ]

    def __init__(self, tax_config: pd.DataFrame, exclusion_list: List[str],
                 tax_marked_columns: List[str] = None, standard_columns: List[str] = None):
        """
        Initialize GST Processor.

        Args:
            tax_config: Tax configuration DataFrame
            exclusion_list: List of columns to exclude
            tax_marked_columns: List of columns marked as Tax in Column List
                               (used for exclusion even if not assigned in TaxConfig)
            standard_columns: List of standard columns to exclude from taxable value
                             (e.g., Date, Particulars, Voucher No.)
        """
        self.tax_config = tax_config
        self.exclusion_list = exclusion_list
        self.tax_marked_columns = tax_marked_columns or []
        self.standard_columns = standard_columns if standard_columns is not None else self.DEFAULT_STANDARD_COLUMNS
        self.tax_mapper = TaxColumnMapper(tax_config)
        self.warnings = []  # Initialize warnings list

    @staticmethod
    def normalize_column_name(name: str) -> str:
        """Normalize column name for comparison (collapse whitespace, lowercase)"""
        return ' '.join(str(name).lower().split())
    
    def find_header_row(self, df: pd.DataFrame) -> int:
        """
        Find the header row containing 'Date' and 'Particulars'.
        Checks first 5 columns (not just 3) and uses case-insensitive matching.
        Returns row index or raises error if not found.
        """
        for idx in range(min(20, len(df))):  # Check first 20 rows max
            row = df.iloc[idx]
            # Check first 5 columns instead of 3, use case-insensitive matching
            first_five = [str(val).strip().lower() if pd.notna(val) else '' for val in row.iloc[:5]]

            if 'date' in first_five and 'particulars' in first_five:
                return idx

        raise ValueError("Header row with 'Date' and 'Particulars' not found in first 5 columns")
    
    def clean_data(self, df: pd.DataFrame, header_row_idx: int) -> pd.DataFrame:
        """Clean data: set headers and remove grand total rows"""
        # Set headers from the header row
        new_headers = df.iloc[header_row_idx].tolist()
        # Normalize column names: strip whitespace and collapse multiple spaces
        new_headers = [
            ' '.join(str(h).split()) if pd.notna(h) else f'Column_{i}'
            for i, h in enumerate(new_headers)
        ]
        
        # Get data rows (after header)
        data = df.iloc[header_row_idx + 1:].copy()
        data.columns = new_headers
        data.reset_index(drop=True, inplace=True)
        
        # Remove Grand Total rows - check Particulars column (or first 3 columns)
        # Grand Total can appear in Particulars column, not necessarily first column
        columns_to_check = []
        if 'Particulars' in data.columns:
            columns_to_check.append('Particulars')
        # Also check first 3 columns as fallback
        for col in data.columns[:3]:
            if col not in columns_to_check:
                columns_to_check.append(col)
        
        # Create mask - row is kept if NONE of the checked columns contain "GRAND TOTAL"
        def is_not_grand_total(row):
            for col in columns_to_check:
                val = row.get(col, '')
                if pd.notna(val) and 'GRAND TOTAL' in str(val).upper():
                    return False
            return True
        
        mask = data.apply(is_not_grand_total, axis=1)
        data = data[mask].copy()
        data.reset_index(drop=True, inplace=True)
        
        return data
    
    def convert_currency_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert currency columns to numeric"""
        tax_columns = self.tax_mapper.get_all_tax_columns()
        all_columns = df.columns.tolist()
        
        # Columns to convert: tax columns + non-excluded columns
        columns_to_convert = []
        for col in all_columns:
            if col in tax_columns:
                columns_to_convert.append(col)
            elif col not in self.exclusion_list:
                # Check if column appears to be numeric
                sample = df[col].dropna().head(10)
                if len(sample) > 0:
                    try:
                        pd.to_numeric(sample, errors='raise')
                        columns_to_convert.append(col)
                    except (ValueError, TypeError):
                        pass
        
        for col in columns_to_convert:
            if col in df.columns:
                original_values = df[col].copy()
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                # Track columns with significant conversion issues (more than 20% converted to 0)
                non_null_count = original_values.notna().sum()
                if non_null_count > 0:
                    converted_to_zero = (original_values.notna() & (df[col] == 0) & (original_values != 0)).sum()
                    if converted_to_zero / non_null_count > 0.2:
                        self.warnings.append(f"Column '{col}': {converted_to_zero} values converted to 0 during numeric conversion")
        
        return df
    
    def has_gst(self, row: pd.Series, existing_tax_cols: List[str]) -> bool:
        """Check if row has any GST values in tax columns"""
        # Check both TaxConfig-assigned columns AND tax-marked columns
        # But exclude columns that are in the exclusion list
        all_tax_cols = set(existing_tax_cols) | set(self.tax_marked_columns)
        # Remove excluded columns from the check
        all_tax_cols = all_tax_cols - set(self.exclusion_list)

        # Normalize tax column names for matching
        all_tax_cols_normalized = {self.normalize_column_name(c): c for c in all_tax_cols}

        for col in row.index:
            col_normalized = self.normalize_column_name(col)
            if col_normalized in all_tax_cols_normalized:
                val = row.get(col, 0)
                if pd.notna(val) and val != 0:
                    return True
        return False
    
    def calculate_taxable_value(self, row: pd.Series, all_columns: List[str],
                                 tax_columns: List[str]) -> float:
        """Calculate taxable value (sum of non-excluded, non-tax, non-standard numeric columns)"""
        # Exclude: exclusion_list + TaxConfig columns + Tax-marked columns + Standard columns
        columns_to_exclude = (set(self.exclusion_list) | set(tax_columns) |
                              set(self.tax_marked_columns) | set(self.standard_columns))

        # Normalize exclusion set for comparison (handles whitespace/case differences)
        columns_to_exclude_normalized = {self.normalize_column_name(c) for c in columns_to_exclude}

        total = 0.0
        for col in all_columns:
            # Use normalized comparison
            if self.normalize_column_name(col) not in columns_to_exclude_normalized:
                val = row.get(col, 0)
                if isinstance(val, (int, float)) and pd.notna(val):
                    total += val

        return total
    
    def get_active_columns(self, row: pd.Series, all_columns: List[str],
                           tax_columns: List[str]) -> str:
        """Get active columns with their values, sorted by amount descending"""
        # Exclude: exclusion_list + TaxConfig columns + Tax-marked columns + Standard columns
        columns_to_exclude = (set(self.exclusion_list) | set(tax_columns) |
                              set(self.tax_marked_columns) | set(self.standard_columns))

        # Normalize exclusion set for comparison (handles whitespace/case differences)
        columns_to_exclude_normalized = {self.normalize_column_name(c) for c in columns_to_exclude}

        active = []
        for col in all_columns:
            # Use normalized comparison
            if self.normalize_column_name(col) not in columns_to_exclude_normalized:
                val = row.get(col, 0)
                if isinstance(val, (int, float)) and pd.notna(val) and val != 0:
                    active.append((col, val))

        # Sort by value descending
        active.sort(key=lambda x: abs(x[1]), reverse=True)

        # Format as "Column: Amount | Column: Amount"
        formatted = [f"{col}: {val:,.2f}" for col, val in active]
        return " | ".join(formatted)
    
    def transform_tax_columns(self, df: pd.DataFrame, existing_mappings: Dict[str, str], 
                                keep_originals: bool = True) -> pd.DataFrame:
        """
        Transform actual tax columns to standardized names.
        
        Args:
            df: DataFrame to transform
            existing_mappings: Dict mapping actual column names to standardized names
            keep_originals: If True, keep original columns for auditing (default True)
        """
        # Group actual columns by mapped name
        mapped_groups = {}
        for actual_col, mapped_name in existing_mappings.items():
            if mapped_name not in mapped_groups:
                mapped_groups[mapped_name] = []
            mapped_groups[mapped_name].append(actual_col)
        
        # Create new columns with summed values
        for mapped_name, actual_cols in mapped_groups.items():
            existing_cols = [c for c in actual_cols if c in df.columns]
            if existing_cols:
                # Use skipna=True explicitly and handle all-NaN rows properly
                df[mapped_name] = df[existing_cols].apply(
                    lambda row: row.sum(skipna=True) if row.notna().any() else 0, axis=1
                )
        
        # Keep original tax columns for auditing (don't remove them)
        # They will remain in their original position for data verification
        if not keep_originals:
            cols_to_remove = [c for c in existing_mappings.keys() if c in df.columns]
            df = df.drop(columns=cols_to_remove, errors='ignore')
        
        return df
    
    def calculate_tax_totals(self, row: pd.Series) -> Dict[str, float]:
        """Calculate totals by tax type (CGST, SGST, IGST)"""
        totals = {'Total CGST': 0.0, 'Total SGST': 0.0, 'Total IGST': 0.0}
        
        for col in row.index:
            val = row[col]
            if isinstance(val, (int, float)) and pd.notna(val):
                if col.startswith('CGST_'):
                    totals['Total CGST'] += val
                elif col.startswith('SGST_'):
                    totals['Total SGST'] += val
                elif col.startswith('IGST_'):
                    totals['Total IGST'] += val
        
        return totals
    
    def get_applicable_rates(self, row: pd.Series) -> str:
        """Get applicable tax rates from the row, combining CGST+SGST"""
        non_zero_fields = []
        
        for col in row.index:
            val = row[col]
            if isinstance(val, (int, float)) and pd.notna(val) and val != 0:
                if col.startswith(('CGST_', 'SGST_', 'IGST_')) or col == 'CESS':
                    non_zero_fields.append(col)
        
        # Extract rates and process
        rate_info = {}  # rate -> {'CGST': bool, 'SGST': bool, 'IGST': bool}
        has_cess = 'CESS' in non_zero_fields
        
        for field in non_zero_fields:
            if field == 'CESS':
                continue
            
            parts = field.split('_')
            if len(parts) >= 2:
                tax_type = parts[0]
                rate = parts[1]
                
                if rate not in rate_info:
                    rate_info[rate] = {'CGST': False, 'SGST': False, 'IGST': False}
                rate_info[rate][tax_type] = True
        
        # Process rates
        processed_rates = []
        for rate, types in rate_info.items():
            if rate == 'Generic':
                processed_rates.append(('Generic', float('inf')))  # Sort last
            elif types['CGST'] and types['SGST']:
                # Combine CGST + SGST
                clean_rate = rate.replace('%', '')
                try:
                    num_rate = float(clean_rate) * 2
                    num_rate = round(num_rate, 2)
                    if num_rate == int(num_rate):
                        formatted = f"{int(num_rate)}%"
                    else:
                        formatted = f"{num_rate}%"
                    processed_rates.append((formatted, num_rate))
                except ValueError:
                    processed_rates.append((rate, 0))
            elif types['IGST']:
                try:
                    rate_val = float(rate.replace('%', '')) if '%' in rate else 0
                except (ValueError, TypeError):
                    rate_val = 0
                processed_rates.append((rate, rate_val))
        
        # Sort by numeric value (Generic last)
        processed_rates.sort(key=lambda x: x[1] if x[1] != float('inf') else 9999)
        
        # Build result
        result_parts = [r[0] for r in processed_rates]
        if has_cess:
            result_parts.append('Cess')
        
        return " | ".join(result_parts)
    
    def calculate_rate_from_values(self, row: pd.Series) -> str:
        """Calculate tax rate from tax and taxable values"""
        taxable_value = row.get('Taxable Value', 0)
        total_cgst = row.get('Total CGST', 0)
        total_sgst = row.get('Total SGST', 0)
        total_igst = row.get('Total IGST', 0)

        # Handle NaN values in tax totals - convert to 0
        if pd.isna(total_cgst):
            total_cgst = 0
        if pd.isna(total_sgst):
            total_sgst = 0
        if pd.isna(total_igst):
            total_igst = 0

        total_tax = total_cgst + total_sgst + total_igst

        if taxable_value == 0 or pd.isna(taxable_value):
            return 'N/A'

        try:
            rate = (total_tax / taxable_value) * 100
            return f"{round(rate, 2)}%"
        except (ZeroDivisionError, TypeError, ValueError):
            return 'N/A'
    
    def get_transaction_type(self, row: pd.Series) -> str:
        """Get transaction type from Voucher Type or Type column"""
        if 'Voucher Type' in row.index and pd.notna(row['Voucher Type']):
            return str(row['Voucher Type'])
        elif 'Type' in row.index and pd.notna(row['Type']):
            return str(row['Type'])
        return 'Transaction'
    
    def get_review_required(self, voucher_type: str) -> str:
        """Get review required message based on voucher type"""
        voucher_upper = voucher_type.upper()
        if 'SALES' in voucher_upper:
            return 'Check Exempt/Export'
        else:  # Purchase, Journal, Debit Note, etc.
            return 'Check RCM/Exempt'
    
    def get_final_column_order(self, all_columns: List[str], is_non_gst: bool) -> List[str]:
        """Get final column order for output"""
        # Define added columns
        added_columns = {'Active Columns', 'Taxable Value', 'Tax Rates (Config)', 
                        'Tax Rates (Calculated)', 'Source'}
        
        # Separate columns by type
        source_data_cols = []
        igst_cols = []
        cgst_cols = []
        sgst_cols = []
        cess_cols = []
        total_cols = []
        end_cols = []
        
        for col in all_columns:
            if col in added_columns:
                continue
            elif col.startswith('IGST_'):
                igst_cols.append(col)
            elif col.startswith('CGST_'):
                cgst_cols.append(col)
            elif col.startswith('SGST_'):
                sgst_cols.append(col)
            elif col == 'CESS':
                cess_cols.append(col)
            elif col.startswith('Total '):
                total_cols.append(col)
            elif col in ('Transaction Type', 'Review Required'):
                end_cols.append(col)
            else:
                source_data_cols.append(col)
        
        # Sort tax columns by rate numerically
        def extract_rate(col_name):
            match = re.search(r'(\d+\.?\d*)%', col_name)
            if match:
                return float(match.group(1))
            # For Generic or non-numeric rates, use a high value to sort last
            if 'generic' in col_name.lower():
                return 9999.0
            return 9998.0  # Other non-standard rates before Generic
        
        igst_cols.sort(key=extract_rate)
        cgst_cols.sort(key=extract_rate)
        sgst_cols.sort(key=extract_rate)
        
        # Build final order
        final_order = ['Source'] + source_data_cols + ['Active Columns', 'Taxable Value', 
                       'Tax Rates (Config)', 'Tax Rates (Calculated)']
        final_order += igst_cols + [''] + cgst_cols + sgst_cols + cess_cols
        final_order += [''] + total_cols
        final_order += ['Transaction Type']
        
        if is_non_gst:
            final_order.append('Review Required')
        
        # Remove empty strings and non-existent columns
        # Note: Keep empty strings for spacing, and keep columns that exist in all_columns
        final_order = [c for c in final_order if c == '' or (c and c in all_columns)]
        
        return final_order
    
    def process_sheet(self, df: pd.DataFrame, source_name: str) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
        """Process a single sheet and return GST and Non-GST dataframes"""
        metadata = {'source': source_name, 'original_rows': len(df)}
        
        # Find and clean headers
        header_row_idx = self.find_header_row(df)
        df = self.clean_data(df, header_row_idx)
        metadata['rows_after_cleaning'] = len(df)
        
        if len(df) == 0:
            self.warnings.append(f"{source_name}: No data rows after cleaning")
            # Return empty DataFrames with expected column structure
            empty_cols = ['Source', 'Active Columns', 'Taxable Value', 'Tax Rates (Config)',
                         'Tax Rates (Calculated)', 'Total CGST', 'Total SGST', 'Total IGST',
                         'Transaction Type']
            empty_df = pd.DataFrame(columns=empty_cols)
            empty_non_gst = empty_df.copy()
            empty_non_gst['Review Required'] = pd.Series(dtype=str)
            return empty_df, empty_non_gst, metadata
        
        # Convert currency columns
        df = self.convert_currency_columns(df)
        
        # Get existing tax columns in data using normalized comparison
        # This handles whitespace/case differences between config and data column names
        all_tax_cols = self.tax_mapper.get_all_tax_columns()

        # Build normalized lookup: {normalized_config_name: config_name}
        config_cols_normalized = {self.normalize_column_name(c): c for c in all_tax_cols}

        # Find existing tax columns using normalized comparison
        # Use DATA column names (not config names) for consistency
        existing_tax_cols = []
        for data_col in df.columns:
            normalized = self.normalize_column_name(data_col)
            if normalized in config_cols_normalized:
                existing_tax_cols.append(data_col)

        # Build mappings with normalized comparison
        # Maps DATA column name -> standardized name (e.g., "Input RCM Cgst @9%" -> "CGST_9%")
        existing_mappings = {}
        for data_col in df.columns:
            normalized = self.normalize_column_name(data_col)
            if normalized in config_cols_normalized:
                config_col = config_cols_normalized[normalized]
                mapped_name = self.tax_mapper.get_mapped_name(config_col)
                if mapped_name:
                    existing_mappings[data_col] = mapped_name
        
        # Add source column
        df['Source'] = source_name
        
        # Split GST and Non-GST
        gst_mask = df.apply(lambda row: self.has_gst(row, existing_tax_cols), axis=1)
        gst_df = df[gst_mask].copy()
        non_gst_df = df[~gst_mask].copy()
        
        metadata['gst_rows'] = len(gst_df)
        metadata['non_gst_rows'] = len(non_gst_df)
        
        # Process GST data
        if len(gst_df) > 0:
            gst_df = self._process_gst_dataframe(gst_df, existing_tax_cols, existing_mappings)
        
        # Process Non-GST data
        if len(non_gst_df) > 0:
            non_gst_df = self._process_non_gst_dataframe(non_gst_df, existing_tax_cols, existing_mappings)
        
        return gst_df, non_gst_df, metadata
    
    def _process_gst_dataframe(self, df: pd.DataFrame, existing_tax_cols: List[str],
                                existing_mappings: Dict[str, str]) -> pd.DataFrame:
        """Process GST transactions dataframe"""
        all_columns = df.columns.tolist()
        
        # Add Active Columns
        df['Active Columns'] = df.apply(
            lambda row: self.get_active_columns(row, all_columns, existing_tax_cols), axis=1)
        
        # Add Taxable Value
        df['Taxable Value'] = df.apply(
            lambda row: self.calculate_taxable_value(row, all_columns, existing_tax_cols), axis=1)
        
        # Transform tax columns
        df = self.transform_tax_columns(df, existing_mappings)
        
        # Add Tax Rates (Config)
        df['Tax Rates (Config)'] = df.apply(lambda row: self.get_applicable_rates(row), axis=1)
        
        # Add tax totals - CRITICAL: preserve index to avoid misalignment
        totals = df.apply(lambda row: self.calculate_tax_totals(row), axis=1, result_type='expand')
        # Explicitly align by index to prevent misalignment issues
        totals.index = df.index
        for col in totals.columns:
            df.loc[:, col] = totals[col].values
        
        # Add Tax Rates (Calculated)
        df['Tax Rates (Calculated)'] = df.apply(lambda row: self.calculate_rate_from_values(row), axis=1)
        
        # Add Transaction Type
        df['Transaction Type'] = df.apply(lambda row: self.get_transaction_type(row), axis=1)
        
        return df
    
    def _process_non_gst_dataframe(self, df: pd.DataFrame, existing_tax_cols: List[str],
                                    existing_mappings: Dict[str, str]) -> pd.DataFrame:
        """Process Non-GST transactions dataframe"""
        all_columns = df.columns.tolist()
        
        # Add Active Columns
        df['Active Columns'] = df.apply(
            lambda row: self.get_active_columns(row, all_columns, existing_tax_cols), axis=1)
        
        # Add Taxable Value
        df['Taxable Value'] = df.apply(
            lambda row: self.calculate_taxable_value(row, all_columns, existing_tax_cols), axis=1)
        
        # Transform tax columns (will create empty columns)
        df = self.transform_tax_columns(df, existing_mappings)
        
        # Add empty Tax Rates columns
        df['Tax Rates (Config)'] = ''
        df['Tax Rates (Calculated)'] = 'N/A'
        
        # Add tax totals (will be zeros)
        df['Total CGST'] = 0.0
        df['Total SGST'] = 0.0
        df['Total IGST'] = 0.0
        
        # Add Transaction Type
        df['Transaction Type'] = df.apply(lambda row: self.get_transaction_type(row), axis=1)
        
        # Add Review Required
        df['Review Required'] = df['Transaction Type'].apply(self.get_review_required)
        
        return df
    
    def process_multiple_sources(self, sources: List[Tuple[pd.DataFrame, str]]) -> ProcessingResult:
        """
        Process multiple sources (file+sheet combinations)
        sources: List of (dataframe, source_name) tuples
        source_name format: "filename.xlsx | SheetName"
        """
        # Suppress FutureWarning for fillna downcasting
        pd.set_option('future.no_silent_downcasting', True)
        
        all_gst = []
        all_non_gst = []
        all_metadata = []
        self.warnings = []
        
        for df, source_name in sources:
            try:
                gst_df, non_gst_df, metadata = self.process_sheet(df, source_name)
                
                if len(gst_df) > 0:
                    all_gst.append(gst_df)
                if len(non_gst_df) > 0:
                    all_non_gst.append(non_gst_df)
                
                all_metadata.append(metadata)
                
            except Exception as e:
                self.warnings.append(f"{source_name}: Error processing - {str(e)}")
                # Include all expected metadata fields for consistency
                all_metadata.append({
                    'source': source_name,
                    'error': str(e),
                    'original_rows': 0,
                    'rows_after_cleaning': 0,
                    'gst_rows': 0,
                    'non_gst_rows': 0
                })
        
        # Merge all GST data
        if all_gst:
            merged_gst = pd.concat(all_gst, ignore_index=True, sort=False)
            # Fill NA values - convert column by column to avoid FutureWarning
            for col in merged_gst.columns:
                if pd.api.types.is_numeric_dtype(merged_gst[col]):
                    merged_gst.loc[:, col] = merged_gst[col].fillna(0)
                else:
                    merged_gst.loc[:, col] = merged_gst[col].fillna('')
        else:
            merged_gst = pd.DataFrame()
        
        # Merge all Non-GST data
        if all_non_gst:
            merged_non_gst = pd.concat(all_non_gst, ignore_index=True, sort=False)
            # Fill NA values - convert column by column to avoid FutureWarning
            for col in merged_non_gst.columns:
                if pd.api.types.is_numeric_dtype(merged_non_gst[col]):
                    merged_non_gst.loc[:, col] = merged_non_gst[col].fillna(0)
                else:
                    merged_non_gst.loc[:, col] = merged_non_gst[col].fillna('')
        else:
            merged_non_gst = pd.DataFrame()
        
        # Reorder columns
        if len(merged_gst) > 0:
            final_order = self.get_final_column_order(merged_gst.columns.tolist(), False)
            existing_cols = [c for c in final_order if c in merged_gst.columns]
            merged_gst = merged_gst[existing_cols]
        
        if len(merged_non_gst) > 0:
            final_order = self.get_final_column_order(merged_non_gst.columns.tolist(), True)
            existing_cols = [c for c in final_order if c in merged_non_gst.columns]
            merged_non_gst = merged_non_gst[existing_cols]
        
        # Build combined metadata
        combined_metadata = {
            'sources': all_metadata,
            'total_gst_rows': len(merged_gst),
            'total_non_gst_rows': len(merged_non_gst),
            'total_sources': len(sources)
        }
        
        return ProcessingResult(
            gst_data=merged_gst,
            non_gst_data=merged_non_gst,
            metadata=combined_metadata,
            warnings=self.warnings
        )
