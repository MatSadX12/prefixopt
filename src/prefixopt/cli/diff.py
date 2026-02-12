"""
Модуль команды diff для CLI.

Позволяет сравнивать два списка префиксов (New vs Old) и выявлять изменения:
добавленные (+), удаленные (-) и неизмененные (=) сети.
Сравнение производится на уровне семантики (после полной оптимизации),
а не простого текстового совпадения.
"""
import sys
from pathlib import Path
from typing import Optional, Iterable

import typer

# Локальные импорты
from .common import console
from ..data.file_reader import read_networks
from ..core.pipeline import process_prefixes
from ..core.operations.diff import calculate_diff
from ..core.operations.sorter import sort_networks
from ..core.ip_utils import IPNet


def diff(
    new_file: Path = typer.Argument(..., help="New/Target file (Source of Truth)"),
    old_file: Path = typer.Argument(..., help="Old/Current file (to compare against)"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file for diff report"),
    summary_only: bool = typer.Option(False, "--summary", "-s", help="Show only counts, not prefixes"),
    show_unchanged: bool = typer.Option(False, "--show-unchanged", "-u", help="Include unchanged prefixes in output"),
    ipv6_only: bool = typer.Option(False, "--ipv6-only", help="Process IPv6 prefixes only"),
    ipv4_only: bool = typer.Option(False, "--ipv4-only", help="Process IPv4 prefixes only"),
) -> None:
    """
    Compares two prefix files and shows the changes.

    Оба файла предварительно проходят полную оптимизацию (сортировка,
    удаление вложенных, агрегация). Это позволяет сравнивать списки
    логически, а не построчно.

    Args:
        new_file: Файл с новым состоянием (целевой список).
        old_file: Файл со старым состоянием (текущий список).
        output_file: Файл для сохранения отчета.
        summary_only: Показывать только количество изменений.
        show_unchanged: Показывать сети, которые не изменились.
        ipv6_only: Обрабатывать только IPv6.
        ipv4_only: Обрабатывать только IPv4.

    Raises:
        SystemExit: При ошибках ввода-вывода или обработки.
    """
    try:
        def prepare(path: Path) -> Iterable[IPNet]:
            """
            Вспомогательная функция для чтения и нормализации списка.
            Запускает полный пайплайн, чтобы превратить сырой список
            в канонический вид (агрегированный и очищенный).
            """
            # Генератор чтения
            raw = read_networks(path)
            
            # Генератор -> Список (в pipeline) -> Генератор (на выходе)
            # process_prefixes гарантирует, что мы сравниваем оптимизированные данные.
            # Например, 192.168.0.0/24 и 192.168.1.0/24 превратятся в /23 перед сравнением.
            return process_prefixes(
                raw, 
                sort=True, 
                remove_nested=True, 
                aggregate=True,
                ipv4_only=ipv4_only,
                ipv6_only=ipv6_only
            )

        with console.status("Processing files (Reading & Optimizing)..."):
            # Материализуем итераторы в списки сразу, так как diff требует множеств
            nets_new = list(prepare(new_file))
            nets_old = list(prepare(old_file))
            
            # Вычисляем разницу
            added, removed, unchanged = calculate_diff(nets_new, nets_old)

        # Режим "Только сводка"
        if summary_only:
            console.print(f"[green]Added: {len(added)}[/green]")
            console.print(f"[red]Removed: {len(removed)}[/red]")
            console.print(f"[blue]Unchanged: {len(unchanged)}[/blue]")
            return

        # Сортировка результатов для удобного чтения
        sorted_added = sort_networks(added)
        sorted_removed = sort_networks(removed)
        sorted_unchanged = sort_networks(unchanged) if show_unchanged else []

        # Вывод результатов
        if output_file:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    for net in sorted_added:
                        f.write(f"+ {net}\n")
                    for net in sorted_removed:
                        f.write(f"- {net}\n")
                    
                    if show_unchanged:
                        for net in sorted_unchanged:
                            f.write(f"= {net}\n")
                            
                console.print(f"[green]Diff saved to {output_file}[/green]")
            except IOError as e:
                console.print(f"[red]Error writing to file: {e}[/red]")
                sys.exit(1)
        
        else:
            # Вывод в консоль
            if not added and not removed:
                console.print("[bold green]Files are identical (semantically)[/bold green]")
                if not show_unchanged:
                    return

            if added:
                console.print(f"\n[bold green]+++ Added ({len(added)}):[/bold green]")
                for net in sorted_added:
                    console.print(f"[green]+ {net}[/green]")
            
            if removed:
                console.print(f"\n[bold red]--- Removed ({len(removed)}):[/bold red]")
                for net in sorted_removed:
                    console.print(f"[red]- {net}[/red]")

            if show_unchanged and sorted_unchanged:
                console.print(f"\n[bold blue]=== Unchanged ({len(sorted_unchanged)}):[/bold blue]")
                for net in sorted_unchanged:
                    console.print(f"[blue]= {net}[/blue]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)