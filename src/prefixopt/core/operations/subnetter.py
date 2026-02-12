"""Модуль для разбиения IP-сетей"""
from typing import List, Union
from ipaddress import IPv4Network, IPv6Network


def split_network(network: Union[IPv4Network, IPv6Network], target_length: int, max_subnets: int = 500000) -> List[Union[IPv4Network, IPv6Network]]:
    """
    Splits the network into subnets with a specified prefix length.

    Args:
        network: Сеть для разбиения
        target_length: Целевая длина префикса (например, 24 для /24)
        max_subnets: Максимальное количество подсетей для предотвращения переполнения

    Returns:
        Список подсетей
    """
    if target_length < network.prefixlen:
        raise ValueError(f"Target prefix length ({target_length}) must be greater than or equal to "
                         f"current prefix length ({network.prefixlen})")

    if network.version == 4:
        if target_length > 32:
            raise ValueError("Target prefix length for IPv4 cannot be greater than 32")
    else:  # IPv6
        if target_length > 128:
            raise ValueError("Target prefix length for IPv6 cannot be greater than 128")

    # Подсчитываем количество подсетей, которое будет создано
    prefix_diff = target_length - network.prefixlen
    num_subnets = 2 ** prefix_diff

    if num_subnets > max_subnets:
        raise ValueError(f"Splitting {network} to /{target_length} would create {num_subnets} subnets, "
                         f"which exceeds the maximum allowed ({max_subnets}). Operation cancelled for safety.")

    # Генерируем подсети
    subnets = list(network.subnets(new_prefix=target_length))

    return subnets