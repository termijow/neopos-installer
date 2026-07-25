@echo off
echo ===================================
echo NeoPOS Installer - Windows Builder
echo ===================================

set "VERSION=%~1"
if "%VERSION%"=="" set VERSION=v0.1.8
echo Version del instalador: %VERSION%

echo Instalando dependencias necesarias (pyinstaller, customtkinter)...
python -m pip install --upgrade pip
if errorlevel 1 exit /b %errorlevel%
python -m pip install pyinstaller customtkinter
if errorlevel 1 exit /b %errorlevel%

echo.
echo Compilando main.py a un ejecutable (.exe)...
python -m PyInstaller --clean --onefile --windowed --name "NeoPOS-Installer-%VERSION%" main.py
if errorlevel 1 (
    echo Error: PyInstaller no pudo compilar el instalador.
    exit /b %errorlevel%
)

echo.
echo Compilacion exitosa. Tu ejecutable esta en la carpeta "dist\NeoPOS-Installer-%VERSION%.exe".
pause
