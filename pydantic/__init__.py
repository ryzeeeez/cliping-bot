"""Version minimale de pydantic pour l'exécution hors-ligne des tests."""

from __future__ import annotations

import copy
from typing import Any, Callable, Optional

__all__ = [
    "BaseModel",
    "BaseSettings",
    "Field",
    "HttpUrl",
    "PositiveInt",
    "validator",
    "conint",
    "constr",
]


HttpUrl = str


def Field(default: Any = None, **kwargs: Any) -> Any:  # noqa: D401 - mimique pydantic.Field
    return default


def conint(**kwargs: Any) -> type[int]:
    return int


def constr(**kwargs: Any) -> type[str]:
    return str


class PositiveInt(int):
    pass


def validator(*args: Any, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        return func

    return decorator


class BaseModel:
    def __init__(self, **data: Any) -> None:
        annotations = getattr(self, "__annotations__", {})
        for field_name in annotations:
            if field_name in data:
                setattr(self, field_name, data[field_name])
            else:
                default = getattr(type(self), field_name, None)
                setattr(self, field_name, copy.deepcopy(default))
        extra = {k: v for k, v in data.items() if k not in annotations}
        for key, value in extra.items():
            setattr(self, key, value)

    def model_dump(self, mode: Optional[str] = None) -> dict[str, Any]:
        annotations = getattr(self, "__annotations__", {})
        return {field: getattr(self, field) for field in annotations if hasattr(self, field)}

    def model_copy(self, deep: bool = False) -> "BaseModel":
        data = self.model_dump()
        return type(self)(**(copy.deepcopy(data) if deep else data))

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> "BaseModel":
        return cls(**data)


class BaseSettings(BaseModel):
    class Config:
        env_file: Optional[str] = None
        env_file_encoding: str = "utf-8"
        populate_by_name: bool = False

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
