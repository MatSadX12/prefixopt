"""
Модуль команд слияния и пересечения для CLI.

Предоставляет функциональность для объединения (merge) нескольких списков
префиксов с опциональным сохранением комментариев, а также для поиска
пересечений (intersect) и перекрытий между двумя списками.
"""
import sys
import ipaddress
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Generator, Set

import typer

# Локальные импорты
from .common import OutputFormat, handle_output, console
from ..data.file_reader import read_networks, read_prefixes_with_comments
from ..core.pipeline import process_prefixes
from ..core.operations.sorter import sort_networks
from ..core.ip_utils import IPNet


def merge(
    file1: Path = typer.Argument(..., help="First input file with IP prefixes"),
    file2: Path = typer.Argument(..., help="Second input file with IP prefixes"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file (default: stdout)"),
    format: OutputFormat = typer.Option(
        OutputFormat.list,
        "--format", "-f",
        help="Output format: 'list' (1 per line) or 'csv' (single line, comma-separated)"
    ),
    keep_comments: bool = typer.Option(False, "--keep-comments", help="Preserve comments. Disables aggregation and CSV format.")
) -> None:
    """
    Combines two files with IP prefixes.

    Команда поддерживает два режима работы:
    1. Стандартный (Оптимизация): Списки загружаются, объединяются, сортируются,
       очищаются от вложенностей и агрегируются.
    2. Режим --keep-comments: Используется для слияния списков "белого доступа"
       или конфигов с комментариями.
       - Агрегация и удаление вложенных сетей ОТКЛЮЧАЮТСЯ (чтобы не потерять
         привязку комментария к конкретной подсети).
       - Выполняется дедупликация (удаление полных дублей IP).
       - Используется потоковая обработка для экономии памяти.
    """
    try:
        # Проверка на конфликт: CSV не поддерживает комментарии
        if keep_comments and format == OutputFormat.csv:
            console.print("[red]Error: Cannot use --keep-comments with CSV format.[/red]")
            sys.exit(1)

        if keep_comments:        
            # Словарь для дедупликации: ключ - строковый IP, значение - комментарий.
            unique_map: Dict[str, str] = {}
            
            # Вспомогательная функция для обработки потока
            def process_stream(stream: Generator[Tuple[IPNet, str], None, None]) -> None:
                for ip, comment in stream:
                    ip_str = str(ip)
                    if ip_str not in unique_map:
                        unique_map[ip_str] = comment
                    else:
                        # Если у существующего нет коммента, а у нового есть - обновляем
                        if not unique_map[ip_str] and comment:
                            unique_map[ip_str] = comment

            # 1. Читаем первый файл прямо в словарь (минуя создание огромных списков)
            process_stream(read_prefixes_with_comments(file1))

            # 2. Читаем второй файл прямо в словарь
            process_stream(read_prefixes_with_comments(file2))

            # Восстанавливаем объекты IP для корректной сортировки
            merged_list: List[Tuple[IPNet, str]] = []
            for ip_str_key, comm in unique_map.items():
                net_obj = ipaddress.ip_network(ip_str_key, strict=False)
                merged_list.append((net_obj, comm))

            # Сортировка Broadest First (аналогично ядру)
            # Ключ: (Версия, Адрес, Маска)
            merged_list.sort(key=lambda item: (
                item[0].version,
                int(item[0].network_address),
                item[0].prefixlen
            ))

            # Формирование текстового вывода
            lines = []
            for ip_obj, comment in merged_list:
                if comment:
                    lines.append(f"{ip_obj} {comment}")
                else:
                    lines.append(str(ip_obj))

            content = "\n".join(lines) + "\n"

            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                console.print(f"[green]Merged {len(lines)} prefixes (with comments) to {output_file}[/green]")
            else:
                print(content, end="")

        else:
            # Используем list() для загрузки генераторов в память, чтобы объединить их
            prefixes1 = list(read_networks(file1))
            prefixes2 = list(read_networks(file2))
            all_prefixes = prefixes1 + prefixes2

            # Запускаем полный цикл оптимизации через Pipeline
            processed_prefixes = process_prefixes(
                all_prefixes,
                sort=True,           # Всегда сортируем при слиянии
                remove_nested=True,  # Чистим вложенность
                aggregate=True       # Склеиваем соседей
            )

            # Материализуем результат
            processed_list = list(processed_prefixes)

            # Передаем результат в обработчик вывода
            handle_output(processed_list, format, output_file)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def _find_overlaps_linear(
    sorted_list1: List[IPNet], 
    sorted_list2: List[IPNet]
) -> List[Tuple[IPNet, IPNet]]:
    """
    Линейный алгоритм поиска пересечений для отсортированных списков.
    Сложность O(N + M) в среднем случае.
    
    Возвращает список пар (Сеть из List1, Сеть из List2), которые пересекаются.
    """
    overlaps = []
    
    # Индексы для прохода по спискам
    i, j = 0, 0
    len1, len2 = len(sorted_list1), len(sorted_list2)
    
    while i < len1 and j < len2:
        net1 = sorted_list1[i]
        net2 = sorted_list2[j]
        
        # 1. Проверка версий (IPv4 vs IPv6)
        if net1.version < net2.version:
            i += 1
            continue
        if net1.version > net2.version:
            j += 1
            continue
            
        # Версии совпадают. Сравниваем диапазоны.
        # Используем числовое представление (int) для скорости.
        start1, end1 = int(net1.network_address), int(net1.broadcast_address)
        start2, end2 = int(net2.network_address), int(net2.broadcast_address)
        
        # 2. Проверка на пересечение интервалов [start, end]
        # Интервалы пересекаются, если max(start1, start2) <= min(end1, end2)
        if max(start1, start2) <= min(end1, end2):
            # Нашли пересечение!
            overlaps.append((net1, net2))
            
            # Одна широкая сеть может пересекаться с несколькими узкими.
            # Нужно продвинуть тот указатель, чей интервал заканчивается раньше,
            # чтобы найти все возможные пересечения.
            
            # Если net1 шире net2 (накрывает её), то net1 может накрыть и следующую net2[j+1].
            # Поэтому двигаем J. Если net2 шире net1, то двигаем I.
            if end1 < end2:
                i += 1
            elif end2 < end1:
                j += 1
            else:
                # Если концы совпадают, двигаем оба (или любой), чтобы избежать зацикливания
                i += 1
                j += 1
        
        # 3. Если пересечения нет, двигаем тот, который левее (меньше)
        elif end1 < start2:
            i += 1
        else:
            j += 1
            
    return overlaps


def intersect(
    file1: Path = typer.Argument(..., help="First input file with IP prefixes"),
    file2: Path = typer.Argument(..., help="Second input file with IP prefixes"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file (default: stdout)"),
    format: OutputFormat = typer.Option(
        OutputFormat.list,
        "--format", "-f",
        help="Output format: 'list' (1 per line) or 'csv' (single line, comma-separated)"
    )
) -> None:
    """
    Finds intersections between two files.

    Определяет:
    1. Common prefixes: Точные совпадения сетей (через Set Intersection).
    2. Overlapping networks: Сети, которые пересекаются или вложены, но не равны.
       Использует оптимизированный алгоритм O(N+M) с предварительной сортировкой.
    """
    try:
        # 1. Загрузка данных
        # Используем set для быстрого поиска точных совпадений
        list1 = list(read_networks(file1))
        list2 = list(read_networks(file2))
        
        name1 = file1.name
        name2 = file2.name
        
        set1 = set(list1)
        set2 = set(list2)

        # 2. Точные совпадения (Exact Match) - O(N)
        common_prefixes = set1.intersection(set2)

        # 3. Частичные перекрытия - O(N log N) из-за сортировки
        # Сначала сортируем оба списка. Это критически важно для линейного алгоритма.
        sorted1 = sort_networks(list1)
        sorted2 = sort_networks(list2)
        
        # Запускаем линейный поиск
        raw_overlaps = _find_overlaps_linear(sorted1, sorted2)
        
        # Фильтруем результаты:
        # - Убираем точные совпадения (они уже в common_prefixes)
        # - Оставляем только пары (Subnet, Supernet) для красивого вывода
        partial_overlaps: List[Tuple[IPNet, IPNet, str, str]] = []
        
        for net1, net2 in raw_overlaps:
            if net1 == net2:
                continue
            
            # Определяем кто в кого вложен
            # Pylance ignore: версии гарантированно совпадают благодаря логике _find_overlaps
            if net1.subnet_of(net2): # type: ignore
                partial_overlaps.append((net1, net2, name1, name2))
            elif net2.subnet_of(net1): # type: ignore
                partial_overlaps.append((net2, net1, name2, name1))
            # Если сети просто пересекаются (частично), но не вложены
            # (обычно означает ошибку агрегации), мы их тоже можем показать или пропустить.
            # Для простоты покажем как (net1, net2).
            else:
                 partial_overlaps.append((net1, net2, name1, name2))


        # Вывод результатов
        should_print_details = output_file is not None or format == OutputFormat.list

        if should_print_details:
            console.print(f"\n[bold underline]Intersection Report[/bold underline]")
            console.print(f"Source A: [cyan]{name1}[/cyan]")
            console.print(f"Source B: [magenta]{name2}[/magenta]\n")

            # Секция 1: Точные совпадения
            if common_prefixes:
                console.print(f"[bold green]=== Exact Matches ({len(common_prefixes)}) ===[/bold green]")
                for prefix in sort_networks(common_prefixes):
                    console.print(f"  [green]= {prefix}[/green]")
            else:
                console.print("[dim]No exact matches found.[/dim]")

            # Секция 2: Частичные перекрытия
            if partial_overlaps:
                console.print(f"\n[bold yellow]=== Partial Overlaps ({len(partial_overlaps)}) ===[/bold yellow]")
                
                # Сортируем для читаемости (по адресу вложенной сети)
                partial_overlaps.sort(key=lambda x: (x[0].version, int(x[0].network_address)))
                
                for sub, parent, sub_src, parent_src in partial_overlaps:
                    # Форматируем цвета в зависимости от источника
                    sub_color = "cyan" if sub_src == name1 else "magenta"
                    parent_color = "cyan" if parent_src == name1 else "magenta"
                    
                    console.print(
                        f"  [{sub_color}]{sub}[/{sub_color}] ({sub_src}) "
                        f"[dim]is inside[/dim] "
                        f"[{parent_color}]{parent}[/{parent_color}] ({parent_src})"
                    )
            else:
                console.print("\n[dim]No partial overlaps found.[/dim]")

        # Формирование выходного списка (только уникальные сети)
        all_results = list(common_prefixes)
        for sub, parent, _, _ in partial_overlaps:
            all_results.extend([sub, parent])

        all_results = list(set(all_results))
        all_results = sort_networks(all_results)

        if not all_results and should_print_details:
             console.print("\n[bold red]No intersections found anywhere.[/bold red]")
             return

        handle_output(all_results, format, output_file)

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)