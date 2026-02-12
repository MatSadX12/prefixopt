"""
Модуль команды filter для CLI.

Реализует функциональность фильтрации списка IP-префиксов по различным критериям:
удаление частных сетей, loopback, link-local, мультикаста и bogons.
"""
import sys
from pathlib import Path
from typing import Optional

import typer

# Локальные импорты
from .common import OutputFormat, handle_output, console
from ..data.file_reader import read_networks
from ..core.pipeline import process_prefixes


def filter(
    input_file: Path = typer.Argument(..., help="Input file with IP prefixes"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file (default: stdout)"),
    exclude_private: bool = typer.Option(False, "--no-private", help="Exclude Private networks (RFC 1918, ULA)"),
    exclude_loopback: bool = typer.Option(False, "--no-loopback", help="Exclude Loopback (127.x.x.x, ::1)"),
    exclude_link_local: bool = typer.Option(False, "--no-link-local", help="Exclude Link-Local (169.254.x.x, fe80::)"),
    exclude_multicast: bool = typer.Option(False, "--no-multicast", help="Exclude Multicast"),
    exclude_reserved: bool = typer.Option(False, "--no-reserved", help="Exclude IETF Reserved networks"),
    bogons: bool = typer.Option(False, "--bogons", help="Exclude ALL special use networks (Private, Loopback, Reserved, etc.)"),
    format: OutputFormat = typer.Option(
        OutputFormat.list,
        "--format", "-f",
        help="Output format: 'list' (1 per line) or 'csv' (single line, comma-separated)"
    )
) -> None:
    """
    Filters out special types of networks.

    Позволяет очистить список от немаршрутизируемых или нежелательных
    адресов. Поддерживает вывод статистики удаленных записей.

    Args:
        input_file: Путь к входному файлу.
        output_file: Путь к выходному файлу (опционально).
        exclude_private: Флаг исключения частных сетей.
        exclude_loopback: Флаг исключения Loopback.
        exclude_link_local: Флаг исключения Link-Local.
        exclude_multicast: Флаг исключения Multicast.
        exclude_reserved: Флаг исключения зарезервированных сетей.
        bogons: Флаг исключения всех специальных сетей сразу.
        format: Формат вывода (список или CSV).

    Raises:
        SystemExit: В случае любой ошибки выполнения (IO, Parsing).
    """
    try:
        # Читаем файл в память ОДИН раз (в список).
        # Это предотвращает двойное чтение с диска (для подсчета и для обработки).
        # Мы осознанно жертвуем потреблением RAM ради скорости IO и возможности 
        # посчитать точную статистику удаленных записей.
        all_prefixes = list(read_networks(input_file))
        original_count = len(all_prefixes)

        # Обрабатываем префиксы через центральный пайплайн.
        # Сортировка и агрегация отключены для максимальной скорости фильтрации.
        filtered_prefixes = process_prefixes(
            all_prefixes,
            sort=False,           # Фильтр не меняет порядок (по возможности)
            remove_nested=False,  # Вложенность не проверяем
            aggregate=False,      # Не склеиваем
            exclude_private=exclude_private,
            exclude_loopback=exclude_loopback,
            exclude_link_local=exclude_link_local,
            exclude_multicast=exclude_multicast,
            exclude_reserved=exclude_reserved,
            exclude_unspecified=True,  # 0.0.0.0 и :: удаляем всегда при фильтрации
            bogons=bogons
        )

        # Материализуем результат в список, чтобы посчитать разницу
        filtered_list = list(filtered_prefixes)
        removed_count = original_count - len(filtered_list)

        # Передаем результат в обработчик вывода
        handle_output(filtered_list, format, output_file)

        # Выводим статистику только если это уместно 
        # (при записи в файл или в режиме списка, чтобы не портить CSV-поток в stdout)
        if output_file or format == OutputFormat.list:
            if removed_count > 0:
                console.print(f"\n[dim]Removed {removed_count} networks based on filter criteria[/dim]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)