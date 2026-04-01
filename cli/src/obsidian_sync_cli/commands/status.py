"""Status command."""

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from obsidian_sync_cli.client.http import SyncHTTPClient
from obsidian_sync_cli.config import CLIConfig

console = Console()
app = typer.Typer()


@app.command()
def status(
    vault: str = typer.Option("", "--vault", "-v", help="Vault name or ID"),
) -> None:
    """Show sync status."""
    config = CLIConfig.load()

    if not config.server.server_url:
        console.print("[red]Not logged in. Run 'oss login' first.[/red]")
        raise typer.Exit(1)

    asyncio.run(_status(config, vault))


async def _status(config: CLIConfig, vault_filter: str) -> None:
    client = SyncHTTPClient(config)
    try:
        vaults = await client.list_vaults()

        table = Table(title="Vault Status")
        table.add_column("Name")
        table.add_column("ID")
        table.add_column("Storage")
        table.add_column("Encrypted")
        table.add_column("Sync Mode")
        table.add_column("Local Dir")

        for v in vaults:
            if vault_filter and vault_filter not in (v["id"], v["name"]):
                continue
            local_dir = ""
            if v["id"] in config.vaults:
                local_dir = config.vaults[v["id"]].local_dir
            table.add_row(
                v["name"],
                v["id"][:8] + "...",
                v.get("storage_backend", "local"),
                "Yes" if v.get("encrypted") else "No",
                v.get("sync_mode", "on_save"),
                local_dir or "-",
            )

        console.print(table)
        console.print(f"\nServer: {config.server.server_url}")
    finally:
        await client.close()
