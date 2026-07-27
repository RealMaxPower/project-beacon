from __future__ import annotations

from typing import Any, Callable

from beacon.models import EventRecorder
from beacon.services.base import SyntheticService


ServiceFactory = Callable[[dict[str, Any], EventRecorder], SyntheticService]

_FACTORIES: dict[str, ServiceFactory] = {}


class ServiceError(ValueError):
    """Raised when a service cannot be registered or built."""


def register_service(name: str, factory: ServiceFactory) -> None:
    """
    Make a synthetic service available to scenarios under a fixture name.

    The runner used to hardcode `if "mail" in scenario.fixtures`, which meant a
    second service could not exist without editing Beacon's core. That is the
    difference between a framework and a demo: nobody can contribute a calendar
    or a filesystem if doing so requires patching the runner.

    Registration is public so a service can live outside this package entirely
    — a scenario pack can ship its own and register it on import.
    """
    if not name or not name.isidentifier():
        raise ServiceError(
            f"service name must be a valid identifier, got {name!r}"
        )
    existing = _FACTORIES.get(name)
    if existing is not None and existing is not factory:
        raise ServiceError(f"a different service is already registered as {name!r}")
    _FACTORIES[name] = factory


def registered_services() -> tuple[str, ...]:
    return tuple(sorted(_FACTORIES))


def is_service(name: str) -> bool:
    return name in _FACTORIES


def build_service(
    name: str,
    fixture: dict[str, Any],
    recorder: EventRecorder,
) -> SyntheticService:
    factory = _FACTORIES.get(name)
    if factory is None:
        raise ServiceError(
            f"no service registered for fixture {name!r}. "
            f"Registered: {', '.join(registered_services()) or 'none'}"
        )
    return factory(fixture, recorder)
