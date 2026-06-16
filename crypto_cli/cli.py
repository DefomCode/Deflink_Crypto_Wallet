import typer
from web3 import Web3
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from crypto_cli.storage.crypto_vault import create_wallet, import_wallet, list_wallets, decrypt_private_key, rename_wallet, delete_wallet
from crypto_cli.core.eth import get_eth_balance, prepare_transaction, estimate_tx_cost, sign_and_send_transaction, wait_for_receipt
from crypto_cli.utils.api import get_eth_usd_price

MIN_RESERVE_ETH = 0.0003

app = typer.Typer(help="DefLink Crypto Wallet (DCW) — автономный менеджер холодных крипто-кошельков")
console = Console()

@app.command()
def create(
    name: str = typer.Argument(None, help="Имя нового кошелька"),
):
    """Создать новый холодный кошелек с шифрованием AES-256."""
    wallets = list_wallets()
    
    # === ИНТЕРАКТИВНЫЙ РЕЖИМ ===
    if name is None:
        if wallets:
            table = Table(title="📋 Существующие кошельки", show_header=True, header_style="bold cyan")
            table.add_column("Имя", style="green")
            table.add_column("Адрес", style="dim")
            for n, addr in wallets.items():
                table.add_row(n, addr)
            console.print(table)
            console.print()
        
        name = Prompt.ask("Придумайте имя для нового кошелька")
        
        # Проверка на дубликат сразу в интерактиве
        if name in wallets:
            console.print(f"[bold red]❌ Имя '{name}' уже занято. Попробуйте другое.[/]")
            raise typer.Exit(code=1)
            
        console.print(f"\nСоздаем кошелек: [bold green]{name}[/]")

    # === ONE-LINER РЕЖИМ (проверка дубликата) ===
    else:
        if name in wallets:
            console.print(f"[bold red]❌ Кошелек '{name}' уже существует. Используйте 'dcw rename' или другое имя.[/]")
            raise typer.Exit(code=1)

    # === ОБЩАЯ ЛОГИКА ===
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
def delete(
    name: str = typer.Argument(None, help="Имя кошелька для удаления"),
):
    """Удалить кошелек из хранилища (требуется подтверждение именем)."""
    wallets = list_wallets()
    
    if not wallets:
        console.print("[yellow]Кошельки не найдены.[/]")
        raise typer.Exit()

    # === ИНТЕРАКТИВНЫЙ РЕЖИМ ===
    if name is None:
        table = Table(title="📋 Ваши кошельки", show_header=True, header_style="bold cyan")
        table.add_column("Имя", style="green")
        table.add_column("Адрес", style="dim")
        for n, addr in wallets.items():
            table.add_row(n, addr)
        console.print(table)
        console.print()
        
        name = Prompt.ask("Введите имя кошелька для удаления")
        
        if name not in wallets:
            console.print(f"[bold red]❌ Кошелек '{name}' не найден.[/]")
            raise typer.Exit(code=1)

    # === ОБЩАЯ ЛОГИКА ПОДТВЕРЖДЕНИЯ ===
    if name not in wallets:
        console.print(f"[bold red]❌ Кошелек '{name}' не найден.[/]")
        raise typer.Exit(code=1)

    console.print(f"\n[bold red]⚠ ВЫ УДАЛЯЕТЕ КОШЕЛЕК: {name}[/]")
    console.print(f"[red]Адрес: {wallets[name]}[/]")
    console.print("[yellow]Это действие необратимо. Приватный ключ будет удален навсегда.[/]\n")
    
    confirm_name = Prompt.ask(f"[bold]Для подтверждения введите имя кошелька ({name})[/]")
    
    if confirm_name != name:
        console.print("[bold red]❌ Имя не совпало. Удаление отменено.[/]")
        raise typer.Exit(code=1)
        
    try:
        delete_wallet(name)
        console.print(f"[bold green]✓ Кошелек '{name}' успешно удален.[/]")
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
    from_name: str = typer.Argument(None, help="Имя кошелька-отправителя"),
    to_address: str = typer.Argument(None, help="Адрес получателя (0x...)"),
    amount: float = typer.Argument(None, help="Сумма в ETH"),
):
    """Перевод ETH с гибридным UX (0-3 аргумента)."""
    wallets = list_wallets()
    
    if not wallets:
        console.print("[yellow]Кошельки не найдены. Сначала создайте или импортируйте.[/]")
        raise typer.Exit()

    # === ИНТЕРАКТИВНЫЙ ВЫБОР ОТПРАВИТЕЛЯ ===
    if from_name is None:
        table = Table(title="📋 Выберите кошелек-отправитель", show_header=True, header_style="bold cyan")
        table.add_column("Имя", style="green")
        table.add_column("Адрес", style="dim")
        for n, addr in wallets.items():
            table.add_row(n, addr)
        console.print(table)
        console.print()
        from_name = Prompt.ask("Отправитель")
        
    if from_name not in wallets:
        console.print(f"[bold red]❌ Кошелек '{from_name}' не найден.[/]")
        raise typer.Exit(code=1)

    # === ИНТЕРАКТИВНЫЙ ВВОД ПОЛУЧАТЕЛЯ ===
    if to_address is None:
        to_address = Prompt.ask("Адрес получателя (0x...)")

    # === ИНТЕРАКТИВНЫЙ ВВОД СУММЫ ===
    if amount is None:
        amount_str = Prompt.ask("Сумма (ETH)")
        try:
            amount = float(amount_str)
        except ValueError:
            console.print("[bold red]❌ Некорректная сумма.[/]")
            raise typer.Exit(code=1)

    # === ОБЩАЯ ЛОГИКА (пароль, подготовка, подтверждение, отправка) ===
    password = Prompt.ask("Пароль от кошелька", password=True)
    private_key = decrypt_private_key(from_name, password)
    
    if private_key is None:
        console.print("[bold red]❌ Неверный пароль или кошелек не существует.[/]")
        raise typer.Exit(code=1)
        
    console.print("[cyan]⏳ Расчет комиссии и проверка сети...[/]")
    
    current_balance = None
    tx = None
    try:
        current_balance = get_eth_balance(wallets[from_name])
        tx = prepare_transaction(wallets[from_name], to_address, amount)
    except Exception as e:
        console.print(f"[bold red]Ошибка подготовки: {e}[/]")
        raise typer.Exit(code=1)
    
    if tx is None:
        console.print("[bold red]❌ Не удалось подготовить транзакцию (нет сети или RPC недоступен).[/]")
        raise typer.Exit(code=1)
        
    fee = estimate_tx_cost(tx)
    usd_price = get_eth_usd_price()
    total_eth = amount + fee
    remaining_eth = (current_balance - total_eth) if current_balance is not None else None
    
    def fmt_usd(eth_val):
        if eth_val is None or usd_price is None:
            return ""
        return f"(${eth_val * usd_price:,.2f})"
    
    def fmt_eth(eth_val):
        if eth_val is None:
            return "[dim]? ETH[/]"
        return f"{eth_val:.6f} ETH"

    console.print("\n[bold cyan]📋 Подтверждение транзакции[/]")
    console.print(f"  Отправитель: [green]{from_name}[/]")
    console.print(f"               [dim]{wallets[from_name]}[/]")
    console.print(f"  Получатель:  [white]{to_address}[/]")
    console.print(f"  Сумма:       [bold]{amount:.6f} ETH[/] {fmt_usd(amount)}")
    console.print(f"  Комиссия:    [yellow]{fee:.6f} ETH[/] {fmt_usd(fee)}")
    console.print(f"  ─────────────────────────────")
    console.print(f"  Текущий баланс: [white]{fmt_eth(current_balance)}[/] {fmt_usd(current_balance)}")
    console.print(f"  Итого спишется: [bold]-{total_eth:.6f} ETH[/] {fmt_usd(total_eth)}")
    
    if remaining_eth is not None:
        color = "green" if remaining_eth >= MIN_RESERVE_ETH else "red"
        console.print(f"  Останется:     [{color}]{remaining_eth:.6f} ETH[/] {fmt_usd(remaining_eth)}")
    else:
        console.print(f"  Останется:     [dim]? ETH (не удалось получить баланс)[/]")
    console.print()
    
    if current_balance is not None:
        if total_eth > current_balance:
            console.print("[bold red]❌ Недостаточно средств![/]")
            raise typer.Exit(code=1)
        if remaining_eth < MIN_RESERVE_ETH:
            console.print(f"[bold red]❌ Нельзя отправить всю сумму! Резерв ≥ {MIN_RESERVE_ETH} ETH.[/]")
            console.print(f"[yellow]Максимум: {current_balance - fee - MIN_RESERVE_ETH:.6f} ETH[/]")
            raise typer.Exit(code=1)

    confirm = Prompt.ask("[bold]Подтвердить отправку?[/] [dim](y/N)[/]", default="N", show_default=False)
    
    if confirm.lower() != 'y':
        console.print("[yellow]Отменено пользователем.[/]")
        raise typer.Exit()
        
    console.print("[cyan]⏳ Подписание и отправка...[/]")
    
    tx_hash = None
    try:
        tx_hash = sign_and_send_transaction(private_key, tx)
    except Exception as e:
        console.print(f"[bold red]❌ Критическая ошибка отправки: {e}[/]")
        raise typer.Exit(code=1)
    finally:
        del private_key
    
    if tx_hash is None:
        console.print("[bold red]❌ Ошибка отправки. Проверьте баланс или соединение.[/]")
        raise typer.Exit(code=1)
        
    etherscan_link = f"https://etherscan.io/tx/{tx_hash}"
    console.print(f"[bold green]✓ Транзакция отправлена![/]")
    console.print(f"Хеш: [link={etherscan_link}]{tx_hash}[/link]")
    
    # === ЭКРАН ОЖИДАНИЯ (Задача 3.3) ===
    receipt = None
    interrupted = False
    try:
        with console.status("[bold cyan]⏳ Ожидание подтверждения...", spinner="dots"):
            receipt = wait_for_receipt(tx_hash)
    except KeyboardInterrupt:
        interrupted = True

    # Вывод результата ВСЕГДА после спиннера
    if interrupted:
        console.print("\n[yellow]⚠ Ожидание прервано. Транзакция уже в сети![/]")
        console.print(f"Статус: [link={etherscan_link}]{etherscan_link}[/link]")
    elif receipt is None:
        console.print("[yellow]⚠ Таймаут ожидания. Транзакция может быть еще в обработке.[/]")
        console.print(f"Статус: [link={etherscan_link}]{etherscan_link}[/link]")
    elif receipt.status == 1:
        gas_used = receipt.gasUsed
        effective_fee = float(Web3.from_wei(gas_used * tx['gasPrice'], 'ether'))
        console.print(f"[bold green]✓ Подтверждена! Блок #{receipt.blockNumber}[/]")
        console.print(f"  Факт. комиссия: [yellow]{effective_fee:.6f} ETH[/]")
    else:
        console.print("[bold red]❌ Транзакция упала (Reverted). Средства на месте, газ списан.[/]")
        console.print(f"  Потрачено газа: [yellow]{receipt.gasUsed} units[/]")
        console.print(f"  Детали: [link={etherscan_link}]{etherscan_link}[/link]")
