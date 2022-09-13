import shutil
from functools import cache
from pathlib import Path

from frozendict import frozendict as FrozenDict
from pydantic import BaseModel as _BaseModel, Extra


@cache
def restic_executable() -> Path:
    if path := shutil.which("restic"):
        return Path(path)
    raise RuntimeError("restic executable not found")


class BaseModel(_BaseModel):
    class Config:
        extra = Extra.ignore

    def dict(self, *args, **kwargs):
        defaults = dict(exclude_unset=True, exclude_none=True)
        return super().dict(*args, **(defaults | kwargs))

    def json(self, *args, **kwargs):
        defaults = dict(exclude_unset=True, exclude_none=True)
        return super().json(*args, **(defaults | kwargs))


class Env(FrozenDict):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, values):
        return cls(values)
