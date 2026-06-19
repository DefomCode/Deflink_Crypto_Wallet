import typer
from web3 import Web3
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from crypto_cli.storage.crypto_vault import create_wallet, import_wallet, list_wallets, decrypt_private_key, rename_wallet, delete_wallet, get_wallet_info
from crypto_cli.core.eth_adapter import EthAdapter
from crypto_cli.core.tron_adapter import TronAdapter
from crypto_cli.utils.api import get_eth_usd_price, get_trx_usd_price
from crypto_cli.storage.db import (
    add_transaction, update_wallet_cache, get_pending_transactions,
    update_transaction_status, get_all_transactions, get_transaction_by_hash,
    count_transactions, get_wallet_caches,
)

MIN_RESERVE_ETH = 0.0003
MIN_RESERVE_TRX = 1.0  # Резерв для TRX

app = typer.Typer(help="DefLink Crypto Wallet (DCW) — автономный менеджер холодных крипто-кошельков")
console = Console()

# Кэш адаптеров, чтобы не создавать их каждый раз
_adapters = {}

def get_adapter(network_type: str):
    """Возвращает экземпляр адаптера для указанной сети."""
    if network_type not in _adapters:
        if network_type == "ETH":
            _adapters[network_type] = EthAdapter()
        elif network_type == "TRX":
            _adapters[network_type] = TronAdapter()
        else:
            raise ValueError(f"Неподдерживаемая сеть: {network_type}")
    return _adapters[network_type]


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Запуск без команды — заглушка для будущего TUI."""
    if ctx.invoked_subcommand is None:
        console.print("[yellow]TUI скоро будет. Используйте 'dcw --help' для списка команд.[/]")


def _complete_wallet_names(incomplete: str):
    """Автодополнение имён кошельков для Typer."""
    try:
        wallets = list_wallets()
        return [name for name in wallets if name.startswith(incomplete)]
    except Exception:
        return []

# ==================== КОШЕЛЬКИ ====================

@app.command()
def create(
    name: str = typer.Argument(None, help="Имя нового кошелька"),
    network: str = typer.Option(None, "--net", "-n", help="Сеть: ETH или TRX"),
):
    """Создать новый холодный кошелек с шифрованием AES-256."""
    wallets = list_wallets()

    # === ИНТЕРАКТИВНЫЙ ВЫБОР СЕТИ (если не передан флаг) ===
    if network is None:
        console.print("\n[bold cyan]Выберите сеть:[/]")
        console.print("  [green]1.[/] ETH (Ethereum)")
        console.print("  [green]2.[/] TRX (Tron)")
        choice = Prompt.ask("Сеть", choices=["1", "2", "ETH", "TRX"], default="1")
        network = "ETH" if choice in ["1", "ETH"] else "TRX"
    
    network = network.upper()
    if network not in ["ETH", "TRX"]:
        console.print("[bold red]❌ Поддерживаются только сети ETH и TRX.[/]")
        raise typer.Exit(code=1)

    adapter = get_adapter(network)

    if name is None:
        if wallets:
            table = Table(title="📋 Существующие кошельки", show_header=True, header_style="bold cyan")
            table.add_column("Имя", style="green")
            table.add_column("Сеть", style="dim")
            table.add_column("Адрес", style="dim")
            for n, info in wallets.items():
                net = info.get('network', 'ETH')
                addr = info['address']
                table.add_row(n, net, addr)
            console.print(table)
            console.print()

        name = Prompt.ask("Придумайте имя для нового кошелька")

        if name in wallets:
            console.print(f"[bold red]❌ Имя '{name}' уже занято. Попробуйте другое.[/]")
            raise typer.Exit(code=1)

        console.print(f"\nСоздаем кошелек: [bold green]{name}[/] ({network})")
    else:
        if name in wallets:
            console.print(f"[bold red]❌ Кошелек '{name}' уже существует. Используйте 'dcw rename' или другое имя.[/]")
            raise typer.Exit(code=1)

    password = Prompt.ask("Пароль", password=True)
    confirm = Prompt.ask("Подтвердите пароль", password=True)

    if password != confirm:
        console.print("[bold red]❌ Пароли не совпадают![/]")
        raise typer.Exit(code=1)

    try:
        address = create_wallet(name, password, network_type=network)
        console.print(f"[bold green]✓ Кошелек '{name}' успешно создан![/]")
        console.print(f"Сеть:   [cyan]{network}[/]")
        console.print(f"Адрес:  [cyan]{address}[/]")
    except ValueError as e:
        console.print(f"[bold red]Ошибка: {e}[/]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Ошибка: {e}[/]")
        raise typer.Exit(code=1)

@app.command()
def rename(
    old_name: str = typer.Argument(None, help="Текущее имя кошелька", autocompletion=_complete_wallet_names),
    new_name: str = typer.Argument(None, help="Новое имя кошелька"),
):
    """Переименовать кошелек. Без аргументов — интерактивный режим со списком."""
    wallets = list_wallets()

    if not wallets:
        console.print("[yellow]Кошельки не найдены. Сначала создайте или импортируйте кошелек.[/]")
        raise typer.Exit()

    if old_name is None:
        table = Table(title="📋 Ваши кошельки", show_header=True, header_style="bold cyan")
        table.add_column("Имя", style="green")
        table.add_column("Сеть", style="dim")
        table.add_column("Адрес", style="dim")
        for n, info in wallets.items():
            net = info.get('network', 'ETH')
            addr = info['address']
            table.add_row(n, net, addr)
        console.print(table)
        console.print()

        old_name = Prompt.ask("Введите имя кошелька для переименования")

        if old_name not in wallets:
            console.print(f"[bold red]❌ Кошелек '{old_name}' не найден.[/]")
            raise typer.Exit(code=1)

        console.print(f"\nВы переименовываете: [bold green]{old_name}[/] ({wallets[old_name].get('network', 'ETH')})")
        new_name = Prompt.ask("Новое название")

    elif new_name is None:
        if old_name not in wallets:
            console.print(f"[bold red]❌ Кошелек '{old_name}' не найден.[/]")
            raise typer.Exit(code=1)
        console.print(f"Вы переименовываете: [bold green]{old_name}[/]")
        new_name = Prompt.ask("Новое название")

    try:
        rename_wallet(old_name, new_name)
        console.print(f"[bold green]✓ Кошелек '{old_name}' переименован в '{new_name}'[/]")
    except ValueError as e:
        console.print(f"[bold red]Ошибка: {e}[/]")
        raise typer.Exit(code=1)


@app.command()
def delete(
    names: str = typer.Argument(None, help="Имена кошельков для удаления (через пробел)", autocompletion=_complete_wallet_names),
):
    """Удалить один или несколько кошельков (требуется подтверждение именем)."""
    wallets = list_wallets()

    if not wallets:
        console.print("[yellow]Кошельки не найдены.[/]")
        raise typer.Exit()

    # === ИНТЕРАКТИВНЫЙ РЕЖИМ ===
    if names is None:
        table = Table(title="📋 Ваши кошельки", show_header=True, header_style="bold cyan")
        table.add_column("Имя", style="green")
        table.add_column("Сеть", style="dim")
        table.add_column("Адрес", style="dim")
        for n, info in wallets.items():
            net = info.get('network', 'ETH')
            addr = info['address']
            table.add_row(n, net, addr)
        console.print(table)
        console.print()

        names_str = Prompt.ask("Введите имена кошельков через пробел для удаления")
        name_list = names_str.split()
    else:
        name_list = names.split()

    # === УДАЛЕНИЕ ПО ОЧЕРЕДИ С ПОДТВЕРЖДЕНИЕМ ===
    deleted_count = 0
    for name in name_list:
        if name not in wallets:
            console.print(f"[yellow]⚠ Кошелек '{name}' не найден, пропускаю.[/]")
            continue

        info = wallets[name]
        console.print(f"\n[bold red]⚠ ВЫ УДАЛЯЕТЕ КОШЕЛЕК: {name}[/]")
        console.print(f"[red]Сеть:  {info.get('network', 'ETH')}[/]")
        console.print(f"[red]Адрес: {info['address']}[/]")
        console.print("[yellow]Это действие необратимо. Приватный ключ будет удален навсегда.[/]\n")

        confirm_name = Prompt.ask(f"[bold]Для подтверждения введите имя кошелька ({name})[/]")

        if confirm_name != name:
            console.print(f"[yellow]⚠ Имя не совпало. Удаление '{name}' отменено.[/]")
            continue

        try:
            delete_wallet(name)
            console.print(f"[bold green]✓ Кошелек '{name}' успешно удален.[/]")
            deleted_count += 1
        except ValueError as e:
            console.print(f"[bold red]Ошибка удаления '{name}': {e}[/]")

    if deleted_count > 0:
        console.print(f"\n[bold green]Удалено кошельков: {deleted_count}[/]")
    else:
        console.print("\n[yellow]Ни один кошелек не был удален.[/]")

@app.command(name="import-key")
def import_key(
    name: str = typer.Argument(None, help="Имя кошелька"),
    private_key: str = typer.Option(None, "--key", "-k", help="Приватный ключ"),
    network: str = typer.Option("ETH", "--net", "-n", help="Сеть: ETH или TRX"),
):
    """Импортировать существующий приватный ключ (офлайн-валидация)."""
    wallets = list_wallets()
    network = network.upper()

    if network not in ["ETH", "TRX"]:
        console.print("[bold red]❌ Поддерживаются только сети ETH и TRX.[/]")
        raise typer.Exit(code=1)

    adapter = get_adapter(network)

    if name is None:
        name = Prompt.ask("Имя для кошелька")

    if name in wallets:
        console.print(f"[bold red]❌ Имя '{name}' уже занято.[/]")
        raise typer.Exit(code=1)

    if private_key is None:
        private_key = Prompt.ask("Приватный ключ (hex)", password=True)

    if not adapter.validate_private_key(private_key):
        console.print("[bold red]❌ Невалидный приватный ключ для выбранной сети.[/]")
        raise typer.Exit(code=1)

    password = Prompt.ask("Пароль для шифрования", password=True)
    confirm = Prompt.ask("Подтвердите пароль", password=True)

    if password != confirm:
        console.print("[bold red]❌ Пароли не совпадают![/]")
        raise typer.Exit(code=1)

    try:
        address = import_wallet(name, private_key, password, network_type=network)
        console.print(f"[bold green]✓ Кошелек '{name}' успешно импортирован![/]")
        console.print(f"Сеть:   [cyan]{network}[/]")
        console.print(f"Адрес:  [cyan]{address}[/]")
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

    # Получаем кэши для всех сетей
    caches_eth = get_wallet_caches(network_type="ETH")
    caches_trx = get_wallet_caches(network_type="TRX")
    all_caches = {**caches_eth, **caches_trx}

    table = Table(title="💰 Ваши кошельки", show_header=True, header_style="bold cyan")
    table.add_column("Имя", style="green", no_wrap=True)
    table.add_column("Сеть", style="dim")
    table.add_column("Адрес", style="white")
    table.add_column("Баланс", justify="right")
    table.add_column("Обновлён", style="dim", justify="right")

    for name, info in wallets.items():
        address = info['address']
        network = info.get('network', 'ETH')
        cache = all_caches.get(address)
        
        symbol = "ETH" if network == "ETH" else "TRX"

        if cache and cache["balance_eth"] is not None:
            bal_str = f"{cache['balance_eth']:.6f} {symbol}"
            if cache["balance_usd"] is not None:
                bal_str += f" (${cache['balance_usd']:,.2f})"
            updated_str = cache["updated_at"][:16]
        else:
            bal_str = "[dim]--[/]"
            updated_str = "[dim]никогда[/]"

        table.add_row(name, network, address, bal_str, updated_str)

    console.print(table)
    console.print("\n[dim]💡 Балансы обновляются при 'dcw balance' и 'dcw pay'. Для принудительного обновления: dcw balance <имя>[/]")


# ==================== БАЛАНС ====================

@app.command()
def balance(
    name: str = typer.Argument(None, help="Имя кошелька. Если не указано — спросит интерактивно", autocompletion=_complete_wallet_names),
):
    """Проверить баланс кошелька в нативной валюте и USD."""
    wallets = list_wallets()

    if name is None:
        name = Prompt.ask("Имя кошелька")

    if name not in wallets:
        console.print(f"[bold red]❌ Кошелек '{name}' не найден. Используйте 'dcw list'.[/]")
        raise typer.Exit(code=1)

    info = wallets[name]
    address = info['address']
    network = info.get('network', 'ETH')
    adapter = get_adapter(network)
    symbol = adapter.currency_symbol

    console.print(f"[cyan]⏳ Запрос баланса для {address} ({network})...[/]")

    coin_balance = adapter.get_balance(address)
    
    if coin_balance is not None:
        if network == "ETH":
            usd_price = get_eth_usd_price()
        elif network == "TRX":
            usd_price = get_trx_usd_price()
        else:
            usd_price = None
    else:
        usd_price = None


    if coin_balance is None:
        console.print("[bold yellow]⚠ Не удалось получить баланс (нет сети или RPC недоступен)[/]")
        console.print(f"Баланс: [white]? {symbol} ($ -- )[/]")
    else:
        try:
            update_wallet_cache(name, address, coin_balance, coin_balance * usd_price if usd_price else None, network_type=network)
        except Exception:
            pass

        if usd_price is not None:
            usd_value = coin_balance * usd_price
            console.print(f"Баланс: [bold green]{coin_balance:.6f} {symbol}[/] ([cyan]${usd_value:,.2f}[/])")
        else:
            console.print(f"Баланс: [bold green]{coin_balance:.6f} {symbol}[/] ([yellow]$ -- [/])")


# ==================== ОПЛАТА ====================

@app.command()
def pay(
    from_name: str = typer.Argument(None, help="Имя кошелька-отправителя", autocompletion=_complete_wallet_names),
    to_address: str = typer.Argument(None, help="Адрес получателя"),
    amount: float = typer.Argument(None, help="Сумма"),
):
    """Перевод средств с гибридным UX (0-3 аргумента)."""
    wallets = list_wallets()

    if not wallets:
        console.print("[yellow]Кошельки не найдены. Сначала создайте или импортируйте.[/]")
        raise typer.Exit()

    if from_name is None:
        table = Table(title="📋 Выберите кошелек-отправитель", show_header=True, header_style="bold cyan")
        table.add_column("Имя", style="green")
        table.add_column("Сеть", style="dim")
        table.add_column("Адрес", style="dim")
        for n, info in wallets.items():
            net = info.get('network', 'ETH')
            addr = info['address']
            table.add_row(n, net, addr)
        console.print(table)
        console.print()
        from_name = Prompt.ask("Отправитель")

    if from_name not in wallets:
        console.print(f"[bold red]❌ Кошелек '{from_name}' не найден.[/]")
        raise typer.Exit(code=1)

    info = wallets[from_name]
    network = info.get('network', 'ETH')
    adapter = get_adapter(network)
    symbol = adapter.currency_symbol
    explorer = adapter.explorer_url
    min_reserve = MIN_RESERVE_ETH if network == "ETH" else MIN_RESERVE_TRX

    if to_address is None:
        to_address = Prompt.ask("Адрес получателя")

    # Простая валидация формата адреса
    if network == "ETH" and not to_address.startswith("0x"):
        console.print("[bold red]❌ Адрес ETH должен начинаться с 0x.[/]")
        raise typer.Exit(code=1)
    if network == "TRX" and not to_address.startswith("T"):
        console.print("[bold red]❌ Адрес TRX должен начинаться с T.[/]")
        raise typer.Exit(code=1)

    if amount is None:
        amount_str = Prompt.ask(f"Сумма ({symbol})")
        try:
            amount = float(amount_str)
        except ValueError:
            console.print("[bold red]❌ Некорректная сумма.[/]")
            raise typer.Exit(code=1)

    password = Prompt.ask("Пароль от кошелька", password=True)
    private_key = decrypt_private_key(from_name, password)

    if private_key is None:
        console.print("[bold red]❌ Неверный пароль или кошелек не существует.[/]")
        raise typer.Exit(code=1)

    console.print("[cyan]⏳ Расчет комиссии и проверка сети...[/]")

    current_balance = None
    tx = None
    try:
        current_balance = adapter.get_balance(info['address'])
        tx = adapter.prepare_transaction(info['address'], to_address, amount)
    except Exception as e:
        console.print(f"[bold red]Ошибка подготовки: {e}[/]")
        raise typer.Exit(code=1)

    if tx is None:
        console.print("[bold red]❌ Не удалось подготовить транзакцию (нет сети или RPC недоступен).[/]")
        raise typer.Exit(code=1)

    fee = adapter.estimate_tx_cost(tx)

    if network == "ETH":
        usd_price = get_eth_usd_price()
    elif network == "TRX":
        usd_price = get_trx_usd_price()
    else:
        usd_price = None
    
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
    console.print(f"               [dim]{info['address']}[/]")
    console.print(f"  Сеть:        [cyan]{network}[/]")
    console.print(f"  Получатель:  [white]{to_address}[/]")
    console.print(f"  Сумма:       [bold]{amount:.6f} {symbol}[/] {fmt_usd(amount)}")
    console.print(f"  Комиссия:    [yellow]{fee:.6f} {symbol}[/] {fmt_usd(fee)}")
    console.print(f"  ─────────────────────────────")
    console.print(f"  Текущий баланс: [white]{fmt_coin(current_balance)}[/] {fmt_usd(current_balance)}")
    console.print(f"  Итого спишется: [bold]-{total_coin:.6f} {symbol}[/] {fmt_usd(total_coin)}")

    if remaining is not None:
        color = "green" if remaining >= min_reserve else "red"
        console.print(f"  Останется:     [{color}]{remaining:.6f} {symbol}[/] {fmt_usd(remaining)}")
    else:
        console.print(f"  Останется:     [dim]? {symbol} (не удалось получить баланс)[/]")
    console.print()

    if current_balance is not None:
        if total_coin > current_balance:
            console.print("[bold red]❌ Недостаточно средств![/]")
            raise typer.Exit(code=1)
        if remaining < min_reserve:
            console.print(f"[bold red]❌ Нельзя отправить всю сумму! Резерв ≥ {min_reserve} {symbol}.[/]")
            console.print(f"[yellow]Максимум: {current_balance - fee - min_reserve:.6f} {symbol}[/]")
            raise typer.Exit(code=1)

    confirm = Prompt.ask("[bold]Подтвердить отправку?[/] [dim](y/N)[/]", default="N", show_default=False)

    if confirm.lower() != "y":
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

    try:
        add_transaction(tx_hash, from_name, to_address, amount, fee, network_type=network)
    except Exception as e:
        console.print(f"[yellow]⚠ Не удалось сохранить в историю: {e}[/]")

    tx_link = f"{explorer}/tx/{tx_hash}"
    console.print(f"[bold green]✓ Транзакция отправлена![/]")
    console.print(f"Хеш: [link={tx_link}]{tx_hash}[/link]")

    if current_balance is not None and usd_price is not None:
        try:
            new_balance = current_balance - total_coin
            update_wallet_cache(from_name, info['address'], new_balance, new_balance * usd_price, network_type=network)
        except Exception:
            pass

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
    elif receipt["status"] == 1:
        gas_used = receipt["gas_used"]
        effective_fee = float(Web3.from_wei(gas_used * receipt["effective_gas_price"], "ether")) if network == "ETH" else gas_used / 1_000_000
        console.print(f"[bold green]✓ Подтверждена! Блок #{receipt['block_number']}[/]")
        console.print(f"  Факт. комиссия: [yellow]{effective_fee:.6f} {symbol}[/]")
    else:
        console.print("[bold red]❌ Транзакция упала (Reverted). Средства на месте, газ списан.[/]")
        console.print(f"  Потрачено газа: [yellow]{receipt['gas_used']} units[/]")
        console.print(f"  Детали: [link={tx_link}]{tx_link}[/link]")


# ==================== ИСТОРИЯ ====================

@app.command()
def history(
    wallet_name: str = typer.Argument(None, help="Фильтр по кошельку", autocompletion=_complete_wallet_names),
    page: int = typer.Option(1, "--page", "-p", help="Номер страницы"),
    limit: int = typer.Option(15, "--limit", "-l", help="Записей на странице"),
):
    """История транзакций с пагинацией."""
    pending_hashes = get_pending_transactions()
    if pending_hashes:
        console.print(f"[cyan]⏳ Проверка {len(pending_hashes)} pending...[/]")
        for tx_hash in pending_hashes:
            # Определяем сеть по первой найденной транзакции или дефолту
            # Для простоты пока проверяем через ETH адаптер, если не найдено - через TRX
            # В идеале нужно хранить сеть в pending_hashes или проверять обе
            receipt = None
            try:
                receipt = get_adapter("ETH").wait_for_receipt(tx_hash, timeout=10, poll_interval=2)
            except Exception:
                try:
                    receipt = get_adapter("TRX").wait_for_receipt(tx_hash, timeout=10, poll_interval=2)
                except Exception:
                    pass
            
            if receipt is not None:
                if receipt["status"] == 1:
                    effective_fee = float(Web3.from_wei(receipt["gas_used"] * receipt["effective_gas_price"], "ether"))
                    update_transaction_status(tx_hash, "success", receipt["block_number"], effective_fee)
                else:
                    update_transaction_status(tx_hash, "failed", receipt["block_number"], error_msg="Reverted")

    offset = (page - 1) * limit
    txs = get_all_transactions(wallet_name, limit=limit, offset=offset)
    total = count_transactions(wallet_name)
    total_pages = max(1, (total + limit - 1) // limit)

    if not txs:
        console.print("[yellow]Транзакции не найдены.[/]")
        raise typer.Exit()

    table = Table(
        title=f"📜 История (стр. {page}/{total_pages}, всего {total})",
        show_header=True,
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("Дата", style="dim", no_wrap=True)
    table.add_column("Кошелек", style="green")
    table.add_column("Сеть", style="dim")
    table.add_column("Куда", style="white")
    table.add_column("Сумма", justify="right")
    table.add_column("Комиссия", justify="right")
    table.add_column("Статус", justify="center")
    table.add_column("Хеш (16)", style="cyan", no_wrap=True)

    status_styles = {
        "success": "[bold green]✓ Success[/]",
        "pending": "[bold yellow]⏳ Pending[/]",
        "failed": "[bold red]✗ Failed[/]",
    }

    for tx in txs:
        date_str = tx["created_at"][:16]
        to_short = tx["to_address"][:8] + "..." + tx["to_address"][-6:]
        status = status_styles.get(tx["status"], tx["status"])
        hash_short = tx["tx_hash"][:16]
        fee = f"{tx['fee_eth']:.6f}" if tx["fee_eth"] else "--"
        network = tx.get("network_type", "ETH")

        table.add_row(date_str, tx["from_name"], network, to_short, f"{tx['amount_eth']:.6f}", fee, status, hash_short)

    console.print(table)
    console.print("\n[dim]💡 Детали транзакции: dcw tx <хеш>[/]")

    if page < total_pages:
        next_cmd = f"dcw history --page {page + 1}"
        if wallet_name:
            next_cmd += f" {wallet_name}"
        console.print(f"\n[dim]Следующая страница: {next_cmd}[/]")


@app.command()
def tx(
    tx_hash: str = typer.Argument(..., help="Полный или частичный хеш транзакции"),
):
    """Показать детали транзакции и ссылку на эксплорер."""
    row = get_transaction_by_hash(tx_hash)

    if not row:
        console.print(f"[bold red]❌ Транзакция '{tx_hash}' не найдена.[/]")
        raise typer.Exit(code=1)

    network = row.get("network_type", "ETH")
    adapter = get_adapter(network)
    link = f"{adapter.explorer_url}/tx/{row['tx_hash']}"

    console.print(f"\n[bold cyan]Детали транзакции[/]")
    console.print(f"  Хеш:       [link={link}]{row['tx_hash']}[/link]")
    console.print(f"  Статус:    {row['status']}")
    console.print(f"  Сеть:      {network}")
    console.print(f"  Отправитель: {row['from_name']}")
    console.print(f"  Получатель:  {row['to_address']}")
    console.print(f"  Сумма:     {row['amount_eth']:.6f} {adapter.currency_symbol}")
    console.print(f"  Комиссия:  {row['fee_eth']:.6f} {adapter.currency_symbol}" if row["fee_eth"] else "  Комиссия:  --")
    console.print(f"  Блок:      #{row['block_number']}" if row["block_number"] else "  Блок:      Pending")
    console.print(f"  Дата:      {row['created_at']}")
    console.print(f"\n  🔗 [link={link}]{link}[/link]\n")


if __name__ == "__main__":
    app()
