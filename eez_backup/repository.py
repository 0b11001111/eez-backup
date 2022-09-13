from pathlib import Path
from typing import Generator

from pydantic import Extra, Field, SecretStr, root_validator

from eez_backup.command import Command
from eez_backup.common import BaseModel, restic_executable, Env

RepositoryGenerator = Generator["Repository", None, None]


class InRepository(BaseModel):
    repository: str
    password: SecretStr | None = None
    password_file: Path | None = None
    password_command: str | None = None
    env: Env = Field(default_factory=Env)

    @root_validator(pre=True)
    def validate_password(cls, values):
        keys = {"password", "password_file", "password_command"}

        if sum(bool(values.get(key)) for key in keys) != 1:
            raise ValueError(f"Exactly one of the fields {keys} must be set!")

        return values


class Repository(InRepository):
    tag: str = Field(min_length=1)
    env: Env = Field(default_factory=Env)

    class Config:
        frozen = True

    def base_command(self, *args: str, **kwargs) -> Command:
        kwargs = {"name": self.tag} | kwargs
        executable = str(restic_executable())
        cmd = Command(executable, *args, **kwargs)
        cmd.add_kwarg("--repo", self.repository)
        cmd.update_env(self.env)
        if (password := self.password) is not None:
            cmd.update_env(RESTIC_PASSWORD=password.get_secret_value())
        elif (password_file := self.password_file) is not None:
            cmd.update_env(RESTIC_PASSWORD_FILE=password_file)
        elif (password_command := self.password_command) is not None:
            cmd.update_env(RESTIC_PASSWORD_COMMAND=password_command)
        return cmd

    def online_cmd(self, **kwargs) -> Command:
        cmd = self.base_command(**kwargs)
        cmd.set_name(f"Check availability of {self.tag!r}")
        cmd.add_arg("snapshots")
        cmd.add_arg("--json")
        return cmd
