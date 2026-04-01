"""CLI configuration — stores server URL, tokens, vault mappings."""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


def _config_dir() -> Path:
    d = Path(os.environ.get("OSS_CONFIG_DIR", Path.home() / ".config" / "obsidian-sync"))
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class ServerConfig:
    server_url: str = ""
    access_token: str = ""
    refresh_token: str = ""


@dataclass
class VaultMapping:
    vault_id: str = ""
    local_dir: str = ""
    last_version: int = 0


@dataclass
class CLIConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    vaults: dict[str, VaultMapping] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "CLIConfig":
        path = _config_dir() / "config.json"
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        cfg = cls()
        if "server" in data:
            cfg.server = ServerConfig(**data["server"])
        if "vaults" in data:
            cfg.vaults = {k: VaultMapping(**v) for k, v in data["vaults"].items()}
        return cfg

    def save(self) -> None:
        path = _config_dir() / "config.json"
        data = {
            "server": asdict(self.server),
            "vaults": {k: asdict(v) for k, v in self.vaults.items()},
        }
        path.write_text(json.dumps(data, indent=2))
