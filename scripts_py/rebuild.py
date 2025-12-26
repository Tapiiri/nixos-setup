from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from scripts_py.utils import OsExecRunner, Runner, read_hostname, repo_root_from_script_path


@dataclass(frozen=True)
class RebuildConfig:
    hostname: str
    flake_dir: Path
    repo_root: Path
    sync_etc_nixos: bool
    sync_ref: str
    sync_checkout: bool
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
    parser.add_argument("--dev", action="store_true", help="Use this repo checkout as the flake source")
    parser.add_argument("--flake", type=Path, help="Override flake directory to use")
    parser.add_argument(
        "--sync",
        dest="sync",
        action="store_true",
        help=(
            "Sync /etc/nixos worktree before rebuilding (fast-forward only). "
            "Enabled by default when rebuilding from /etc/nixos." 
        ),
    )
    parser.add_argument(
        "--no-sync",
        dest="sync",
        action="store_false",
        help="Do not sync /etc/nixos before rebuilding.",
    )
    parser.set_defaults(sync=None)
    parser.add_argument(
        "--sync-ref",
        default="origin/main",
        help=(
            "Git ref to fast-forward /etc/nixos to when syncing. "
            "Default: origin/main"
        ),
    )
    parser.add_argument(
        "--sync-checkout",
        action="store_true",
        help=(
            "Also update the /etc/nixos checkout to the synced ref. "
            "Use this only if /etc/nixos is writable by root git and its worktree admin area is healthy."
        ),
    )
    parser.add_argument(
        "--mirror",
        action="store_true",
        help=(
            "Use a local bare mirror (recommended for root-owned /etc/nixos). "
            "Fetch from GitHub as the user into the mirror, then fast-forward /etc/nixos from it."
        ),
    )
    parser.add_argument(
        "--mirror-dir",
        type=Path,
        default=DEFAULT_MIRROR_DIR,
        help=f"Path to bare mirror repository (default: {DEFAULT_MIRROR_DIR})",
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

    # Default to syncing when using the system flake dir.
    if args.sync is None:
        sync_etc_nixos = (not args.dev) and (flake_dir == DEFAULT_SYSTEM_FLAKE_DIR)
    else:
        sync_etc_nixos = bool(args.sync)

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

    return RebuildConfig(
        hostname=hostname,
        flake_dir=flake_dir,
        repo_root=repo_root,
        sync_etc_nixos=sync_etc_nixos,
        sync_ref=str(args.sync_ref),
        sync_checkout=bool(args.sync_checkout),
        use_mirror=bool(args.mirror),
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


def root_ensure_etc_nixos_clone(*, mirror_dir: Path, etc_dir: Path, stderr) -> int:
    """Ensure /etc/nixos exists as a root-owned clone of the mirror."""

    if (etc_dir / "flake.nix").is_file() and (etc_dir / ".git").exists():
        return 0

    if etc_dir.exists():
        print(f"Refusing to overwrite existing {etc_dir}. Move it aside first.", file=stderr)
        return 1

    print(f"Cloning {mirror_dir} into {etc_dir} (root-owned)", file=stderr)
    cp = subprocess.run(["sudo", "git", "clone", str(mirror_dir), str(etc_dir)], text=True)
    return int(cp.returncode)


def root_update_from_mirror(*, etc_dir: Path, ref: str, stderr) -> int:
    """Fast-forward /etc/nixos from its origin (the local mirror)."""

    # Ensure we have latest from mirror (no network).
    cp = subprocess.run(["sudo", "git", "-C", str(etc_dir), "fetch", "--prune", "origin"], text=True)
    if cp.returncode != 0:
        return int(cp.returncode)
    cp = subprocess.run(["sudo", "git", "-C", str(etc_dir), "merge", "--ff-only", ref], text=True)
    return int(cp.returncode)


def sync_worktree(
    *,
    worktree_dir: Path,
    repo_root: Path,
    ref: str,
    update_checkout: bool,
    stderr,
) -> int:
    """Fast-forward a worktree to a given ref.

    This is intentionally conservative:
    - no hard resets
    - no rebases
    - no interactive prompts
    """

    def git_env() -> dict[str, str]:
        # Git 2.35+ introduced “safe.directory” checks to prevent CVE-style attacks.
        # On NixOS it's common for /etc/nixos to be root-owned while `rebuild` is
        # run as the normal user. Also, some setups have a read-only $HOME/.config
        # which prevents `git config --global` from working.
        #
        # Use an ephemeral config override so we don't need to write any files.
        env = dict(os.environ)
        env.update(
            {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "safe.directory",
                "GIT_CONFIG_VALUE_0": str(worktree_dir),
            }
        )
        return env

    def run(argv: list[str]) -> int:
        cp = subprocess.run(
            argv,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=git_env(),
        )
        if cp.stdout:
            print(cp.stdout.rstrip(), file=stderr)
        if cp.stderr:
            print(cp.stderr.rstrip(), file=stderr)
        return int(cp.returncode)

    # Ensure the target directory is registered as a worktree in the main repo.
    # IMPORTANT: when the worktree is root-owned, running git in the worktree
    # directory can fail because git needs to write to the worktree admin dir
    # under <repo>/.git/worktrees/<name>. So we always operate via repo_root.
    rc = run(["git", "-C", str(repo_root), "worktree", "list"])
    if rc != 0:
        print(f"Not a git repo/worktree setup at {repo_root} (skipping sync)", file=stderr)
        return 0

    # Verify the worktree_dir looks like a git worktree (without touching its admin files).
    # If it's not registered, syncing won't work.
    cp = subprocess.run(
        ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=git_env(),
    )
    if cp.returncode != 0:
        if cp.stderr:
            print(cp.stderr.rstrip(), file=stderr)
        return int(cp.returncode)
    if f"worktree {worktree_dir}" not in cp.stdout:
        print(f"Not a registered git worktree: {worktree_dir} (skipping sync)", file=stderr)
        return 0

    # Fetch in the *main* repo so SSH/agent works.
    rc = run(["git", "-C", str(repo_root), "fetch", "--prune", "origin"])
    if rc != 0:
        return rc

    # Fail cleanly if there are local modifications.
    # Check worktree dirtiness via `-C /etc/nixos` but still running under our
    # user account; this should only read. If this trips permissions, we can
    # fall back to `git -C repo_root status --porcelain` after `worktree lock`.
    cp = subprocess.run(
        ["git", "-C", str(worktree_dir), "status", "--porcelain=v1"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=git_env(),
    )
    if cp.returncode != 0:
        print(cp.stderr.rstrip(), file=stderr)
        return int(cp.returncode)
    if cp.stdout.strip():
        print(
            f"Refusing to sync {worktree_dir}: working tree is dirty. "
            "Commit/stash changes or rerun with --no-sync.",
            file=stderr,
        )
        return 1

    if not update_checkout:
        print(
            f"Sync note: fetched updates into {repo_root}, but did not update the /etc/nixos checkout. "
            "(Pass --sync-checkout to enable checkout updates.)",
            file=stderr,
        )
        return 0

    # Updating a root-owned worktree checkout is tricky because git needs to
    # write into worktree admin data. We run this part as root and avoid network
    # access (we already fetched as the user).
    #
    # This assumes /etc/nixos has access to the same object database (normal
    # worktree setup) so the ref resolves locally.
    update_cmd = ["sudo", "git", "-C", str(worktree_dir), "merge", "--ff-only", ref]
    cp = subprocess.run(update_cmd, text=True)
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

        # Sync should happen as the invoking user (SSH keys, agents, etc).
        if cfg.sync_etc_nixos and cfg.flake_dir == DEFAULT_SYSTEM_FLAKE_DIR:
            if cfg.use_mirror:
                # Use a local bare mirror under /var/lib to avoid root needing SSH.
                # We rely on the mirror having the correct upstream URL already.
                # If it doesn't exist yet, try to create it using this repo's origin.
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
                        print("Mirror fetch failed (offline?). Continuing without updates.", file=stderr)
                    else:
                        return rc

                rc = root_ensure_etc_nixos_clone(mirror_dir=cfg.mirror_dir, etc_dir=DEFAULT_SYSTEM_FLAKE_DIR, stderr=stderr)
                if rc != 0:
                    return rc

                # Always update checkout in mirror mode (root fast-forward only).
                rc = root_update_from_mirror(etc_dir=DEFAULT_SYSTEM_FLAKE_DIR, ref=cfg.sync_ref, stderr=stderr)
                if rc != 0:
                    if cfg.offline_ok:
                        print("/etc/nixos update failed; continuing with existing checkout.", file=stderr)
                    else:
                        return rc
            else:
                rc = sync_worktree(
                    worktree_dir=DEFAULT_SYSTEM_FLAKE_DIR,
                    repo_root=cfg.repo_root,
                    ref=cfg.sync_ref,
                    update_checkout=cfg.sync_checkout,
                    stderr=stderr,
                )
                if rc != 0:
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
