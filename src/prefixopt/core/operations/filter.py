"""
Модуль фильтрации.

Содержит функции для фильтрации IP-сетей (частные, зарезервированные, multicast и т.д.).
Реализован как ленивый генератор для максимальной производительности и экономии памяти.
"""
from typing import Iterable, Iterator, Union
from ipaddress import IPv4Network, IPv6Network


def filter_special(
    networks: Iterable[Union[IPv4Network, IPv6Network]],
    exclude_private: bool = False,
    exclude_loopback: bool = False,
    exclude_link_local: bool = False,
    exclude_multicast: bool = False,
    exclude_reserved: bool = False,
    exclude_unspecified: bool = False
) -> Iterator[Union[IPv4Network, IPv6Network]]:
    """
    Filters IP networks, excluding special ranges.

    Функция работает как генератор: она берет элементы из входного итератора
    и отдает их (yield) только если они проходят все проверки. Это позволяет
    обрабатывать списки любого размера без загрузки в память.

    Args:
        networks: Итератор или список объектов IPv4Network/IPv6Network.
        exclude_private: Исключить частные сети (RFC 1918, ULA).
        exclude_loopback: Исключить Loopback (127.0.0.0/8, ::1).
        exclude_link_local: Исключить Link-Local (169.254.x.x, fe80::).
        exclude_multicast: Исключить Multicast (224.0.0.0/4, ff00::/8).
        exclude_reserved: Исключить зарезервированные IETF диапазоны.
        exclude_unspecified: Исключить "unspecified" адреса (0.0.0.0, ::) и дефолтные маршруты (/0).

    Yields:
        Объекты IP сетей, прошедшие фильтрацию.
    """
    for network in networks:
        # Проверка свойств сети через атрибуты ipaddress
        
        if exclude_private and network.is_private:
            continue

        if exclude_loopback and network.is_loopback:
            continue

        if exclude_link_local and network.is_link_local:
            continue

        if exclude_multicast and network.is_multicast:
            continue

        if exclude_reserved and network.is_reserved:
            continue

        # Проверка на Unspecified (0.0.0.0, ::) и Default Route (0.0.0.0/0, ::/0)
        # network.is_unspecified обычно истинно только для адреса 0.0.0.0, но не для сети /0.
        # Поэтому добавляем проверку prefixlen == 0.
        if exclude_unspecified and (network.is_unspecified or network.prefixlen == 0):
            continue

        # Если сеть прошла все фильтры, возвращаем её в поток
        yield network