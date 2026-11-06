{
  config,
  inputs,
  lib,
  pkgs,
  ...
}: let
  inherit (lib) mkEnableOption mkIf;

  # Community flake repackaging Anthropic's official Linux beta .deb
  # (github:poeck/claude-desktop-nix-flake).  Its auto-updater stalled at
  # 2.9939.4, so we pin a newer upstream release here.  4.x also links
  # libpipewire from the native bindings, which the flake doesn't provide yet.
  # Drop this override once the flake catches up.
  version = "4.23118.0";
  package = inputs.claude-desktop.packages.${pkgs.stdenv.hostPlatform.system}.claude-desktop.overrideAttrs (old: {
    inherit version;
    src = pkgs.fetchurl {
      url = "https://downloads.claude.ai/claude-desktop/apt/stable/pool/main/c/claude-desktop/claude-desktop_${version}_amd64.deb";
      hash = "sha256-GtmW6MqrBcmzdGRgUcQMtrudhPNxdW8VuNNyiJdRWpc=";
    };
    buildInputs = old.buildInputs ++ [pkgs.pipewire];
    meta = old.meta // {platforms = ["x86_64-linux"];};
  });
in {
  options.my.claude-desktop.enable = mkEnableOption "Claude Desktop (official Linux beta)";

  config = mkIf config.my.claude-desktop.enable {
    home.packages = [package];
  };
}
