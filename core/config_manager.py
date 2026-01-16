"""
Configuration Manager
Handles TaxConfig and ExclusionList persistence and versioning.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pandas as pd
from dataclasses import dataclass, asdict
import hashlib


@dataclass
class AppConfig:
    """Application configuration container"""
    tax_config: List[Dict]  # List of {TaxType, TaxRate, ColumnNames, Delimiter}
    exclusion_list: List[str]
    client_name: str = ""
    version: str = "v1"
    created_at: str = ""
    updated_at: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AppConfig':
        return cls(**data)


class ConfigManager:
    """Manages configuration persistence and versioning"""
    
    DEFAULT_TAX_CONFIG = [
        # CGST rates - ColumnNames empty by default, user selects from dropdown
        {"TaxType": "CGST", "TaxRate": "Generic", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "CGST", "TaxRate": "0%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "CGST", "TaxRate": "0.05%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "CGST", "TaxRate": "0.125%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "CGST", "TaxRate": "1.5%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "CGST", "TaxRate": "2.5%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "CGST", "TaxRate": "5%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "CGST", "TaxRate": "6%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "CGST", "TaxRate": "7.5%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "CGST", "TaxRate": "9%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "CGST", "TaxRate": "12%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "CGST", "TaxRate": "14%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "CGST", "TaxRate": "18%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "CGST", "TaxRate": "28%", "ColumnNames": "", "Delimiter": ","},
        # SGST rates
        {"TaxType": "SGST", "TaxRate": "Generic", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "SGST", "TaxRate": "0%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "SGST", "TaxRate": "0.05%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "SGST", "TaxRate": "0.125%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "SGST", "TaxRate": "1.5%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "SGST", "TaxRate": "2.5%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "SGST", "TaxRate": "5%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "SGST", "TaxRate": "6%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "SGST", "TaxRate": "7.5%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "SGST", "TaxRate": "9%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "SGST", "TaxRate": "12%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "SGST", "TaxRate": "14%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "SGST", "TaxRate": "18%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "SGST", "TaxRate": "28%", "ColumnNames": "", "Delimiter": ","},
        # IGST rates
        {"TaxType": "IGST", "TaxRate": "Generic", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "IGST", "TaxRate": "0%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "IGST", "TaxRate": "0.1%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "IGST", "TaxRate": "0.25%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "IGST", "TaxRate": "3%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "IGST", "TaxRate": "5%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "IGST", "TaxRate": "12%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "IGST", "TaxRate": "18%", "ColumnNames": "", "Delimiter": ","},
        {"TaxType": "IGST", "TaxRate": "28%", "ColumnNames": "", "Delimiter": ","},
        # CESS
        {"TaxType": "CESS", "TaxRate": "Generic", "ColumnNames": "", "Delimiter": ","},
    ]
    
    DEFAULT_EXCLUSION_LIST = [
        "Round Off",
        "TDS Payable",
        "TCS Payable",
        "Discount",
        "Late Fee",
        "Interest",
        "Penalty",
    ]
    
    def __init__(self, config_dir: Optional[str] = None):
        """Initialize config manager with optional config directory"""
        if config_dir is None:
            # Default to user's home directory
            self.config_dir = os.path.join(os.path.expanduser("~"), ".gst_tool_configs")
        else:
            self.config_dir = config_dir
        
        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Current config
        self.current_config = self.get_default_config()
        self._last_saved_hash = self._compute_hash(self.current_config)
    
    def get_default_config(self) -> AppConfig:
        """Get default configuration"""
        now = datetime.now().isoformat()
        return AppConfig(
            tax_config=self.DEFAULT_TAX_CONFIG.copy(),
            exclusion_list=self.DEFAULT_EXCLUSION_LIST.copy(),
            client_name="Default",
            version="v1",
            created_at=now,
            updated_at=now
        )
    
    def _compute_hash(self, config: AppConfig) -> str:
        """Compute hash of config for change detection"""
        # Only hash the actual config data, not metadata
        data = {
            'tax_config': config.tax_config,
            'exclusion_list': config.exclusion_list
        }
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()
    
    def has_changes(self) -> bool:
        """Check if current config has unsaved changes"""
        return self._compute_hash(self.current_config) != self._last_saved_hash
    
    def get_tax_config_df(self) -> pd.DataFrame:
        """Get tax config as DataFrame"""
        return pd.DataFrame(self.current_config.tax_config)
    
    def get_exclusion_list(self) -> List[str]:
        """Get exclusion list"""
        return self.current_config.exclusion_list.copy()
    
    def set_tax_config(self, tax_config: List[Dict]):
        """Set tax config"""
        self.current_config.tax_config = tax_config
        self.current_config.updated_at = datetime.now().isoformat()
    
    def set_exclusion_list(self, exclusion_list: List[str]):
        """Set exclusion list"""
        self.current_config.exclusion_list = exclusion_list
        self.current_config.updated_at = datetime.now().isoformat()
    
    def add_tax_config_row(self, tax_type: str, tax_rate: str, column_names: str, delimiter: str = ","):
        """Add a row to tax config"""
        self.current_config.tax_config.append({
            "TaxType": tax_type,
            "TaxRate": tax_rate,
            "ColumnNames": column_names,
            "Delimiter": delimiter
        })
        self.current_config.updated_at = datetime.now().isoformat()
    
    def remove_tax_config_row(self, index: int):
        """Remove a row from tax config"""
        if 0 <= index < len(self.current_config.tax_config):
            del self.current_config.tax_config[index]
            self.current_config.updated_at = datetime.now().isoformat()
    
    def add_exclusion(self, column_name: str):
        """Add a column to exclusion list"""
        if column_name not in self.current_config.exclusion_list:
            self.current_config.exclusion_list.append(column_name)
            self.current_config.updated_at = datetime.now().isoformat()
    
    def remove_exclusion(self, column_name: str):
        """Remove a column from exclusion list"""
        if column_name in self.current_config.exclusion_list:
            self.current_config.exclusion_list.remove(column_name)
            self.current_config.updated_at = datetime.now().isoformat()
    
    def _generate_version_name(self, client_name: str) -> str:
        """Generate version name with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return f"{client_name}_{timestamp}"
    
    def _get_next_version(self, client_name: str) -> str:
        """Get next version number for a client"""
        # Find existing configs for this client
        existing = self.list_configs()
        client_configs = [c for c in existing if c.startswith(client_name)]
        
        if not client_configs:
            return "v1"
        
        # Find highest version
        max_version = 0
        for config_name in client_configs:
            # Try to extract version number
            parts = config_name.replace(client_name + "_", "").split("_")
            for part in parts:
                if part.startswith("v") and part[1:].isdigit():
                    max_version = max(max_version, int(part[1:]))
        
        return f"v{max_version + 1}"
    
    def save_config(self, client_name: str, force_new_version: bool = False) -> str:
        """
        Save current config.
        Returns the filename saved.
        
        If config hasn't changed since last save, doesn't create new version unless forced.
        """
        self.current_config.client_name = client_name
        
        # Check if we need a new version
        if not force_new_version and not self.has_changes():
            # No changes, return existing filename
            return f"{client_name}_current.json"
        
        # Generate new version
        version = self._get_next_version(client_name)
        self.current_config.version = version
        self.current_config.updated_at = datetime.now().isoformat()
        
        # Generate filename with timestamp
        version_name = self._generate_version_name(client_name)
        filename = f"{version_name}.json"
        filepath = os.path.join(self.config_dir, filename)
        
        # Save config
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.current_config.to_dict(), f, indent=2, ensure_ascii=False)
        
        # Update hash
        self._last_saved_hash = self._compute_hash(self.current_config)
        
        return filename
    
    def load_config(self, filename: str) -> bool:
        """
        Load config from file.
        Returns True if successful.
        """
        filepath = os.path.join(self.config_dir, filename)
        
        if not os.path.exists(filepath):
            return False
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.current_config = AppConfig.from_dict(data)
            self._last_saved_hash = self._compute_hash(self.current_config)
            return True
        except json.JSONDecodeError as e:
            import logging
            logging.error(f"Failed to parse config file {filepath}: Invalid JSON - {str(e)}")
            return False
        except KeyError as e:
            import logging
            logging.error(f"Failed to load config file {filepath}: Missing required field - {str(e)}")
            return False
        except Exception as e:
            import logging
            logging.error(f"Failed to load config file {filepath}: {str(e)}")
            return False

    def list_configs(self) -> List[str]:
        """List all saved config files"""
        if not os.path.exists(self.config_dir):
            return []
        
        configs = []
        for f in os.listdir(self.config_dir):
            if f.endswith('.json'):
                configs.append(f.replace('.json', ''))
        
        # Sort by date (newest first)
        configs.sort(reverse=True)
        return configs
    
    def delete_config(self, filename: str) -> bool:
        """Delete a config file"""
        filepath = os.path.join(self.config_dir, filename)
        if not filepath.endswith('.json'):
            filepath += '.json'
        
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False
    
    def export_to_json(self, filepath: str):
        """Export current config to a JSON file at specified path"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.current_config.to_dict(), f, indent=2, ensure_ascii=False)
    
    def import_from_json(self, filepath: str) -> bool:
        """Import config from a JSON file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.current_config = AppConfig.from_dict(data)
            self._last_saved_hash = self._compute_hash(self.current_config)
            return True
        except json.JSONDecodeError as e:
            import logging
            logging.error(f"Failed to import config from {filepath}: Invalid JSON - {str(e)}")
            return False
        except KeyError as e:
            import logging
            logging.error(f"Failed to import config from {filepath}: Missing required field - {str(e)}")
            return False
        except Exception as e:
            import logging
            logging.error(f"Failed to import config from {filepath}: {str(e)}")
            return False
    
    def reset_to_defaults(self):
        """Reset to default configuration"""
        self.current_config = self.get_default_config()
        self._last_saved_hash = self._compute_hash(self.current_config)
    
    def get_all_tax_column_names(self) -> List[str]:
        """Get all configured tax column names (flattened)"""
        all_names = []
        for row in self.current_config.tax_config:
            delimiter = row.get('Delimiter', ',')
            # Validate delimiter - use comma as fallback for empty/invalid delimiters
            if not delimiter or not isinstance(delimiter, str):
                delimiter = ','
            column_names = row.get('ColumnNames', '')
            if column_names:
                names = [n.strip() for n in column_names.split(delimiter) if n.strip()]
                all_names.extend(names)
        return list(set(all_names))
