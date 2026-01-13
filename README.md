# GST Compliance Data Transformation Tool

A PyQt5 Windows application for transforming Tally ERP GST data exports into structured formats suitable for GST compliance and ITC analysis in India.

## Features

- **Multiple File Support**: Process multiple Excel files simultaneously
- **Multi-Sheet Selection**: Select specific sheets from each file
- **Configuration-Driven**: Flexible tax column mapping and exclusion lists
- **Automatic Header Detection**: Finds "Date" and "Particulars" in Tally exports
- **Grand Total Removal**: Automatically filters out summary rows
- **GST/Non-GST Separation**: Intelligent transaction classification
- **Dual Tax Rate Calculation**:
  - Config-based rates (from column mapping)
  - Calculated rates (from tax/taxable values)
- **Source Tracking**: Audit trail with file and sheet information
- **Comprehensive Export**: 4-sheet Excel output with metadata

## Installation

### Prerequisites

- Python 3.8 or higher
- Windows OS (tested on Windows 10/11)

### Setup

1. Clone or download this repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the application:

```bash
python main.py
```

## Usage

### Step 1: Add Files

1. Click "Add File(s)..." in the Setup tab
2. Select one or more Excel files (.xlsx or .xls)
3. Check/uncheck sheets you want to process

### Step 2: Configure Columns

1. Click "Scan Columns from Selected Files"
2. Review the column list - columns are auto-categorized:
   - **[T] Tax**: Columns configured in Tax Configuration
   - **[E] Excluded**: Columns in Exclusion List
   - **[S] Standard**: Standard columns (Date, Particulars, etc.)
   - **[ ] Taxable**: Columns contributing to taxable value

### Step 3: Adjust Configuration (if needed)

**Tax Configuration:**
- Add new tax column mappings
- TaxType: CGST, SGST, IGST, or CESS
- TaxRate: Percentage (e.g., "9%", "0.05%") or "Generic"
- ColumnNames: Comma-separated list of column names
- Delimiter: Usually comma (,)

**Exclusion List:**
- Add columns that should NOT contribute to taxable value
- Common: Round Off, TDS Payable, Discount

### Step 4: Process Data

1. Click "Process Data"
2. Review results in GST Transactions and Non-GST Transactions tabs

### Step 5: Export

- **Individual Export**: Use "Export" button in each tab
- **Complete Report**: Use File → Export Complete Report

## Output Structure

### 4-Sheet Excel Export

1. **Metadata**: Processing summary, source files, column configuration
2. **Configuration**: Tax Config and Exclusion List tables
3. **GST Transactions**: All transactions with GST
4. **Non-GST Transactions**: Transactions without GST (needs RCM/Exempt review)

### Output Columns

| Column | Description |
|--------|-------------|
| Source | File and sheet name |
| Date | Transaction date |
| Particulars | Party/ledger name |
| Active Columns | Contributing ledgers with amounts |
| Taxable Value | Calculated taxable amount |
| Tax Rates (Config) | Rate from configuration |
| Tax Rates (Calculated) | Rate computed from values |
| CGST_X%, SGST_X%, IGST_X% | Individual tax amounts |
| Total CGST, Total SGST, Total IGST | Tax totals |
| Transaction Type | Voucher type |
| Review Required | For Non-GST: RCM/Exempt guidance |

## Configuration Management

### Save Configuration
- File → Save Configuration (or Setup tab button)
- Enter client name
- Auto-versioned with timestamp if changes detected

### Load Configuration
- File → Load Configuration
- Select from saved configurations

### Configuration Location
- Stored in: `~/.gst_tool_configs/`
- Format: JSON files

## Technical Details

### Supported File Formats
- `.xlsx` (Excel 2007+)
- `.xls` (Legacy Excel)

### Header Detection
The tool looks for rows containing both "Date" and "Particulars" in the first 3 columns.

### Tax Rate Processing
- Decimal rates (0.05%) are converted to percentage (5%)
- CGST + SGST are combined for display (9% + 9% = 18%)
- Generic columns are labeled as "Generic"

### Taxable Value Calculation
```
Taxable Value = Sum of all numeric columns 
                - Tax columns 
                - Exclusion list columns
```

## Troubleshooting

### "Header row not found"
- Ensure your file has "Date" and "Particulars" in the first 3 columns
- Check if there are extra rows before the header

### Missing columns in output
- Verify column names match exactly (case-sensitive in some cases)
- Check Tax Configuration for typos

### Performance issues
- Process files in batches for very large datasets
- Close other applications if memory is limited

## Project Structure

```
gst_tool/
├── main.py              # Application entry point
├── requirements.txt     # Python dependencies
├── README.md           # This file
├── core/
│   ├── __init__.py
│   ├── processor.py    # Core processing logic
│   └── config_manager.py # Configuration management
├── ui/
│   ├── __init__.py
│   ├── setup_tab.py    # Setup tab UI
│   ├── gst_tab.py      # GST transactions tab
│   └── non_gst_tab.py  # Non-GST transactions tab
└── utils/
    ├── __init__.py
    ├── excel_handler.py # Excel read/write utilities
    └── helpers.py       # Common helper functions
```

## Version History

- **v1.0** (January 2025): Initial release
  - Port from Power Query M Code
  - Multiple file/sheet support
  - Configuration versioning
  - Dual tax rate calculation

## Author

**Sidhant**  
Contact: 7003395384

## Acknowledgments

- Based on Power Query M Code solution developed collaboratively with Claude
- Built for Indian GST compliance requirements
- Designed for accountants and CA professionals

## License

Proprietary - For authorized use only.
