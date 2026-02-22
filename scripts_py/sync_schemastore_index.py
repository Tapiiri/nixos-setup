from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from scripts_py.schemastore import (
    CatalogSchema,
    choose_schema_for_file,
    dump_json,
    schema_cache_filename,
)
from scripts_py.utils import RepoMarkers, log_error, log_info, repo_root_from_script_path

DEFAULT_CATALOG_URL = "https://www.schemastore.org/api/json/catalog.json"


def _http_get_json(url: str) -> Any:
    req = Request(url, headers={"User-Agent": "nixos-setup/schemastore-index"})
    with urlopen(req, timeout=30) as resp:
        raw = resp.read()
    return json.loads(raw.decode("utf-8"))


def _git_ls_files(repo_root: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        check=True,
        stdout=subprocess.PIPE,
    )
    return [p for p in proc.stdout.decode("utf-8").split("\0") if p]


def _parse_catalog_schemas(catalog: dict[str, Any]) -> list[CatalogSchema]:
    schemas: list[CatalogSchema] = []
    for entry in catalog.get("schemas", []):
        url = entry.get("url")
        name = entry.get("name")
        if not url or not name:
            continue

        file_match = tuple(entry.get("fileMatch") or ())
        if not file_match:
            continue

        schemas.append(
            CatalogSchema(
                name=str(name),
                url=str(url),
                description=(str(entry.get("description")) if entry.get("description") else None),
                file_match=tuple(str(p) for p in file_match),
            )
        )
    return schemas


def _download_schema(schema_url: str, *, dest: Path, refresh: bool) -> None:
    if dest.exists() and not refresh:
        return

    dest.parent.mkdir(parents=True, exist_ok=True)

    req = Request(schema_url, headers={"User-Agent": "nixos-setup/schemastore-index"})
    with urlopen(req, timeout=30) as resp:
        raw = resp.read()

    # Validate that it's JSON before writing.
    json.loads(raw.decode("utf-8"))

    dest.write_bytes(raw)


def sync_index(
    *,
    repo_root: Path,
    catalog_url: str,
    index_path: Path,
    schemas_dir: Path,
    refresh_schemas: bool,
    out,
    err,
) -> int:
    try:
        catalog = _http_get_json(catalog_url)
    except URLError as e:
        log_error(f"Failed to fetch SchemaStore catalog: {e}", err=err)
        return 2

    catalog_schemas = _parse_catalog_schemas(catalog)
    files = _git_ls_files(repo_root)

    file_to_schema_url: dict[str, str] = {}
    used_schema_urls: set[str] = set()

    for path in files:
        chosen = choose_schema_for_file(path, catalog_schemas)
        if not chosen:
            continue
        schema, _pattern = chosen
        file_to_schema_url[path] = schema.url
        used_schema_urls.add(schema.url)

    # Materialize schema cache entries for used schemas.
    schemas_dir.mkdir(parents=True, exist_ok=True)

    schema_entries: dict[str, dict[str, Any]] = {}
    for schema in catalog_schemas:
        if schema.url not in used_schema_urls:
            continue

        local_rel = schemas_dir.relative_to(repo_root) / schema_cache_filename(schema.url)
        local_abs = repo_root / local_rel

        try:
            _download_schema(schema.url, dest=local_abs, refresh=refresh_schemas)
        except Exception as e:  # noqa: BLE001
            log_error(f"Failed to download schema {schema.url}: {e}", err=err)
            return 2

        schema_entries[schema.url] = {
            "name": schema.name,
            "description": schema.description,
            "url": schema.url,
            "fileMatch": list(schema.file_match),
            "localPath": str(local_rel.as_posix()),
        }

    payload = {
        "schemaStore": {
            "catalogUrl": catalog_url,
            "fetchedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "catalogVersion": catalog.get("version"),
            "schemaCount": len(catalog_schemas),
        },
        "schemas": schema_entries,
        "files": dict(sorted(file_to_schema_url.items())),
    }

    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(dump_json(payload), encoding="utf-8")

    log_info(
        f"Indexed {len(file_to_schema_url)} files across {len(schema_entries)} schemas",
        out=out,
    )
    log_info(f"Wrote {index_path.relative_to(repo_root)}", out=out)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync SchemaStore schema index for this repo")
    parser.add_argument("--catalog-url", default=DEFAULT_CATALOG_URL)
    parser.add_argument(
        "--index",
        default="schemas/schemastore-index.json",
        help="Path to write the committed schema index",
    )
    parser.add_argument(
        "--schemas-dir",
        default="schemas/schemastore",
        help="Directory to store vendored schema JSON files",
    )
    parser.add_argument(
        "--refresh-schemas",
        action="store_true",
        help="Re-download schema JSON even if already present",
    )

    args = parser.parse_args(argv)

    repo_root = repo_root_from_script_path(Path(__file__), markers=RepoMarkers())
    index_path = repo_root / args.index
    schemas_dir = repo_root / args.schemas_dir

    return sync_index(
        repo_root=repo_root,
        catalog_url=args.catalog_url,
        index_path=index_path,
        schemas_dir=schemas_dir,
        refresh_schemas=args.refresh_schemas,
        out=sys.stdout,
        err=sys.stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main())
