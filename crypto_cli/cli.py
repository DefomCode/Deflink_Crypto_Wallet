import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from crypto_cli.storage.crypto_vault import create_wallet, import_wallet, list_wallets

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

@app.command(name="list")
def show_wallets():
    """Показать все сохраненные кошельки."""
    wallets = list_wallets()
    
    if not wallets:
        console.print("[yellow]Кошельки не найдены. Используйте 'dcw create' или 'dcw import-key'.[/]")
        raise typer.Exit()

    table = Table(title="💰 Ваши кошельки", show_header=True, header_style="bold cyan")
    table.add_column("Имя", style="green", no_wrap=True)
    table.add_column("Адрес (ETH)", style="white")
    
    for name, address in wallets.items():
        table.add_row(name, address)
        
    console.print(table)
