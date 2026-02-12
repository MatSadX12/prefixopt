"""
Модуль чтения и парсинга файлов (File Reader).

Отвечает за извлечение IP-префиксов из файлов различных форматов (TXT, CSV, JSON).
Реализует ленивую загрузку для экономии памяти и механизмы защиты
от переполнения для больших файлов.
"""
import sys
import csv
import json
import re
import ipaddress
from pathlib import Path
from typing import List, Union, Generator, Iterator, Tuple

from ipaddress import IPv4Network, IPv6Network
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn, TaskID

# Ограничения для защиты от Out Of Memory
MAX_FILE_SIZE_MB = 700
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_LINE_COUNT = 8_000_000


def parse_ipv4(text: str) -> List[str]:
    """
    Парсит IPv4 адреса и префиксы из текста с помощью Regex.
    
    Args:
        text: Входная строка.
        
    Returns:
        Список найденных кандидатов.
    """
    ipv4_pattern = r'(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?'
    matches = re.findall(ipv4_pattern, text)
    return [match.strip() for match in matches]


def parse_ipv6(text: str) -> List[str]:
    """
    Парсит IPv6 адреса и префиксы из текста с помощью Regex.
    
    Args:
        text: Входная строка.
        
    Returns:
        Список найденных кандидатов.
    """
    ipv6_pattern = r'(?:[0-9a-fA-F]{0,4}:){2,7}[0-9a-fA-F]{0,4}(?:/\d{1,3})?'
    matches = re.findall(ipv6_pattern, text)
    return [match.strip() for match in matches]


def normalize_single_ip(candidate: str) -> Union[IPv4Network, IPv6Network, None]:
    """
    Преобразует строку IP в объект сети с очисткой и нормализацией.

    Обрабатывает распространенные проблемы ввода, такие как ведущие нули
    в октетах IPv4 и отсутствие маски.

    Args:
        candidate: Строка-кандидат (например, "10.0.0.1" или "010.0.0.1/24").

    Returns:
        Объект сети или None, если кандидат невалиден.
    """
    # 1. Попытка стандартного преобразования
    try:
        return ipaddress.ip_network(candidate, strict=False)
    except ValueError:
        pass

    # 2. Попытка очистки от ведущих нулей (только для IPv4)
    # Пример: 008.008.008.008/32 -> 8.8.8.8/32
    if '.' in candidate and ':' not in candidate:
        try:
            parts = candidate.split('/')
            ip_part = parts[0]
            mask_part = f"/{parts[1]}" if len(parts) > 1 else ""
            
            # Удаляем ведущие нули из каждого октета
            clean_ip = ".".join(str(int(octet)) for octet in ip_part.split('.'))
            clean_candidate = f"{clean_ip}{mask_part}"
            
            return ipaddress.ip_network(clean_candidate, strict=False)
        except (ValueError, IndexError):
            pass

    # 3. Обработка одиночного IP без маски
    try:
        if '.' in candidate and ':' not in candidate:
             # Чистим нули и для хостового адреса
             clean_ip = ".".join(str(int(octet)) for octet in candidate.split('.'))
             ip = ipaddress.ip_address(clean_ip)
        else:
             ip = ipaddress.ip_address(candidate)

        if ip.version == 4:
            return ipaddress.IPv4Network(f"{ip}/32", strict=False)
        else:
            return ipaddress.IPv6Network(f"{ip}/128", strict=False)
    except ValueError:
        return None


def extract_prefixes_from_text(text: str) -> List[Union[IPv4Network, IPv6Network]]:
    """
    Извлекает ВСЕ валидные IP префиксы из произвольной строки текста.
    
    Устойчив к мусору, комментариям и тексту вокруг IP.

    Args:
        text: Входная строка (например, лог или конфиг).

    Returns:
        Список валидных объектов сетей.
    """
    prefixes = []
    all_candidates = parse_ipv4(text) + parse_ipv6(text)

    for candidate in all_candidates:
        if not candidate:
            continue
        network = normalize_single_ip(candidate)
        if network is not None:
            prefixes.append(network)

    return prefixes


def _read_txt_generator(path: Path, progress: Progress, task_id: TaskID) -> Generator[Union[IPv4Network, IPv6Network], None, None]:
    """Генератор для чтения TXT файлов с поддержкой прогресса."""
    with open(path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            
            if line_num > MAX_LINE_COUNT:
                raise ValueError(f"File exceeds the limit of {MAX_LINE_COUNT} lines. Processing stopped for safety.")

            line_bytes = len(line.encode('utf-8')) + 1 # +1 на перенос строки (приблизительно)
            progress.update(task_id, advance=line_bytes)
            
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            prefixes = extract_prefixes_from_text(line)
            if prefixes:
                for prefix in prefixes:
                    yield prefix
            else:
                try:
                    yield ipaddress.ip_network(line, strict=False)
                except ValueError:
                    print(f"Warning: Invalid prefix '{line}' at line {line_num}", file=sys.stderr)


def _read_csv_generator(path: Path, progress: Progress, task_id: TaskID, column_name: str = 'prefix') -> Generator[Union[IPv4Network, IPv6Network], None, None]:
    """Генератор для чтения CSV файлов."""
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            count += 1
            if count > MAX_LINE_COUNT:
                raise ValueError(f"CSV exceeds the limit of {MAX_LINE_COUNT} rows.")

            # Примерный прогресс
            progress.update(task_id, advance=50) 
            
            prefix_text = row.get(column_name, '').strip()
            if not prefix_text:
                continue

            extracted = extract_prefixes_from_text(prefix_text)
            if extracted:
                for network in extracted:
                    yield network
            else:
                try:
                    yield ipaddress.ip_network(prefix_text, strict=False)
                except ValueError:
                    # Номер строки CSV здесь неявный, предупреждение упрощено
                    pass


def _read_json_generator(path: Path, progress: Progress, task_id: TaskID, key_name: str = 'prefixes') -> Generator[Union[IPv4Network, IPv6Network], None, None]:
    """
    Генератор для чтения JSON.
    Внимание: Загружает JSON в память целиком (ограничение стандартной библиотеки).
    """
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        progress.update(task_id, completed=path.stat().st_size)

    prefix_list = data.get(key_name, [])
    
    if len(prefix_list) > MAX_LINE_COUNT:
        raise ValueError(f"JSON array exceeds the limit of {MAX_LINE_COUNT} items.")

    for item_num, item in enumerate(prefix_list, 1):
        prefix_text = str(item).strip()
        extracted = extract_prefixes_from_text(prefix_text)
        if extracted:
            for network in extracted:
                yield network
        else:
            try:
                yield ipaddress.ip_network(prefix_text, strict=False)
            except ValueError:
                print(f"Warning: Invalid prefix '{prefix_text}' at item {item_num}", file=sys.stderr)


def read_prefixes(file_path: Union[str, Path], show_progress: bool = True) -> Iterator[Union[IPv4Network, IPv6Network]]:
    """
    Главная точка входа для чтения файлов.

    Автоматически определяет формат по расширению и выбирает нужный генератор.
    Включает защиту от переполнения памяти (Max 700MB / 8M lines).

    Args:
        file_path: Путь к файлу.
        show_progress: Флаг отображения прогресс-бара (для больших файлов).

    Returns:
        Итератор объектов IP сетей.

    Raises:
        ValueError: Если файл слишком большой.
        FileNotFoundError: Если файл не найден.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    file_size = path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File size ({file_size / 1024 / 1024:.2f} MB) exceeds the safety limit of {MAX_FILE_SIZE_MB} MB. "
            "Please split the file or use a database-oriented tool."
        )

    # Показываем бар только для файлов больше 1МБ
    should_show = show_progress and file_size > 1024 * 1024

    extension = path.suffix.lower()

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        transient=True,
        disable=not should_show
    ) as progress:
        
        task_id = progress.add_task(f"Reading {path.name}", total=file_size)

        if extension == '.csv':
            yield from _read_csv_generator(path, progress, task_id)
        elif extension == '.json':
            yield from _read_json_generator(path, progress, task_id)
        else:
            yield from _read_txt_generator(path, progress, task_id)


# Алиас для семантической понятности в других модулях
read_networks = read_prefixes


def read_prefixes_with_comments(file_path: Path) -> List[Tuple[Union[IPv4Network, IPv6Network], str]]:
    """
    Специальная функция чтения с сохранением комментариев.

    Используется только для команды merge --keep-comments.
    В отличие от основного ридера, возвращает список, а не генератор,
    так как логика слияния комментариев требует загрузки в память.

    Args:
        file_path: Путь к файлу.

    Returns:
        Список кортежей (Объект Сети, Строка Комментария).
    """
    path = Path(file_path)
    
    if path.stat().st_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(f"File too large ({path.stat().st_size/1024/1024:.2f} MB) for merge with comments.")

    results = []
    line_count = 0

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line_count += 1
            if line_count > MAX_LINE_COUNT:
                raise ValueError(f"File exceeds {MAX_LINE_COUNT} lines.")

            line_stripped = line.strip()
            if not line_stripped:
                continue

            if '#' in line:
                content, comment_raw = line.split('#', 1)
                cleaned_comment = comment_raw.strip()
                comment = f"# {cleaned_comment}" if cleaned_comment else ""
            else:
                content = line
                comment = ""

            prefixes = extract_prefixes_from_text(content)
            for p in prefixes:
                results.append((p, comment))
    return results