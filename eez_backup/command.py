import asyncio
import logging
from enum import Enum
from pathlib import Path
from subprocess import CompletedProcess as ProcessResult
from typing import Any, Iterable, List

from eez_backup.common import Env, BaseModel
from eez_backup.monitor import Monitor, DummyMonitor

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


class StatusCode(int, Enum):
    Ok = 0
    Warning = 1
    Error = 2


class Status:
    def __init__(self, code: StatusCode = StatusCode.Ok, message: str | None = None):
        self._code = code
        self._messages = [message.strip()] if message else []

    def __repr__(self) -> str:
        return self._repr(-1)

    def __str__(self) -> str:
        return self._code.name

    def _repr(self, max_message_length: int = 0) -> str:
        message = ", ".join(self._messages)

        if max_message_length < 0:
            message = ""
        elif 3 < max_message_length < len(message):
            message = f"{message[:max_message_length - 3]:.<{max_message_length}}"

        return f"{self._code.name}({message})"

    def markup(self) -> str:
        match self._code:
            case StatusCode.Ok:
                return f"[green]{self._repr(0)}[/green]"
            case StatusCode.Warning:
                return f"[bold yellow]{self._repr(16)}[/bold yellow]"
            case StatusCode.Error:
                return f"[bold red]{self._repr(64)}[/bold red]"

    @classmethod
    def from_process_result(cls, result: ProcessResult) -> "Status":
        return cls(
            code=StatusCode.Ok if result.returncode == 0 else StatusCode.Error,
            message=result.stderr.decode("utf-8") if result.stderr else None,
        )

    def __add__(self, other: "Status") -> "Status":
        status = Status(0)
        status._code = max(self.code, other.code)
        status._messages = self._messages + other.messages
        return status

    def __iadd__(self, other: "Status"):
        self._code = max(self.code, other.code)
        self._messages.extend(other.messages)
        return self

    @property
    def code(self) -> StatusCode:
        return self._code

    @property
    def messages(self) -> List[str]:
        return self._messages[:]

    def is_ok(self) -> bool:
        return self.code == StatusCode.Ok

    def is_err(self) -> bool:
        return self.code == StatusCode.Error


class Command(list):
    def __init__(
        self,
        *args: str,
        name: str | None = None,
        cwd: Path | None = None,
        env: Env | None = None,
    ):
        self._env = env
        self._cwd = cwd
        self._name = name
        super().__init__(args)

    def __repr__(self) -> str:
        return " ".join(self)

    def __str__(self) -> str:
        if (name := self._name) is not None:
            return name
        return f"$ {repr(self)}"

    def set_name(self, name: str):
        self._name = name

    def set_cwd(self, cwd: Path):
        self._cwd = cwd

    def update_env(self, env: Env | None = None, **kwargs):
        self._env = (self._env or Env()) | (env or Env()) | Env(kwargs)

    def add_arg(self, arg):
        self.append(str(arg))

    def add_args_from(self, args: Iterable[str]):
        self.extend(map(str, args))

    def add_kwarg(self, key: str, value: Any):
        self.extend([key, str(value)])

    async def exec(
        self, capture_output=False, timeout_s: float = float("inf"), **kwargs
    ) -> ProcessResult:
        logging.debug(f"Run {self!r}")
        logging.debug(f"In {self._cwd}")
        logging.debug(f"With {set((self._env or {}).keys())}")
        process = await asyncio.create_subprocess_exec(
            *self,
            stdout=asyncio.subprocess.PIPE if capture_output else None,
            stderr=asyncio.subprocess.PIPE if capture_output else None,
            env=self._env,
            cwd=self._cwd,
            **kwargs,
        )

        try:
            return_code, (stdout, stderr) = await asyncio.wait_for(
                asyncio.gather(process.wait(), process.communicate()), timeout_s
            )
        except asyncio.TimeoutError as error:
            return_code = 1
            stdout = b""
            stderr = repr(error).encode("utf-8")

        logging.debug(f"Completed with {return_code=}, {stderr=}")
        return ProcessResult(
            list(self),
            return_code,
            stdout if capture_output else None,
            stderr if capture_output else None,
        )


class _CommandSequenceItem(BaseModel):
    command: Command
    abort_on_error: bool = True
    ignore_error: bool = False


class CommandSequence:
    def __init__(self, name: str = "", commands: Iterable[Command] = ()):
        self._name = name
        self._commands: List[_CommandSequenceItem] = []

        for command in commands:
            self.add_command(command)

    def add_command(
        self, command: Command, abort_on_error: bool = True, ignore_error: bool = False
    ):
        self._commands.append(
            _CommandSequenceItem(
                command=command, abort_on_error=abort_on_error, ignore_error=ignore_error
            )
        )

    async def exec(self, monitor: Monitor | None = None, **kwargs) -> Status:
        global_status = Status()
        monitor = monitor or DummyMonitor()
        await monitor.open(len(self._commands), self._name)

        for item in self._commands:
            await monitor.start_command(str(item.command))
            result = await item.command.exec(**kwargs)

            status = Status.from_process_result(result)
            await monitor.complete_command(status)

            if not status.is_ok():
                if not item.ignore_error:
                    global_status += Status(StatusCode.Warning, "Abort")
                else:
                    global_status += status
                if item.abort_on_error:
                    break

        await monitor.close(global_status)
        return global_status
