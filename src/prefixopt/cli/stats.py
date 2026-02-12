"""
Модуль команд статистики и проверки для CLI.

Предоставляет команды для анализа содержимого файлов с префиксами:
- stats: Показывает детальную статистику (количество, уникальные IP, экономия).
- check: Проверяет вхождение IP-адреса или подсети в список.
"""
import sys
import ipaddress
from pathlib import Path
from typing import List, Union

import typer
from rich.table import Table
from ipaddress import IPv4Network, IPv6Network, IPv4Address, IPv6Address

# Локальные импорты
from .common import console
from ..data.file_reader import read_networks
from ..core.ip_counter import get_prefix_statistics


def stats(
    input_file: Path = typer.Argument(..., help="Input file with IP prefixes"),
    show_details: bool = typer.Option(False, "--details", "-d", help="Show detailed statistics")
) -> None:
    """
    Displays statistics on a list of IP prefixes.

    Анализирует файл и показывает:
    - Общее количество префиксов.
    - Количество префиксов после оптимизации.
    - Коэффициент сжатия.
    - Количество уникальных IP-адресов.
    - Разделение по версиям (IPv4/IPv6) при запросе деталей.

    Args:
        input_file: Путь к файлу для анализа.
        show_details: Флаг для вывода дополнительной информации (версии IP).

    Raises:
        SystemExit: При ошибках чтения файла.
    """
    try:
        # Читаем все префиксы в память для анализа.
        # Статистика требует полного набора данных.
        prefixes = list(read_networks(input_file))
        
        # Получаем словарь с метриками (использует безопасную сортировку внутри)
        statistics = get_prefix_statistics(prefixes)

        # Создание и настройка таблицы rich
        table = Table(title=f"Statistics for {input_file}")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="magenta")

        table.add_row("Original prefix count", str(statistics['original_prefix_count']))
        table.add_row("Optimized prefix count", str(statistics['optimized_prefix_count']))
        table.add_row("Compression ratio", f"{statistics['compression_ratio_percent']}%")
        table.add_row("Original total IPs", f"{statistics['original_total_ips']:,}")
        table.add_row("Unique IPs", f"{statistics['unique_ips']:,}")
        table.add_row("Addresses saved", f"{statistics['addresses_saved']:,}")

        console.print(table)

        if show_details:
            console.print("\n[bold]Detailed information:[/bold]")
            ipv4_count = len([p for p in prefixes if p.version == 4])
            ipv6_count = len([p for p in prefixes if p.version == 6])
            
            detail_table = Table()
            detail_table.add_column("Category", style="cyan")
            detail_table.add_column("Count", justify="right", style="magenta")
            detail_table.add_row("IPv4 prefixes", str(ipv4_count))
            detail_table.add_row("IPv6 prefixes", str(ipv6_count))
            console.print(detail_table)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def check(
    ip_or_prefix: str = typer.Argument(..., help="IP address or prefix to check"),
    input_file: Path = typer.Argument(..., help="Input file with IP prefixes")
) -> None:
    """
    Checks whether the specified IP or subnet is included in the prefix list.

    Реализует поиск вхождения:
    - Для IP-адреса: проверяет, содержится ли он в любой из сетей списка.
    - Для подсети: проверяет, является ли она подсетью любой из сетей списка.

    Args:
        ip_or_prefix: Строка с IP-адресом или CIDR (например, "1.1.1.1" или "10.0.0.0/24").
        input_file: Путь к файлу со списком префиксов.

    Raises:
        SystemExit: Если введенный IP некорректен или при ошибках файла.
    """
    try:
        # Валидация и нормализация входного аргумента
        check_item: Union[IPv4Network, IPv6Network, IPv4Address, IPv6Address]
        try:
            if '/' in ip_or_prefix:
                check_item = ipaddress.ip_network(ip_or_prefix, strict=False)
            else:
                check_item = ipaddress.ip_address(ip_or_prefix)
        except ValueError:
            console.print(f"[red]Error: Invalid IP address or prefix {ip_or_prefix}[/red]")
            sys.exit(1)

        # Используем генератор для ленивого чтения.
        # Это позволяет не загружать весь файл в память, если мы просто ищем совпадение.
        prefixes = read_networks(input_file)

        containing_networks: List[Union[IPv4Network, IPv6Network]] = []
        
        for net in prefixes:
            # Пропускаем сравнение разных версий IP для безопасности и скорости
            if check_item.version != net.version:
                continue

            if isinstance(check_item, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
                # Проверка: находится ли IP-адрес внутри сети
                if check_item in net:
                    containing_networks.append(net)
            else:
                # Проверка: является ли запрошенная сеть подсетью текущей сети из файла
                # Используем явные проверки типов для mypy/pylance
                if isinstance(check_item, ipaddress.IPv4Network) and isinstance(net, ipaddress.IPv4Network):
                    if check_item.subnet_of(net):
                        containing_networks.append(net)
                elif isinstance(check_item, ipaddress.IPv6Network) and isinstance(net, ipaddress.IPv6Network):
                    if check_item.subnet_of(net):
                        containing_networks.append(net)

        if containing_networks:
            console.print(f"[green]{ip_or_prefix} is contained in:[/green]")
            for net in containing_networks:
                console.print(f"  [blue]{net}[/blue]")
        else:
            console.print(f"[red]{ip_or_prefix} is not contained in any prefix from {input_file}[/red]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)