@echo off
echo ===================================
echo NeoPOS Installer - Windows Builder
echo ===================================

echo Instalando dependencias necesarias (pyinstaller, customtkinter)...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo Compilando main.py a un ejecutable (.exe)...
pyinstaller --onefile --windowed --name NeoPOS-Installer main.py

echo.
echo Compilacion exitosa. Tu ejecutable esta en la carpeta "dist".
pause
