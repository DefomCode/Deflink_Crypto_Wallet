import typer
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from crypto_cli.storage.crypto_vault import create_wallet, import_wallet, list_wallets, decrypt_private_key, rename_wallet
from crypto_cli.core.eth import get_eth_balance, prepare_transaction, estimate_tx_cost
from crypto_cli.utils.api import get_eth_usd_price


app = typer.Typer(help="DefLink Crypto Wallet (DCW) — автономный менеджер холодных крипто-кошельков")
console = Console()

@app.command()
def create(
    name: str = typer.Argument(None, help="Имя нового кошелька. Если не указано — спросит интерактивно"),
):
    """Создать новый холодный кошелек с шифрованием AES-256."""
    if name is None:
        name = Prompt.ask("Имя кошелька")
        
    password = Prompt.ask("Пароль", password=True)
    confirm = Prompt.ask("Подтвердите пароль", password=True)
    
    if password != confirm:
        console.print("[bold red]❌ Пароли не совпадают![/]")
        raise typer.Exit(code=1)
        
    try:
        address = create_wallet(name, password)
        console.print(f"[bold green]✓ Кошелек '{name}' успешно создан![/]")
        console.print(f"Адрес: [cyan]{address}[/]")
    except ValueError as e:
        console.print(f"[bold red]Ошибка: {e}[/]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Ошибка: {e}[/]")
        raise typer.Exit(code=1)

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Запуск без команды — заглушка для будущего TUI."""
    if ctx.invoked_subcommand is None:
        console.print("[yellow]TUI скоро будет. Используйте 'dcw --help' для списка команд.[/]")

@app.command()
def rename(
    old_name: str = typer.Argument(None, help="Текущее имя кошелька"),
    new_name: str = typer.Argument(None, help="Новое имя кошелька"),
):
    """Переименовать кошелек. Без аргументов — интерактивный режим со списком."""
    wallets = list_wallets()
    
    if not wallets:
        console.print("[yellow]Кошельки не найдены. Сначала создайте или импортируйте кошелек.[/]")
        raise typer.Exit()

    # === ИНТЕРАКТИВНЫЙ РЕЖИМ ===
    if old_name is None:
        # Показываем список сразу
        table = Table(title="📋 Ваши кошельки", show_header=True, header_style="bold cyan")
        table.add_column("Имя", style="green")
        table.add_column("Адрес", style="dim")
        for n, addr in wallets.items():
            table.add_row(n, addr)
        console.print(table)
        console.print()
        
        old_name = Prompt.ask("Введите имя кошелька для переименования")
        
        if old_name not in wallets:
            console.print(f"[bold red]❌ Кошелек '{old_name}' не найден.[/]")
            raise typer.Exit(code=1)
            
        # Подтверждение выбора
        console.print(f"\nВы переименовываете: [bold green]{old_name}[/] ({wallets[old_name][:10]}...)")
        new_name = Prompt.ask("Новое название")
        
    # === ONE-LINER РЕЖИМ (проверка если new_name не передан) ===
    elif new_name is None:
        if old_name not in wallets:
            console.print(f"[bold red]❌ Кошелек '{old_name}' не найден.[/]")
            raise typer.Exit(code=1)
        console.print(f"Вы переименовываете: [bold green]{old_name}[/]")
        new_name = Prompt.ask("Новое название")

    # === ОБЩАЯ ЛОГИКА ===
    try:
        rename_wallet(old_name, new_name)
        console.print(f"[bold green]✓ Кошелек '{old_name}' переименован в '{new_name}'[/]")
    except ValueError as e:
        console.print(f"[bold red]Ошибка: {e}[/]")
        raise typer.Exit(code=1)

@app.command()
def import_key(
    name: str = typer.Option(..., prompt="Имя кошелька", help="Локальный алиас для импортируемого кошелька"),
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
        console.print(f"[bold green]✓ Кошелек '{name}' успешно импортирован![/]")
        console.print(f"Адрес: [cyan]{address}[/]")
    except ValueError as e:
        console.print(f"[bold red]Ошибка: {e}[/]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Неизвестная ошибка: {e}[/]")
        raise typer.Exit(code=1)

@app.command(name="list")
def show_wallets():
    """Показать список всех сохраненных кошельков."""
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

@app.command()
def balance(
    name: str = typer.Argument(None, help="Имя кошелька. Если не указано — спросит интерактивно"),
):
    """Проверить баланс кошелька в ETH и USD."""
    wallets = list_wallets()
    
    if name is None:
        name = Prompt.ask("Имя кошелька")
        
    if name not in wallets:
        console.print(f"[bold red]❌ Кошелек '{name}' не найден. Используйте 'dcw list'.[/]")
        raise typer.Exit(code=1)
        
    address = wallets[name]
    console.print(f"[cyan]⏳ Запрос баланса для {address}...[/]")
    
    eth_balance = get_eth_balance(address)
    usd_price = get_eth_usd_price() if eth_balance is not None else None
    
    if eth_balance is None:
        console.print("[bold yellow]⚠ Не удалось получить баланс (нет сети или RPC недоступен)[/]")
        console.print(f"Баланс: [white]? ETH ($ -- )[/]")
    else:
        if usd_price is not None:
            usd_value = eth_balance * usd_price
            console.print(f"Баланс: [bold green]{eth_balance:.6f} ETH[/] ([cyan]${usd_value:,.2f}[/])")
        else:
            console.print(f"Баланс: [bold green]{eth_balance:.6f} ETH[/] ([yellow]$ -- [/])")

@app.command()
def pay(
    from_name: str = typer.Argument(..., help="Имя кошелька-отправителя"),
    to_address: str = typer.Argument(..., help="Адрес получателя (0x...)"),
    amount: float = typer.Argument(..., help="Сумма в ETH"),
):
    """Подготовить перевод ETH (экран подтверждения)."""
    wallets = list_wallets()
    
    if from_name not in wallets:
        console.print(f"[bold red]❌ Кошелек '{from_name}' не найден.[/]")
        raise typer.Exit(code=1)
        
    # 1. Запрос пароля и расшифровка
    password = Prompt.ask("Пароль от кошелька", password=True)
    private_key = decrypt_private_key(from_name, password)
    
    if private_key is None:
        console.print("[bold red]❌ Неверный пароль или кошелек не существует.[/]")
        raise typer.Exit(code=1)
        
    # 2. Подготовка транзакции
    console.print("[cyan]⏳ Расчет комиссии и проверка сети...[/]")
    tx = prepare_transaction(wallets[from_name], to_address, amount)
    
    if tx is None:
        console.print("[bold red]❌ Не удалось подготовить транзакцию (нет сети или RPC недоступен).[/]")
        raise typer.Exit(code=1)
        
    # 3. Экран подтверждения (ИСПРАВЛЕННЫЙ)
    fee = estimate_tx_cost(tx)
    usd_price = get_eth_usd_price()
    
    total_eth = amount + fee
    
    # Форматируем USD строки
    def fmt_usd(eth_val):
        return f"(${eth_val * usd_price:,.2f})" if usd_price else ""
    
    console.print("\n[bold cyan]📋 Подтверждение транзакции[/]")
    console.print(f"  Отправитель: [green]{from_name}[/]")
    console.print(f"               [dim]{wallets[from_name]}[/]")
    console.print(f"  Получатель:  [white]{to_address}[/]")
    console.print(f"  Сумма:       [bold]{amount:.6f} ETH[/] {fmt_usd(amount)}")
    console.print(f"  Комиссия:    [yellow]{fee:.6f} ETH[/] {fmt_usd(fee)}")
    console.print(f"  ─────────────────────────────")
    console.print(f"  Итого:       [bold green]{total_eth:.6f} ETH[/] {fmt_usd(total_eth)}\n")
    
    # Безопасное подтверждение с явным (y/N)
    confirm = Prompt.ask(
        "[bold]Подтвердить отправку?[/] [dim](y/N)[/]",
        default="N",
        show_default=False
    )
    
    if confirm.lower() != 'y':
        console.print("[yellow]Отменено пользователем.[/]")
        raise typer.Exit()
        
    # TODO: Здесь будет подпись и отправка (Задача 3.2)
    console.print("[yellow]⚠ Подпись и отправка пока не реализованы. Транзакция подготовлена успешно.[/]")
