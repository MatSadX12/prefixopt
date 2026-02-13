"""Модуль для разбиения IP-сетей"""
from typing import List, Union
from ipaddress import IPv4Network, IPv6Network


def split_network(network: Union[IPv4Network, IPv6Network], target_length: int, max_subnets: int = 500000) -> List[Union[IPv4Network, IPv6Network]]:
    """
    Excludes the specified networks from the input list.

    Команда принимает на вход цель для исключения и исходный файл.
    Если исключаемая сеть перекрывается с сетями из списка, исходные сети
    будут разбиты на фрагменты или удалены, чтобы исключить указанный диапазон.

    Target может быть:
    1. Одиночным префиксом (например, "192.168.1.1/32").
    2. Путем к файлу, содержащему список префиксов для исключения (Blacklist).

    После исключения автоматически выполняется полный цикл оптимизации
    (сортировка, удаление вложенных, агрегация) для полученного результата.

    Args:
        target: Строка с префиксом или путь к файлу с исключениями.
        input_file: Путь к исходному файлу.
        output_file: Путь к файлу для сохранения результата.
        ipv6_only: Обрабатывать только IPv6.
        ipv4_only: Обрабатывать только IPv4.
        format: Формат вывода.

    Raises:
        SystemExit: Если target не является ни валидным префиксом, ни файлом.
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