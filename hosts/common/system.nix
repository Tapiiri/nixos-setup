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
    operator = "tapiiri";
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

  # Keep pam_gnome_keyring out of the login stack, so the GNOME login
  # keyring rests on LUKS alone and can never be silently re-keyed.
  #
  # pam_gnome_keyring hands PAM's authtok to the daemon as the keyring
  # master password. When that fails — which it always does for a
  # keyring with an empty password — gnome-keyring stashes the rejected
  # password (gkd-login.c:211 → gkm-wrap-login.c:53). The next unlock
  # prompt that succeeds then *adopts* that stash as the new master
  # (gkm-wrap-prompt.c:1033 → :724, "fixed login keyring password to
  # match login password"). The keyring therefore drifts to whatever
  # PAM last offered, with no user action and no warning.
  #
  # On fingerprint logins what PAM offers is worse than the account
  # password: gdm's pam_gdm.so reads the cached LUKS passphrase out of
  # the kernel keyring and sets it as the authtok, so the keyring could
  # end up sealed with the disk passphrase. See the password-cache=no
  # crypttab option in hosts/fw16/disk-config.nix, which removes that
  # cache; this setting removes the adoption mechanism itself.
  #
  # Nothing else needs pam_gnome_keyring here. gnome-keyring stays
  # D-Bus activatable via services.dbus.packages, and an empty-password
  # keyring is opened without any prompt by the Secret Service's first
  # unlock attempt, which passes a zero-length credential
  # (gkd-secret-unlock.c:281 → gkm-secret-binary.c:394).
  #
  # mkForce is required: services.gnome.gnome-keyring.enable sets this
  # to true unconditionally.
  #
  # Consequence: every user's keyring must have an empty password. A
  # password-protected keyring will prompt once per session instead,
  # because nothing auto-unlocks it any more.
  security.pam.services.login.enableGnomeKeyring = lib.mkForce false;

  # Distrust emSign ECC Root CA - G3 for server authentication.
  #
  # eMudhra disclosed on 2026-10-20 that eight intermediate CAs chaining to
  # this root had trivially recoverable P-384 private keys; the intermediates
  # were revoked 2026-10-18. Anyone holding those keys can mint a valid-looking
  # certificate for any host, so the root has to come out of the trust store.
  #
  # This cannot be fixed by bumping inputs: the root was still a trusted
  # serverAuth CA in nss-cacert 3.126 — what these hosts build, and what
  # nixos-unstable also carried as of 2026-10-23. The option feeds
  # pkgs.cacert's `blacklist`
  # override, which drops the certificate's PEM block from ca-bundle.crt and
  # records it as "Rejected for: 1.3.6.1.5.5.7.3.1" instead (121 roots -> 120).
  #
  # Note when verifying: the CA *name* still appears in the bundle after this
  # takes effect, because the rejection record keeps the label. The thing to
  # grep for is "Traditional PEM block omitted", not the name.
  #
  # Only G3 is affected. emSign ECC Root CA - C3, emSign Root CA - C1 and
  # emSign Root CA - G1 stay trusted, matching upstream certifi 2026.10.19,
  # which removed G3 alone and kept the other three.
  #
  # Remove this once nss-cacert ships a bundle without the root, at which
  # point the entry becomes a harmless no-op rather than a behaviour change.
  security.pki.caCertificateBlacklist = ["emSign ECC Root CA - G3"];

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
    cachixCaches.forallSystems.url
    "https://cache.nixos.org"
  ];
  nix.settings.trusted-public-keys = [
    cachixCaches.nixos.publicKey
    cachixCaches.nixCommunity.publicKey
    cachixCaches.forallSystems.publicKey
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
  # The copy is a no-op once the target files exist, but the chown is not:
  # ownership is re-asserted on every rebuild so an earlier bad run heals.
  # The hooks in settings.json use $HOME so they resolve correctly per user.
  #
  # The group must come from the account definition, not from the user name.
  # Every account here shares the `users` group — no per-user group exists —
  # so `chown ilmari-offeri:ilmari-offeri` failed with "invalid group". The
  # activation snippet only records that failure (ERR trap, no `set -e`), so
  # the copy still happened and left ~/.claude owned by root:root. Claude
  # Code could read the seeded settings but not write ~/.claude, so the
  # OAuth handshake succeeded in the browser and then failed to persist
  # .credentials.json, which surfaces as "Not logged in".
  system.activationScripts = lib.concatMapAttrs (name: entry:
    lib.optionalAttrs (entry ? claudeSeedFrom) {
      "${name}-claude-seed" = lib.stringAfter ["users" "groups"] ''
        owner=${name}:${config.users.users.${name}.group}
        for f in settings.json settings.local.json; do
          if [ ! -f /home/${name}/.claude/"$f" ] && [ -f /home/${entry.claudeSeedFrom}/.claude/"$f" ]; then
            mkdir -p /home/${name}/.claude
            cp /home/${entry.claudeSeedFrom}/.claude/"$f" /home/${name}/.claude/"$f"
            chmod 644 /home/${name}/.claude/"$f"
          fi
          if [ -f /home/${name}/.claude/"$f" ]; then
            chown "$owner" /home/${name}/.claude/"$f"
          fi
        done
        if [ -d /home/${name}/.claude ]; then
          chown "$owner" /home/${name}/.claude
        fi
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
    selfPkgs = inputs.self.packages.${pkgs.stdenv.hostPlatform.system};
  in [
    selfPkgs.rebuild
    selfPkgs.switch-user
    # Inspect wifi link rate, band and signal when a connection is slow;
    # NetworkManager alone will not show the negotiated PHY rate.
    pkgs.iw
  ];

  nix.settings.experimental-features = "nix-command flakes";
}
