import customtkinter as ctk
import tkinter.messagebox as messagebox
import sys
import os

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

        self.progress_label = ctk.CTkLabel(self.progress_frame, text="Installing...", font=ctk.CTkFont(size=14))
        self.progress_label.grid(row=0, column=0, pady=(20, 10))

        self.progressbar = ctk.CTkProgressBar(self.progress_frame, mode="indeterminate")
        self.progressbar.grid(row=1, column=0, sticky="ew", padx=40)

    def show_progress(self):
        self.options_frame.grid_forget()
        self.progress_frame.grid(row=2, column=0, padx=20, pady=20, sticky="ew")
        self.progressbar.start()

    def install_app(self):
        response = messagebox.askyesno("Confirm", "Are you sure you want to install NeoPOS as a Desktop App?")
        if response:
            self.show_progress()
            self.progress_label.configure(text="Installing Desktop App... Please wait.")
            # Here we will add actual installation logic later
            self.after(3000, self.finish_installation) # Simulate installation

    def install_web(self):
        response = messagebox.askyesno("Confirm", "Are you sure you want to install NeoPOS as a Web App?")
        if response:
            self.show_progress()
            self.progress_label.configure(text="Installing Web App... Please wait.")
            # Here we will add actual installation logic later
            self.after(3000, self.finish_installation) # Simulate installation

    def finish_installation(self):
        self.progressbar.stop()
        messagebox.showinfo("Success", "Installation complete!")
        self.destroy()
        sys.exit(0)

if __name__ == "__main__":
    app = NeoPOSInstaller()
    app.mainloop()
