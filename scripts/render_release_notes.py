"""Render GitHub release notes from the public NeoPOS Local manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def render_release_notes(manifest: dict) -> str:
    version = str(manifest.get("app_version", "")).strip()
    notes = str(manifest.get("release_notes", "")).strip()
    if not version:
        raise ValueError("El manifiesto no contiene app_version.")
    if not notes:
        raise ValueError("El manifiesto no contiene release_notes.")

    migration = str(manifest.get("database_migration", "unknown")).strip()
    breaking = bool(manifest.get("breaking_changes", False))
    compatibility = "Requiere confirmación manual" if breaking else "Actualización compatible"
    return (
        f"## Novedades de NeoPOS Local {version}\n\n"
        f"{notes}\n\n"
        "## Compatibilidad\n\n"
        f"- Base de datos: `{migration}`.\n"
        f"- Instalación: {compatibility}.\n"
        "- Los volúmenes de PostgreSQL, MinIO y backups se conservan durante la actualización.\n"
    )


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "Uso: python scripts/render_release_notes.py "
            "neopos-local-manifest.json release-notes.md",
            file=sys.stderr,
        )
        return 2

    source = Path(sys.argv[1])
    destination = Path(sys.argv[2])
    try:
        manifest = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("El manifiesto debe ser un objeto JSON.")
        destination.write_text(render_release_notes(manifest), encoding="utf-8")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"No se pudieron generar las notas de la release: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
