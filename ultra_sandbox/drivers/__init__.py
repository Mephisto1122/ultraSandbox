"""Driver router: language → backend. Both drivers implement the same
interface, so nothing above this line cares which one runs the code."""

from __future__ import annotations

from ..config import Config
from ..models import driver_for_lang
from .base import Driver, DriverError
from .docker_driver import DockerDriver
from .ssh_mac import SshMacDriver

__all__ = ["Driver", "DriverError", "Router"]


class Router:
    def __init__(self, config: Config):
        self._drivers: dict[str, Driver] = {
            "docker": DockerDriver(config),
            "mac": SshMacDriver(config),
        }

    def for_lang(self, lang: str) -> tuple[str, Driver]:
        name = driver_for_lang(lang)
        return name, self._drivers[name]

    def by_name(self, name: str) -> Driver:
        return self._drivers[name]
