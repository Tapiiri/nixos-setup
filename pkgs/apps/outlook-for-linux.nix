{
  lib,
  stdenv,
  fetchurl,
  dpkg,
  autoPatchelfHook,
  makeWrapper,
  wrapGAppsHook3,
  alsa-lib,
  at-spi2-atk,
  at-spi2-core,
  atk,
  cairo,
  cups,
  dbus,
  expat,
  glib,
  gtk3,
  libdrm,
  libgbm,
  libnotify,
  libsecret,
  libglvnd,
  libxkbcommon,
  nspr,
  nss,
  pango,
  systemd,
  libx11,
  libxcomposite,
  libxdamage,
  libxext,
  libxfixes,
  libxrandr,
  libxcb,
}:
# Unofficial Outlook desktop client, repackaged from the upstream .deb.
#
# Microsoft ships no Outlook desktop client for Linux; this is the same
# Electron-wrapper family as teams-for-linux, by the same maintainer. Not in
# nixpkgs, so it lives here alongside the other repackaged .deb apps.
#
# Releases are tagged `v<version>-outlook`. Bump with:
#   gh api repos/mahmoudbahaa/outlook-for-linux/releases/latest -q .tag_name
# The Electron auto-updater is a no-op for .deb installs, so the pinned
# version is what you get.
stdenv.mkDerivation (finalAttrs: {
  pname = "outlook-for-linux";
  version = "1.3.13";

  src = fetchurl {
    url = "https://github.com/mahmoudbahaa/outlook-for-linux/releases/download/v${finalAttrs.version}-outlook/outlook-for-linux_${finalAttrs.version}_amd64.deb";
    hash = "sha256-a7uwtn9h6T/hQeVznGcQYzh2sTzIz4rv0hmH7GT8rzQ=";
  };

  nativeBuildInputs = [
    dpkg
    autoPatchelfHook
    makeWrapper
    wrapGAppsHook3
  ];

  buildInputs = [
    alsa-lib
    at-spi2-atk
    at-spi2-core
    atk
    cairo
    cups
    dbus
    expat
    glib
    gtk3
    libdrm
    libgbm
    libnotify
    libsecret
    libxkbcommon
    nspr
    nss
    pango
    libx11
    libxcomposite
    libxdamage
    libxext
    libxfixes
    libxrandr
    libxcb
  ];

  # Electron dlopen()s libudev at runtime rather than linking it, so
  # autoPatchelf cannot discover it from the ELF headers.
  runtimeDependencies = [(lib.getLib systemd)];

  # The bundled ANGLE libEGL.so dlopen()s the system libEGL.so.1 to reach the
  # real GPU driver. runtimeDependencies only extends the runpath of
  # executables, and a DT_RUNPATH on the main binary does not apply to a
  # dlopen() made from inside a library, so append it everywhere instead --
  # otherwise Chromium drops to SwiftShader and spams EGL_NOT_INITIALIZED.
  appendRunpaths = [(lib.getLib libglvnd + "/lib")];

  unpackPhase = ''
    runHook preUnpack
    dpkg-deb -x $src .
    runHook postUnpack
  '';

  installPhase = ''
    runHook preInstall

    mkdir -p $out/share/outlook-for-linux
    cp -r opt/outlook-for-linux/. $out/share/outlook-for-linux/

    # The bundled SUID sandbox helper cannot be setuid root from a Nix store
    # path; Electron uses unprivileged user namespaces on NixOS instead.
    rm -f $out/share/outlook-for-linux/chrome-sandbox

    # Keep upstream's desktop file name: it is what registers the
    # x-scheme-handler/msoutlook handler in the xdg mime cache.
    install -Dm644 usr/share/applications/outlook-for-linux.desktop \
      $out/share/applications/outlook-for-linux.desktop
    substituteInPlace $out/share/applications/outlook-for-linux.desktop \
      --replace-fail "/opt/outlook-for-linux/outlook-for-linux" "$out/bin/outlook-for-linux"

    for icon in usr/share/icons/hicolor/*/apps/outlook-for-linux.png; do
      install -Dm644 "$icon" "$out/share/icons/''${icon#usr/share/icons/}"
    done

    makeWrapper $out/share/outlook-for-linux/outlook-for-linux $out/bin/outlook-for-linux \
      --add-flags "\''${NIXOS_OZONE_WL:+\''${WAYLAND_DISPLAY:+--ozone-platform-hint=auto --enable-features=WaylandWindowDecorations}}"

    runHook postInstall
  '';

  meta = {
    description = "Unofficial Microsoft Outlook client for Linux, an Electron wrapper around the web app";
    homepage = "https://github.com/mahmoudbahaa/outlook-for-linux";
    license = lib.licenses.gpl3Only;
    mainProgram = "outlook-for-linux";
    platforms = ["x86_64-linux"];
    sourceProvenance = [lib.sourceTypes.binaryNativeCode];
  };
})
