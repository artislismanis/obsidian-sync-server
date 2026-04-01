"""Watch command: file system watcher for continuous sync."""

import asyncio
import hashlib
from pathlib import Path

import typer
from rich.console import Console
from watchfiles import awatch, Change

from obsidian_sync_cli.client.http import SyncHTTPClient
from obsidian_sync_cli.config import CLIConfig

console = Console()
app = typer.Typer()


@app.command()
def watch(
    vault: str = typer.Option("", "--vault", "-v", help="Vault name or ID"),
) -> None:
    """Watch local directory and sync changes in real-time."""
    config = CLIConfig.load()

    if vault and vault in config.vaults:
        mapping = config.vaults[vault]
    elif len(config.vaults) == 1:
        mapping = next(iter(config.vaults.values()))
    else:
        console.print("[red]No vault configured. Run 'oss sync' first.[/red]")
        raise typer.Exit(1)

    console.print(f"Watching [cyan]{mapping.local_dir}[/cyan] for changes...")
    console.print("Press Ctrl+C to stop.")

    asyncio.run(_watch(config, mapping.vault_id, Path(mapping.local_dir)))


async def _watch(config: CLIConfig, vault_id: str, local_dir: Path) -> None:
    client = SyncHTTPClient(config)
    try:
        async for changes in awatch(local_dir):
            for change_type, path_str in changes:
                path = Path(path_str)
                rel = str(path.relative_to(local_dir))

                # Skip hidden files and conflict files
                if rel.startswith(".") or ".conflict-" in rel:
                    continue

                if change_type == Change.modified or change_type == Change.added:
                    if path.is_file():
                        content = path.read_bytes()
                        try:
                            await client.upload_file(vault_id, rel, content)
                            console.print(f"  [green]↑[/green] {rel}")
                        except Exception as e:
                            console.print(f"  [red]✗[/red] {rel}: {e}")

                elif change_type == Change.deleted:
                    try:
                        await client.delete_file(vault_id, rel)
                        console.print(f"  [red]✗[/red] {rel} (deleted)")
                    except Exception:
                        pass
    except KeyboardInterrupt:
        pass
    finally:
        await client.close()
