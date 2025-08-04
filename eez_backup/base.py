import shutil
from functools import cache
from pathlib import Path
from typing import Any
from typing import Dict

from frozendict import frozendict
from pydantic import BaseModel as _BaseModel, ConfigDict, JsonValue
from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


@cache
def restic_executable() -> Path:
    if path := shutil.which("restic"):
        return Path(path)
    raise RuntimeError("restic executable not found")


class BaseModel(_BaseModel):
    model_config = ConfigDict(extra="ignore")

    def dump(self) -> Dict[str, JsonValue]:
        return self.model_dump(exclude_unset=True, exclude_none=True)


class Env(frozendict[str, str]):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        return core_schema.no_info_after_validator_function(lambda values: cls(values), handler(dict))
