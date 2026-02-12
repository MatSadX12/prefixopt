"""
Модуль центрального пайплайна обработки (Pipeline).

Этот модуль служит оркестратором для всех операций над IP-префиксами.
Он принимает поток данных, применяет к нему фильтры, затем
выполняет тяжелые операции (сортировка, очистка, агрегация), требующие
полной загрузки данных, и возвращает результат в виде итератора.
"""
from typing import Iterable, Iterator, Set

# Локальные импорты
from .ip_utils import IPNet
# Импортируем операции с алиасами, чтобы избежать конфликта имен 
# между аргументами функции (флагами) и самими функциями.
from .operations import aggregate as aggregate_op
from .operations import remove_nested as remove_nested_op
from .operations import sort_networks as sort_networks_op
from .operations import filter_special as filter_special_op


def process_prefixes(
    networks: Iterable[IPNet],
    sort: bool = True,
    remove_nested: bool = True,
    aggregate: bool = True,
    ipv4_only: bool = False,
    ipv6_only: bool = False,
    exclude_private: bool = False,
    exclude_loopback: bool = False,
    exclude_link_local: bool = False,
    exclude_multicast: bool = False,
    exclude_reserved: bool = False,
    exclude_unspecified: bool = False,
    bogons: bool = False
) -> Iterator[IPNet]:
    """
    Главная функция обработки префиксов.

    Выполняет полный цикл оптимизации в оптимальном порядке:
    1. Ленивая фильтрация (версии, bogons, дубликаты).
    2. Материализация списка.
    3. Сортировка (Broadest First).
    4. Удаление вложенных сетей.
    5. Агрегация.

    Args:
        networks: Входной итератор объектов IP сетей.
        sort: Выполнять сортировку (обязательно для remove_nested/aggregate).
        remove_nested: Удалять вложенные подсети.
        aggregate: Объединять смежные подсети.
        ipv4_only: Оставить только IPv4.
        ipv6_only: Оставить только IPv6.
        exclude_private: Исключить частные сети.
        exclude_loopback: Исключить Loopback.
        exclude_link_local: Исключить Link-Local.
        exclude_multicast: Исключить Multicast.
        exclude_reserved: Исключить зарезервированные сети.
        exclude_unspecified: Исключить 0.0.0.0/::.
        bogons: Включить все фильтры исключения сразу.

    Yields:
        Обработанные объекты IP сетей по одному.
    """
    
    # На этом этапе не загружаем все данные в память, работаем потоково.
    
    current_data: Iterable[IPNet] = networks

    # Ленивая дедупликация (удаление полных повторов)
    # Используем set для отслеживания увиденных сетей
    seen: Set[IPNet] = set()
    # Конструкция (n for n in ... if n not in seen and not seen.add(n))
    # работает, потому что set.add возвращает None (что есть False),
    # поэтому условие "not None" становится True, и элемент проходит дальше.
    current_data = (n for n in current_data if n not in seen and not seen.add(n))

    # 1. Фильтры по версии IP
    if ipv4_only:
        current_data = (n for n in current_data if n.version == 4)
    elif ipv6_only:
        current_data = (n for n in current_data if n.version == 6)

    # 2. Специальные фильтры (Bogons и т.д.)
    if bogons:
        exclude_private = exclude_loopback = exclude_link_local = \
            exclude_multicast = exclude_reserved = exclude_unspecified = True

    # Если включен хотя бы один фильтр, подключаем генератор фильтрации
    if any([exclude_private, exclude_loopback, exclude_link_local,
            exclude_multicast, exclude_reserved, exclude_unspecified]):
        current_data = filter_special_op(
            current_data,
            exclude_private=exclude_private,
            exclude_loopback=exclude_loopback,
            exclude_link_local=exclude_link_local,
            exclude_multicast=exclude_multicast,
            exclude_reserved=exclude_reserved,
            exclude_unspecified=exclude_unspecified
        )

    # Тяжелые операции
    # Сортировка и агрегация требуют видения всей картины данных,
    # поэтому здесь вынуждены загрузить отфильтрованный поток в список.
    
    data_list = list(current_data)
    
    # Флаг, указывающий, отсортирован ли список в порядке Broadest First.
    # Это требование для корректной работы remove_nested и aggregate.
    is_sorted_broadest = False

    if sort:
        data_list = sort_networks_op(data_list)
        is_sorted_broadest = True
    
    if remove_nested:
        # Передаем флаг is_sorted_broadest. Если True, функция пропустит
        # свою внутреннюю сортировку, что сэкономит время.
        data_list = remove_nested_op(data_list, assume_sorted=is_sorted_broadest)
        # После remove_nested список гарантированно остается отсортированным
        is_sorted_broadest = True
        
    if aggregate:
        # Защита от логических ошибок: агрегация работает ТОЛЬКО на сортированных данных.
        # Если по какой-то причине sort=False, а aggregate=True, мы обязаны
        # отсортировать данные сейчас, иначе результат будет некорректным.
        if not is_sorted_broadest:
            data_list = sort_networks_op(data_list)
            is_sorted_broadest = True
        
        data_list = aggregate_op(data_list)

    # Возвращаем результат как итератор, чтобы сохранить единый интерфейс
    yield from data_list