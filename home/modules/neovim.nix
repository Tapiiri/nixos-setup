{
  config,
  lib,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;
in {
  options.my.neovim.enable = mkEnableOption "Neovim";

  config = mkIf config.my.neovim.enable {
    programs.neovim = {
      enable = true;
      # `vi` and `vim` on PATH point at nvim, so muscle memory keeps working.
      viAlias = true;
      vimAlias = true;
      # Adopt the post-26.05 defaults now: no Ruby/Python remote plugin
      # providers unless something actually needs them.
      withRuby = false;
      withPython3 = false;
    };
  };
}
