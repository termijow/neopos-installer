import customtkinter as ctk
import tkinter.messagebox as messagebox
import sys
import json
import os
import subprocess
import threading
import time
import platform
import secrets
import shutil
import tempfile
from datetime import datetime
import urllib.error
import urllib.request
import webbrowser
import zipfile


NEOPOS_LOCAL_RELEASE_URL = (
    "https://github.com/termijow/neopos-installer/releases/latest/download/neopos-local.zip"
)
NEOPOS_LOCAL_MANIFEST_URL = (
    "https://github.com/termijow/neopos-installer/releases/latest/download/neopos-local-manifest.json"
)
WINDOWS_AUTOSTART_TASK = "NeoPOS Local Services"
LOCAL_COMPOSE_SERVICES = {"api", "frontend", "postgres", "printer", "minio"}
LOCAL_FRONTEND_URL = "http://127.0.0.1:5173"
DOCKER_READY_TIMEOUT_SECONDS = 180
LOCAL_SERVICES_READY_TIMEOUT_SECONDS = 180
BUNDLED_RELEASE_FILENAME = "neopos-local.zip"
REQUIRED_RELEASE_MEMBERS = {
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
FORBIDDEN_RELEASE_SUFFIXES = (
    ".go",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    "Dockerfile",
    ".env",
)

ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class NeoPOSInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.install_dir = None
        self.confirmed_breaking_version = None
        self.log_path = os.path.join(tempfile.gettempdir(), "neopos-installer.log")
        self.install_log_path = os.path.join(
            os.path.expanduser("~"), "NeoPOS", "installer.log"
        )
        self.logs_visible = True
        self.task_running = False

        self.title("NeoPOS Installer")
        self.geometry("820x500")
        self.resizable(False, False)

        # Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Main Frame
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Welcome Title
        self.title_label = ctk.CTkLabel(self.main_frame, text="Welcome to NeoPOS", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.grid(row=0, column=0, padx=20, pady=(30, 10))

        # Subtitle
        self.subtitle_label = ctk.CTkLabel(self.main_frame, text="Choose your installation type below:", font=ctk.CTkFont(size=14))
        self.subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 30))

        # Options Frame
        self.options_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.options_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        self.options_frame.grid_columnconfigure(0, weight=1)
        self.options_frame.grid_columnconfigure(1, weight=1)
        self.options_frame.grid_columnconfigure(2, weight=1)

        # Full installation/update button
        self.app_btn = ctk.CTkButton(
            self.options_frame, 
            text="Instalar / Actualizar NeoPOS",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=80,
            command=self.install_app
        )
        self.app_btn.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        # Full installation/update with web shortcut flow
        self.web_btn = ctk.CTkButton(
            self.options_frame, 
            text="Instalar y abrir Web",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=80,
            fg_color="#2b7a54",
            hover_color="#1e573b",
            command=self.install_web
        )
        self.web_btn.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # Start/repair an existing local installation without downloading it again.
        self.repair_btn = ctk.CTkButton(
            self.options_frame,
            text="Iniciar / Reparar servicios",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=80,
            fg_color="#8a5a00",
            hover_color="#6b4600",
            command=self.start_services,
        )
        self.repair_btn.grid(row=0, column=2, padx=10, pady=10, sticky="ew")

        # Descriptions
        self.app_desc = ctk.CTkLabel(
            self.options_frame, 
            text="Instala Docker, NeoPOS Local y\nconfigura el inicio automático.",
            text_color="gray",
            font=ctk.CTkFont(size=12)
        )
        self.app_desc.grid(row=1, column=0, padx=10, pady=0)

        self.web_desc = ctk.CTkLabel(
            self.options_frame, 
            text="Instala los servicios y abre\nel POS en el navegador.",
            text_color="gray",
            font=ctk.CTkFont(size=12)
        )
        self.web_desc.grid(row=1, column=1, padx=10, pady=0)

        self.repair_desc = ctk.CTkLabel(
            self.options_frame,
            text="Usa una instalación existente y levanta\nlos contenedores sin descargarla otra vez.",
            text_color="gray",
            font=ctk.CTkFont(size=12),
        )
        self.repair_desc.grid(row=1, column=2, padx=10, pady=0)

        # Progress Frame (Hidden initially)
        self.progress_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.progress_frame.grid_columnconfigure(0, weight=1)
        self.progress_frame.grid_rowconfigure(3, weight=1)

        self.progress_label = ctk.CTkLabel(self.progress_frame, text="Preparando...", font=ctk.CTkFont(size=14))
        self.progress_label.grid(row=0, column=0, pady=(10, 10))

        self.progressbar = ctk.CTkProgressBar(self.progress_frame, mode="indeterminate")
        self.progressbar.grid(row=1, column=0, sticky="ew", padx=40, pady=(0, 10))

        self.progress_actions = ctk.CTkFrame(self.progress_frame, fg_color="transparent")
        self.progress_actions.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 6))
        self.progress_actions.grid_columnconfigure(0, weight=1)
        self.progress_actions.grid_columnconfigure(1, weight=1)
        self.progress_actions.grid_columnconfigure(2, weight=1)

        self.log_toggle_btn = ctk.CTkButton(
            self.progress_actions,
            text="Ocultar logs",
            command=self.toggle_logs,
        )
        self.log_toggle_btn.grid(row=0, column=0, padx=4, sticky="ew")

        self.open_log_btn = ctk.CTkButton(
            self.progress_actions,
            text="Abrir carpeta de logs",
            command=self.open_log_location,
        )
        self.open_log_btn.grid(row=0, column=1, padx=4, sticky="ew")

        self.close_btn = ctk.CTkButton(
            self.progress_actions,
            text="Cerrar",
            command=self.destroy,
            state="disabled",
        )
        self.close_btn.grid(row=0, column=2, padx=4, sticky="ew")

        self.log_box = ctk.CTkTextbox(self.progress_frame, height=150, font=ctk.CTkFont(size=12, family="Consolas"))
        self.log_box.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 4))
        self.log_box.insert("0.0", "Iniciando proceso de instalación...\n")
        self.log_box.configure(state="disabled")

        self.log_path_label = ctk.CTkLabel(
            self.progress_frame,
            text=f"Log principal: {self.install_log_path}\nCopia temporal: {self.log_path}",
            text_color="gray",
            font=ctk.CTkFont(size=10),
            wraplength=760,
        )
        self.log_path_label.grid(row=4, column=0, padx=20, pady=(0, 6), sticky="w")

    def append_log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        for path in {self.log_path, self.install_log_path}:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "a", encoding="utf-8") as log_file:
                    log_file.write(text + "\n")
            except OSError:
                pass
        print(text)

    def show_progress(self):
        self.task_running = True
        for button in (self.app_btn, self.web_btn, self.repair_btn):
            button.configure(state="disabled")
        self.close_btn.configure(state="disabled")
        self.log_toggle_btn.configure(state="normal")
        self.open_log_btn.configure(state="normal")
        self.options_frame.grid_forget()
        self.progress_frame.grid(row=2, column=0, padx=20, pady=20, sticky="ew")
        self.progressbar.start()

    def toggle_logs(self):
        self.logs_visible = not self.logs_visible
        if self.logs_visible:
            self.log_box.grid(row=3, column=0, sticky="nsew", padx=20, pady=(0, 4))
            self.log_toggle_btn.configure(text="Ocultar logs")
        else:
            self.log_box.grid_forget()
            self.log_toggle_btn.configure(text="Mostrar logs")

    def open_log_location(self):
        path = self.install_log_path if os.path.exists(self.install_log_path) else self.log_path
        directory = os.path.dirname(path)
        try:
            if platform.system() == "Windows":
                os.startfile(directory)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", directory])
            else:
                subprocess.Popen(["xdg-open", directory])
        except (OSError, AttributeError) as error:
            self.append_log(f"[ERROR] No se pudo abrir la carpeta de logs: {error}")

    def run_streaming_process(self, command, cwd=None, env=None):
        """Run a process while forwarding stdout/stderr to the visible log."""
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
        )
        if process.stdout is not None:
            for line in process.stdout:
                line = line.rstrip()
                if line:
                    self.after(0, lambda value=line: self.append_log(value))
        return process.wait()

    @staticmethod
    def find_bundled_release():
        """Find the production ZIP embedded by PyInstaller or next to main.py."""
        locations = []
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            locations.append(meipass)
        locations.append(os.path.dirname(os.path.abspath(__file__)))
        locations.append(os.path.dirname(os.path.abspath(sys.executable)))

        seen = set()
        for location in locations:
            if not location or location in seen:
                continue
            seen.add(location)
            candidate = os.path.join(location, BUNDLED_RELEASE_FILENAME)
            if os.path.isfile(candidate):
                return candidate
        return None

    @classmethod
    def validate_release_zip(cls, zip_ref, source_label="el paquete"):
        """Validate the source-free production package before it is extracted."""
        members = set()
        for info in zip_ref.infolist():
            name = info.filename.replace("\\", "/")
            if not name or name.endswith("/"):
                continue
            parts = name.split("/")
            if name.startswith("/") or any(part in {"", ".", ".."} for part in parts):
                raise RuntimeError(f"{source_label} contiene una ruta inválida: {info.filename}")
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise RuntimeError(f"{source_label} contiene un enlace simbólico no permitido: {name}")
            members.add(name)

        missing = sorted(REQUIRED_RELEASE_MEMBERS - members)
        if missing:
            raise RuntimeError(
                "La build de producción está incompleta. Falta(n): " + ", ".join(missing)
            )

        forbidden = sorted(
            name
            for name in members
            if name.endswith(FORBIDDEN_RELEASE_SUFFIXES)
            or name.startswith((".git/", "local/backend/internal/", "local/frontend/src/"))
        )
        if forbidden:
            raise RuntimeError(
                "La build de producción contiene código fuente o secretos: "
                + ", ".join(forbidden[:12])
            )

        try:
            manifest = json.loads(zip_ref.read("release-images.json").decode("utf-8"))
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeError(f"No se pudo leer release-images.json: {error}") from error

        images = manifest.get("images") if isinstance(manifest, dict) else None
        if not isinstance(images, list) or not images:
            raise RuntimeError("release-images.json no contiene imágenes de producción.")
        for image in images:
            if not isinstance(image, dict):
                raise RuntimeError("release-images.json contiene una imagen inválida.")
            image_name = image.get("name")
            archive = str(image.get("archive", "")).replace("\\", "/")
            if not image_name or not archive or archive.startswith("/") or ".." in archive.split("/"):
                raise RuntimeError("release-images.json contiene una ruta de imagen inválida.")
            if archive not in members:
                raise RuntimeError(f"No se encontró la imagen de producción declarada: {archive}")

        corrupt_member = zip_ref.testzip()
        if corrupt_member is not None:
            raise RuntimeError(f"El ZIP de producción está corrupto: {corrupt_member}")

    @classmethod
    def validate_release_file(cls, archive_path):
        try:
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                cls.validate_release_zip(zip_ref, os.path.basename(archive_path))
        except zipfile.BadZipFile as error:
            raise RuntimeError(f"El archivo de producción no es un ZIP válido: {error}") from error

    @classmethod
    def validate_extracted_release(cls, install_dir):
        missing = sorted(
            member
            for member in REQUIRED_RELEASE_MEMBERS
            if not os.path.isfile(os.path.join(install_dir, *member.split("/")))
        )
        if missing:
            raise RuntimeError(
                "La instalación quedó incompleta; falta(n): " + ", ".join(missing)
            )

    @staticmethod
    def _read_env_file(env_path):
        values = {}
        if not os.path.exists(env_path):
            return values
        with open(env_path, "r", encoding="utf-8-sig") as env_file:
            for line in env_file:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value
        return values

    @staticmethod
    def _write_env_value(env_path, key, value):
        lines = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8-sig") as env_file:
                lines = env_file.read().splitlines()
        prefix = f"{key}="
        for index, line in enumerate(lines):
            if line.startswith(prefix):
                lines[index] = f"{key}={value}"
                break
        else:
            lines.append(f"{key}={value}")
        with open(env_path, "w", encoding="utf-8", newline="\n") as env_file:
            env_file.write("\n".join(lines) + "\n")
        try:
            os.chmod(env_path, 0o600)
        except OSError:
            pass

    def ensure_runtime_environment(self, install_dir):
        """Create local secrets without putting credentials in the release ZIP."""
        backend_dir = os.path.join(install_dir, "local", "backend")
        backend_env = os.path.join(backend_dir, ".env")
        root_env = os.path.join(install_dir, ".env")
        os.makedirs(backend_dir, exist_ok=True)
        legacy_install = os.path.exists(backend_env)

        root_values = self._read_env_file(root_env)
        postgres_password = root_values.get("POSTGRES_PASSWORD", "")
        minio_user = root_values.get("MINIO_ROOT_USER", "")
        minio_password = root_values.get("MINIO_ROOT_PASSWORD", "")
        if not postgres_password:
            postgres_password = "pos" if legacy_install else secrets.token_hex(32)
            self._write_env_value(root_env, "POSTGRES_PASSWORD", postgres_password)
        if not minio_user:
            minio_user = "admin" if legacy_install else "neopos-minio"
            self._write_env_value(root_env, "MINIO_ROOT_USER", minio_user)
        if not minio_password:
            minio_password = "password123" if legacy_install else secrets.token_hex(32)
            self._write_env_value(root_env, "MINIO_ROOT_PASSWORD", minio_password)

        if not os.path.exists(backend_env):
            example_path = os.path.join(backend_dir, ".env.example")
            if not os.path.isfile(example_path):
                raise RuntimeError(
                    "Falta la carpeta o configuración de producción: " + example_path
                )
            shutil.copy2(example_path, backend_env)
            admin_password = secrets.token_hex(24)
            self._write_env_value(backend_env, "APP_ENV", "production")
            self._write_env_value(
                backend_env,
                "DATABASE_URL",
                f"postgres://pos:{postgres_password}@postgres:5432/pos?sslmode=disable",
            )
            self._write_env_value(backend_env, "JWT_SECRET", secrets.token_hex(32))
            self._write_env_value(backend_env, "ADMIN_PASSWORD", admin_password)
            cashier_password = secrets.token_hex(24)
            self._write_env_value(backend_env, "CASHIER_PASSWORD", cashier_password)
            self._write_env_value(backend_env, "MINIO_ROOT_USER", minio_user)
            self._write_env_value(backend_env, "MINIO_ROOT_PASSWORD", minio_password)

            credentials_path = os.path.join(install_dir, "admin-credentials.txt")
            with open(credentials_path, "w", encoding="utf-8", newline="\n") as credentials:
                credentials.write(
                    "NeoPOS Local - credenciales iniciales\n"
                    f"Administrador: {self._read_env_file(backend_env).get('ADMIN_EMAIL', 'admin@pos.local')}\n"
                    f"Contraseña: {admin_password}\n\n"
                    f"Cajero: {self._read_env_file(backend_env).get('CASHIER_EMAIL', 'cajero@neopos.com')}\n"
                    f"Contraseña: {cashier_password}\n\n"
                    "Guarda este archivo en un lugar seguro y elimínalo cuando cambies la contraseña.\n"
                )
            try:
                os.chmod(credentials_path, 0o600)
            except OSError:
                pass
        else:
            backend_values = self._read_env_file(backend_env)
            self._write_env_value(
                backend_env,
                "MINIO_ROOT_USER",
                backend_values.get("MINIO_ROOT_USER") or minio_user,
            )
            self._write_env_value(
                backend_env,
                "MINIO_ROOT_PASSWORD",
                backend_values.get("MINIO_ROOT_PASSWORD") or minio_password,
            )

    def ensure_release_images(self, docker_cli, install_dir):
        """Load every bundled production image and fail clearly if one is missing."""
        manifest_path = os.path.join(install_dir, "release-images.json")
        if not os.path.exists(manifest_path):
            raise RuntimeError(
                "No se encontró release-images.json en la instalación. "
                "La build de producción no se extrajo completa."
            )

        try:
            with open(manifest_path, "r", encoding="utf-8") as manifest_file:
                manifest = json.load(manifest_file)
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"No se pudo leer release-images.json: {error}") from error

        images = manifest.get("images") if isinstance(manifest, dict) else None
        if not isinstance(images, list) or not images:
            raise RuntimeError("release-images.json no contiene imágenes de producción.")

        install_root = os.path.abspath(install_dir)
        for image in images:
            image_name = image.get("name")
            archive = image.get("archive")
            if not image_name or not archive:
                raise RuntimeError("release-images.json contiene una imagen incompleta.")

            inspect = subprocess.run(
                [docker_cli, "image", "inspect", image_name],
                capture_output=True,
                text=True,
            )
            if inspect.returncode == 0:
                self.after(0, lambda name=image_name: self.append_log(
                    f"[IMAGE] {name} ya está cargada."
                ))
                continue

            archive_path = os.path.abspath(os.path.join(install_dir, archive))
            if os.path.commonpath((install_root, archive_path)) != install_root:
                raise RuntimeError(f"La ruta de imagen no es segura: {archive}")
            if not os.path.exists(archive_path):
                raise RuntimeError(f"No se encontró la imagen de producción: {archive_path}")

            self.after(0, lambda name=image_name: self.append_log(
                f"[IMAGE] Cargando {name}..."
            ))
            load_command = [docker_cli, "load", "--input", archive_path]
            if platform.system() == "Linux" and os.geteuid() != 0:
                load_command.insert(0, "sudo")
            returncode = self.run_streaming_process(load_command, cwd=install_dir)
            if returncode != 0:
                raise RuntimeError(f"No se pudo cargar la imagen {image_name}.")

    def finish_with_error(self, title, error):
        self.task_running = False
        self.progressbar.stop()
        self.progress_label.configure(text="La operación terminó con errores")
        self.append_log(f"[ERROR] {error}")
        self.close_btn.configure(state="normal")
        self.open_log_btn.configure(state="normal")
        messagebox.showerror(
            title,
            f"{error}\n\nLog principal:\n{self.install_log_path}\n\n"
            f"Copia temporal:\n{self.log_path}",
        )

    def register_windows_autostart(self, install_dir):
        """Make Docker Compose start after login and survive process failures."""
        start_script = os.path.join(install_dir, "start.ps1")
        username = os.environ.get("USERNAME") or os.getlogin()
        command = (
            f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{start_script}" '
            "--local --auto"
        )
        result = subprocess.run(
            [
                "schtasks",
                "/Create",
                "/TN",
                WINDOWS_AUTOSTART_TASK,
                "/SC",
                "ONLOGON",
                "/DELAY",
                "0000:30",
                "/RU",
                username,
                "/RL",
                "LIMITED",
                "/TR",
                command,
                "/F",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            details = (result.stderr or result.stdout).strip()
            raise RuntimeError(
                "No se pudo configurar el inicio automático de NeoPOS. "
                f"El Programador de tareas respondió: {details}"
            )
        self.after(0, lambda: self.append_log(
            "[+] Inicio automático configurado: los servicios se levantan al iniciar sesión "
            "y Docker Compose los recupera si se caen."
        ))

    def register_linux_autostart(self, install_dir):
        """Register a systemd unit for Linux installations."""
        compose_file = os.path.join(install_dir, "docker-compose.yml")
        unit = f"""[Unit]
Description=NeoPOS Local Services
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
WorkingDirectory={install_dir}
ExecStart=/usr/bin/docker compose -f {compose_file} up -d --remove-orphans
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""
        with tempfile.NamedTemporaryFile("w", suffix=".service", delete=False) as unit_file:
            unit_file.write(unit)
            unit_path = unit_file.name
        try:
            subprocess.run(
                ["sudo", "install", "-m", "0644", unit_path, "/etc/systemd/system/neopos-local.service"],
                check=True,
            )
            subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
            subprocess.run(["sudo", "systemctl", "enable", "--now", "neopos-local.service"], check=True)
        finally:
            try:
                os.remove(unit_path)
            except OSError:
                pass
        self.after(0, lambda: self.append_log(
            "[+] Servicio systemd configurado para iniciar NeoPOS al arrancar Linux."
        ))

    def verify_windows_virtualization(self):
        """Fail early with a useful message when BIOS virtualization is disabled."""
        if platform.system() != "Windows":
            return

        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty VirtualizationFirmwareEnabled)",
            ],
            capture_output=True,
            text=True,
        )
        value = result.stdout.strip().lower()
        if result.returncode == 0 and value in {"false", "no"}:
            raise RuntimeError(
                "Este equipo no tiene activada la virtualización de hardware.\n\n"
                "Antes de instalar NeoPOS, reinicia el equipo y activa en BIOS/UEFI "
                "Intel Virtualization Technology (VT-x) o AMD SVM/AMD-V.\n\n"
                "Después guarda los cambios, inicia Windows y vuelve a ejecutar el instalador."
            )

        if result.returncode != 0 or value not in {"true", "yes"}:
            self.after(0, lambda: self.append_log(
                "[!] No se pudo confirmar el estado de virtualización; Docker validará el requisito."
            ))

    def find_docker_cli(self):
        candidates = []
        docker_from_path = shutil.which("docker")
        if docker_from_path:
            candidates.append(docker_from_path)
        if platform.system() == "Windows":
            program_files = os.environ.get("ProgramFiles")
            local_app_data = os.environ.get("LOCALAPPDATA")
            if program_files:
                candidates.append(os.path.join(program_files, "Docker", "Docker", "resources", "bin", "docker.exe"))
            if local_app_data:
                candidates.append(os.path.join(local_app_data, "Programs", "Docker", "resources", "bin", "docker.exe"))
        for candidate in candidates:
            if os.path.isfile(candidate):
                return candidate
        return None

    @staticmethod
    def find_powershell():
        """Resolve Windows PowerShell even when the installer has a stale PATH."""
        candidates = [shutil.which("powershell.exe"), shutil.which("powershell")]
        system_root = os.environ.get("SystemRoot")
        if system_root:
            candidates.append(
                os.path.join(
                    system_root,
                    "System32",
                    "WindowsPowerShell",
                    "v1.0",
                    "powershell.exe",
                )
            )
        for candidate in candidates:
            if candidate and os.path.isfile(candidate):
                return candidate
        return None

    def ensure_docker_ready(self, docker_cli):
        """Start Docker Desktop when needed and wait for a usable daemon."""
        if platform.system() == "Windows":
            docker_info = subprocess.run(
                [docker_cli, "info"], capture_output=True, text=True
            )
            if docker_info.returncode != 0:
                desktop_candidates = []
                if os.environ.get("ProgramFiles"):
                    desktop_candidates.append(
                        os.path.join(
                            os.environ["ProgramFiles"],
                            "Docker",
                            "Docker",
                            "Docker Desktop.exe",
                        )
                    )
                if os.environ.get("LOCALAPPDATA"):
                    desktop_candidates.append(
                        os.path.join(
                            os.environ["LOCALAPPDATA"],
                            "Programs",
                            "Docker",
                            "Docker Desktop.exe",
                        )
                    )
                for desktop in desktop_candidates:
                    if os.path.exists(desktop):
                        self.after(0, lambda: self.append_log(
                            "[*] Iniciando Docker Desktop y esperando al daemon..."
                        ))
                        subprocess.Popen(
                            [desktop],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        )
                        break

        attempts = max(1, DOCKER_READY_TIMEOUT_SECONDS // 2)
        for attempt in range(1, attempts + 1):
            result = subprocess.run(
                [docker_cli, "info"], capture_output=True, text=True
            )
            if result.returncode == 0:
                self.after(0, lambda: self.append_log("[+] Docker daemon disponible."))
                return
            self.after(0, lambda attempt=attempt: self.append_log(
                f"[*] Esperando a Docker Desktop... ({attempt}/{attempts})"
            ))
            time.sleep(2)

        details = (result.stderr or result.stdout).strip()
        raise RuntimeError(
            f"Docker Desktop está instalado, pero el daemon no respondió después de "
            f"{DOCKER_READY_TIMEOUT_SECONDS} segundos. "
            "Verifica que WSL2/virtualización estén habilitados y vuelve a ejecutar el instalador. "
            f"Detalle: {details}"
        )

    @staticmethod
    def _trim_process_output(value, limit=12000):
        value = (value or "").strip()
        if len(value) <= limit:
            return value
        return "...\n" + value[-limit:]

    def wait_for_local_services(self, docker_cli, compose_file):
        """Wait until Compose reports every local service running and the UI answers."""
        compose = [
            docker_cli,
            "compose",
            "-p",
            "neopos-local",
            "-f",
            compose_file,
        ]
        deadline = time.monotonic() + LOCAL_SERVICES_READY_TIMEOUT_SECONDS
        last_details = ""

        while time.monotonic() < deadline:
            status = subprocess.run(
                compose + ["ps", "--services", "--status", "running"],
                cwd=os.path.dirname(compose_file),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            running_services = {
                line.strip()
                for line in status.stdout.splitlines()
                if line.strip()
            }
            missing = LOCAL_COMPOSE_SERVICES - running_services
            last_details = self._trim_process_output(status.stderr or status.stdout)

            frontend_ready = False
            if not missing:
                try:
                    with urllib.request.urlopen(LOCAL_FRONTEND_URL, timeout=5) as response:
                        frontend_ready = 200 <= response.status < 500
                except (OSError, urllib.error.URLError):
                    frontend_ready = False

            if status.returncode == 0 and not missing and frontend_ready:
                self.after(0, lambda: self.append_log(
                    "[+] NeoPOS Local está disponible: todos los servicios están activos "
                    "y el frontend responde en http://localhost:5173."
                ))
                return

            elapsed = LOCAL_SERVICES_READY_TIMEOUT_SECONDS - max(
                0, int(deadline - time.monotonic())
            )
            if elapsed == 0 or elapsed % 10 == 0:
                missing_text = ", ".join(sorted(missing)) or "frontend aún no responde"
                self.after(0, lambda missing_text=missing_text: self.append_log(
                    f"[*] Esperando servicios NeoPOS Local ({missing_text})..."
                ))
            time.sleep(2)

        diagnostics = subprocess.run(
            compose + ["ps", "-a"],
            cwd=os.path.dirname(compose_file),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        logs = subprocess.run(
            compose + ["logs", "--tail", "80"],
            cwd=os.path.dirname(compose_file),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        diagnostic_text = self._trim_process_output(
            diagnostics.stdout or diagnostics.stderr
        )
        log_text = self._trim_process_output(logs.stdout or logs.stderr)
        raise RuntimeError(
            "Docker Compose terminó, pero NeoPOS Local no quedó listo después de "
            f"{LOCAL_SERVICES_READY_TIMEOUT_SECONDS} segundos.\n\n"
            f"Estado de contenedores:\n{diagnostic_text or last_details or 'sin salida'}\n\n"
            f"Últimos logs:\n{log_text or 'sin salida'}"
        )

    def ask_confirmation(self, title, message):
        decision = {"confirmed": False}
        completed = threading.Event()

        def prompt():
            decision["confirmed"] = messagebox.askyesno(title, message)
            completed.set()

        self.after(0, prompt)
        completed.wait()
        return decision["confirmed"]

    @staticmethod
    def read_manifest_from_zip(zip_ref):
        try:
            with zip_ref.open("release-manifest.json") as manifest_file:
                return json.loads(manifest_file.read().decode("utf-8"))
        except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {
                "app_version": "legacy",
                "database_migration": "unknown",
                "breaking_changes": True,
                "release_notes": "El paquete no incluye información de migración.",
            }

    @staticmethod
    def read_installed_manifest(install_dir):
        manifest_path = os.path.join(install_dir, "release-manifest.json")
        if not os.path.exists(manifest_path):
            return None
        try:
            with open(manifest_path, "r", encoding="utf-8") as manifest_file:
                return json.load(manifest_file)
        except (OSError, json.JSONDecodeError):
            return None

    @classmethod
    def read_manifest_from_archive(cls, archive_path):
        try:
            with zipfile.ZipFile(archive_path, "r") as zip_ref:
                cls.validate_release_zip(zip_ref, os.path.basename(archive_path))
                return cls.read_manifest_from_zip(zip_ref)
        except zipfile.BadZipFile as error:
            raise RuntimeError(f"El archivo de producción no es un ZIP válido: {error}") from error

    def check_update_before_download(self, install_dir, bundled_manifest=None):
        """Check update compatibility using the embedded release when available."""
        existing_compose = os.path.join(install_dir, "docker-compose.yml")
        if not os.path.exists(existing_compose):
            return

        current_manifest = self.read_installed_manifest(install_dir) or {
            "app_version": "legacy",
            "database_migration": "unknown",
        }
        current_version = current_manifest.get("app_version", "legacy")
        self.after(0, lambda: self.append_log(
            "[*] Verificando compatibilidad de la actualización antes de instalarla..."
        ))

        if bundled_manifest is not None:
            remote_manifest = bundled_manifest
        else:
            try:
                with urllib.request.urlopen(NEOPOS_LOCAL_MANIFEST_URL, timeout=30) as response:
                    remote_manifest = json.loads(response.read().decode("utf-8"))
                if not isinstance(remote_manifest, dict):
                    raise ValueError("el manifiesto remoto no tiene un objeto JSON válido")
            except Exception as error:
                raise RuntimeError(
                    "No se pudo verificar la compatibilidad de la actualización antes de instalarla. "
                    "La instalación existente se dejó intacta. "
                    f"URL: {NEOPOS_LOCAL_MANIFEST_URL}. Motivo: {error}"
                ) from error

        new_version = remote_manifest.get("app_version", "unknown")
        migration_type = remote_manifest.get("database_migration", "unknown")
        breaking = bool(remote_manifest.get("breaking_changes", False)) or migration_type == "breaking"
        self.after(0, lambda: self.append_log(
            f"[*] Versión instalada: {current_version}; versión disponible: {new_version} "
            f"(migración: {migration_type})"
        ))

        if not breaking:
            return

        notes = remote_manifest.get(
            "release_notes", "La versión declara cambios incompatibles."
        )
        confirmed = self.ask_confirmation(
            "Actualización con cambios incompatibles",
            f"La versión {new_version} declara cambios potencialmente incompatibles.\n\n"
            f"{notes}\n\n"
            "Todavía no se descargará ni modificará la instalación. "
            "¿Deseas continuar?",
        )
        if not confirmed:
            raise RuntimeError("Actualización cancelada por el usuario antes de descargarla.")
        self.confirmed_breaking_version = new_version

    def backup_database(self, install_dir):
        compose_file = os.path.join(install_dir, "docker-compose.yml")
        if not os.path.exists(compose_file):
            return

        docker_cli = self.find_docker_cli()
        if not docker_cli:
            raise RuntimeError("No se encontró docker.exe para respaldar la base de datos antes de actualizar.")

        backup_dir = os.path.join(install_dir, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_file = os.path.join(backup_dir, f"pos-{timestamp}.sql")

        start_db = subprocess.run(
            [docker_cli, "compose", "-p", "neopos-local", "-f", compose_file, "up", "-d", "postgres"],
            capture_output=True,
            text=True,
        )
        if start_db.returncode != 0:
            raise RuntimeError(
                "No se pudo iniciar PostgreSQL para crear el respaldo. "
                f"{(start_db.stderr or start_db.stdout).strip()}"
            )

        dump = None
        for _ in range(30):
            dump = subprocess.run(
                [
                    docker_cli,
                    "compose",
                    "-p",
                    "neopos-local",
                    "-f",
                    compose_file,
                    "exec",
                    "-T",
                    "postgres",
                    "pg_dump",
                    "-U",
                    "pos",
                    "-d",
                    "pos",
                ],
                capture_output=True,
            )
            if dump.returncode == 0 and dump.stdout:
                break
            time.sleep(2)
        if dump is None or dump.returncode != 0 or not dump.stdout:
            details = dump.stderr.decode("utf-8", errors="replace").strip() if dump else "sin respuesta de pg_dump"
            raise RuntimeError(f"No se pudo crear el respaldo de PostgreSQL. {details}")

        with open(backup_file, "wb") as backup:
            backup.write(dump.stdout)

        env_file = os.path.join(install_dir, "local", "backend", ".env")
        if os.path.exists(env_file):
            shutil.copy2(env_file, os.path.join(backup_dir, f"backend-{timestamp}.env"))
        self.after(0, lambda: self.append_log(f"[+] Respaldo de base de datos creado: {backup_file}"))

    def prepare_update(self, install_dir, zip_ref):
        existing_compose = os.path.join(install_dir, "docker-compose.yml")
        if not os.path.exists(existing_compose):
            return

        new_manifest = self.read_manifest_from_zip(zip_ref)
        current_manifest = self.read_installed_manifest(install_dir) or {
            "app_version": "legacy",
            "database_migration": "unknown",
        }
        current_version = current_manifest.get("app_version", "legacy")
        new_version = new_manifest.get("app_version", "unknown")
        migration_type = new_manifest.get("database_migration", "unknown")
        breaking = bool(new_manifest.get("breaking_changes", False)) or migration_type == "breaking"

        self.after(0, lambda: self.append_log(
            f"[*] Actualización detectada: {current_version} -> {new_version} "
            f"(migración: {migration_type})"
        ))
        if breaking and new_version != self.confirmed_breaking_version:
            notes = new_manifest.get("release_notes", "La versión declara cambios incompatibles.")
            confirmed = self.ask_confirmation(
                "Actualización con cambios incompatibles",
                f"La versión {new_version} declara cambios potencialmente incompatibles.\n\n"
                f"{notes}\n\nSe creará un respaldo antes de continuar. ¿Deseas aplicar la actualización?",
            )
            if not confirmed:
                raise RuntimeError("Actualización cancelada por el usuario antes de modificar la instalación.")

        self.backup_database(install_dir)

    def run_installation_task(self, target_type):
        try:
            def update_status(msg):
                self.after(0, lambda: self.progress_label.configure(text=msg))
                self.after(0, lambda: self.append_log(f"[*] {msg}"))

            # 1. Install Dependencies (Docker)
            update_status("Verificando dependencias (Docker)...")
            system = platform.system()
            self.after(0, lambda: self.append_log(f"[*] SO detectado: {system}"))

            self.verify_windows_virtualization()

            docker_cli = self.find_docker_cli()
            docker_available = False
            if docker_cli:
                result = subprocess.run([docker_cli, "--version"], capture_output=True, text=True)
                docker_available = result.returncode == 0

            if system == "Windows" and not docker_available:
                    update_status("Descargando Docker Desktop (esto tomará unos minutos)...")
                    installer_path = os.path.join(os.environ["TEMP"], "DockerInstaller.exe")
                    urllib.request.urlretrieve(
                        "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe",
                        installer_path,
                    )

                    update_status("Instalando Docker Desktop silenciosamente...")
                    subprocess.run([installer_path, "install", "--quiet"], check=True)
                    update_status("Docker instalado correctamente.")
                    docker_cli = self.find_docker_cli()
                    if not docker_cli:
                        raise RuntimeError(
                            "Docker Desktop se instaló, pero Windows todavía no expone docker.exe. "
                            "Reinicia Windows y vuelve a ejecutar el instalador."
                        )
            elif system == "Linux" and not docker_available:
                    update_status("Instalando Docker Engine mediante apt...")
                    subprocess.run(["sudo", "apt-get", "update"], check=True)
                    subprocess.run(["sudo", "apt-get", "install", "-y", "docker.io", "docker-compose-v2"], check=True)
                    docker_cli = self.find_docker_cli()
                    if not docker_cli:
                        raise RuntimeError("Docker se instaló, pero no se encontró el comando docker.")
            elif docker_available:
                self.after(0, lambda: self.append_log("[+] Docker ya se encuentra instalado."))
            else:
                raise RuntimeError(f"Sistema operativo no soportado: {system}")

            self.ensure_docker_ready(docker_cli)

            # 2. Deploy NeoPOS. The production package is embedded in the
            # installer; downloading is only a compatibility fallback for old
            # executables built before the package was bundled.
            update_status("Preparando la build de producción de NeoPOS...")

            install_dir = os.path.join(os.path.expanduser("~"), "NeoPOS")
            bundled_release = self.find_bundled_release()
            bundled_manifest = None
            if bundled_release:
                self.validate_release_file(bundled_release)
                bundled_manifest = self.read_manifest_from_archive(bundled_release)
                self.after(0, lambda: self.append_log(
                    f"[+] Build de producción incluida en el instalador: {bundled_release}"
                ))
            self.check_update_before_download(install_dir, bundled_manifest)

            release_path = bundled_release
            temporary_release = None
            if release_path is None:
                update_status("Descargando build de producción desde GitHub...")
                temporary_release = os.path.join(
                    os.environ.get("TEMP", tempfile.gettempdir()),
                    "neopos-local.zip",
                )
                if os.path.exists(temporary_release):
                    os.remove(temporary_release)
                try:
                    urllib.request.urlretrieve(NEOPOS_LOCAL_RELEASE_URL, temporary_release)
                except Exception as error:
                    raise RuntimeError(
                        "No se pudo obtener la build de producción de NeoPOS. "
                        f"URL: {NEOPOS_LOCAL_RELEASE_URL}. Motivo: {error}"
                    ) from error
                release_path = temporary_release

            self.validate_release_file(release_path)
            update_status("Descomprimiendo la build de producción...")
            os.makedirs(install_dir, exist_ok=True)
            self.install_dir = install_dir
            with zipfile.ZipFile(release_path, "r") as zip_ref:
                self.validate_release_zip(zip_ref, os.path.basename(release_path))
                self.prepare_update(install_dir, zip_ref)
                with tempfile.TemporaryDirectory(prefix="neopos-release-") as extraction_dir:
                    zip_ref.extractall(extraction_dir)
                    self.validate_extracted_release(extraction_dir)
                    shutil.copytree(extraction_dir, install_dir, dirs_exist_ok=True)
            self.validate_extracted_release(install_dir)
            self.ensure_runtime_environment(install_dir)
            if temporary_release and os.path.exists(temporary_release):
                os.remove(temporary_release)
            self.after(0, lambda: self.append_log(f"[+] Archivos extraídos en: {install_dir}"))
            self.ensure_release_images(docker_cli, install_dir)
            
            update_status(f"Iniciando servicios de backend ({target_type})...")
            
            if platform.system() == "Windows" and os.path.exists(os.path.join(install_dir, "start.ps1")):
                self.after(0, lambda: self.append_log("[*] Ejecutando start.ps1 en Windows..."))
                powershell = self.find_powershell()
                if not powershell:
                    raise RuntimeError(
                        "No se encontró Windows PowerShell para iniciar NeoPOS Local."
                    )

                process_env = os.environ.copy()
                docker_directory = os.path.dirname(docker_cli)
                process_env["PATH"] = os.pathsep.join(
                    [docker_directory, process_env.get("PATH", "")]
                )
                start_returncode = self.run_streaming_process(
                    [
                        powershell,
                        "-NoProfile",
                        "-NonInteractive",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        os.path.join(install_dir, "start.ps1"),
                        "--local",
                        "--prod",
                        "--no-logs",
                    ],
                    cwd=install_dir,
                    env=process_env,
                )
                if start_returncode != 0:
                    raise RuntimeError(
                        "start.ps1 no pudo iniciar NeoPOS Local "
                        f"(código {start_returncode}). Revisa los logs para ver la salida completa."
                    )

                self.wait_for_local_services(
                    docker_cli,
                    os.path.join(install_dir, "docker-compose.yml"),
                )

                self.after(0, lambda: self.append_log("[*] Configurando recuperación automática de servicios..."))
                self.register_windows_autostart(install_dir)
                
                # Crear acceso directo en el escritorio
                try:
                    self.after(0, lambda: self.append_log("[*] Creando acceso directo en el escritorio..."))
                    desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
                    bat_path = os.path.join(install_dir, "Abrir_NeoPOS.bat")
                    vbs_path = os.path.join(install_dir, "shortcut.vbs")
                    
                    vbs_code = f'Set oWS = WScript.CreateObject("WScript.Shell")\n' \
                               f'sLinkFile = "{desktop}\\\\NeoPOS.lnk"\n' \
                               f'Set oLink = oWS.CreateShortcut(sLinkFile)\n' \
                               f'oLink.TargetPath = "{bat_path}"\n' \
                               f'oLink.WorkingDirectory = "{install_dir}"\n' \
                               f'oLink.Save'
                    
                    with open(vbs_path, "w") as f:
                        f.write(vbs_code)
                    subprocess.run(["cscript", "//Nologo", vbs_path])
                except Exception as ex:
                    self.after(0, lambda: self.append_log(f"[-] No se pudo crear el acceso directo: {ex}"))
            elif platform.system() == "Linux" and os.path.exists(os.path.join(install_dir, "docker-compose.yml")):
                self.after(0, lambda: self.append_log("[*] Ejecutando docker compose up en Linux..."))
                subprocess.run([
                    "sudo", "docker", "compose", "-f",
                    os.path.join(install_dir, "docker-compose.yml"), "up", "-d", "--remove-orphans",
                ], check=True)
                self.after(0, lambda: self.append_log("[*] Configurando inicio automático en Linux..."))
                self.register_linux_autostart(install_dir)
            else:
                raise RuntimeError(
                    "La release no contiene un script de inicio compatible "
                    f"con el sistema operativo {platform.system()}."
                )

            # 3. Finish
            self.after(0, self.finish_installation)
        except Exception as e:
            self.after(0, lambda error=str(e): self.finish_with_error(
                "Error de Instalación", f"Hubo un problema: {error}"
            ))

    def install_app(self):
        response = messagebox.askyesno(
            "Instalar NeoPOS",
            "Se instalarán o actualizarán Docker y todos los servicios de NeoPOS Local. ¿Continuar?",
        )
        if response:
            self.show_progress()
            threading.Thread(target=self.run_installation_task, args=("Desktop App",), daemon=True).start()

    def install_web(self):
        response = messagebox.askyesno(
            "Instalar NeoPOS",
            "Se instalarán o actualizarán Docker y todos los servicios de NeoPOS Local. ¿Continuar?",
        )
        if response:
            self.show_progress()
            threading.Thread(target=self.run_installation_task, args=("Web App",), daemon=True).start()

    def start_services(self):
        response = messagebox.askyesno(
            "Iniciar NeoPOS",
            "Se usarán los archivos existentes en la carpeta NeoPOS y se levantarán "
            "los servicios en modo producción. ¿Continuar?",
        )
        if response:
            self.show_progress()
            threading.Thread(target=self.run_services_task, daemon=True).start()

    def run_services_task(self):
        """Start or repair an already downloaded NeoPOS installation."""
        try:
            def update_status(msg):
                self.after(0, lambda: self.progress_label.configure(text=msg))
                self.after(0, lambda: self.append_log(f"[*] {msg}"))

            install_dir = os.path.join(os.path.expanduser("~"), "NeoPOS")
            start_script = os.path.join(install_dir, "start.ps1")
            compose_file = os.path.join(install_dir, "docker-compose.yml")
            if not os.path.exists(start_script) or not os.path.exists(compose_file):
                raise RuntimeError(
                    f"No se encontró una instalación completa en {install_dir}. "
                    "Usa primero el botón Instalar / Actualizar NeoPOS."
                )

            update_status(f"Verificando instalación existente en {install_dir}...")
            self.verify_windows_virtualization()
            docker_cli = self.find_docker_cli()
            if not docker_cli:
                raise RuntimeError("No se encontró Docker. Usa primero el botón de instalación.")
            self.ensure_docker_ready(docker_cli)
            self.ensure_runtime_environment(install_dir)
            self.ensure_release_images(docker_cli, install_dir)

            if platform.system() == "Windows":
                powershell = self.find_powershell()
                if not powershell:
                    raise RuntimeError("No se encontró Windows PowerShell para iniciar NeoPOS Local.")
                update_status("Construyendo e iniciando los servicios locales...")
                process_env = os.environ.copy()
                process_env["PATH"] = os.pathsep.join(
                    [os.path.dirname(docker_cli), process_env.get("PATH", "")]
                )
                returncode = self.run_streaming_process(
                    [
                        powershell,
                        "-NoProfile",
                        "-NonInteractive",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        start_script,
                        "--local",
                        "--prod",
                        "--no-logs",
                    ],
                    cwd=install_dir,
                    env=process_env,
                )
                if returncode != 0:
                    raise RuntimeError(
                        f"start.ps1 no pudo iniciar NeoPOS Local (código {returncode}). "
                        "Revisa los logs para ver la salida completa."
                    )
                self.wait_for_local_services(docker_cli, compose_file)
                self.register_windows_autostart(install_dir)
            elif platform.system() == "Linux":
                update_status("Construyendo e iniciando los servicios locales...")
                subprocess.run(
                    [
                        "sudo", "docker", "compose", "-p", "neopos-local", "-f", compose_file,
                        "up", "-d", "--remove-orphans",
                    ],
                    check=True,
                )
                self.register_linux_autostart(install_dir)
            else:
                raise RuntimeError(f"Sistema operativo no soportado: {platform.system()}")

            self.after(0, self.finish_installation)
        except Exception as error:
            self.after(0, lambda message=str(error): self.finish_with_error(
                "Error al iniciar NeoPOS",
                f"No se pudieron iniciar los servicios: {message}",
            ))

    def finish_installation(self):
        self.task_running = False
        self.progressbar.stop()
        credentials_file = os.path.join(
            os.path.expanduser("~"), "NeoPOS", "admin-credentials.txt"
        )
        credentials_hint = (
            f"\n\nCredenciales iniciales: {credentials_file}"
            if os.path.exists(credentials_file)
            else ""
        )
        messagebox.showinfo(
            "NeoPOS instalado",
            "Instalación completa. NeoPOS Local está disponible en http://localhost:5173."
            + credentials_hint,
        )
        webbrowser.open("http://localhost:5173")
        self.destroy()
        sys.exit(0)

if __name__ == "__main__":
    app = NeoPOSInstaller()
    app.mainloop()
