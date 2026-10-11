from app.importers.base import ProductImporter

_REGISTRY: dict[str, type[ProductImporter]] = {}


def register(cls: type[ProductImporter]) -> type[ProductImporter]:
    if cls.key in _REGISTRY:
        raise ValueError(f"Importer '{cls.key}' already registered")
    _REGISTRY[cls.key] = cls
    return cls


def get_importer(key: str) -> ProductImporter | None:
    cls = _REGISTRY.get(key)
    return cls() if cls else None


def list_importers() -> list[type[ProductImporter]]:
    return list(_REGISTRY.values())
