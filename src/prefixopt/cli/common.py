"""
Модуль общих утилит для CLI-интерфейса.

Содержит общие компоненты, используемые различными командами CLI,
включая перечисления форматов вывода и функции для обработки
результатов (вывод в файл или консоль).
"""
import sys
from enum import Enum
from pathlib import Path
from typing import Optional, Union, Iterable, TextIO

from ipaddress import IPv4Network, IPv6Network
from rich.console import Console

# Глобальный объект консоли для цветного вывода
console = Console()


class OutputFormat(str, Enum):
    """
    Форматы вывода данных.
    
    Attributes:
        list: Вывод каждого префикса на новой строке.
        csv: Вывод всех префиксов в одну строку через запятую.
    """
    list = "list"
    csv = "csv"


def handle_output(
    prefixes: Iterable[Union[IPv4Network, IPv6Network]],
    fmt: OutputFormat,
    output_file: Optional[Path]
) -> None:
    """
    Processes the output of the program results.

    Реализует потоковую запись данных, что позволяет экономить память
    при работе с большими списками, не загружая их целиком в RAM
    перед записью. Поддерживает форматы List и CSV.

    Args:
        prefixes: Итератор или список объектов IPv4Network/IPv6Network.
        fmt: Формат вывода (OutputFormat.list или OutputFormat.csv).
        output_file: Путь к файлу для сохранения результата. 
                     Если None, вывод производится в stdout.

    Raises:
        SystemExit: В случае ошибки записи (IOError) завершает программу с кодом 1.
    """
    # Определяем целевой поток (файл или стандартный вывод)
    # Используем sys.stdout по умолчанию, если файл не указан
    file_handle: TextIO
    if output_file:
        try:
            file_handle = open(output_file, 'w', encoding='utf-8')
        except IOError as e:
            console.print(f"[red]Error opening file: {e}[/red]")
            sys.exit(1)
    else:
        file_handle = sys.stdout
    
    count = 0
    try:
        # Итерируемся по генератору, чтобы писать данные по мере поступления
        for i, prefix in enumerate(prefixes):
            prefix_str = str(prefix)
            
            if fmt == OutputFormat.csv:
                # В CSV добавляем запятую перед элементом (кроме первого)
                separator = "," if i > 0 else ""
                file_handle.write(f"{separator}{prefix_str}")
            else:
                # В List формате каждый префикс с новой строки
                file_handle.write(f"{prefix_str}\n")
            
            count = i + 1

        # Добавляем финальный перенос строки для CSV (требование POSIX)
        # Для List он уже добавляется в цикле
        if fmt == OutputFormat.csv and count > 0:
            file_handle.write("\n")

        # Выводим отчет только при записи в файл
        if output_file:
            file_handle.close()
            format_desc = "comma-separated" if fmt == OutputFormat.csv else "list"
            console.print(f"[green]Saved {count} prefixes to {output_file} ({format_desc})[/green]")

    except IOError as e:
        console.print(f"[red]Error writing output: {e}[/red]")
        sys.exit(1)
    finally:
        # Гарантируем закрытие файла, но НЕ закрываем stdout
        if output_file and not file_handle.closed:
            file_handle.close()