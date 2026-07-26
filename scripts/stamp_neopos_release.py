"""Stamp the bundled NeoPOS Local archive with the installer release version."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path


REQUIRED_MEMBERS = {
    "start.ps1",
    "docker-compose.yml",
    "local/backend/.env.example",
    "release-images.json",
    "images/api.tar",
    "images/printer.tar",
    "images/frontend.tar",
}


def build_manifest(archive: zipfile.ZipFile, version: str) -> dict:
    manifest = {
        "schema_version": 1,
        "app_version": version,
        "database_migration": "additive",
        "breaking_changes": False,
        "release_notes": "Cambios compatibles y migraciones aditivas.",
    }
    try:
        manifest.update(json.loads(archive.read("release-manifest.json")))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError):
        pass
    manifest["app_version"] = version
    return manifest


def stamp_archive(archive_path: Path, manifest_path: Path, version: str) -> None:
    with zipfile.ZipFile(archive_path, "r") as source:
        members = {info.filename for info in source.infolist()}
        missing = REQUIRED_MEMBERS - members
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise RuntimeError(f"El paquete NeoPOS Local está incompleto: {missing_text}")

        manifest = build_manifest(source, version)
        archive_directory = archive_path.parent
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".zip", dir=archive_directory, delete=False
        ) as temporary_archive:
            temporary_path = Path(temporary_archive.name)

    try:
        with zipfile.ZipFile(archive_path, "r") as source, zipfile.ZipFile(
            temporary_path, "w", compression=zipfile.ZIP_DEFLATED
        ) as destination:
            for info in source.infolist():
                if info.filename == "release-manifest.json":
                    continue
                destination.writestr(info, source.read(info.filename))
            destination.writestr(
                "release-manifest.json",
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            )
        os.replace(temporary_path, archive_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()

    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "Uso: python scripts/stamp_neopos_release.py "
            "neopos-local.zip neopos-local-manifest.json",
            file=sys.stderr,
        )
        return 2

    version = os.environ.get("RELEASE_VERSION", "").strip()
    if not version:
        print("RELEASE_VERSION es obligatorio para publicar el paquete.", file=sys.stderr)
        return 2

    try:
        stamp_archive(Path(sys.argv[1]), Path(sys.argv[2]), version)
    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
        print(f"No se pudo preparar el paquete NeoPOS Local: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
