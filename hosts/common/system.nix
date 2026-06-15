# Shared system configuration for all NixOS hosts.
# Machine-specific settings (hostname, bootloader, hardware, stateVersion)
# belong in each host's configuration.nix.
{
  config,
  lib,
  pkgs,
  inputs,
  cachixCaches,
  ...
}: let
  userRegistry = import ../../users.nix;
  userNames = builtins.attrNames userRegistry;
in {
  my.tailscale = {
    enable = true;
    operator = "ilmari";
  };

  services.ollama.enable = true;

  my.esp32-dev = {
    enable = true;
    users = ["tapiiri"];
  };

  networking.networkmanager.enable = true;

  time.timeZone = "Europe/Helsinki";

  i18n.defaultLocale = "fi_FI.UTF-8";

  i18n.extraLocaleSettings = {
    LC_ADDRESS = "fi_FI.UTF-8";
    LC_IDENTIFICATION = "fi_FI.UTF-8";
    LC_MEASUREMENT = "fi_FI.UTF-8";
    LC_MONETARY = "fi_FI.UTF-8";
    LC_NAME = "fi_FI.UTF-8";
    LC_NUMERIC = "fi_FI.UTF-8";
    LC_PAPER = "fi_FI.UTF-8";
    LC_TELEPHONE = "fi_FI.UTF-8";
    LC_TIME = "fi_FI.UTF-8";
  };

  services.xserver.enable = true;

  services.displayManager.gdm.enable = true;
  services.desktopManager.gnome.enable = true;

  services.gnome.gnome-keyring.enable = true;
  security.pam.services.gdm.enableGnomeKeyring = true;

  services.xserver.xkb = {
    layout = "fi";
    variant = "";
  };

  console.keyMap = "fi";

  services.printing.enable = true;

  services.pulseaudio.enable = false;
  security.rtkit.enable = true;
  services.pipewire = {
    enable = true;
    alsa.enable = true;
    alsa.support32Bit = true;
    pulse.enable = true;
  };

  users.users =
    lib.mapAttrs (name: entry: {
      isNormalUser = true;
      inherit (entry) description extraGroups;
      home = "/home/${name}";
    })
    userRegistry;

  nix.settings.trusted-users =
    ["root"]
    ++ lib.filter (n: userRegistry.${n}.isTrusted) userNames;
  nix.settings.substituters = [
    cachixCaches.nixos.url
    cachixCaches.nixCommunity.url
    cachixCaches.garnix.url
    "https://cache.nixos.org"
  ];
  nix.settings.trusted-public-keys = [
    cachixCaches.nixos.publicKey
    cachixCaches.nixCommunity.publicKey
    cachixCaches.garnix.publicKey
    "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY="
  ];

  users.groups.nixos-setup = {};

  my.rebuild = {
    enable = true;
    upstreamUrl = "https://github.com/Tapiiri/nixos-setup.git";
    mirrorDir = "/var/lib/nixos-setup/mirror.git";
    ref = "origin/main";
    offlineOk = true;
  };

  systemd.tmpfiles.rules = [
    "d /var/lib/nixos-setup 2775 root nixos-setup - -"
    "z /var/lib/nixos-setup 2775 root nixos-setup - -"
  ];

  # One-time seed: copy Claude Code settings from a source user on first use.
  # Runs on every rebuild but is a no-op once the target files exist.
  # The hooks in settings.json use $HOME so they resolve correctly per user.
  system.activationScripts = lib.concatMapAttrs (name: entry:
    lib.optionalAttrs (entry ? claudeSeedFrom) {
      "${name}-claude-seed" = lib.stringAfter ["users" "groups"] ''
        for f in settings.json settings.local.json; do
          if [ ! -f /home/${name}/.claude/"$f" ] && [ -f /home/${entry.claudeSeedFrom}/.claude/"$f" ]; then
            mkdir -p /home/${name}/.claude
            cp /home/${entry.claudeSeedFrom}/.claude/"$f" /home/${name}/.claude/"$f"
            chown ${name}:${name} /home/${name}/.claude /home/${name}/.claude/"$f"
            chmod 644 /home/${name}/.claude/"$f"
          fi
        done
      '';
    })
  userRegistry;

  security.sudo.extraRules = [
    {
      groups = ["nixos-setup"];
      commands = [
        {
          command = "${pkgs.git}/bin/git";
          options = ["NOPASSWD"];
        }
        {
          command = "${pkgs.coreutils}/bin/mkdir";
          options = ["NOPASSWD"];
        }
        {
          command = "${pkgs.coreutils}/bin/chown";
          options = ["NOPASSWD"];
        }
        {
          command = "${pkgs.coreutils}/bin/chmod";
          options = ["NOPASSWD"];
        }
        {
          command = "${pkgs.nixos-rebuild}/bin/nixos-rebuild";
          options = ["NOPASSWD"];
        }
      ];
    }
  ];

  home-manager = {
    useGlobalPkgs = true;
    backupFileExtension = "backup";
    extraSpecialArgs = {
      inherit inputs cachixCaches;
      flakeRoot = inputs.self;
    };
    users = lib.mapAttrs (_: entry: import entry.nixosHome) userRegistry;
  };

  programs._1password.enable = true;
  programs._1password-gui = {
    enable = true;
    polkitPolicyOwners = userNames;
  };

  services.earlyoom = {
    enable = true;
    freeMemThreshold = 5;
    freeSwapThreshold = 10;
    enableNotifications = true;
  };

  nixpkgs.config.allowUnfree = true;
  nixpkgs.overlays = [inputs.affinity-nix.overlays.default];

  environment.systemPackages = let
    selfPkgs = inputs.self.packages.${pkgs.system};
  in [
    selfPkgs.rebuild
    selfPkgs.switch-user
  ];

  nix.settings.experimental-features = "nix-command flakes";
}
