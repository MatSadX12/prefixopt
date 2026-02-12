"""Модуль для сортировки IP-сетей"""

from typing import List, Union, Iterable
from ipaddress import IPv4Network, IPv6Network


def sort_networks(networks: Iterable[Union[IPv4Network, IPv6Network]]) -> List[Union[IPv4Network, IPv6Network]]:
    """
    Sorting networks (Broadest First).
    Порядок:
    1. Версия (IPv4 -> IPv6)
    2. Адрес сети (по возрастанию)
    3. Длина префикса (по возрастанию: /8 -> /24)

    Канонический порядок для маршрутизации и ACL.
    """
    def sort_key(net: Union[IPv4Network, IPv6Network]):
        return (
            net.version,
            int(net.network_address),
            net.prefixlen  # От широких к узким.
        )

    return sorted(networks, key=sort_key)