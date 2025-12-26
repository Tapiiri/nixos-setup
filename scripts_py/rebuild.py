from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from scripts_py.utils import OsExecRunner, Runner, read_hostname, repo_root_from_script_path


@dataclass(frozen=True)
class RebuildConfig:
    hostname: str
    flake_dir: Path
    repo_root: Path
    use_mirror: bool
    mirror_dir: Path
    offline_ok: bool


DEFAULT_SYSTEM_FLAKE_DIR = Path("/etc/nixos")
DEFAULT_MIRROR_DIR = Path("/var/lib/nixos-setup/mirror.git")


def parse_args(argv: Sequence[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        prog="rebuild",
        add_help=True,
        formatter_class=argparse.RawTextHelpFormatter,
        description=(
            "Run nixos-rebuild switch for the given host using the repository flake.\n"
            "If HOSTNAME is omitted, the current hostname from /etc/hostname is used.\n\n"
            "By default the flake is assumed to live in a root-owned location (a stable\n"
            "system path), so rebuilding still works even if your development checkout is\n"
            "somewhere else."
        ),
    )
    parser.add_argument("--dev", action="store_true", help="Use the development repo checkout as the flake source")
    parser.add_argument("--flake", type=Path, help="Override flake directory to use")
    parser.add_argument(
        "--mirror",
        action="store_true",
        help=(
            "Explicitly enable mirror sync (on by default when rebuilding from /etc/nixos). "
            "Fetch from GitHub as the user into the mirror, then fast-forward /etc/nixos from it."
        ),
    )
    parser.add_argument(
        "--no-mirror",
        dest="no_mirror",
        action="store_true",
        help=(
            "Disable mirror sync even when rebuilding from /etc/nixos. "
            "Use this only if you know /etc/nixos is already up to date."
        ),
    )
    parser.add_argument(
        "--mirror-dir",
        type=Path,
        default=DEFAULT_MIRROR_DIR,
        help=f"Path to bare mirror repository (default: {DEFAULT_MIRROR_DIR}). Be sure that both the user and root can access it.",
    )
    parser.add_argument(
        "--offline-ok",
        action="store_true",
        help=(
            "If network fetch fails, continue rebuilding using the existing /etc/nixos checkout."
        ),
    )
    parser.add_argument("hostname", nargs="?", help="Target host (defaults to /etc/hostname)")

    # allow passing through any extra nixos-rebuild flags after `--`
    args, rest = parser.parse_known_args(list(argv))

    # emulate the shell script's behavior: unknown options before `--` are errors
    # parse_known_args will accept them into rest; we reject if rest begins with '-' and no `--` was used.
    # But we can't know if `--` was used in argv; simplest robust rule:
    # If any token in rest starts with '-' and it appeared before a literal `--` in argv, error.
    if "--" not in argv:
        for tok in rest:
            if tok.startswith("-"):
                parser.error(f"Unknown option: {tok}")

    # If there was a `--`, only pass through tokens after it.
    if "--" in argv:
        idx = list(argv).index("--")
        rest = list(argv)[idx + 1 :]

    # Stash whether --flake was explicitly provided (argparse doesn't expose that directly).
    args._flake_explicit = "--flake" in argv  # type: ignore[attr-defined]
    return args, list(rest)


def compute_config(
    *,
    args: argparse.Namespace,
    script_path: Path,
    hostname_path: Path = Path("/etc/hostname"),
) -> RebuildConfig:
    repo_root = repo_root_from_script_path(script_path)

    hostname = args.hostname or read_hostname(hostname_path)
    if not hostname:
        raise ValueError("Host name is required and could not be inferred from /etc/hostname")

    if args.flake is not None:
        flake_dir = args.flake
    else:
        flake_dir = repo_root if args.dev else DEFAULT_SYSTEM_FLAKE_DIR

    if not (flake_dir / "flake.nix").is_file():
        hint = None
        if not args.dev and (repo_root / "flake.nix").is_file():
            hint = (
                f"Hint: either link your flake into {DEFAULT_SYSTEM_FLAKE_DIR} or rerun with --dev.\n"
                "      (You can also explicitly set it with --flake PATH.)"
            )
        msg = f"Could not find flake.nix in {flake_dir}"
        if hint:
            msg = msg + "\n" + hint
        raise FileNotFoundError(msg)

    # Mirror sync is the default when rebuilding from the system flake dir.
    # Note: if user explicitly overrides --flake, we still want mirror sync by
    # default because the intent is generally still "use the system-style flow",
    # not "use worktree".
    default_mirror = (not args.dev) and not bool(getattr(args, "no_mirror", False))
    use_mirror = bool(args.mirror) or (default_mirror and not bool(getattr(args, "no_mirror", False)))

    return RebuildConfig(
        hostname=hostname,
        flake_dir=flake_dir,
        repo_root=repo_root,
        use_mirror=use_mirror,
        mirror_dir=Path(args.mirror_dir),
        offline_ok=bool(args.offline_ok),
    )


def run_cp(argv: Sequence[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(argv), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)


def ensure_mirror(
    *,
    mirror_dir: Path,
    upstream_url: str,
    stderr,
) -> int:
    """Ensure bare mirror exists; create if missing.

    This function does not require root; it assumes permissions are already
    configured (e.g. nixos-setup group + writable mirror dir).
    """

    if mirror_dir.exists():
        return 0

    mirror_dir.parent.mkdir(parents=True, exist_ok=True)
    print(f"Creating mirror repo at {mirror_dir}", file=stderr)
    cp = subprocess.run(["git", "clone", "--mirror", upstream_url, str(mirror_dir)], text=True)
    return int(cp.returncode)


def mirror_fetch(*, mirror_dir: Path, stderr) -> int:
    """Fetch updates into the bare mirror."""

    cp = run_cp(["git", "-C", str(mirror_dir), "fetch", "--prune", "origin"])
    if cp.stdout:
        print(cp.stdout.rstrip(), file=stderr)
    if cp.stderr:
        print(cp.stderr.rstrip(), file=stderr)
    return int(cp.returncode)


def mirror_push_from_dev(*, repo_root: Path, mirror_dir: Path, branch: str, stderr) -> int:
    """Push current dev repo state into the local bare mirror.

    This is useful for offline operation: if we can't fetch from GitHub but the
    user has local commits, we can still update the mirror from the dev checkout.

    Contract:
    - Does not require network access.
    - Requires that the user can write to mirror_dir.
    - Pushes refs/heads/<branch> -> refs/heads/<branch>.
    """

    cp = run_cp(["git", "-C", str(repo_root), "rev-parse", "--verify", f"refs/heads/{branch}"])
    if cp.returncode != 0:
        if cp.stderr:
            print(cp.stderr.rstrip(), file=stderr)
        print(f"Dev repo does not have local branch '{branch}' to push.", file=stderr)
        return int(cp.returncode or 1)

    print(f"Offline fallback: pushing dev branch '{branch}' to mirror", file=stderr)
    cp = run_cp(["git", "-C", str(repo_root), "push", str(mirror_dir), f"refs/heads/{branch}:refs/heads/{branch}"])
    if cp.stdout:
        print(cp.stdout.rstrip(), file=stderr)
    if cp.stderr:
        print(cp.stderr.rstrip(), file=stderr)
    return int(cp.returncode)


def root_ensure_etc_nixos_clone(*, mirror_dir: Path, etc_dir: Path, stderr) -> int:
    """Ensure /etc/nixos exists as a root-owned clone of the mirror."""

    if (etc_dir / "flake.nix").is_file() and (etc_dir / ".git").exists():
        return 0

    if etc_dir.exists():
        # If /etc/nixos exists but is NOT a git repo, it's usually a partially
        # recreated directory (e.g. user ran `sudo mkdir /etc/nixos` and copied
        # in flake.nix). In mirror mode we want /etc/nixos to be a proper clone.
        #
        # Be safe: don't delete. Move aside to a timestamped backup and then
        # clone.
        if not (etc_dir / ".git").exists():
            backup = Path(f"{etc_dir}.bak.{int(time.time())}")
            print(f"Moving aside non-git {etc_dir} -> {backup}", file=stderr)
            cp = subprocess.run(["sudo", "mv", "--", str(etc_dir), str(backup)], text=True)
            if cp.returncode != 0:
                return int(cp.returncode)
        else:
            print(f"Refusing to overwrite existing git repo at {etc_dir}. Move it aside first.", file=stderr)
            return 1

    print(f"Cloning {mirror_dir} into {etc_dir} (root-owned)", file=stderr)
    cp = subprocess.run(["sudo", "git", "clone", str(mirror_dir), str(etc_dir)], text=True)
    return int(cp.returncode)


def root_set_origin_to_mirror(*, etc_dir: Path, mirror_dir: Path, stderr) -> int:
    """Force /etc/nixos 'origin' to point at the local mirror.

    This prevents root operations from ever trying to contact GitHub directly.
    """

    # Get current origin (best-effort).
    cur = subprocess.run(
        ["sudo", "git", "-C", str(etc_dir), "remote", "get-url", "origin"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    current = (cur.stdout or "").strip()
    desired = str(mirror_dir)

    if current == desired:
        return 0

    if current:
        print(f"Updating /etc/nixos origin: {current} -> {desired}", file=stderr)
    else:
        print(f"Setting /etc/nixos origin to {desired}", file=stderr)

    cp = subprocess.run(["sudo", "git", "-C", str(etc_dir), "remote", "set-url", "origin", desired], text=True)
    return int(cp.returncode)


def root_update_from_mirror(*, etc_dir: Path, mirror_dir: Path, ref: str, stderr) -> int:
    """Fast-forward /etc/nixos from the local mirror (no network)."""

    rc = root_set_origin_to_mirror(etc_dir=etc_dir, mirror_dir=mirror_dir, stderr=stderr)
    if rc != 0:
        return rc

    # Ensure we have latest from mirror (no network).
    cp = subprocess.run(["sudo", "git", "-C", str(etc_dir), "fetch", "--prune", "origin"], text=True)
    if cp.returncode != 0:
        return int(cp.returncode)
    cp = subprocess.run(["sudo", "git", "-C", str(etc_dir), "merge", "--ff-only", ref], text=True)
    return int(cp.returncode)


def build_nixos_rebuild_command(cfg: RebuildConfig, passthrough: Sequence[str]) -> list[str]:
    cmd = ["nixos-rebuild", "switch", "--flake", f"{cfg.flake_dir}/.#{cfg.hostname}"]
    cmd.extend(passthrough)
    return cmd


def build_exec_command(cmd: Sequence[str]) -> list[str]:
    """Return the final argv to exec.

    We want `rebuild` to be runnable as the normal user (so git/ssh works), and
    only escalate privileges for the actual nixos-rebuild call.
    """

    if os.geteuid() == 0:
        return list(cmd)
    return ["sudo", *list(cmd)]


def main(argv: Sequence[str] | None = None, *, runner: Runner | None = None, stderr=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if runner is None:
        runner = OsExecRunner()
    if stderr is None:
        stderr = sys.stderr

    try:
        args, passthrough = parse_args(argv)
        cfg = compute_config(args=args, script_path=Path(__file__))

        # In dev mode, if offline-ok is set, allow pushing local dev state into
        # the mirror so /etc/nixos can still be updated from it.
        dev_offline_push = bool(args.dev) and bool(args.offline_ok)

        # Sync step for /etc/nixos (mirror mode only).
        # Sync should happen as the invoking user (SSH keys, agents, etc).
        if cfg.use_mirror and cfg.flake_dir == DEFAULT_SYSTEM_FLAKE_DIR:
            # Use a local bare mirror under /var/lib to avoid root needing SSH.
            # If it doesn't exist yet, create it using this repo's origin.
            origin_cp = run_cp(["git", "-C", str(cfg.repo_root), "remote", "get-url", "origin"])
            upstream = (origin_cp.stdout or "").strip()
            if origin_cp.returncode != 0 or not upstream:
                print("Could not determine origin URL for mirror creation.", file=stderr)
                return 1

            rc = ensure_mirror(mirror_dir=cfg.mirror_dir, upstream_url=upstream, stderr=stderr)
            if rc != 0:
                return rc

            rc = mirror_fetch(mirror_dir=cfg.mirror_dir, stderr=stderr)
            if rc != 0:
                if cfg.offline_ok:
                    print("Mirror fetch failed (offline?).", file=stderr)
                    if dev_offline_push:
                        push_rc = mirror_push_from_dev(
                            repo_root=cfg.repo_root,
                            mirror_dir=cfg.mirror_dir,
                            branch="main",
                            stderr=stderr,
                        )
                        if push_rc != 0:
                            print("Offline push-to-mirror failed; continuing without updates.", file=stderr)
                    else:
                        print("Continuing without updates.", file=stderr)
                else:
                    return rc

            rc = root_ensure_etc_nixos_clone(mirror_dir=cfg.mirror_dir, etc_dir=DEFAULT_SYSTEM_FLAKE_DIR, stderr=stderr)
            if rc != 0:
                return rc

            # Always update checkout in mirror mode (root fast-forward only).
            # Use the mirror's tracking branch name.
            ref = "origin/main"
            rc = root_update_from_mirror(
                etc_dir=DEFAULT_SYSTEM_FLAKE_DIR,
                mirror_dir=cfg.mirror_dir,
                ref=ref,
                stderr=stderr,
            )
            if rc != 0:
                if cfg.offline_ok:
                    print("/etc/nixos update failed; continuing with existing checkout.", file=stderr)
                else:
                    return rc

        cmd = build_nixos_rebuild_command(cfg, passthrough)
        exec_cmd = build_exec_command(cmd)
    except SystemExit:
        raise
    except Exception as e:
        print(str(e), file=stderr)
        return 1

    print("Running: " + " ".join(exec_cmd), file=stderr)
    runner.exec(exec_cmd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
