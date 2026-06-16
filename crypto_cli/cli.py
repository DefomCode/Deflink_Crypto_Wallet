import typer
from rich.console import Console
from rich.prompt import Prompt
from crypto_cli.storage.crypto_vault import create_wallet, import_wallet


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

@app.command()
def import_key(
    name: str = typer.Option(..., prompt="Имя кошелька", help="Локальный алиас"),
):
    """Импортировать существующий приватный ключ (офлайн-валидация)."""
    pk = Prompt.ask("Приватный ключ (0x...)", password=True)
    password = Prompt.ask("Пароль для шифрования", password=True)
    confirm = Prompt.ask("Подтвердите пароль", password=True)
    
    if password != confirm:
        console.print("[bold red]❌ Пароли не совпадают![/]")
        raise typer.Exit(code=1)
        
    try:
        address = import_wallet(name, pk, password)
        console.print(f"[bold green]✓ Кошелек '{name}' импортирован![/]")
        console.print(f"Адрес: [cyan]{address}[/]")
    except ValueError as e:
        console.print(f"[bold red]Ошибка: {e}[/]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Неизвестная ошибка: {e}[/]")
        raise typer.Exit(code=1)
