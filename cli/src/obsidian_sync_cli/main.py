import typer

from obsidian_sync_cli import __version__
from obsidian_sync_cli.commands.auth import app as auth_app
from obsidian_sync_cli.commands.sync import app as sync_app
from obsidian_sync_cli.commands.watch import watch
from obsidian_sync_cli.commands.status import status

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


# Register sub-commands
app.add_typer(auth_app, name="auth", help="Authentication commands")
app.add_typer(sync_app, name="vault", help="Vault sync commands")
app.command(name="watch")(watch)
app.command(name="status")(status)

# Top-level shortcuts
app.command(name="login")(auth_app.registered_commands[0].callback)  # type: ignore[arg-type]
app.command(name="pull")(sync_app.registered_commands[0].callback)  # type: ignore[arg-type]
app.command(name="push")(sync_app.registered_commands[1].callback)  # type: ignore[arg-type]
app.command(name="sync")(sync_app.registered_commands[2].callback)  # type: ignore[arg-type]
