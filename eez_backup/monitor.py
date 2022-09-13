import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, TYPE_CHECKING

from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    MofNCompleteColumn,
    TimeElapsedColumn,
)

if TYPE_CHECKING:
    from eez_backup.command import Status


class Monitor(ABC):
    @abstractmethod
    async def open(self, size: int, message: str = ""):
        raise NotImplementedError

    @abstractmethod
    async def close(self, status: "Status"):
        raise NotImplementedError

    @abstractmethod
    async def start_command(self, message: str):
        raise NotImplementedError

    @abstractmethod
    async def complete_command(self, status: "Status"):
        raise NotImplementedError


class DummyMonitor(Monitor):
    async def open(self, size: int, message: str = ""):
        pass

    async def close(self, status: "Status"):
        pass

    async def start_command(self, message: str):
        pass

    async def complete_command(self, status: "Status"):
        pass


class LoggerMonitor(Monitor):
    def __init__(self, name: str, logger: logging.Logger | None = None):
        self._stack: List[str] = []
        self._name = name
        self._logger = logger or logging.getLogger()

    async def open(self, size: int, message: str = ""):
        self._logger.info(f"{self._name}: start {message}")

    async def close(self, status: "Status"):
        self._logger.info(f"{self._name}: done {status}")

    async def start_command(self, message: str):
        self._stack.append(message)

    async def complete_command(self, status: "Status"):
        self._stack.append(str(status))
        self._logger.info(f"{self._name}: " + " ".join(self._stack))
        self._stack.clear()


class ProgressMonitor(Monitor):
    def __init__(
        self,
        name: str,
        progress: Progress,
        delay: float = 0.0,
    ):
        self._name = name
        self._delay = delay
        self._current: str = ""
        self._counter = 0
        self._progress = progress
        self._task_id = None

    @staticmethod
    def default_progress() -> Progress:
        return Progress(
            SpinnerColumn(),
            TextColumn("[bold]{task.description}[/bold]"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TextColumn("{task.fields[activity]}"),
        )

    async def open(self, size: int, message: str = ""):
        self._task_id = self._progress.add_task(
            description=self._name,
            activity=message,
            total=size,
        )

    async def close(self, status: "Status"):
        if (task := self._task_id) is not None:
            self._progress.update(task, activity=status.markup())
            self._progress.stop_task(task)

        self._current = ""
        self._counter = 0
        self._task_id = None

    async def start_command(self, message: str):
        if (task := self._task_id) is not None:
            self._current = message
            self._progress.update(task, activity=message)

    async def complete_command(self, status: "Status"):
        self._counter += 1

        if (task := self._task_id) is not None:
            self._progress.update(
                task, advance=1, activity=f"{self._current} -> {status.markup()}"
            )

        if (delay := self._delay) > 0.0:
            await asyncio.sleep(delay)
