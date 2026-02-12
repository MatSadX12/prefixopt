"""
Модуль вычисления разницы (Diff) между наборами префиксов.
"""
from typing import Iterable, Set, Tuple
from ..ip_utils import IPNet

def calculate_diff(
    prefixes_new: Iterable[IPNet],
    prefixes_old: Iterable[IPNet]
) -> Tuple[Set[IPNet], Set[IPNet], Set[IPNet]]:
    """
    Calculates the difference between two sets of networks.

    Args:
        prefixes_new: Новый список (целевое состояние).
        prefixes_old: Старый список (текущее состояние).

    Returns:
        Кортеж из трех множеств:
        1. Added (есть в new, нет в old)
        2. Removed (есть в old, нет в new)
        3. Unchanged (есть в обоих)
    """
    # Материализуем в множества для быстрой математики
    set_new = set(prefixes_new)
    set_old = set(prefixes_old)

    added = set_new - set_old
    removed = set_old - set_new
    unchanged = set_new & set_old

    return added, removed, unchanged