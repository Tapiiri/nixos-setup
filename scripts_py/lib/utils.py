from __future__ import annotations

import os
from pathlib import Path
from typing import NoReturn, Protocol, Sequence


def log_info(msg: str, *, out) -> None:
    print(f"[INFO] {msg}", file=out)


def log_warn(msg: str, *, err) -> None:
    print(f"[WARN] {msg}", file=err)


def log_error(msg: str, *, err) -> None:
    print(f"[ERROR] {msg}", file=err)


class Runner(Protocol):
    def exec(self, argv: Sequence[str]) -> NoReturn:  # pragma: no cover
        """Replace the current process with argv[0] and arguments."""


class OsExecRunner:
    def exec(self, argv: Sequence[str]) -> NoReturn:
        os.execvp(argv[0], list(argv))
        raise AssertionError("os.execvp returned")


def read_hostname(path: Path = Path("/etc/hostname")) -> str | None:
    """Read hostname from a file, trimming whitespace.

    Returns None if the file can't be read or results in an empty hostname.
    """

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    host = "".join(ch for ch in raw if ch not in " \t\r\n")
    return host or None
