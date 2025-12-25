#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: $(basename "$0") [--host HOST] [--root-helper PATH]

Create or update symlinks from this repository to standard locations.
- User-owned targets are linked directly.
- Root-owned targets are skipped unless a root helper is provided, in which case
  the helper is invoked with the source and target paths.

Options:
  --host HOST          Host directory name under hosts/ to use. Defaults to the
                      current hostname from /etc/hostname when available.
  --root-helper PATH   Command to call for root-owned targets. It receives the
                      source path followed by the target path.
  -h, --help           Show this help message.
USAGE
  exit "${1:-0}"
}

log_info() { echo "[INFO] $*"; }
log_warn() { echo "[WARN] $*" >&2; }
log_error() { echo "[ERROR] $*" >&2; }

nearest_existing_path() {
  local path="$1"
  while [[ ! -e "$path" && "$path" != "/" ]]; do
    path="$(dirname "$path")"
  done
  echo "$path"
}

owner_uid_for_path() {
  local path
  path="$(nearest_existing_path "$1")"
  stat -c '%u' "$path"
}

ensure_parent_dir() {
  local target="$1"
  local parent
  parent="$(dirname "$target")"
  if [[ ! -d "$parent" ]]; then
    log_info "Creating directory $parent"
    mkdir -p "$parent"
  fi
}

link_user_owned() {
  local source="$1" target="$2"
  ensure_parent_dir "$target"

  if [[ -L "$target" ]]; then
    local resolved
    resolved="$(readlink -f "$target")"
    if [[ "$resolved" == "$source" ]]; then
      log_info "Already linked: $target -> $source"
      return
    fi
    log_info "Updating symlink: $target -> $source"
  elif [[ -e "$target" ]]; then
    log_warn "Replacing existing path at $target with symlink to $source"
  else
    log_info "Linking $target -> $source"
  fi

  ln -sfn "$source" "$target"
}

process_mapping() {
  local source="$1" target="$2" root_helper="$3"

  if [[ ! -e "$source" ]]; then
    log_warn "Source does not exist, skipping: $source"
    return
  fi

  local owner_uid
  owner_uid="$(owner_uid_for_path "$target")"

  if [[ "$owner_uid" -eq 0 ]]; then
    if [[ -n "$root_helper" ]]; then
      log_info "Delegating root-owned target to helper: $target"
      "$root_helper" "$source" "$target"
    else
      log_warn "Skipping root-owned target: $target"
      log_warn "To link manually, run (as root): ln -sfn $source $target"
    fi
    return
  fi

  link_user_owned "$source" "$target"
}

HOSTNAME=""
ROOT_HELPER=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage 0
      ;;
    --host)
      HOSTNAME="$2"
      shift 2
      ;;
    --root-helper)
      ROOT_HELPER="$2"
      shift 2
      ;;
    *)
      log_error "Unknown argument: $1"
      usage 1
      ;;
  esac
done

if [[ -z "$HOSTNAME" && -r /etc/hostname ]]; then
  HOSTNAME="$(tr -d ' \t\r\n' </etc/hostname)"
fi

if [[ -z "$HOSTNAME" ]]; then
  log_error "Host name is required and could not be inferred. Use --host."
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST_DIR="${REPO_ROOT}/hosts/${HOSTNAME}"

if [[ ! -d "$HOST_DIR" ]]; then
  log_error "Host directory not found: $HOST_DIR"
  exit 1
fi

log_info "Using host configuration from $HOST_DIR"

MAPPINGS=()

if [[ -f "${HOST_DIR}/home.nix" ]]; then
  MAPPINGS+=("${HOST_DIR}/home.nix:::${HOME}/.config/home-manager/home.nix")
fi

if [[ -d "${HOST_DIR}/home" ]]; then
  MAPPINGS+=("${HOST_DIR}/home:::${HOME}/.config/home-manager")
fi

if [[ -f "${HOST_DIR}/configuration.nix" ]]; then
  MAPPINGS+=("${HOST_DIR}/configuration.nix:::/etc/nixos/configuration.nix")
fi

if [[ -f "${HOST_DIR}/hardware-configuration.nix" ]]; then
  MAPPINGS+=("${HOST_DIR}/hardware-configuration.nix:::/etc/nixos/hardware-configuration.nix")
fi

USER_BIN_DIR="${HOME}/.local/bin"
for path in "${REPO_ROOT}/scripts"/*; do
  if [[ -f "$path" && -x "$path" ]]; then
    MAPPINGS+=("${path}:::${USER_BIN_DIR}/$(basename "$path")")
  fi
done

if [[ ${#MAPPINGS[@]} -eq 0 ]]; then
  log_warn "No mappings found to process."
  exit 0
fi

for mapping in "${MAPPINGS[@]}"; do
  source="${mapping%%:::*}"
  target="${mapping#*:::}"
  process_mapping "$source" "$target" "$ROOT_HELPER"
done
