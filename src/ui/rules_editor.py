"""Rules Editor — visual YAML editor with Pydantic validation."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.shared.config import ConfigError, load_rules
from src.shared.logging import get_logger

logger = get_logger(__name__)


class RulesEditorWindow(QMainWindow):
    """Visual editor for rules.yaml with live Pydantic validation."""

    def __init__(self, rules_path: Path | None = None) -> None:
        super().__init__()
        self._rules_path = rules_path or Path("config/rules.yaml")
        self._setup_ui()
        self._load_file()

    def _setup_ui(self) -> None:
        """Build the rules editor UI."""
        self.setWindowTitle("Smart File Organizer — Rules Editor")
        self.setMinimumSize(700, 500)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Header
        header = QLabel(f"Editing: {self._rules_path}")
        header.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(header)

        # Editor
        self._editor = QPlainTextEdit()
        self._editor.setStyleSheet("font-family: 'Consolas', 'Courier New', monospace;")
        self._editor.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._editor)

        # Status bar
        self._status = QLabel("Ready")
        self._status.setStyleSheet("padding: 4px; color: green;")
        layout.addWidget(self._status)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._btn_validate = QPushButton("Validate")
        self._btn_validate.clicked.connect(self._validate)
        btn_layout.addWidget(self._btn_validate)

        self._btn_save = QPushButton("Save")
        self._btn_save.clicked.connect(self._save)
        self._btn_save.setEnabled(False)
        btn_layout.addWidget(self._btn_save)

        layout.addLayout(btn_layout)

    def _load_file(self) -> None:
        """Load the rules.yaml file into the editor."""
        if self._rules_path.exists():
            content = self._rules_path.read_text(encoding="utf-8")
            self._editor.setPlainText(content)
            self._status.setText("File loaded")
            self._status.setStyleSheet("padding: 4px; color: green;")
        else:
            self._status.setText("File not found — start with empty rules")
            self._status.setStyleSheet("padding: 4px; color: orange;")

    def _on_text_changed(self) -> None:
        """Enable save button when text changes."""
        self._btn_save.setEnabled(True)
        self._status.setText("Modified (unsaved)")
        self._status.setStyleSheet("padding: 4px; color: orange;")

    def _validate(self) -> bool:
        """Validate the current YAML content against the Pydantic schema."""
        import tempfile

        content = self._editor.toPlainText()

        # Write to temp file for validation
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            tmp_path = Path(f.name)

        try:
            load_rules(path=tmp_path)
            self._status.setText("✓ Valid — all rules pass Pydantic validation")
            self._status.setStyleSheet("padding: 4px; color: green;")
            return True
        except ConfigError as e:
            self._status.setText(f"✗ Invalid: {e}")
            self._status.setStyleSheet("padding: 4px; color: red;")
            return False
        finally:
            tmp_path.unlink(missing_ok=True)

    def _save(self) -> None:
        """Save after validation passes."""
        if not self._validate():
            QMessageBox.warning(
                self,
                "Validation Failed",
                "Cannot save — fix validation errors first.",
            )
            return

        content = self._editor.toPlainText()
        self._rules_path.parent.mkdir(parents=True, exist_ok=True)
        self._rules_path.write_text(content, encoding="utf-8")
        self._btn_save.setEnabled(False)
        self._status.setText("✓ Saved successfully")
        self._status.setStyleSheet("padding: 4px; color: green;")
        logger.info("rules_saved", path=str(self._rules_path))
