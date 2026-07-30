"""NeoPOS Local uninstaller."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except ImportError:  # CLI cleanup must work on minimal Linux images too.
    tk = None
    messagebox = None
    ttk = None


PROJECT_NAME = "neopos-local"
TASK_NAME = "NeoPOS Local Services"
INSTALL_DIR = Path.home() / "NeoPOS"


def docker_cli() -> str | None:
    candidates = [shutil.which("docker")]
    if platform.system() == "Windows":
        candidates.extend(
            [
                os.path.join(os.environ.get("ProgramFiles", ""), "Docker", "Docker", "resources", "bin", "docker.exe"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Docker", "resources", "bin", "docker.exe"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "DockerDesktop", "resources", "bin", "docker.exe"),
            ]
        )
    return next((candidate for candidate in candidates if candidate and Path(candidate).is_file()), None)


def run(command: list[str], cwd: Path | None = None) -> tuple[bool, str]:
    try:
        completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        output = (completed.stdout or completed.stderr or "").strip()
        return completed.returncode == 0, output
    except OSError as error:
        return False, str(error)


def image_names() -> list[str]:
    manifest = INSTALL_DIR / "release-images.json"
    if not manifest.is_file():
        return []
    try:
        value = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    images = value.get("images", []) if isinstance(value, dict) else []
    return [str(item["name"]) for item in images if isinstance(item, dict) and item.get("name")]


def remove_autostart() -> None:
    if platform.system() == "Windows":
        run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
        desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop" / "NeoPOS.lnk"
        try:
            desktop.unlink(missing_ok=True)
        except OSError:
            pass
    elif platform.system() == "Linux":
        service = Path.home() / ".config" / "systemd" / "user" / "neopos-local.service"
        run(["systemctl", "--user", "disable", "--now", "neopos-local.service"])
        try:
            service.unlink(missing_ok=True)
        except OSError:
            pass


def remove_docker_installation(cli: str | None) -> list[str]:
    """Remove Docker only when the user explicitly requests it.

    Docker is shared by many applications. This path therefore remains
    completely separate from the normal NeoPOS cleanup and warns that the
    Docker uninstall also removes containers, images, and volumes globally.
    """
    messages: list[str] = []
    if cli:
        ok, output = run([cli, "system", "prune", "--all", "--volumes", "--force"])
        messages.append(
            "Recursos globales de Docker eliminados."
            if ok
            else f"No se pudieron limpiar todos los recursos globales de Docker: {output}"
        )

    if platform.system() == "Windows":
        # Docker's supported uninstaller is shipped separately from the
        # desktop UI. The old implementation attempted to run Docker
        # Desktop.exe, which only starts the application and does not uninstall
        # Docker Desktop.
        candidates = [
            Path(os.environ.get("ProgramFiles", ""))
            / "Docker"
            / "Docker"
            / "Docker Desktop Installer.exe",
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Programs"
            / "DockerDesktop"
            / "Docker Desktop Installer.exe",
        ]
        installer = next((path for path in candidates if path.is_file()), None)
        if installer is None:
            messages.append("No se encontró el desinstalador oficial de Docker Desktop.")
        else:
            ok, output = run([str(installer), "uninstall"])
            messages.append(
                "Docker Desktop desinstalado."
                if ok
                else f"Docker Desktop no pudo desinstalarse completamente: {output}"
            )
    elif platform.system() == "Linux":
        run(["sudo", "systemctl", "disable", "--now", "docker", "docker.socket", "containerd"])
        packages = [
            "docker-desktop",
            "docker-ce",
            "docker-ce-cli",
            "containerd.io",
            "docker-buildx-plugin",
            "docker-compose-plugin",
            "docker.io",
            "docker-compose-v2",
        ]
        ok, output = run(["sudo", "apt-get", "purge", "-y", *packages])
        messages.append(
            "Docker Desktop/Engine desinstalado."
            if ok
            else f"No se pudieron desinstalar todos los paquetes de Docker: {output}"
        )
        ok, output = run(["sudo", "apt-get", "autoremove", "--purge", "-y"])
        if not ok:
            messages.append(f"No se pudo completar la limpieza de paquetes: {output}")
    else:
        messages.append(
            f"La desinstalación automática de Docker no está implementada para {platform.system()}."
        )
    return messages


def uninstall(delete_data: bool, remove_images: bool, remove_docker: bool = False) -> list[str]:
    """Remove NeoPOS resources and optionally remove Docker itself."""
    messages: list[str] = []
    compose = INSTALL_DIR / "docker-compose.yml"
    cli = docker_cli()
    if cli and compose.is_file():
        command = [cli, "compose", "-p", PROJECT_NAME, "-f", str(compose), "down", "--remove-orphans"]
        if delete_data:
            command.append("--volumes")
        ok, output = run(command, INSTALL_DIR)
        messages.append("Servicios y contenedores detenidos." if ok else f"Docker no pudo detener completamente los servicios: {output}")
        if remove_images:
            for image in image_names():
                ok, output = run([cli, "image", "rm", "-f", image])
                messages.append(f"Imagen eliminada: {image}" if ok else f"No se pudo eliminar {image}: {output}")
    else:
        messages.append("No se encontró Docker Compose o la instalación ya estaba detenida.")

    remove_autostart()
    if delete_data and INSTALL_DIR.exists():
        try:
            shutil.rmtree(INSTALL_DIR)
            messages.append("Datos, configuración, respaldos y volúmenes de NeoPOS eliminados.")
        except OSError as error:
            messages.append(f"No se pudo borrar toda la carpeta de NeoPOS: {error}")
    else:
        messages.append("Datos conservados. Solo se retiraron los servicios de NeoPOS.")
    if remove_docker:
        messages.extend(remove_docker_installation(cli))
    else:
        messages.append("Docker Desktop/Engine se conserva y no se desinstala.")
    return messages


def cli_main(delete_data: bool, remove_images: bool, remove_docker: bool) -> int:
    messages = uninstall(delete_data, remove_images, remove_docker)
    print("\n".join(messages))
    return 0 if not any("No se pudo" in message for message in messages) else 1


_TkBase = tk.Tk if tk is not None else object


class Uninstaller(_TkBase):
    def __init__(self) -> None:
        if tk is None or ttk is None or messagebox is None:
            raise RuntimeError("La interfaz gráfica requiere Tk; usa --cli para desinstalar en este entorno.")
        super().__init__()
        self.title("Desinstalar NeoPOS")
        self.geometry("560x470")
        self.resizable(False, False)
        self.delete_data = tk.BooleanVar(value=False)
        self.remove_images = tk.BooleanVar(value=True)
        self.remove_docker = tk.BooleanVar(value=False)
        frame = ttk.Frame(self, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Desinstalar NeoPOS Local", font=("Segoe UI", 18, "bold")).pack(pady=(0, 12))
        ttk.Label(frame, text="Se eliminarán los contenedores, la tarea de inicio automático y la configuración del proyecto.", wraplength=500).pack(anchor="w")
        ttk.Checkbutton(frame, text="Eliminar también la BD, volúmenes, respaldos y datos locales", variable=self.delete_data).pack(anchor="w", pady=(22, 4))
        ttk.Checkbutton(frame, text="Eliminar imágenes Docker de NeoPOS", variable=self.remove_images).pack(anchor="w", pady=4)
        ttk.Checkbutton(frame, text="Desinstalar Docker Desktop/Engine y limpiar todos sus recursos", variable=self.remove_docker).pack(anchor="w", pady=4)
        ttk.Label(frame, text="Docker se conserva por defecto. Si marcas la opción anterior, también se eliminarán imágenes, contenedores y volúmenes de otros proyectos Docker.", foreground="#8a5a00", wraplength=500).pack(anchor="w", pady=14)
        self.status = ttk.Label(frame, text="", wraplength=500)
        self.status.pack(anchor="w", pady=5)
        ttk.Button(frame, text="Desinstalar", command=self.confirm).pack(side="right", pady=16)
        ttk.Button(frame, text="Cancelar", command=self.destroy).pack(side="right", padx=8, pady=16)

    def confirm(self) -> None:
        if self.delete_data.get() and not messagebox.askyesno("Confirmar borrado", "Esto eliminará la BD y los datos locales de NeoPOS. Esta acción no se puede deshacer. ¿Continuar?", parent=self):
            return
        if self.remove_docker.get() and not messagebox.askyesno(
            "Confirmar eliminación de Docker",
            "Esto desinstalará Docker Desktop/Engine y eliminará TODOS los contenedores, imágenes y volúmenes Docker del equipo, incluidos los de otros proyectos. ¿Continuar?",
            parent=self,
        ):
            return
        if not self.delete_data.get() and not messagebox.askyesno("Confirmar desinstalación", "¿Detener y retirar NeoPOS conservando los datos?", parent=self):
            return
        self.status.configure(text="Desinstalando...", foreground="#334155")
        self.update_idletasks()
        messages = uninstall(self.delete_data.get(), self.remove_images.get(), self.remove_docker.get())
        self.status.configure(text="\n".join(messages), foreground="#166534")
        messagebox.showinfo("NeoPOS desinstalado", "\n".join(messages), parent=self)
        self.destroy()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete-data", action="store_true")
    parser.add_argument("--remove-images", action="store_true")
    parser.add_argument("--remove-docker", action="store_true", help="Desinstala Docker y elimina todos sus recursos")
    parser.add_argument("--cli", action="store_true")
    args = parser.parse_args()
    if args.cli:
        return cli_main(args.delete_data, args.remove_images, args.remove_docker)
    app = Uninstaller()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
