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
# Grok Bot desktop app (SpaceXAI LLC), repackaged from the upstream .deb.
#
# Upstream ships Linux builds on the Cursor CDN but does not advertise or
# document them -- the launch announcement lists only macOS/iOS/Android, and
# there is no Linux button on x.ai/bot. Treat version bumps as manual: there
# is no release feed to watch, and the URL embeds an opaque build commit.
stdenv.mkDerivation (finalAttrs: {
  pname = "grok-bot";
  version = "0.55.0";

  src = fetchurl {
    url = "https://downloads.cursor.com/grokbot/stable/b4d3f3b656b57c91705c69d2aea9dd31d6428748/linux/x64/grok-bot_${finalAttrs.version}_amd64.deb";
    hash = "sha256-VbOjjlgbngxR7cLeJV0zmyx8/t/5oW/dkI6HD7AWCjE=";
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

  # Electron dlopen()s libudev and libcurl at runtime rather than linking them,
  # so autoPatchelf cannot discover them from the ELF headers.
  runtimeDependencies = [(lib.getLib systemd)];

  unpackPhase = ''
    runHook preUnpack
    dpkg-deb -x $src .
    runHook postUnpack
  '';

  installPhase = ''
    runHook preInstall

    # Upstream has shipped this under both /opt and /usr/share across builds,
    # so resolve it rather than hardcoding one.
    appDir=""
    for candidate in opt/grok-bot opt/"Grok Bot" usr/share/grok-bot; do
      if [ -d "$candidate" ]; then
        appDir="$candidate"
        break
      fi
    done
    if [ -z "$appDir" ]; then
      echo "grok-bot: could not locate the app directory in the .deb. Contents:"
      find opt usr/share -maxdepth 2 2>/dev/null || true
      exit 1
    fi

    mkdir -p $out/share/grok-bot
    cp -r "$appDir"/. $out/share/grok-bot/

    # The bundled SUID sandbox helper cannot be setuid root from a Nix store
    # path; Electron uses unprivileged user namespaces on NixOS instead.
    rm -f $out/share/grok-bot/chrome-sandbox

    install -Dm644 usr/share/applications/grok-bot.desktop \
      $out/share/applications/grok-bot.desktop
    substituteInPlace $out/share/applications/grok-bot.desktop \
      --replace-quiet "/opt/grok-bot/grok-bot" "$out/bin/grok-bot" \
      --replace-quiet "/usr/share/grok-bot/grok-bot" "$out/bin/grok-bot"

    for icon in usr/share/icons/hicolor/*/apps/grok-bot.png; do
      [ -e "$icon" ] || continue
      install -Dm644 "$icon" "$out/share/icons/''${icon#usr/share/icons/}"
    done

    makeWrapper $out/share/grok-bot/grok-bot $out/bin/grok-bot \
      --add-flags "\''${NIXOS_OZONE_WL:+\''${WAYLAND_DISPLAY:+--ozone-platform-hint=auto --enable-features=WaylandWindowDecorations}}"

    runHook postInstall
  '';

  meta = {
    description = "Always-on AI agent desktop app by SpaceXAI";
    homepage = "https://x.ai/bot";
    downloadPage = "https://cursor.com/download/bot";
    license = lib.licenses.unfree;
    mainProgram = "grok-bot";
    platforms = ["x86_64-linux"];
    sourceProvenance = [lib.sourceTypes.binaryNativeCode];
  };
})
