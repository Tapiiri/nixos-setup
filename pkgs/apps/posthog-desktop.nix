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
# PostHog Desktop, repackaged from the upstream .deb.
#
# Unlike most of the Electron apps here, upstream publishes Linux builds on a
# real release feed: GitHub releases on PostHog/posthog tagged `desktop-v*`.
# Bump with:
#   gh api repos/PostHog/posthog/releases --paginate \
#     -q '.[] | select(.tag_name|startswith("desktop-v")) | .tag_name' | head -1
# Linux does not self-update, so the pinned version is what you get.
stdenv.mkDerivation (finalAttrs: {
  pname = "posthog-desktop";
  version = "0.61.493";

  src = fetchurl {
    url = "https://github.com/PostHog/posthog/releases/download/desktop-v${finalAttrs.version}/PostHog-Desktop-${finalAttrs.version}-amd64-linux.deb";
    hash = "sha256-dTeWaPSC+7Y0FY0tmHOAofJiwpFB0cJLTs1s2j3oeRc=";
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

  # koffi ships both a glibc and a musl prebuild and picks one at runtime; the
  # musl copy is dead weight on NixOS and is the only thing wanting musl libc.
  autoPatchelfIgnoreMissingDeps = ["libc.musl-x86_64.so.1"];

  unpackPhase = ''
    runHook preUnpack
    dpkg-deb -x $src .
    runHook postUnpack
  '';

  installPhase = ''
    runHook preInstall

    mkdir -p $out/share/posthog-desktop
    cp -r opt/PostHog/. $out/share/posthog-desktop/

    # The bundled SUID sandbox helper cannot be setuid root from a Nix store
    # path; Electron uses unprivileged user namespaces on NixOS instead.
    rm -f $out/share/posthog-desktop/chrome-sandbox

    # Keep upstream's desktop file name: it is what registers the
    # posthog-code:// scheme handler in the xdg mime cache.
    install -Dm644 usr/share/applications/PostHog.desktop \
      $out/share/applications/PostHog.desktop
    substituteInPlace $out/share/applications/PostHog.desktop \
      --replace-fail "/opt/PostHog/PostHog" "$out/bin/posthog-desktop"

    for icon in usr/share/icons/hicolor/*/apps/PostHog.png; do
      install -Dm644 "$icon" "$out/share/icons/''${icon#usr/share/icons/}"
    done

    makeWrapper $out/share/posthog-desktop/PostHog $out/bin/posthog-desktop \
      --add-flags "\''${NIXOS_OZONE_WL:+\''${WAYLAND_DISPLAY:+--ozone-platform-hint=auto --enable-features=WaylandWindowDecorations}}"

    runHook postInstall
  '';

  meta = {
    description = "PostHog Desktop, the agentic workspace for product builders";
    homepage = "https://posthog.com/desktop";
    downloadPage = "https://posthog.com/docs/posthog-desktop/download-posthog-desktop";
    license = lib.licenses.unfree;
    mainProgram = "posthog-desktop";
    platforms = ["x86_64-linux"];
    sourceProvenance = [lib.sourceTypes.binaryNativeCode];
  };
})
