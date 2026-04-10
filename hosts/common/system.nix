# Shared system configuration for all NixOS hosts.
# Machine-specific settings (hostname, bootloader, hardware, stateVersion)
# belong in each host's configuration.nix.
{
  config,
  pkgs,
  inputs,
  cachixCaches,
  ...
}: {
  my.tailscale = {
    enable = true;
    operator = "ilmari";
    funnel = {
      enable = true;
      target = "http://127.0.0.1:3000";
      httpsPort = 8443;
    };
  };

  my.dokploy = {
    enable = true;
    users = ["tapiiri" "ilmari"];
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

  users.users.tapiiri = {
    isNormalUser = true;
    description = "Ilmari Tarpila";
    extraGroups = ["networkmanager" "wheel" "nixos-setup"];
    packages = with pkgs; [];
  };

  users.users.ilmari = {
    isNormalUser = true;
    description = "Ilmari (Catalys)";
    home = "/home/ilmari";
    extraGroups = ["networkmanager"];
  };

  nix.settings.trusted-users = ["root" "tapiiri"];
  nix.settings.substituters = [
    cachixCaches.nixos.url
    "https://cache.nixos.org"
  ];
  nix.settings.trusted-public-keys = [
    cachixCaches.nixos.publicKey
    "cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY="
  ];

  users.groups.nixos-setup = {};

  my.rebuild = {
    enable = true;
    upstreamUrl = "git@github.com:Tapiiri/nixos-setup.git";
    mirrorDir = "/var/lib/nixos-setup/mirror.git";
    ref = "origin/main";
    offlineOk = true;
  };

  systemd.tmpfiles.rules = [
    "d /var/lib/nixos-setup 2775 root nixos-setup - -"
    "z /var/lib/nixos-setup 2775 root nixos-setup - -"
  ];

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
    backupFileExtension = "backup";
    extraSpecialArgs = {
      inherit inputs cachixCaches;
      flakeRoot = inputs.self;
    };
    users = {
      tapiiri = import ./home.nix;
      ilmari = import ./home-work.nix;
    };
  };

  programs._1password.enable = true;
  programs._1password-gui = {
    enable = true;
    polkitPolicyOwners = ["tapiiri" "ilmari"];
  };

  services.earlyoom = {
    enable = true;
    freeMemThreshold = 5;
    freeSwapThreshold = 10;
    enableNotifications = true;
  };

  nixpkgs.config.allowUnfree = true;

  environment.systemPackages = with pkgs; [];

  nix.settings.experimental-features = "nix-command flakes";
}
