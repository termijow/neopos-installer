import customtkinter as ctk
import tkinter.messagebox as messagebox
import sys
import os
import subprocess
import threading
import platform
import tempfile
import urllib.request
import zipfile


NEOPOS_LOCAL_RELEASE_URL = (
    "https://github.com/termijow/neopos-installer/releases/latest/download/neopos-local.zip"
)
WINDOWS_AUTOSTART_TASK = "NeoPOS Local Services"

ctk.set_appearance_mode("System")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class NeoPOSInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("NeoPOS Installer")
        self.geometry("600x450")
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

        # Install as App Button
        self.app_btn = ctk.CTkButton(
            self.options_frame, 
            text="Desktop App",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=80,
            command=self.install_app
        )
        self.app_btn.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        # Install as Web Button
        self.web_btn = ctk.CTkButton(
            self.options_frame, 
            text="Web App (Local Server)",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=80,
            fg_color="#2b7a54",
            hover_color="#1e573b",
            command=self.install_web
        )
        self.web_btn.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # Descriptions
        self.app_desc = ctk.CTkLabel(
            self.options_frame, 
            text="Installs backend services and a native\ndesktop application wrapper.",
            text_color="gray",
            font=ctk.CTkFont(size=12)
        )
        self.app_desc.grid(row=1, column=0, padx=10, pady=0)

        self.web_desc = ctk.CTkLabel(
            self.options_frame, 
            text="Installs backend services and opens\nin your default web browser.",
            text_color="gray",
            font=ctk.CTkFont(size=12)
        )
        self.web_desc.grid(row=1, column=1, padx=10, pady=0)

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

            docker_available = False
            try:
                result = subprocess.run(
                    ["docker", "--version"], capture_output=True, text=True
                )
                docker_available = result.returncode == 0
            except FileNotFoundError:
                pass

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
            elif system == "Linux" and not docker_available:
                    update_status("Instalando Docker Engine mediante apt...")
                    subprocess.run(["sudo", "apt-get", "update"], check=True)
                    subprocess.run(["sudo", "apt-get", "install", "-y", "docker.io", "docker-compose-v2"], check=True)
            elif docker_available:
                self.after(0, lambda: self.append_log("[+] Docker ya se encuentra instalado."))
            else:
                raise RuntimeError(f"Sistema operativo no soportado: {system}")

            # 2. Deploy NeoPOS
            update_status("Descargando última versión de NeoPOS desde GitHub...")

            install_dir = os.path.join(os.path.expanduser("~"), "NeoPOS")
            zip_path = os.path.join(os.environ.get("TEMP", "/tmp"), "neopos-local.zip")
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
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                install_root = os.path.abspath(install_dir) + os.sep
                for member in zip_ref.infolist():
                    member_path = os.path.abspath(os.path.join(install_dir, member.filename))
                    if not member_path.startswith(install_root):
                        raise RuntimeError("El paquete descargado contiene una ruta inválida.")
                zip_ref.extractall(install_dir)
            self.after(0, lambda: self.append_log(f"[+] Archivos extraídos en: {install_dir}"))
            
            update_status(f"Iniciando servicios de backend ({target_type})...")
            
            if platform.system() == "Windows" and os.path.exists(os.path.join(install_dir, "start.ps1")):
                self.after(0, lambda: self.append_log("[*] Ejecutando start.ps1 en Windows..."))
                subprocess.run([
                    "powershell", "-ExecutionPolicy", "Bypass", "-File",
                    os.path.join(install_dir, "start.ps1"), "--prod", "--no-logs",
                ], check=True)

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
                "Error de Instalación", f"Hubo un problema: {error}"
            ))
            self.after(0, self.destroy)

    def install_app(self):
        response = messagebox.askyesno("Confirm", "Are you sure you want to install NeoPOS as a Desktop App?")
        if response:
            self.show_progress()
            threading.Thread(target=self.run_installation_task, args=("Desktop App",), daemon=True).start()

    def install_web(self):
        response = messagebox.askyesno("Confirm", "Are you sure you want to install NeoPOS as a Web App?")
        if response:
            self.show_progress()
            threading.Thread(target=self.run_installation_task, args=("Web App",), daemon=True).start()

    def finish_installation(self):
        self.progressbar.stop()
        messagebox.showinfo("Success", "Installation complete!")
        self.destroy()
        sys.exit(0)

if __name__ == "__main__":
    app = NeoPOSInstaller()
    app.mainloop()
