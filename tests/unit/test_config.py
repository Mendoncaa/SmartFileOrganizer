"""Unit tests for config loader."""

from pathlib import Path

import pytest

from src.shared.config import ConfigError, load_rules, load_settings, load_yaml


class TestLoadYaml:
    def test_loads_valid_yaml(self, tmp_path: Path):
        f = tmp_path / "test.yaml"
        f.write_text("key: value\nnested:\n  a: 1\n", encoding="utf-8")
        result = load_yaml(f)
        assert result == {"key": "value", "nested": {"a": 1}}

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(ConfigError, match="not found"):
            load_yaml(tmp_path / "nonexistent.yaml")

    def test_directory_raises(self, tmp_path: Path):
        with pytest.raises(ConfigError, match="not a file"):
            load_yaml(tmp_path)

    def test_invalid_yaml_raises(self, tmp_path: Path):
        f = tmp_path / "bad.yaml"
        f.write_text("key: [unclosed", encoding="utf-8")
        with pytest.raises(ConfigError, match="Invalid YAML"):
            load_yaml(f)

    def test_empty_file_returns_empty_dict(self, tmp_path: Path):
        f = tmp_path / "empty.yaml"
        f.write_text("", encoding="utf-8")
        assert load_yaml(f) == {}

    def test_non_mapping_raises(self, tmp_path: Path):
        f = tmp_path / "list.yaml"
        f.write_text("- item1\n- item2\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="Expected a YAML mapping"):
            load_yaml(f)


class TestLoadSettings:
    def test_loads_default_settings_file(self, tmp_path: Path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        settings_file = config_dir / "settings.yaml"
        settings_file.write_text(
            """
watch_folders:
  - path: ~/Downloads
    recursive: false
debounce_seconds: 3.0
""",
            encoding="utf-8",
        )
        settings = load_settings(base_dir=tmp_path)
        assert settings.debounce_seconds == 3.0
        assert len(settings.watch_folders) == 1

    def test_loads_explicit_path(self, tmp_path: Path):
        custom = tmp_path / "custom_settings.yaml"
        custom.write_text(
            """
watch_folders:
  - path: ~/Desktop
""",
            encoding="utf-8",
        )
        settings = load_settings(path=custom)
        assert len(settings.watch_folders) == 1

    def test_invalid_settings_raises(self, tmp_path: Path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        settings_file = config_dir / "settings.yaml"
        settings_file.write_text(
            """
watch_folders: []
""",
            encoding="utf-8",
        )
        with pytest.raises(ConfigError, match="Invalid settings"):
            load_settings(base_dir=tmp_path)


class TestLoadRules:
    def test_loads_rules_file(self, tmp_path: Path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        rules_file = config_dir / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "PDFs"
    priority: 10
    condition:
      extensions: [pdf]
    destination: "~/Documents/PDFs/"
  - name: "Images"
    priority: 5
    condition:
      extensions: [jpg, png]
    destination: "~/Pictures/"
""",
            encoding="utf-8",
        )
        config = load_rules(base_dir=tmp_path)
        assert len(config.rules) == 2
        assert config.rules[0].name == "PDFs"

    def test_active_rules_sorted_by_priority(self, tmp_path: Path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        rules_file = config_dir / "rules.yaml"
        rules_file.write_text(
            """
rules:
  - name: "Low"
    priority: 1
    condition:
      extensions: [txt]
    destination: "/dest"
  - name: "High"
    priority: 99
    condition:
      extensions: [pdf]
    destination: "/dest"
""",
            encoding="utf-8",
        )
        config = load_rules(base_dir=tmp_path)
        active = config.get_active_rules()
        assert active[0].name == "High"
        assert active[1].name == "Low"

    def test_empty_rules_valid(self, tmp_path: Path):
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        rules_file = config_dir / "rules.yaml"
        rules_file.write_text("rules: []\n", encoding="utf-8")
        config = load_rules(base_dir=tmp_path)
        assert config.rules == []

    def test_loads_project_rules_yaml(self):
        """Validate the actual project rules.yaml file is well-formed."""
        project_root = Path(__file__).parent.parent.parent
        config = load_rules(base_dir=project_root)
        assert len(config.rules) > 0
        # All rules should have a name and destination
        for rule in config.rules:
            assert rule.name
            assert rule.destination
