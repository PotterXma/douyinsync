import sys
import json
from pathlib import Path
from modules.logger import logger

if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys.executable).parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

class ConfigManager:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        """Implementation of the Singleton pattern"""
        if not cls._instance:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance.config_file = PROJECT_ROOT / "config.json"
            cls._instance._cache = {}
            cls._instance.reload()
        return cls._instance

    def reload(self) -> bool:
        """
        Reloads the configuration from disk into memory.
        Returns True if successful, False if reading or parsing fails 
        (preserving the old cache to prevent pipeline crash).
        """
        if not self.config_file.exists():
            logger.critical(f"Configuration file missing at {self.config_file}. Please create it.")
            raise FileNotFoundError(f"Configuration file missing at {self.config_file}")

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                new_data = json.load(f)
            self._cache = new_data
            logger.info("Configuration loaded/reloaded successfully.")
            return True
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse config.json. Retaining previous working configuration. Detail: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error loading config.json: {e}")
            return False

    def get(self, key: str, default=None):
        """Retrieves a configuration value with dictionary-like .get logic."""
        return self._cache.get(key, default)

    def get_proxies(self) -> dict:
        """
        Returns a requests-compatible proxies dict formatted based on configuration.
        Returns None if no proxy is configured.
        """
        proxy_val = str(self.get("proxy", "")).strip()
        if proxy_val:
            return {
                "http": proxy_val,
                "https": proxy_val
            }
        return None

# Singleton exported instance
config = ConfigManager()
