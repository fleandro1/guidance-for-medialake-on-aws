"""Configuration management for LakeLoader application."""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


def get_config_dir() -> Path:
    """Get the platform-specific configuration directory."""
    if os.name == "nt":  # Windows
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif os.name == "posix" and hasattr(os, "uname") and os.uname().sysname == "Darwin":  # macOS
        base = Path.home() / "Library" / "Application Support"
    else:  # Linux and others
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    config_dir = base / "LakeLoader"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_data_dir() -> Path:
    """Get the platform-specific data directory."""
    if os.name == "nt":  # Windows
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif os.name == "posix" and hasattr(os, "uname") and os.uname().sysname == "Darwin":  # macOS
        base = Path.home() / "Library" / "Application Support"
    else:  # Linux and others
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    data_dir = base / "LakeLoader"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


# AWS regions for Cognito
AWS_REGIONS = [
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
    "eu-west-1",
    "eu-west-2",
    "eu-west-3",
    "eu-central-1",
    "eu-north-1",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-northeast-1",
    "ap-northeast-2",
    "ap-south-1",
    "sa-east-1",
    "ca-central-1",
]


@dataclass
class Config:
    """Application configuration."""

    # Media Lake connection
    api_base_url: str = ""  # e.g. https://abc123.execute-api.us-east-1.amazonaws.com/prod

    # Cognito auth
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_region: str = "us-east-1"

    # Stored credentials (optional, for auto-login)
    saved_username: str = ""
    # NOTE: Never store passwords. Store only tokens with expiry.

    # Ingest behaviour
    max_concurrent_uploads: int = 5
    default_connector_id: str = ""
    default_destination_path: str = ""
    retry_on_failure: bool = True
    max_retries: int = 3
    chunk_size_mb: int = 500  # Part size used for multipart uploads

    # History
    max_history_records: int = 10000

    # Internal - not persisted
    _config_path: Optional[Path] = field(default=None, repr=False)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """Load configuration from file."""
        if config_path is None:
            config_path = get_config_dir() / "config.json"

        config = cls()
        config._config_path = config_path

        if config_path.exists():
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Update config with loaded values
                for key, value in data.items():
                    if hasattr(config, key) and not key.startswith("_"):
                        setattr(config, key, value)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load config from {config_path}: {e}")

        return config

    def save(self) -> None:
        """Save configuration to file."""
        if self._config_path is None:
            self._config_path = get_config_dir() / "config.json"

        # Ensure directory exists
        self._config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict, excluding private attributes
        data = {}
        for key, value in asdict(self).items():
            if not key.startswith("_"):
                data[key] = value

        try:
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"Error: Failed to save config to {self._config_path}: {e}")
            raise

    def is_configured(self) -> bool:
        """Check if minimum required configuration is present."""
        return bool(
            self.api_base_url and self.cognito_user_pool_id and self.cognito_client_id
        )

    def get_chunk_size_bytes(self) -> int:
        """Get chunk size in bytes for multipart uploads."""
        return self.chunk_size_mb * 1024 * 1024
