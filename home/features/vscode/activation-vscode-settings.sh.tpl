# shellcheck shell=bash
set -euo pipefail

vscode_settings_file="$HOME/.config/Code/User/settings.json"
vscode_settings_dir="$(dirname "$vscode_settings_file")"

# Ensure the directory exists
$DRY_RUN_CMD mkdir -p "$vscode_settings_dir"

# If settings.json doesn't exist or is a symlink (from old home-manager config),
# create/replace it with our base settings
if [[ ! -f "$vscode_settings_file" ]] || [[ -L "$vscode_settings_file" ]]; then
  $DRY_RUN_CMD rm -f "$vscode_settings_file"
  $DRY_RUN_CMD cp -f "@SETTINGS_TEMPLATE@" "$vscode_settings_file"
  $VERBOSE_ECHO "VS Code settings initialized (writable file created)"
else
  # File exists and is not a symlink - preserve it but ensure our structural settings are present
  # We use jq to merge, with our settings taking precedence for managed keys
  if command -v jq >/dev/null 2>&1; then
    managed_settings='@MANAGED_SETTINGS_JSON@'
    current_settings=$(cat "$vscode_settings_file")

    # Merge: current settings as base, overlay our managed settings on top
    merged=$(echo "$current_settings" | @JQ_BIN@ --argjson managed "$managed_settings" '. + $managed')

    $DRY_RUN_CMD echo "$merged" > "$vscode_settings_file"
    $VERBOSE_ECHO "VS Code settings updated (structural settings enforced)"
  else
    $VERBOSE_ECHO "VS Code settings preserved (jq not available for merge)"
  fi
fi
