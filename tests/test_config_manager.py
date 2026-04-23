import pytest
import os
import tempfile
import json
from modules.config_manager import ConfigManager, ConfigNotFoundError, ConfigParseError
from utils.models import AppConfig, TargetConfig, ProxyConfig

def test_config_not_found() -> None:
    manager = ConfigManager("nonexistent_config.json")
    with pytest.raises(ConfigNotFoundError):
        manager.load_config()

def test_invalid_json() -> None:
    f = tempfile.NamedTemporaryFile(mode='w', delete=False)
    config_path = f.name
    f.close()
    
    try:
        with open(config_path, 'w', encoding='utf-8') as f2:
            f2.write("{invalid json")
            
        manager = ConfigManager(config_path)
        with pytest.raises(ConfigParseError):
            manager.load_config()
    finally:
        os.unlink(config_path)

def test_valid_config() -> None:
    valid_data = {
        "targets": [
            {"douyin_id": "test_id_1", "name": "user 1"},
            {"douyin_id": "test_id_2"}
        ],
        "proxies": {
            "http": "http://user:pass@127.0.0.1:1080",
            "https": "http://user:pass@127.0.0.1:1080"
        }
    }
    f = tempfile.NamedTemporaryFile(mode='w', delete=False)
    config_path = f.name
    f.close()
        
    try:
        with open(config_path, 'w', encoding='utf-8') as f2:
            json.dump(valid_data, f2)
            
        manager = ConfigManager(config_path)
        config = manager.load_config()
        assert isinstance(config, AppConfig)
        assert len(config.targets) == 2
        assert config.targets[0].douyin_id == "test_id_1"
        assert config.targets[0].name == "user 1"
        assert config.targets[1].douyin_id == "test_id_2"
        assert config.targets[1].name is None
        assert config.proxies.http == "http://user:pass@127.0.0.1:1080"
        assert config.proxies.https == "http://user:pass@127.0.0.1:1080"
    finally:
        os.unlink(config_path)

def test_targets_omitted_loads_empty_list() -> None:
    data = {"proxies": {}, "douyin_accounts": [{"url": "https://example", "mark": "x"}]}
    f = tempfile.NamedTemporaryFile(mode="w", delete=False)
    config_path = f.name
    f.close()
    try:
        with open(config_path, "w", encoding="utf-8") as f2:
            json.dump(data, f2)
        manager = ConfigManager(config_path)
        cfg = manager.load_config()
        assert isinstance(cfg, AppConfig)
        assert cfg.targets == []
        assert manager.get("douyin_accounts", []) != []
    finally:
        os.unlink(config_path)


def test_missing_douyin_id() -> None:
    invalid_data = {
        "targets": [
            {"name": "user 1"}
        ]
    }
    f = tempfile.NamedTemporaryFile(mode='w', delete=False)
    config_path = f.name
    f.close()
        
    try:
        with open(config_path, 'w', encoding='utf-8') as f2:
            json.dump(invalid_data, f2)
            
        manager = ConfigManager(config_path)
        with pytest.raises(ConfigParseError) as exc:
            manager.load_config()
        assert "missing 'douyin_id'" in str(exc.value)
    finally:
        os.unlink(config_path)


def test_get_reads_raw_json_keys() -> None:
    valid_data = {
        "targets": [{"douyin_id": "id_a", "name": "A"}],
        "proxies": {},
        "sync_interval_minutes": 42,
        "sync_schedule_mode": "clock",
        "sync_clock_times": ["08:00", "20:30"],
    }
    f = tempfile.NamedTemporaryFile(mode="w", delete=False)
    config_path = f.name
    f.close()
    try:
        with open(config_path, "w", encoding="utf-8") as f2:
            json.dump(valid_data, f2)
        manager = ConfigManager(config_path)
        manager.load_config()
        assert manager.get("sync_interval_minutes", 1) == 42
        assert manager.get("sync_schedule_mode", "interval") == "clock"
        assert manager.get("sync_clock_times", []) == ["08:00", "20:30"]
        assert manager.get("missing_key", "dflt") == "dflt"
    finally:
        os.unlink(config_path)
