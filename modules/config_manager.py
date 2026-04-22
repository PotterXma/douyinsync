import sys
import json
import threading
from pathlib import Path
from modules.logger import logger
from utils.models import AppConfig, TargetConfig, ProxyConfig

if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys.executable).parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

class ConfigParseError(Exception):
    """Raised when the config.json file is malformed or invalid."""
    pass

class ConfigNotFoundError(Exception):
    """Raised when the config.json file cannot be found."""
    pass

class ConfigManager:
    _instance = None
    _class_lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """Implementation of the Singleton pattern"""
        if not cls._instance:
            with cls._class_lock:
                if not cls._instance:
                    cls._instance = super(ConfigManager, cls).__new__(cls)
                    cls._instance.config_file = str(PROJECT_ROOT / "config.json")
                    cls._instance._lock = threading.Lock()
                    cls._instance._config = None
        return cls._instance

    def __init__(self, config_path: str | None = None) -> None:
        """
        Initialization allows overriding config path for testing.
        """
        if config_path:
            self.config_file = config_path
            self._config = None  # Force reload if path changes globally

    def load_config(self) -> AppConfig:
        """
        Reads from config.json, maps to strongly typed AppConfig Dataclass.
        Throws ConfigNotFoundError if file is missing.
        Throws ConfigParseError if JSON is invalid or schema is malformed.
        """
        with self._lock:
            if self._config is not None:
                return self._config
                
            path_obj = Path(self.config_file)
            if not path_obj.is_file():
                logger.critical("Configuration file missing or not a file at %s", self.config_file)
                raise ConfigNotFoundError(f"Configuration file not found at {self.config_file}")
            
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except OSError as e:
                logger.critical("OS/Permission error reading config file: %s", e)
                raise ConfigParseError(f"File read error: {e}")
            except json.JSONDecodeError as e:
                logger.critical("JSON Parse error in config file: %s", e)
                raise ConfigParseError(f"Failed to parse JSON configuration: {e}")

            if not isinstance(data, dict):
                raise ConfigParseError("Configuration root must be a JSON object")

            # Parse proxies
            proxy_data = data.get("proxies", {})
            if not isinstance(proxy_data, dict):
                raise ConfigParseError("'proxies' field must be an object")
                
            http_val = proxy_data.get("http")
            https_val = proxy_data.get("https")
            proxies = ProxyConfig(
                http=str(http_val) if http_val is not None else None,
                https=str(https_val) if https_val is not None else None
            )

            # Parse targets
            target_data = data.get("targets")
            if target_data is None:
                raise ConfigParseError("Configuration missing mandatory 'targets' array")
            if not isinstance(target_data, list):
                raise ConfigParseError("'targets' field must be a list")
                
            targets = []
            for index, t in enumerate(target_data):
                if not isinstance(t, dict):
                    raise ConfigParseError(f"Target at index {index} must be an object")
                douyin_id = t.get("douyin_id")
                if not douyin_id:
                    raise ConfigParseError(f"Target at index {index} is missing 'douyin_id'")
                
                name_val = t.get("name")
                targets.append(TargetConfig(
                    douyin_id=str(douyin_id),
                    name=str(name_val) if name_val is not None else None
                ))

            self._config = AppConfig(targets=targets, proxies=proxies)
            logger.info("Configuration loaded successfully via ConfigManager.")
            return self._config

    @property
    def config(self) -> AppConfig:
        """Returns the loaded AppConfig. Raises if not loaded yet."""
        if not self._config:
            return self.load_config()
        return self._config

    def get(self, key: str, default=None):
        """Legacy dictionary default access helper. Avoid using in new code."""
        if key == "proxies":
            return self.get_proxies()
        return default

    def get_proxies(self) -> dict | None:
        """Returns a requests-compatible proxies dict formatted based on configuration."""
        conf = self.config
        if conf.proxies.http or conf.proxies.https:
            return {
                "http": conf.proxies.http or conf.proxies.https,
                "https": conf.proxies.https or conf.proxies.http
            }
        return None

# Singleton instance exported
config = ConfigManager()
config_manager = config
