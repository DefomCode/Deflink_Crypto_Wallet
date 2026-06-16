import typer
from rich.console import Console
from rich.prompt import Prompt
from crypto_cli.storage.crypto_vault import create_wallet

app = typer.Typer(help="DefLink Crypto Wallet (DCW)")
console = Console()

@app.command()
def create(
    name: str = typer.Option(..., prompt="Wallet name (e.g. main)", help="Local alias for the wallet"),
):
    """Create a new cold wallet with AES-256 encryption."""
    password = Prompt.ask("Password", password=True)
    confirm = Prompt.ask("Confirm password", password=True)
    
    if password != confirm:
        console.print("[bold red]Passwords do not match![/]")
        raise typer.Exit(code=1)
        
    try:
        address = create_wallet(name, password)
        console.print(f"[bold green]✓ Wallet '{name}' created successfully![/]")
        console.print(f"Address: [cyan]{address}[/]")
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/]")
        raise typer.Exit(code=1)

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """If no command is passed, launch TUI (placeholder for now)."""
    if ctx.invoked_subcommand is None:
        console.print("[yellow]TUI mode coming soon. Use 'dcw --help' for commands.[/]")
