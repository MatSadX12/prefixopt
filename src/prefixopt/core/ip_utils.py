"""
Модуль утилит для работы с IP-адресами и сетями.

Содержит вспомогательные функции для конвертации, нормализации
и сравнения объектов ipaddress. Служит базовым слоем для операций ядра.
"""
import ipaddress
from typing import Union, Tuple, Literal

from ipaddress import IPv4Network, IPv6Network, IPv4Address, IPv6Address

# Alias для упрощения аннотаций типов
IPNet = Union[IPv4Network, IPv6Network]


def ip_to_int(ip: Union[str, IPv4Address, IPv6Address]) -> int:
    """
    Преобразует IP-адрес в его целочисленное представление.

    Полезно для математических операций сравнения.

    Args:
        ip: IP-адрес (строка или объект).

    Returns:
        Целое число, представляющее адрес.
    """
    if isinstance(ip, str):
        ip_obj = ipaddress.ip_address(ip)
    else:
        ip_obj = ip

    return int(ip_obj)


def int_to_ip(ip_int: int, is_ipv6: bool = False) -> str:
    """
    Преобразует целое число обратно в строковый IP-адрес.

    Args:
        ip_int: Целочисленное представление адреса.
        is_ipv6: Флаг принудительной интерпретации как IPv6.
                 Если False, тип определяется автоматически по значению (> 2^32).

    Returns:
        Строковое представление IP-адреса.
    """
    if is_ipv6 or ip_int > 0xFFFFFFFF:  # 0xFFFFFFFF - макс. значение IPv4
        return str(ipaddress.IPv6Address(ip_int))
    else:
        return str(ipaddress.IPv4Address(ip_int))


def prefix_to_int_range(network: Union[str, IPNet]) -> Tuple[int, int]:
    """
    Преобразует сетевой префикс в диапазон целых чисел (start, end).

    Используется для быстрой проверки вхождения и сортировки.

    Args:
        network: Сеть (строка или объект).

    Returns:
        Кортеж (начало диапазона, конец диапазона) в виде int.
    """
    if isinstance(network, str):
        net = ipaddress.ip_network(network, strict=False)
    else:
        net = network

    start = int(net.network_address)
    end = int(net.broadcast_address)

    return start, end


def normalize_prefix(s: str) -> IPNet:
    """
    Нормализует строку в объект IP-сети.

    Умеет обрабатывать как сети с маской ("10.0.0.0/8"), так и одиночные IP ("10.0.0.1"),
    автоматически добавляя маску /32 или /128.

    Args:
        s: Строковое представление адреса или сети.

    Returns:
        Объект IPv4Network или IPv6Network.

    Raises:
        ValueError: Если строка не является валидным IP-адресом или сетью.
    """
    try:
        # Сначала пробуем стандартное преобразование
        return ipaddress.ip_network(s, strict=False)
    except ValueError:
        # Если не вышло, возможно это одиночный IP без маски.
        # Пробуем распарсить как адрес и превратить в хост-сеть.
        try:
            ip = ipaddress.ip_address(s)
            if ip.version == 4:
                return ipaddress.IPv4Network(f"{ip}/32", strict=False)
            else:
                return ipaddress.IPv6Network(f"{ip}/128", strict=False)
        except ValueError:
            raise ValueError(f"Cannot normalize '{s}' to an IP network")


def get_version(net: IPNet) -> Literal[4, 6]:
    """
    Возвращает версию IP-протокола для сети (4 или 6).

    Args:
        net: Объект IP сети.

    Returns:
        4 или 6.
    """
    # type: ignore - Pylance иногда теряет атрибут version в Union, но он гарантированно есть
    return net.version  


def is_subnet_of(a: IPNet, b: IPNet) -> bool:
    """
    Безопасная проверка: является ли 'a' подсетью 'b'.

    Обертка над стандартным subnet_of, которая корректно обрабатывает
    сравнение разных версий протоколов (IPv4 vs IPv6), возвращая False
    вместо ошибки TypeError.

    Args:
        a: Потенциальная подсеть.
        b: Потенциальная суперсеть.

    Returns:
        True, если 'a' входит в 'b', иначе False.
    """
    if a.version != b.version:
        return False
    
    # Явная проверка типов для удовлетворения статического анализатора (Pylance/Mypy)
    if isinstance(a, IPv4Network) and isinstance(b, IPv4Network):
        return a.subnet_of(b)
    if isinstance(a, IPv6Network) and isinstance(b, IPv6Network):
        return a.subnet_of(b)
    
    return False