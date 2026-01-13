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
    
    def __init__(self, tax_config: pd.DataFrame, exclusion_list: List[str]):
        self.tax_config = tax_config
        self.exclusion_list = exclusion_list
        self.tax_mapper = TaxColumnMapper(tax_config)
        self.warnings = []
    
    def find_header_row(self, df: pd.DataFrame) -> int:
        """
        Find the header row containing 'Date' and 'Particulars' in first 3 columns.
        Returns row index or raises error if not found.
        """
        for idx in range(min(20, len(df))):  # Check first 20 rows max
            row = df.iloc[idx]
            first_three = [str(val).strip() if pd.notna(val) else '' for val in row.iloc[:3]]
            
            if 'Date' in first_three and 'Particulars' in first_three:
                return idx
        
        raise ValueError("Header row with 'Date' and 'Particulars' not found in first 3 columns")
    
    def clean_data(self, df: pd.DataFrame, header_row_idx: int) -> pd.DataFrame:
        """Clean data: set headers and remove grand total rows"""
        # Set headers from the header row
        new_headers = df.iloc[header_row_idx].tolist()
        new_headers = [str(h).strip() if pd.notna(h) else f'Column_{i}' 
                       for i, h in enumerate(new_headers)]
        
        # Get data rows (after header)
        data = df.iloc[header_row_idx + 1:].copy()
        data.columns = new_headers
        data.reset_index(drop=True, inplace=True)
        
        # Remove Grand Total rows
        first_col = data.columns[0]
        mask = data[first_col].apply(lambda x: 
            'GRAND TOTAL' not in str(x).upper() if pd.notna(x) else True)
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
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        return df
    
    def has_gst(self, row: pd.Series, existing_tax_cols: List[str]) -> bool:
        """Check if row has any GST values"""
        for col in existing_tax_cols:
            val = row.get(col, 0)
            if pd.notna(val) and val != 0:
                return True
        return False
    
    def calculate_taxable_value(self, row: pd.Series, all_columns: List[str], 
                                 tax_columns: List[str]) -> float:
        """Calculate taxable value (sum of non-excluded, non-tax numeric columns)"""
        columns_to_exclude = set(self.exclusion_list) | set(tax_columns)
        
        total = 0.0
        for col in all_columns:
            if col not in columns_to_exclude:
                val = row.get(col, 0)
                if isinstance(val, (int, float)) and pd.notna(val):
                    total += val
        
        return total
    
    def get_active_columns(self, row: pd.Series, all_columns: List[str], 
                           tax_columns: List[str]) -> str:
        """Get active columns with their values, sorted by amount descending"""
        columns_to_exclude = set(self.exclusion_list) | set(tax_columns)
        
        active = []
        for col in all_columns:
            if col not in columns_to_exclude:
                val = row.get(col, 0)
                if isinstance(val, (int, float)) and pd.notna(val) and val != 0:
                    active.append((col, val))
        
        # Sort by value descending
        active.sort(key=lambda x: abs(x[1]), reverse=True)
        
        # Format as "Column: Amount | Column: Amount"
        formatted = [f"{col}: {val:,.2f}" for col, val in active]
        return " | ".join(formatted)
    
    def transform_tax_columns(self, df: pd.DataFrame, existing_mappings: Dict[str, str]) -> pd.DataFrame:
        """Transform actual tax columns to standardized names"""
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
                df[mapped_name] = df[existing_cols].sum(axis=1)
        
        # Remove original tax columns
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
                processed_rates.append((rate, float(rate.replace('%', '')) if '%' in rate else 0))
        
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
        
        total_tax = total_cgst + total_sgst + total_igst
        
        if taxable_value == 0 or pd.isna(taxable_value):
            return 'N/A'
        
        rate = (total_tax / taxable_value) * 100
        return f"{round(rate, 2)}%"
    
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
            return float('inf')
        
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
        final_order = [c for c in final_order if c and c in all_columns or c == '']
        
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
            return pd.DataFrame(), pd.DataFrame(), metadata
        
        # Convert currency columns
        df = self.convert_currency_columns(df)
        
        # Get existing tax columns in data
        all_tax_cols = self.tax_mapper.get_all_tax_columns()
        existing_tax_cols = [c for c in all_tax_cols if c in df.columns]
        existing_mappings = self.tax_mapper.get_existing_mappings(df.columns.tolist())
        
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
        
        # Add tax totals
        totals = df.apply(lambda row: self.calculate_tax_totals(row), axis=1)
        totals_df = pd.DataFrame(totals.tolist())
        for col in totals_df.columns:
            df[col] = totals_df[col]
        
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
                all_metadata.append({'source': source_name, 'error': str(e)})
        
        # Merge all GST data
        if all_gst:
            merged_gst = pd.concat(all_gst, ignore_index=True, sort=False)
            # Fill NA values - handle different column types appropriately
            for col in merged_gst.columns:
                if merged_gst[col].dtype in ['float64', 'int64']:
                    merged_gst[col] = merged_gst[col].fillna(0)
                else:
                    merged_gst[col] = merged_gst[col].fillna('')
        else:
            merged_gst = pd.DataFrame()
        
        # Merge all Non-GST data
        if all_non_gst:
            merged_non_gst = pd.concat(all_non_gst, ignore_index=True, sort=False)
            # Fill NA values - handle different column types appropriately
            for col in merged_non_gst.columns:
                if merged_non_gst[col].dtype in ['float64', 'int64']:
                    merged_non_gst[col] = merged_non_gst[col].fillna(0)
                else:
                    merged_non_gst[col] = merged_non_gst[col].fillna('')
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
