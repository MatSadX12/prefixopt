"""
Модуль для удаления вложенных IP-сетей.
"""

from typing import List, Union, Iterable
from ipaddress import IPv4Network, IPv6Network


def remove_nested(
    networks: Iterable[Union[IPv4Network, IPv6Network]],
    assume_sorted: bool = False,
) -> List[Union[IPv4Network, IPv6Network]]:
    """
    Deletes nested networks.
    
    Алгоритм O(N) требует, чтобы входные данные были отсортированы 
    в порядке Broadest First (см. sorter.py).

    Args:
        networks: Итератор или список объектов IPNetwork.
        assume_sorted: Если True — не сортирует заново (экономия времени).
                       Использовать ТОЛЬКО если уверены в порядке данных.

    Returns:
        Список невложенных сетей.
    """
    if assume_sorted:
        # Оптимизация: если это уже список, не копируем его лишний раз
        sorted_networks = networks if isinstance(networks, list) else list(networks)
    else:
        # Принудительная сортировка (Broadest First)
        sorted_networks = sorted(
            networks,
            key=lambda net: (
                net.version,
                int(net.network_address),
                net.prefixlen,
            )
        )

    if not sorted_networks:
        return []

    optimized: List[Union[IPv4Network, IPv6Network]] = []
    
    # Инициализируем первым элементом
    last_added = sorted_networks[0]
    optimized.append(last_added)

    for current in sorted_networks[1:]:
        # Если версии разные - это новая сеть, сброс контекста
        if current.version != last_added.version:
            optimized.append(current)
            last_added = current
            continue

        # Проверка: входит ли текущая (узкая) в последнюю (широкую)?
        if current.subnet_of(last_added):
            continue  # Вложенная сеть или дубликат
        
        # Если не входит
        optimized.append(current)
        last_added = current

    return optimized