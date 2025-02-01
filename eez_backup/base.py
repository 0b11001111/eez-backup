import shutil
from functools import cache
from pathlib import Path
from typing import Dict

from frozendict import frozendict
from pydantic import BaseModel as _BaseModel, ConfigDict, JsonValue


@cache
def restic_executable() -> Path:
    if path := shutil.which("restic"):
        return Path(path)
    raise RuntimeError("restic executable not found")


class BaseModel(_BaseModel):
    model_config = ConfigDict(extra="ignore")

    def dump(self) -> Dict[str, JsonValue]:
        return self.model_dump(exclude_unset=True, exclude_none=True)


class Env(frozendict):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, values, _validation_info):
        return cls(values)
