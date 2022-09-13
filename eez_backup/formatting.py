from collections import UserList
from enum import Enum
from typing import Iterable, Union


class Formatter:
    def render(self) -> str:
        raise NotImplementedError

    def escape(self, text: str) -> str:
        raise NotImplementedError


class Format(int, Formatter, Enum):
    """Implements subset of https://en.wikipedia.org/wiki/Escape_character"""

    Reset = "0"  # Reset

    # Formatting
    FB = 1  # Bold
    FF = 2  # Faint
    FI = 3  # Italic
    FU = 4  # Underline
    FSB = 5  # Slow Blink
    FRB = 6  # Rabit Blink

    # normal colors
    K = 30  # black
    R = 31  # red
    G = 32  # green
    Y = 33  # yellow (brown)
    B = 34  # blue
    M = 35  # magenta
    C = 36  # cyan
    W = 37  # white (L.gray)

    # background colors
    BK = 40  # black
    BR = 41  # red
    BG = 42  # green
    BY = 43  # yellow (brown)
    BB = 44  # blue
    BM = 45  # magenta
    BC = 46  # cyan
    BW = 47  # white (L.gray)

    def __add__(self, other: Union["Format", Iterable["Format"]]) -> "MultiFormat":
        if isinstance(other, Format):
            return MultiFormat((self, other))
        return MultiFormat((self, *other))

    def render(self) -> str:
        return f"\033[{self.value}m"

    def escape(self, text: str) -> str:
        formatter = MultiFormat([self])
        return formatter.escape(text)


class MultiFormat(UserList[Format], Formatter):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, values):
        if isinstance(values, Format):
            return cls([values])
        return cls(values)

    def render(self) -> str:
        code = ";".join(map(lambda c: str(c.value), self))
        return f"\033[{code}m"

    def escape(self, text: str) -> str:
        if self:
            prefix = self.render()
            suffix = Format.Reset.render()
            return f"{prefix}{text}" if text.endswith(suffix) else f"{prefix}{text}{suffix}"
        return text
