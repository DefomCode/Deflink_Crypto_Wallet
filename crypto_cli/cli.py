import typer
from web3 import Web3
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from crypto_cli.storage.crypto_vault import create_wallet, import_wallet, list_wallets, decrypt_private_key, rename_wallet, delete_wallet
from crypto_cli.core.eth import get_eth_balance, prepare_transaction, estimate_tx_cost, sign_and_send_transaction, wait_for_receipt
from crypto_cli.core.eth_adapter import EthAdapter
from crypto_cli.utils.api import get_eth_usd_price
from crypto_cli.storage.db import add_transaction, update_wallet_cache, get_pending_transactions, update_transaction_status, get_all_transactions, get_transaction_by_hash, count_transactions, get_connection, get_wallet_caches 

MIN_RESERVE_ETH = 0.0003

adapter = EthAdapter()

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
    """Показать список кошельков с последним известным балансом."""
    wallets = list_wallets()
    
    if not wallets:
        console.print("[yellow]Кошельки не найдены. Используйте 'dcw create' или 'dcw import-key'.[/]")
        raise typer.Exit()

    caches = get_wallet_caches()
    
    table = Table(title="💰 Ваши кошельки", show_header=True, header_style="bold cyan")
    table.add_column("Имя", style="green", no_wrap=True)
    table.add_column("Адрес (ETH)", style="white")
    table.add_column("Баланс", justify="right")
    table.add_column("Обновлён", style="dim", justify="right")

    for name, address in wallets.items():
        cache = caches.get(address)
        
        if cache and cache["balance_eth"] is not None:
            bal_str = f"{cache['balance_eth']:.6f} ETH"
            if cache["balance_usd"] is not None:
                bal_str += f" (${cache['balance_usd']:,.2f})"
            updated_str = cache["updated_at"][:16]
        else:
            bal_str = "[dim]--[/]"
            updated_str = "[dim]никогда[/]"
            
        table.add_row(name, address, bal_str, updated_str)
        
    console.print(table)
    console.print("\n[dim]💡 Балансы обновляются при 'dcw balance' и 'dcw pay'. Для принудительного обновления: dcw balance <имя>[/]")

@app.command()
def balance(
    name: str = typer.Argument(None, help="Имя кошелька. Если не указано — спросит интерактивно"),
):
    """Проверить баланс кошелька в нативной валюте и USD."""
    wallets = list_wallets()

    if name is None:
        name = Prompt.ask("Имя кошелька")

    if name not in wallets:
        console.print(f"[bold red]❌ Кошелек '{name}' не найден. Используйте 'dcw list'.[/]")
        raise typer.Exit(code=1)

    address = wallets[name]
    symbol = adapter.currency_symbol
    console.print(f"[cyan]⏳ Запрос баланса для {address}...[/]")

    coin_balance = adapter.get_balance(address)
    usd_price = get_eth_usd_price() if coin_balance is not None else None

    if coin_balance is None:
        console.print("[bold yellow]⚠ Не удалось получить баланс (нет сети или RPC недоступен)[/]")
        console.print(f"Баланс: [white]? {symbol} ($ -- )[/]")
    else:
        try:
            update_wallet_cache(name, address, coin_balance, coin_balance * usd_price if usd_price else None)
        except Exception:
            pass

        if usd_price is not None:
            usd_value = coin_balance * usd_price
            console.print(f"Баланс: [bold green]{coin_balance:.6f} {symbol}[/] ([cyan]${usd_value:,.2f}[/])")
        else:
            console.print(f"Баланс: [bold green]{coin_balance:.6f} {symbol}[/] ([yellow]$ -- [/])")
# === Блок команды оплаты ===

@app.command()
def pay(
    from_name: str = typer.Argument(None, help="Имя кошелька-отправителя"),
    to_address: str = typer.Argument(None, help="Адрес получателя"),
    amount: float = typer.Argument(None, help="Сумма"),
):
    """Перевод средств с гибридным UX (0-3 аргумента)."""
    wallets = list_wallets()
    symbol = adapter.currency_symbol
    explorer = adapter.explorer_url

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
        to_address = Prompt.ask("Адрес получателя")

    # === ИНТЕРАКТИВНЫЙ ВВОД СУММЫ ===
    if amount is None:
        amount_str = Prompt.ask(f"Сумма ({symbol})")
        try:
            amount = float(amount_str)
        except ValueError:
            console.print("[bold red]❌ Некорректная сумма.[/]")
            raise typer.Exit(code=1)

    # === ОБЩАЯ ЛОГИКА ===
    password = Prompt.ask("Пароль от кошелька", password=True)
    private_key = decrypt_private_key(from_name, password)

    if private_key is None:
        console.print("[bold red]❌ Неверный пароль или кошелек не существует.[/]")
        raise typer.Exit(code=1)

    console.print("[cyan]⏳ Расчет комиссии и проверка сети...[/]")

    current_balance = None
    tx = None
    try:
        current_balance = adapter.get_balance(wallets[from_name])
        tx = adapter.prepare_transaction(wallets[from_name], to_address, amount)
    except Exception as e:
        console.print(f"[bold red]Ошибка подготовки: {e}[/]")
        raise typer.Exit(code=1)

    if tx is None:
        console.print("[bold red]❌ Не удалось подготовить транзакцию (нет сети или RPC недоступен).[/]")
        raise typer.Exit(code=1)

    fee = adapter.estimate_tx_cost(tx)
    usd_price = get_eth_usd_price()
    total_coin = amount + fee
    remaining = (current_balance - total_coin) if current_balance is not None else None

    def fmt_usd(val):
        if val is None or usd_price is None:
            return ""
        return f"(${val * usd_price:,.2f})"

    def fmt_coin(val):
        if val is None:
            return f"[dim]? {symbol}[/]"
        return f"{val:.6f} {symbol}"

    console.print(f"\n[bold cyan]📋 Подтверждение транзакции[/]")
    console.print(f"  Отправитель: [green]{from_name}[/]")
    console.print(f"               [dim]{wallets[from_name]}[/]")
    console.print(f"  Получатель:  [white]{to_address}[/]")
    console.print(f"  Сумма:       [bold]{amount:.6f} {symbol}[/] {fmt_usd(amount)}")
    console.print(f"  Комиссия:    [yellow]{fee:.6f} {symbol}[/] {fmt_usd(fee)}")
    console.print(f"  ─────────────────────────────")
    console.print(f"  Текущий баланс: [white]{fmt_coin(current_balance)}[/] {fmt_usd(current_balance)}")
    console.print(f"  Итого спишется: [bold]-{total_coin:.6f} {symbol}[/] {fmt_usd(total_coin)}")

    if remaining is not None:
        color = "green" if remaining >= MIN_RESERVE_ETH else "red"
        console.print(f"  Останется:     [{color}]{remaining:.6f} {symbol}[/] {fmt_usd(remaining)}")
    else:
        console.print(f"  Останется:     [dim]? {symbol} (не удалось получить баланс)[/]")
    console.print()

    if current_balance is not None:
        if total_coin > current_balance:
            console.print("[bold red]❌ Недостаточно средств![/]")
            raise typer.Exit(code=1)
        if remaining < MIN_RESERVE_ETH:
            console.print(f"[bold red]❌ Нельзя отправить всю сумму! Резерв ≥ {MIN_RESERVE_ETH} {symbol}.[/]")
            console.print(f"[yellow]Максимум: {current_balance - fee - MIN_RESERVE_ETH:.6f} {symbol}[/]")
            raise typer.Exit(code=1)

    confirm = Prompt.ask("[bold]Подтвердить отправку?[/] [dim](y/N)[/]", default="N", show_default=False)

    if confirm.lower() != 'y':
        console.print("[yellow]Отменено пользователем.[/]")
        raise typer.Exit()

    console.print("[cyan]⏳ Подписание и отправка...[/]")

    tx_hash = None
    try:
        tx_hash = adapter.sign_and_send(private_key, tx)
    except Exception as e:
        console.print(f"[bold red]❌ Критическая ошибка отправки: {e}[/]")
        raise typer.Exit(code=1)
    finally:
        del private_key

    if tx_hash is None:
        console.print("[bold red]❌ Ошибка отправки. Проверьте баланс или соединение.[/]")
        raise typer.Exit(code=1)

    # === ЗАПИСЬ В ИСТОРИЮ ===
    try:
        add_transaction(tx_hash, from_name, to_address, amount, fee)
    except Exception as e:
        console.print(f"[yellow]⚠ Не удалось сохранить в историю: {e}[/]")

    tx_link = f"{explorer}/tx/{tx_hash}"
    console.print(f"[bold green]✓ Транзакция отправлена![/]")
    console.print(f"Хеш: [link={tx_link}]{tx_hash}[/link]")

    # Обновляем кэш баланса
    if current_balance is not None and usd_price is not None:
        try:
            new_balance = current_balance - total_coin
            update_wallet_cache(from_name, wallets[from_name], new_balance, new_balance * usd_price)
        except Exception:
            pass

    # === ЭКРАН ОЖИДАНИЯ ===
    receipt = None
    interrupted = False
    try:
        with console.status("[bold cyan]⏳ Ожидание подтверждения...", spinner="dots"):
            receipt = adapter.wait_for_receipt(tx_hash)
    except KeyboardInterrupt:
        interrupted = True

    if interrupted:
        console.print("\n[yellow]⚠ Ожидание прервано. Транзакция уже в сети![/]")
        console.print(f"Статус: [link={tx_link}]{tx_link}[/link]")
    elif receipt is None:
        console.print("[yellow]⚠ Таймаут ожидания. Транзакция может быть еще в обработке.[/]")
        console.print(f"Статус: [link={tx_link}]{tx_link}[/link]")
    elif receipt['status'] == 1:
        gas_used = receipt['gas_used']
        effective_fee = float(Web3.from_wei(gas_used * receipt['effective_gas_price'], 'ether'))
        console.print(f"[bold green]✓ Подтверждена! Блок #{receipt['block_number']}[/]")
        console.print(f"  Факт. комиссия: [yellow]{effective_fee:.6f} {symbol}[/]")
    else:
        console.print("[bold red]❌ Транзакция упала (Reverted). Средства на месте, газ списан.[/]")
        console.print(f"  Потрачено газа: [yellow]{receipt['gas_used']} units[/]")
        console.print(f"  Детали: [link={tx_link}]{tx_link}[/link]")

# === Конец блока оплаты ===

# === История транзакций ===
@app.command()
def history(
    wallet_name: str = typer.Argument(None, help="Фильтр по кошельку"),
    page: int = typer.Option(1, "--page", "-p", help="Номер страницы"),
    limit: int = typer.Option(15, "--limit", "-l", help="Записей на странице"),
):
    """История транзакций с пагинацией."""
    # Автообновление pending
    pending_hashes = get_pending_transactions()
    if pending_hashes:
        console.print(f"[cyan]⏳ Проверка {len(pending_hashes)} pending...[/]")
        for tx_hash in pending_hashes:
            receipt = wait_for_receipt(tx_hash, timeout=10, poll_interval=2)
            if receipt is not None:
                if receipt.status == 1:
                    effective_fee = float(Web3.from_wei(receipt.gasUsed * receipt.effectiveGasPrice, 'ether'))
                    update_transaction_status(tx_hash, 'success', receipt.blockNumber, effective_fee)
                else:
                    update_transaction_status(tx_hash, 'failed', receipt.blockNumber, error_msg='Reverted')

    offset = (page - 1) * limit
    txs = get_all_transactions(wallet_name, limit=limit, offset=offset)
    total = count_transactions(wallet_name)
    total_pages = max(1, (total + limit - 1) // limit)

    if not txs:
        console.print("[yellow]Транзакции не найдены.[/]")
        raise typer.Exit()

    # show_lines=True добавляет горизонтальные разделители между строками
    table = Table(
        title=f"📜 История (стр. {page}/{total_pages}, всего {total})",
        show_header=True,
        header_style="bold cyan",
        show_lines=True
    )
    table.add_column("Дата", style="dim", no_wrap=True)
    table.add_column("Кошелек", style="green")
    table.add_column("Куда", style="white")
    table.add_column("Сумма", justify="right")
    table.add_column("Комиссия", justify="right")
    table.add_column("Статус", justify="center")
    table.add_column("Хеш (Первые 16)", style="cyan", no_wrap=True)  # Короткий хеш вместо блока

    status_styles = {
        'success': '[bold green]✓ Success[/]',
        'pending': '[bold yellow]⏳ Pending[/]',
        'failed': '[bold red]✗ Failed[/]',
    }

    for tx in txs:
        date_str = tx['created_at'][:16]
        to_short = tx['to_address'][:8] + '...' + tx['to_address'][-6:]
        status = status_styles.get(tx['status'], tx['status'])
        hash_short = tx['tx_hash'][:16]
        fee = f"{tx['fee_eth']:.6f}" if tx['fee_eth'] else '--'

        table.add_row(date_str, tx['from_name'], to_short, f"{tx['amount_eth']:.6f}", fee, status, hash_short)

    console.print(table)
    console.print("\n[dim]💡 Детали транзакции: dcw tx <часть_хеша>[/]")
    if page < total_pages:
        next_cmd = f"dcw history --page {page + 1}"
        if wallet_name:
            next_cmd += f" {wallet_name}"
        console.print(f"\n[dim]Следующая страница: {next_cmd}[/]")

# === Получение ссылки транзакции из хеша  ===
@app.command()
def tx(
    tx_hash: str = typer.Argument(..., help="Полный или частичный хеш транзакции"),
):
    """Показать детали транзакции и ссылку на Etherscan."""
    from crypto_cli.storage.db import get_connection
    
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM transactions WHERE tx_hash LIKE ?", (f"%{tx_hash}%",)
    ).fetchone()
    conn.close()
    
    if not row:
        console.print(f"[bold red]❌ Транзакция '{tx_hash}' не найдена.[/]")
        raise typer.Exit(code=1)
    
    tx_data = dict(row)
    link = f"https://etherscan.io/tx/{tx_data['tx_hash']}"
    
    console.print(f"\n[bold cyan]Детали транзакции[/]")
    console.print(f"  Хеш:       [link={link}]{tx_data['tx_hash']}[/link]")
    console.print(f"  Статус:    {tx_data['status']}")
    console.print(f"  Отправитель: {tx_data['from_name']}")
    console.print(f"  Получатель:  {tx_data['to_address']}")
    console.print(f"  Сумма:     {tx_data['amount_eth']:.6f} ETH")
    console.print(f"  Комиссия:  {tx_data['fee_eth']:.6f} ETH" if tx_data['fee_eth'] else "  Комиссия:  --")
    console.print(f"  Блок:      #{tx_data['block_number']}" if tx_data['block_number'] else "  Блок:      Pending")
    console.print(f"  Дата:      {tx_data['created_at']}")
    console.print(f"\n  🔗 [link={link}]{link}[/link]\n")
