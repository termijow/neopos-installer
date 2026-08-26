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
    "Abrir_NeoPOS.bat",
    "init.sql",
    "local/backend/.env.example",
    "release-images.json",
    "images/api.tar",
    "images/printer.tar",
    "images/frontend.tar",
}
FORBIDDEN_SUFFIXES = (".go", ".ts", ".tsx", ".js", ".jsx", "Dockerfile", ".env")
PERSISTENT_VOLUME_MOUNTS = (
    "postgres-data:/var/lib/postgresql/data",
    "minio-data:/data",
)


def validate_source_free_archive(archive: zipfile.ZipFile, expected_version: str) -> None:
    members = set()
    for info in archive.infolist():
        name = info.filename.replace("\\", "/")
        if not name or name.endswith("/"):
            continue
        parts = name.split("/")
        if name.startswith("/") or any(part in {"", ".", ".."} for part in parts):
            raise RuntimeError(f"El paquete contiene una ruta inválida: {info.filename}")
        mode = (info.external_attr >> 16) & 0o170000
        if mode == 0o120000:
            raise RuntimeError(f"El paquete contiene un enlace simbólico no permitido: {name}")
        members.add(name)

    missing = REQUIRED_MEMBERS - members
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise RuntimeError(f"El paquete NeoPOS Local está incompleto: {missing_text}")

    try:
        compose_text = archive.read("docker-compose.yml").decode("utf-8")
    except (KeyError, UnicodeDecodeError) as error:
        raise RuntimeError(f"No se pudo leer docker-compose.yml: {error}") from error
    missing_mounts = [mount for mount in PERSISTENT_VOLUME_MOUNTS if mount not in compose_text]
    if missing_mounts:
        raise RuntimeError(
            "El paquete no conserva los volúmenes persistentes requeridos: "
            + ", ".join(missing_mounts)
        )

    forbidden = sorted(
        name
        for name in members
        if name.endswith(FORBIDDEN_SUFFIXES)
        or name.startswith((".git/", "local/backend/internal/", "local/frontend/src/"))
    )
    if forbidden:
        raise RuntimeError(
            "El paquete contiene código fuente o secretos: " + ", ".join(forbidden[:12])
        )

    try:
        manifest = json.loads(archive.read("release-images.json").decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"No se pudo leer release-images.json: {error}") from error
    images = manifest.get("images") if isinstance(manifest, dict) else None
    if not isinstance(images, list) or not images:
        raise RuntimeError("release-images.json no contiene imágenes de producción.")

    try:
        release_manifest = json.loads(archive.read("release-manifest.json").decode("utf-8"))
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError(f"No se pudo leer release-manifest.json: {error}") from error
    package_version = release_manifest.get("app_version") if isinstance(release_manifest, dict) else None
    if package_version != expected_version:
        raise RuntimeError(
            f"La versión del paquete ({package_version}) no coincide con la release ({expected_version})."
        )

    for image in images:
        if not isinstance(image, dict) or not image.get("name"):
            raise RuntimeError("release-images.json contiene una imagen incompleta.")
        image_path = str(image.get("archive", "")).replace("\\", "/")
        if image_path.startswith("/") or ".." in image_path.split("/") or image_path not in members:
            raise RuntimeError(f"No se encontró la imagen declarada: {image_path}")
        if str(image["name"]).startswith("neopos-local-"):
            image_tag = str(image["name"]).rsplit(":", 1)[-1]
            if image_tag != expected_version:
                raise RuntimeError(
                    f"La imagen {image['name']} no coincide con la release {expected_version}."
                )

    corrupt_member = archive.testzip()
    if corrupt_member is not None:
        raise RuntimeError(f"El ZIP está corrupto: {corrupt_member}")


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
    manifest["version"] = version
    manifest["notes"] = manifest.get("release_notes", "")
    manifest["download_url"] = "https://github.com/termijow/neopos-installer/releases/latest"
    manifest["download_urls"] = {
        "windows": "https://github.com/termijow/neopos-installer/releases/latest/download/NeoPOS-Installer.exe",
        "linux": "https://github.com/termijow/neopos-installer/releases/latest/download/NeoPOS-Installer-Linux",
    }
    return manifest


def stamp_archive(archive_path: Path, manifest_path: Path, version: str) -> None:
    with zipfile.ZipFile(archive_path, "r") as source:
        validate_source_free_archive(source, version)

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
