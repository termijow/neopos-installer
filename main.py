import customtkinter as ctk
import tkinter.messagebox as messagebox
import sys
import json
import os
import subprocess
import threading
import time
import platform
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

ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class NeoPOSInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.install_dir = None
        self.confirmed_breaking_version = None
        self.log_path = os.path.join(tempfile.gettempdir(), "neopos-installer.log")

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
        self.progress_frame.grid_rowconfigure(2, weight=1)

        self.progress_label = ctk.CTkLabel(self.progress_frame, text="Preparando...", font=ctk.CTkFont(size=14))
        self.progress_label.grid(row=0, column=0, pady=(10, 10))

        self.progressbar = ctk.CTkProgressBar(self.progress_frame, mode="indeterminate")
        self.progressbar.grid(row=1, column=0, sticky="ew", padx=40, pady=(0, 10))
        
        self.log_box = ctk.CTkTextbox(self.progress_frame, height=150, font=ctk.CTkFont(size=12, family="Consolas"))
        self.log_box.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 10))
        self.log_box.insert("0.0", "Iniciando proceso de instalación...\n")
        self.log_box.configure(state="disabled")

    def append_log(self, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        try:
            with open(self.log_path, "a", encoding="utf-8") as log_file:
                log_file.write(text + "\n")
        except OSError:
            pass
        print(text)

    def show_progress(self):
        self.options_frame.grid_forget()
        self.progress_frame.grid(row=2, column=0, padx=20, pady=20, sticky="ew")
        self.progressbar.start()

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

    def check_update_before_download(self, install_dir):
        """Check the public release manifest before downloading the full package."""
        existing_compose = os.path.join(install_dir, "docker-compose.yml")
        if not os.path.exists(existing_compose):
            return

        current_manifest = self.read_installed_manifest(install_dir) or {
            "app_version": "legacy",
            "database_migration": "unknown",
        }
        current_version = current_manifest.get("app_version", "legacy")
        self.after(0, lambda: self.append_log(
            "[*] Verificando compatibilidad de la actualización antes de descargarla..."
        ))

        try:
            with urllib.request.urlopen(NEOPOS_LOCAL_MANIFEST_URL, timeout=30) as response:
                remote_manifest = json.loads(response.read().decode("utf-8"))
            if not isinstance(remote_manifest, dict):
                raise ValueError("el manifiesto remoto no tiene un objeto JSON válido")
        except Exception as error:
            raise RuntimeError(
                "No se pudo verificar la compatibilidad de la actualización antes de descargarla. "
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

            # 2. Deploy NeoPOS
            update_status("Descargando última versión de NeoPOS desde GitHub...")

            install_dir = os.path.join(os.path.expanduser("~"), "NeoPOS")
            zip_path = os.path.join(os.environ.get("TEMP", "/tmp"), "neopos-local.zip")
            self.check_update_before_download(install_dir)
            if os.path.exists(zip_path):
                os.remove(zip_path)

            try:
                urllib.request.urlretrieve(NEOPOS_LOCAL_RELEASE_URL, zip_path)
            except Exception as error:
                raise RuntimeError(
                    "No se pudo descargar NeoPOS Local desde la release pública. "
                    f"URL: {NEOPOS_LOCAL_RELEASE_URL}. Motivo: {error}"
                ) from error

            update_status("Descomprimiendo archivos en la carpeta del usuario...")
            os.makedirs(install_dir, exist_ok=True)
            self.install_dir = install_dir
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                install_root = os.path.abspath(install_dir) + os.sep
                for member in zip_ref.infolist():
                    member_path = os.path.abspath(os.path.join(install_dir, member.filename))
                    if not member_path.startswith(install_root):
                        raise RuntimeError("El paquete descargado contiene una ruta inválida.")
                self.prepare_update(install_dir, zip_ref)
                zip_ref.extractall(install_dir)
            self.after(0, lambda: self.append_log(f"[+] Archivos extraídos en: {install_dir}"))
            
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
                start_result = subprocess.run(
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
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                start_output = self._trim_process_output(
                    "\n".join(filter(None, [start_result.stdout, start_result.stderr]))
                )
                if start_output:
                    self.after(0, lambda output=start_output: self.append_log(output))
                if start_result.returncode != 0:
                    raise RuntimeError(
                        "start.ps1 no pudo iniciar NeoPOS Local "
                        f"(código {start_result.returncode}).\n\n"
                        f"Salida:\n{start_output or 'sin salida'}"
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
                    os.path.join(install_dir, "docker-compose.yml"), "up", "-d", "--build",
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
            self.after(0, lambda error=str(e): messagebox.showerror(
                "Error de Instalación", f"Hubo un problema: {error}\n\nLog: {self.log_path}"
            ))
            self.after(0, self.destroy)

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

            if platform.system() == "Windows":
                powershell = self.find_powershell()
                if not powershell:
                    raise RuntimeError("No se encontró Windows PowerShell para iniciar NeoPOS Local.")
                update_status("Construyendo e iniciando los servicios locales...")
                process_env = os.environ.copy()
                process_env["PATH"] = os.pathsep.join(
                    [os.path.dirname(docker_cli), process_env.get("PATH", "")]
                )
                result = subprocess.run(
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
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                output = self._trim_process_output(
                    "\n".join(filter(None, [result.stdout, result.stderr]))
                )
                if output:
                    self.after(0, lambda value=output: self.append_log(value))
                if result.returncode != 0:
                    raise RuntimeError(
                        f"start.ps1 no pudo iniciar NeoPOS Local (código {result.returncode}).\n\n"
                        f"Salida:\n{output or 'sin salida'}"
                    )
                self.wait_for_local_services(docker_cli, compose_file)
                self.register_windows_autostart(install_dir)
            elif platform.system() == "Linux":
                update_status("Construyendo e iniciando los servicios locales...")
                subprocess.run(
                    [
                        "sudo", "docker", "compose", "-p", "neopos-local", "-f", compose_file,
                        "up", "-d", "--build", "--remove-orphans",
                    ],
                    check=True,
                )
                self.register_linux_autostart(install_dir)
            else:
                raise RuntimeError(f"Sistema operativo no soportado: {platform.system()}")

            self.after(0, self.finish_installation)
        except Exception as error:
            self.after(0, lambda message=str(error): messagebox.showerror(
                "Error al iniciar NeoPOS",
                f"No se pudieron iniciar los servicios: {message}\n\nLog: {self.log_path}",
            ))

    def finish_installation(self):
        self.progressbar.stop()
        messagebox.showinfo(
            "NeoPOS instalado",
            "Instalación completa. NeoPOS Local está disponible en http://localhost:5173.",
        )
        webbrowser.open("http://localhost:5173")
        self.destroy()
        sys.exit(0)

if __name__ == "__main__":
    app = NeoPOSInstaller()
    app.mainloop()
