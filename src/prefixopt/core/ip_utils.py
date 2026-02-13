"""
Модуль утилит для работы с IP-адресами и сетями.

Содержит вспомогательные функции для конвертации, нормализации
и сравнения объектов ipaddress. Служит базовым слоем для операций ядра.
"""
import ipaddress
from typing import Union, Literal

from ipaddress import IPv4Network, IPv6Network

# Alias для упрощения аннотаций типов
IPNet = Union[IPv4Network, IPv6Network]


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