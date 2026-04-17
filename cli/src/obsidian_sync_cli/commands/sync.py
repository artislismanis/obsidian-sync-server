"""Sync commands: sync, pull, push."""

import asyncio
import hashlib
import os
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress

from obsidian_sync_cli.client.http import SyncHTTPClient
from obsidian_sync_cli.config import CLIConfig, VaultMapping
from obsidian_sync_cli.sync.crypto import decrypt as crypto_decrypt
from obsidian_sync_cli.sync.crypto import derive_key, encrypt as crypto_encrypt

console = Console()
app = typer.Typer()


def _get_passphrase() -> str:
    """Read the vault passphrase from the environment or prompt the user."""
    passphrase = os.environ.get("OSS_VAULT_PASSPHRASE", "")
    if not passphrase:
        passphrase = typer.prompt("Vault passphrase", hide_input=True)
    return passphrase


# Fixed salt used for key derivation (shared across clients).
_DEFAULT_SALT = "0" * 64


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _local_files(directory: Path) -> dict[str, str]:
    """Scan local directory, return {relative_path: sha256_hash}."""
    files = {}
    for root, _dirs, filenames in os.walk(directory):
        for name in filenames:
            full = Path(root) / name
            rel = str(full.relative_to(directory))
            if rel.startswith(".") or ".conflict-" in rel:
                continue
            files[rel] = _hash_file(full)
    return files


@app.command()
def pull(
    vault: str = typer.Option("", "--vault", "-v", help="Vault name or ID"),
    encrypted: bool = typer.Option(False, "--encrypted", "-e", help="Decrypt files after download"),
) -> None:
    """Pull latest files from server."""
    config = CLIConfig.load()
    mapping = _resolve_vault(config, vault)
    if not mapping:
        console.print("[red]No vault configured. Run 'oss sync' first.[/red]")
        raise typer.Exit(1)

    key: bytes | None = None
    if encrypted:
        passphrase = _get_passphrase()
        key = derive_key(passphrase, _DEFAULT_SALT)

    asyncio.run(_pull(config, mapping, key=key))


async def _pull(
    config: CLIConfig,
    mapping: VaultMapping,
    *,
    key: bytes | None = None,
) -> None:
    client = SyncHTTPClient(config)
    try:
        data = await client.list_files(mapping.vault_id)
        server_files = data.get("files", [])
        local_dir = Path(mapping.local_dir)
        local_dir.mkdir(parents=True, exist_ok=True)

        with Progress() as progress:
            task = progress.add_task("Pulling files...", total=len(server_files))
            for sf in server_files:
                path = sf["path"]
                local_path = local_dir / path

                # Check if local file needs updating
                if local_path.exists():
                    local_hash = _hash_file(local_path)
                    if local_hash == sf.get("content_hash"):
                        progress.advance(task)
                        continue

                content, version = await client.download_file(mapping.vault_id, path)
                if key is not None:
                    content = crypto_decrypt(key, content)
                local_path.parent.mkdir(parents=True, exist_ok=True)
                local_path.write_bytes(content)
                progress.advance(task)

        console.print(f"[green]Pulled {len(server_files)} files[/green]")
    finally:
        await client.close()


@app.command()
def push(
    vault: str = typer.Option("", "--vault", "-v", help="Vault name or ID"),
    encrypted: bool = typer.Option(False, "--encrypted", "-e", help="Encrypt files before upload"),
) -> None:
    """Push local changes to server."""
    config = CLIConfig.load()
    mapping = _resolve_vault(config, vault)
    if not mapping:
        console.print("[red]No vault configured. Run 'oss sync' first.[/red]")
        raise typer.Exit(1)

    key: bytes | None = None
    if encrypted:
        passphrase = _get_passphrase()
        key = derive_key(passphrase, _DEFAULT_SALT)

    asyncio.run(_push(config, mapping, key=key))


async def _push(
    config: CLIConfig,
    mapping: VaultMapping,
    *,
    key: bytes | None = None,
) -> None:
    client = SyncHTTPClient(config)
    try:
        local_dir = Path(mapping.local_dir)
        local_files = _local_files(local_dir)

        # Get server state
        data = await client.list_files(mapping.vault_id)
        server_files = {f["path"]: f for f in data.get("files", [])}

        uploaded = 0
        with Progress() as progress:
            task = progress.add_task("Pushing files...", total=len(local_files))
            for rel_path, local_hash in local_files.items():
                sf = server_files.get(rel_path)
                if sf and sf.get("content_hash") == local_hash:
                    progress.advance(task)
                    continue

                content = (local_dir / rel_path).read_bytes()
                if key is not None:
                    content = crypto_encrypt(key, content)
                version = sf["version"] if sf else 0
                await client.upload_file(mapping.vault_id, rel_path, content, version)
                uploaded += 1
                progress.advance(task)

        console.print(f"[green]Pushed {uploaded} changed files[/green]")
    finally:
        await client.close()


@app.command("sync")
def sync_cmd(
    local_dir: str = typer.Argument(help="Local directory to sync"),
    vault: str = typer.Option("", "--vault", "-v", help="Vault name or ID"),
    encrypted: bool = typer.Option(False, "--encrypted", "-e", help="Encrypt/decrypt files during sync"),
) -> None:
    """Bidirectional sync between local directory and server vault."""
    config = CLIConfig.load()

    if not vault:
        console.print("[red]Specify --vault[/red]")
        raise typer.Exit(1)

    key: bytes | None = None
    if encrypted:
        passphrase = _get_passphrase()
        key = derive_key(passphrase, _DEFAULT_SALT)

    # Store mapping
    mapping = VaultMapping(vault_id=vault, local_dir=str(Path(local_dir).resolve()))
    config.vaults[vault] = mapping
    config.save()

    # Pull then push
    asyncio.run(_pull(config, mapping, key=key))
    asyncio.run(_push(config, mapping, key=key))
    console.print("[green]Sync complete[/green]")


def _resolve_vault(config: CLIConfig, vault: str) -> VaultMapping | None:
    if vault and vault in config.vaults:
        return config.vaults[vault]
    # Return first vault if only one configured
    if len(config.vaults) == 1:
        return next(iter(config.vaults.values()))
    return None
