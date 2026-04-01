import typer

from obsidian_sync_cli import __version__

app = typer.Typer(
    name="oss",
    help="Obsidian Sync Server CLI — headless vault sync client",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"oss {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-v", help="Show version", callback=version_callback
    ),
) -> None:
    """Obsidian Sync Server CLI."""


@app.command()
def login(server_url: str = typer.Argument(help="Server URL to connect to")) -> None:
    """Authenticate with a sync server."""
    typer.echo(f"Connecting to {server_url}...")
    # Will be implemented in Phase 3


@app.command()
def vaults() -> None:
    """List available vaults."""
    typer.echo("Listing vaults...")
    # Will be implemented in Phase 3


@app.command()
def status() -> None:
    """Show sync status."""
    typer.echo("Checking sync status...")
    # Will be implemented in Phase 3
