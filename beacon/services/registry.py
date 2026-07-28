from __future__ import annotations

import hashlib
import importlib
import importlib.util
import sys
from pathlib import Path
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


def import_service_module(target: str) -> None:
    """
    Import a module so that its `register_service` calls run.

    A generated service sitting in `scenarios/my-thing/service.py` is not on
    `sys.path` and has no package to be imported from, so accepting a file
    path — not only a dotted name — is what makes `beacon init --service`
    produce something runnable rather than something you first have to install.
    """
    path = Path(target)
    if path.suffix == ".py" or path.exists():
        if not path.is_file():
            raise ServiceError(f"no such service module: {target}")
        # A name that cannot collide with a real module, so two scenario packs
        # that both ship service.py do not overwrite each other in sys.modules.
        name = "beacon_service_" + hashlib.sha256(
            str(path.resolve()).encode("utf-8")
        ).hexdigest()[:12]
        if name in sys.modules:
            # Importing twice would run register_service again with a freshly
            # constructed factory, which the registry correctly refuses as a
            # conflicting registration. Normal import semantics: load once.
            return
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ServiceError(f"cannot load service module: {target}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return
    try:
        importlib.import_module(target)
    except ImportError as error:
        raise ServiceError(f"cannot import service module {target!r}: {error}") from error


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
