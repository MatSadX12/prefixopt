"""
Модуль команды optimize для CLI.

Этот модуль предоставляет основные команды для оптимизации списков IP-префиксов:
- optimize: Очистка списка (удаление вложенных, агрегация, сортировка).
- add: Добавление нового префикса с последующей полной оптимизацией.
"""
import sys
from pathlib import Path
from typing import Optional

import typer

# Локальные импорты
from .common import OutputFormat, handle_output, console
from ..data.file_reader import read_networks
from ..core.pipeline import process_prefixes
from ..core.ip_utils import normalize_prefix


def optimize(
    input_file: Path = typer.Argument(..., help="Input file with IP prefixes"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file (default: stdout)"),
    ipv6_only: bool = typer.Option(False, "--ipv6-only", help="Process IPv6 prefixes only"),
    ipv4_only: bool = typer.Option(False, "--ipv4-only", help="Process IPv4 prefixes only"),
    format: OutputFormat = typer.Option(
        OutputFormat.list,
        "--format", "-f",
        help="Output format: 'list' (1 per line) or 'csv' (single line, comma-separated)"
    )
) -> None:
    """
    Optimizes the list of IP prefixes.

    Выполняет полный цикл обработки:
    1. Чтение и парсинг файла.
    2. Фильтрация по версии IP (опционально).
    3. Сортировка (Broadest First).
    4. Удаление вложенных сетей.
    5. Агрегация смежных сетей.

    Результат всегда отсортирован.

    Args:
        input_file: Путь к входному файлу.
        output_file: Путь к выходному файлу (опционально).
        ipv6_only: Обрабатывать только IPv6.
        ipv4_only: Обрабатывать только IPv4.
        format: Формат вывода (List/CSV).

    Raises:
        SystemExit: При ошибках чтения или обработки.
    """
    try:
        # Получаем генератор префиксов
        prefixes = read_networks(input_file)

        # Запускаем пайплайн обработки
        processed_prefixes = process_prefixes(
            prefixes,
            sort=True,           # Обязательная сортировка для корректной агрегации
            remove_nested=True,  # Включаем удаление вложенных
            aggregate=True,      # Включаем агрегацию
            ipv4_only=ipv4_only,
            ipv6_only=ipv6_only
        )

        # Передаем результат (список или итератор) на вывод
        handle_output(processed_prefixes, format, output_file)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def add(
    new_prefix: str = typer.Argument(..., help="New prefix to add"),
    input_file: Path = typer.Argument(..., help="Input file with existing IP prefixes"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file (default: stdout)"),
    format: OutputFormat = typer.Option(
        OutputFormat.list,
        "--format", "-f",
        help="Output format: 'list' (1 per line) or 'csv' (single line, comma-separated)"
    )
) -> None:
    """
    Adds a new prefix to the file and optimizes the entire list.
    
    Функция сначала валидирует новый префикс, затем читает существующий список,
    добавляет новый элемент (если его нет) и запускает полную оптимизацию.

    Args:
        new_prefix: Новый IP-префикс (строка, например "10.0.0.0/24").
        input_file: Файл с существующим списком.
        output_file: Файл для сохранения результата.
        format: Формат вывода.

    Raises:
        SystemExit: Если префикс некорректен или при ошибках IO.
    """
    try:
        # Валидация нового префикса перед загрузкой файла
        try:
            network = normalize_prefix(new_prefix)
        except ValueError:
            console.print(f"[red]Error: Invalid prefix {new_prefix}[/red]")
            sys.exit(1)

        # Читаем файл в память (list), так как нам нужно проверить наличие 
        # и добавить элемент перед обработкой.
        # Для команды add это допустимо, так как добавление подразумевает работу с целостным списком.
        prefixes = list(read_networks(input_file))

        if network not in prefixes:
            prefixes.append(network)

        # Запускаем оптимизацию объединенного списка
        processed_prefixes = process_prefixes(
            prefixes,
            sort=True,
            remove_nested=True,
            aggregate=True
        )

        handle_output(processed_prefixes, format, output_file)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)