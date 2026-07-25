@echo off
echo ===================================
echo NeoPOS Installer - Windows Builder
echo ===================================

echo Instalando dependencias necesarias (pyinstaller, customtkinter)...
python -m pip install --upgrade pip
python -m pip install pyinstaller customtkinter

echo.
echo Compilando main.py a un ejecutable (.exe)...
python -m PyInstaller --onefile --windowed --name NeoPOS-Installer main.py

echo.
echo Compilacion exitosa. Tu ejecutable esta en la carpeta "dist".
pause
