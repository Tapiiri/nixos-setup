from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Protocol, Sequence

SPECIALISATION_DIR = "/run/current-system/specialisation"
BASE_SWITCH_BIN = "/run/current-system/bin/switch-to-configuration"


class SubprocessRunner(Protocol):
    def run(self, argv: Sequence[str]) -> int:  # pragma: no cover
        ...


class DefaultRunner:
    def run(self, argv: Sequence[str]) -> int:
        return subprocess.run(list(argv)).returncode


def list_specialisations(specialisation_dir: str = SPECIALISATION_DIR) -> list[str]:
    """Return sorted names of available specialisations."""
    d = Path(specialisation_dir)
    if not d.is_dir():
        return []
    return sorted(e.name for e in d.iterdir() if e.is_dir())


def build_switch_argv(
    name: str | None,
    specialisation_dir: str = SPECIALISATION_DIR,
    base_switch_bin: str = BASE_SWITCH_BIN,
) -> list[str]:
    """Build the sudo argv to activate a specialisation (or the base system).

    Passing None or "base" switches back to the base NixOS configuration.
    """
    if name is None or name == "base":
        binary = base_switch_bin
    else:
        binary = f"{specialisation_dir}/{name}/bin/switch-to-configuration"
    return ["sudo", binary, "switch"]


def switch_specialisation(
    name: str | None,
    runner: SubprocessRunner,
    specialisation_dir: str = SPECIALISATION_DIR,
    base_switch_bin: str = BASE_SWITCH_BIN,
) -> int:
    return runner.run(
        build_switch_argv(
            name,
            specialisation_dir=specialisation_dir,
            base_switch_bin=base_switch_bin,
        )
    )


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="switch-specialisation",
        description=(
            'Switch between NixOS specialisations.\n\n'
            'Omit NAME or pass "base" to return to the base system.'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "specialisation",
        nargs="?",
        default=None,
        metavar="NAME",
        help='Specialisation name (e.g. "my-project"). '
             'Omit or use "base" to return to the base system.',
    )
    p.add_argument(
        "--list",
        action="store_true",
        help="List available specialisations and exit.",
    )
    return p.parse_args(list(argv))


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: SubprocessRunner | None = None,
    specialisation_dir: str = SPECIALISATION_DIR,
    base_switch_bin: str = BASE_SWITCH_BIN,
) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if runner is None:
        runner = DefaultRunner()
    args = parse_args(argv)
    if args.list:
        names = list_specialisations(specialisation_dir)
        if names:
            print("\n".join(names))
        else:
            print("(no specialisations found)")
        return 0
    return switch_specialisation(
        args.specialisation,
        runner,
        specialisation_dir=specialisation_dir,
        base_switch_bin=base_switch_bin,
    )
