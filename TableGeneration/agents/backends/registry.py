from typing import Dict, Iterable

from ..capabilities.protocols import CapabilityBackend


class BackendRegistry:
    def __init__(self, backends: Iterable[CapabilityBackend] = ()):
        self._backends: Dict[str, CapabilityBackend] = {}
        for backend in backends:
            self.register(backend)

    def register(self, backend: CapabilityBackend) -> None:
        if not backend.name:
            raise ValueError("backend name must not be empty")
        if backend.name in self._backends:
            raise ValueError(f"backend already registered: {backend.name}")
        self._backends[backend.name] = backend

    def get(self, name: str) -> CapabilityBackend:
        try:
            return self._backends[name]
        except KeyError as exc:
            raise KeyError(f"unknown backend: {name}") from exc

    def names(self):
        return tuple(self._backends)
