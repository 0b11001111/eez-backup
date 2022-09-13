import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, TYPE_CHECKING

from pydantic import BaseModel
from tqdm.asyncio import tqdm as Tqdm

from eez_backup.formatting import Format, MultiFormat

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


class TqdmMonitorFormattingConfig(BaseModel):
    description: MultiFormat = Format.FB + Format.B
    job: MultiFormat = Format.Y
    bar: MultiFormat = Format.Y
    suffix: MultiFormat = MultiFormat()
    status_ok: MultiFormat = Format.G
    status_err: MultiFormat = Format.FB + Format.R


class TqdmMonitor(Monitor):
    def __init__(
        self,
        name: str,
        delay: float = 0.0,
        formatter: TqdmMonitorFormattingConfig | None = None,
    ):
        self._name = name
        self._delay = delay
        self._formatter = formatter
        self._current: str = ""
        self._tqdm: Tqdm | None = None

    def _format_str(self) -> str:
        desc_template = "{desc:>10}"
        job_template = "[{n_fmt}/{total_fmt} Jobs]"
        bar_template = "{bar:20}"
        suffix_template = "{postfix:<32}"

        if format_config := self._formatter:
            desc_template = format_config.description.escape(desc_template)
            job_template = format_config.job.escape(job_template)
            bar_template = format_config.bar.escape(bar_template)
            suffix_template = format_config.suffix.escape(suffix_template)

        return f"{desc_template} {bar_template} {job_template}{suffix_template}"

    def _status_str(self, status: "Status") -> str:
        status_str = str(status)
        if format_config := self._formatter:
            if status.is_ok():
                status_str = format_config.status_ok.escape(status_str)
            else:
                status_str = format_config.status_err.escape(status_str)
        return status_str

    async def open(self, size: int, message: str = ""):
        self._tqdm = Tqdm(
            bar_format=self._format_str(),
            desc=self._name,
            total=size,
        )
        self._tqdm.set_postfix_str(message)

    async def close(self, status: "Status"):
        if tqdm := self._tqdm:
            tqdm.set_postfix_str(self._status_str(status))
            tqdm.close()
        self._current = ""
        self._tqdm = None

    async def start_command(self, message: str):
        if tqdm := self._tqdm:
            self._current = message
            tqdm.set_postfix_str(message)

    async def complete_command(self, status: "Status"):
        if tqdm := self._tqdm:
            tqdm.set_postfix_str(f"{self._current} -> {self._status_str(status)}")
            tqdm.update(1)

        if (delay := self._delay) > 0.0:
            await asyncio.sleep(delay)


def default_monitor(name: str) -> Monitor:
    if logging.getLogger().level > logging.INFO:
        return TqdmMonitor(name, delay=0.8, formatter=TqdmMonitorFormattingConfig())
    return LoggerMonitor(name)
