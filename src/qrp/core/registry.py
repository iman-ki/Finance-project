"""Plugin registry.

Each kind of plugin (signal, strategy, data provider...) gets its own Registry.
A new idea is added by decorating a class; the core code never changes.

    signals = Registry("signal")

    @signals.register("momentum_12_1")
    class Momentum121(Signal): ...

    signals.get("momentum_12_1")
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class Registry:
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._items: dict[str, type] = {}

    def register(self, name: str) -> Callable[[type[T]], type[T]]:
        def decorator(cls: type[T]) -> type[T]:
            if name in self._items:
                raise ValueError(f"{self.kind} '{name}' is already registered")
            self._items[name] = cls
            return cls

        return decorator

    def get(self, name: str) -> type:
        try:
            return self._items[name]
        except KeyError:
            raise KeyError(f"unknown {self.kind} '{name}'. Available: {self.names()}") from None

    def names(self) -> list[str]:
        return sorted(self._items)


def autodiscover(package: str, path: list[str], skip: tuple[str, ...] = ("base",)) -> None:
    """Import every module in a plugin package so its decorators run.

    Called from a package's __init__, this is what makes "drop a file in the folder"
    enough to add a plugin: no import list to keep up to date.
    """
    for module in pkgutil.iter_modules(path):
        if module.name not in skip and not module.name.startswith("_"):
            importlib.import_module(f"{package}.{module.name}")
