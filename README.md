# GST Compliance Data Transformation Tool

A PyQt5 Windows application for transforming Tally ERP GST data exports into structured formats suitable for GST compliance and ITC analysis in India.

## What's New in v2.0

- **Redesigned UI**: Separate tabs for Files, Columns, and Tax Config
- **Improved Files Tab**: Visual file tree with row counts per sheet
- **Side-by-side Layouts**: Column List and Exclusion List visible together
- **Simplified Tax Config**: Shows only Tax-marked columns (no 40+ default rows)
- **Auto-assign Feature**: Automatically detects tax type and rate from column names
- **Better UX**: Process/Export buttons on every tab for convenience

## Features

- **Multiple File Support**: Process multiple Excel files simultaneously with drag-and-drop
- **Multi-Sheet Selection**: Select specific sheets from each file with row counts
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

### Tab 1: Files

1. Click "Add Files..." or drag-and-drop Excel files
2. Check/uncheck sheets you want to process
3. View row counts per sheet

### Tab 2: Columns

1. Columns auto-populate after adding files
2. Mark columns as Tax, Excluded, or Taxable:
   - **[T] Tax**: Tax columns (CGST, SGST, IGST, CESS)
   - **[E] Excluded**: Columns excluded from taxable value
   - **[S] Standard**: Standard columns (Date, Particulars, etc.)
   - **[ ] Taxable**: Columns contributing to taxable value
3. Use "Auto-detect Tax" to find tax columns by name
4. Manage Exclusion List on the right panel

### Tab 3: Tax Config

1. Tax-marked columns appear automatically
2. Assign Tax Type (CGST/SGST/IGST/CESS) and Rate
3. Use "Auto-assign by Name" to detect from column names
4. View mapping preview (e.g., "→ CGST_9%")

### Process & Export

- Click "Process Data" from any tab
- Results appear in GST Transactions and Non-GST Transactions tabs
- Export complete report with File → Export Complete Report

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
- Configuration → Save Configuration
- Enter client name
- Auto-versioned with timestamp

### Load Configuration
- Configuration → Load Configuration
- Select from saved configurations

### Configuration Location
- Stored in: `~/.gst_tool_configs/`
- Format: JSON files

## Switching to Old UI

If you prefer the v1.x single-tab layout, the backup file `setup_tab.py` is retained. To switch:

```python
# In main.py, comment out new imports:
# from ui.files_tab import FilesTab
# from ui.columns_tab import ColumnsTab
# from ui.tax_config_tab import TaxConfigTab

# Uncomment old import:
from ui.setup_tab import SetupTab
```

## Project Structure

```
gst_tool/
├── main.py              # Application entry point (v2.0)
├── requirements.txt     # Python dependencies
├── README.md           # This file
├── core/
│   ├── __init__.py
│   ├── processor.py    # Core processing logic
│   └── config_manager.py # Configuration management
├── ui/
│   ├── __init__.py
│   ├── widgets/        # NEW: Shared widgets
│   │   ├── __init__.py
│   │   └── multi_select.py
│   ├── files_tab.py    # NEW: Tab 1 - Files
│   ├── columns_tab.py  # NEW: Tab 2 - Columns
│   ├── tax_config_tab.py # NEW: Tab 3 - Tax Config
│   ├── setup_tab.py    # BACKUP: Old combined UI
│   ├── gst_tab.py      # GST transactions tab
│   └── non_gst_tab.py  # Non-GST transactions tab
└── utils/
    ├── __init__.py
    ├── excel_handler.py # Excel read/write utilities
    └── helpers.py       # Common helper functions
```

## Roadmap

### Version 2.0 (Current)
- [x] UI Restructuring: 3 separate tabs for Files, Columns, Tax Config
- [x] Improved Files Tab: Visual tree with row counts, sheet tooltips
- [x] Columns Tab: Side-by-side Column List + Exclusion List
- [x] Tax Config Tab: Simplified view showing only Tax-marked columns
- [x] Auto-assign tax columns by name detection

### Version 2.1 (Planned)
- [ ] Data preview before processing
- [ ] Progress feedback during file scan
- [ ] Undo/Redo for column markings

### Version 2.2 (Future)
- [ ] Batch export (multiple files → multiple outputs)
- [ ] GSTR-1/3B JSON generation
- [ ] Summary dashboard with pivot analysis

### Version 3.0 (Long-term)
- [ ] GSTR-2A/2B reconciliation
- [ ] Direct GST portal integration
- [ ] Multi-company consolidated processing

## Version History

- **v2.0** (January 2025): UI Redesign
  - Separate tabs for Files, Columns, Tax Config
  - Improved UX with side-by-side layouts
  - Auto-assign tax columns by name
  - Process/Export buttons on every tab

- **v1.0** (January 2025): Initial release
  - Port from Power Query M Code
  - Multiple file/sheet support
  - Configuration versioning
  - Dual tax rate calculation

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

## Author

**Sidhant**
Contact: 7003395384

## Acknowledgments

- Based on Power Query M Code solution developed collaboratively with Claude
- Built for Indian GST compliance requirements
- Designed for accountants and CA professionals

## License

Proprietary - For authorized use only.
