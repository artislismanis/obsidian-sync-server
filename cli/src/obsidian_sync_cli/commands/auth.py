"""Authentication commands: login, logout."""

import asyncio
import getpass

import typer
from rich.console import Console

from obsidian_sync_cli.client.http import SyncHTTPClient
from obsidian_sync_cli.config import CLIConfig

console = Console()
app = typer.Typer()


@app.command()
def login(server_url: str = typer.Argument(help="Server URL")) -> None:
    """Authenticate with a sync server."""
    username = typer.prompt("Username")
    password = getpass.getpass("Password: ")

    config = CLIConfig.load()
    config.server.server_url = server_url.rstrip("/")
    config.save()

    async def _login() -> None:
        client = SyncHTTPClient(config)
        try:
            await client.login(username, password)
            console.print(f"[green]Logged in to {server_url}[/green]")
        finally:
            await client.close()

    asyncio.run(_login())


@app.command()
def logout() -> None:
    """Clear stored credentials."""
    config = CLIConfig.load()
    config.server.access_token = ""
    config.server.refresh_token = ""
    config.save()
    console.print("[yellow]Logged out[/yellow]")
