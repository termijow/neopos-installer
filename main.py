import customtkinter as ctk
import tkinter.messagebox as messagebox
import sys
import os
import subprocess
import threading
import platform
import urllib.request
import zipfile


NEOPOS_LOCAL_RELEASE_URL = (
    "https://github.com/termijow/neopos-local/releases/latest/download/neopos-local.zip"
)

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

    def run_installation_task(self, target_type):
        try:
            def update_status(msg):
                self.after(0, lambda: self.progress_label.configure(text=msg))
                self.after(0, lambda: self.append_log(f"[*] {msg}"))

            # 1. Install Dependencies (Docker)
            update_status("Verificando dependencias (Docker)...")
            system = platform.system()
            self.after(0, lambda: self.append_log(f"[*] SO detectado: {system}"))

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
                zip_ref.extractall(install_dir)
            self.after(0, lambda: self.append_log(f"[+] Archivos extraídos en: {install_dir}"))
            
            update_status(f"Iniciando servicios de backend ({target_type})...")
            
            if platform.system() == "Windows" and os.path.exists(os.path.join(install_dir, "start.ps1")):
                self.after(0, lambda: self.append_log("[*] Ejecutando start.ps1 en Windows..."))
                subprocess.run([
                    "powershell", "-ExecutionPolicy", "Bypass", "-File",
                    os.path.join(install_dir, "start.ps1"), "--prod", "--no-logs",
                ], check=True)
                
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
            else:
                raise RuntimeError(
                    "La release no contiene un script de inicio compatible "
                    f"con el sistema operativo {platform.system()}."
                )

            # 3. Finish
            self.after(0, self.finish_installation)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Error de Instalación", f"Hubo un problema: {str(e)}"))
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
