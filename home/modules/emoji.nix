{
  config,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf mkOption types;
  cfg = config.my.emoji;
  keyPath = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/emoji-picker/";
in {
  options.my.emoji = {
    enable = mkEnableOption "Smile emoji picker with a GNOME shortcut";

    binding = mkOption {
      type = types.str;
      default = "<Super>period";
      description = ''
        GNOME accelerator that launches the emoji picker. Uses the same syntax
        as Settings > Keyboard > Custom Shortcuts, e.g. "<Super>period" or
        "<Control><Alt>e".
      '';
    };
  };

  config = mkIf cfg.enable {
    home.packages = [pkgs.smile];

    # GNOME's built-in emoji input (Ctrl+.) only works inside GTK text fields.
    # Smile is a standalone picker that copies the chosen emoji to the
    # clipboard, so it works in any app.
    #
    # Note: custom-keybindings is a whole-list replacement. Any shortcut added
    # by hand in GNOME Settings will be dropped on activation; add them here
    # instead.
    dconf.settings = {
      "org/gnome/settings-daemon/plugins/media-keys".custom-keybindings = [keyPath];

      # Path is relative (no leading slash) even though the list above is absolute.
      "org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/emoji-picker" = {
        name = "Emoji picker";
        command = "${pkgs.smile}/bin/smile";
        binding = cfg.binding;
      };
    };
  };
}
