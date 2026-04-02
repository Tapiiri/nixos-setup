{
  lib,
  buildNpmPackage,
  fetchurl,
}:
buildNpmPackage (finalAttrs: {
  pname = "dokploy-cli";
  version = "0.2.8";

  src = fetchurl {
    url = "https://registry.npmjs.org/@dokploy/cli/-/cli-${finalAttrs.version}.tgz";
    hash = "sha512-lVyDKHbZmkyx9nW1oDu8TWR6kWE7y32Zqlh4U67Sz9a9cGOOyOPH05BHHyxZYtiBCAm9v7nK1auUHJr9I2ZgVw==";
  };

  postPatch = ''
    ln -s ${./dokploy-cli-package-lock.json} package-lock.json
  '';

  npmDepsHash = "sha256-YmrxWT5PXm/JyEXQ1sosCYeXHx4EOAoql4siMCuY6jE=";
  dontNpmBuild = true;

  npmPackFlags = [
    "--ignore-scripts"
  ];

  meta = {
    description = "CLI to manage Dokploy servers remotely";
    homepage = "https://github.com/Dokploy/cli";
    downloadPage = "https://www.npmjs.com/package/@dokploy/cli";
    license = lib.licenses.mit;
    mainProgram = "dokploy";
    platforms = lib.platforms.all;
  };
})
