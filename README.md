# NeoPOS Installer

Este repositorio publica el instalador de NeoPOS Local. El código fuente de
NeoPOS Local permanece en su repositorio privado; el paquete público contiene
solamente imágenes Docker de producción, archivos de ejecución y configuración
de ejemplo. El ejecutable publicado lleva el ZIP de producción embebido, así
que una instalación nueva no depende de descargar la build después de instalar
Docker.

## Repositorios

- `neopos-local`: repositorio privado con Go, React/TypeScript, pruebas y código de desarrollo.
- `neopos-installer`: repositorio público con el instalador y el paquete binario de producción.
- `neopos-cloud`: panel cloud y página que enlaza al instalador estable.

## Proceso para publicar una release

Los siguientes comandos se ejecutan desde la máquina de desarrollo que tiene
acceso al repositorio privado `neopos-local`.

### 1. Validar NeoPOS Local

```bash
cd /ruta/neopos-local/local/backend
go test ./...

cd ../frontend
npm ci
npm run typecheck
npm run build
```

También se valida la configuración de Docker:

```bash
cd /ruta/neopos-local
docker compose config --quiet
```

### 2. Construir el paquete de producción

```bash
cd /ruta/neopos-local
RELEASE_VERSION=v0.1.10 python3 scripts/build_release.py
```

Este script utiliza el código privado únicamente como contexto de compilación:

1. Construye las imágenes Docker `api`, `printer` y `frontend`.
2. Compila el backend Go dentro de la imagen multi-stage.
3. Compila el frontend React/Vite dentro de la imagen multi-stage.
4. Guarda las imágenes finales en archivos `.tar`.
5. Genera un `docker-compose.yml` que usa esas imágenes, sin `build:`.
6. Incluye scripts, `init.sql`, `.env.example` sin credenciales reales y manifiestos.
7. Genera `releases/neopos-local.zip`.

El ZIP no incluye el repositorio fuente. La comprobación del script falla si
detecta archivos `.go`, `.ts`, `.tsx`, `.js`, `.jsx`, `Dockerfile`, `internal/`
o `frontend/src/`.

### 3. Inspeccionar el paquete

```bash
unzip -l releases/neopos-local.zip
unzip -t releases/neopos-local.zip
```

Debe contener imágenes como:

```text
images/api.tar
images/printer.tar
images/frontend.tar
docker-compose.yml
release-images.json
release-manifest.json
start.ps1
start.sh
```

No deben aparecer archivos fuente de NeoPOS Local.

### 4. Transferir únicamente el artefacto al repositorio público

```bash
cp /ruta/neopos-local/releases/neopos-local.zip \
  /ruta/neopos-installer/neopos-local.zip
```

No se copia `local/backend`, `local/frontend`, el repositorio Git ni archivos
`.env` al repositorio público.

### 5. Crear la release del instalador

Desde `neopos-installer`:

```bash
cd /ruta/neopos-installer
python3 -m py_compile main.py scripts/stamp_neopos_release.py
git diff --check
git status

git add README.md main.py build_windows.bat .github/workflows/build.yml \
  scripts/stamp_neopos_release.py neopos-local.zip
git commit -m "release: v0.1.10"
git tag v0.1.10
git push origin main v0.1.10
```

El tag activa `.github/workflows/build.yml`. GitHub Actions:

- compila el instalador Windows con PyInstaller;
- compila el instalador Linux;
- valida el paquete NeoPOS Local;
- publica nombres versionados, por ejemplo `NeoPOS-Installer-v0.1.10.exe`;
- publica también los alias estables `NeoPOS-Installer.exe` y `NeoPOS-Installer-Linux`;
- publica `neopos-local.zip` y su manifiesto de compatibilidad.

### 6. Validar la publicación

```bash
curl -fL -o /tmp/NeoPOS-Installer-v0.1.10.exe \
  https://github.com/termijow/neopos-installer/releases/download/v0.1.10/NeoPOS-Installer-v0.1.10.exe

curl -fL -o /tmp/neopos-local.zip \
  https://github.com/termijow/neopos-installer/releases/latest/download/neopos-local.zip
unzip -t /tmp/neopos-local.zip
```

La página de `neopos-cloud` usa el alias estable, por lo que no hay que
modificarla en cada release:

```text
https://github.com/termijow/neopos-installer/releases/latest/download/NeoPOS-Installer.exe
```

## Qué ocurre en el equipo del cliente

El instalador usa primero el ZIP embebido (y solo usa la descarga como respaldo
para ejecutables antiguos), carga las imágenes Docker con `docker load`, crea
los archivos de runtime si todavía no existen y ejecuta:

```text
docker compose -p neopos-local up -d --remove-orphans
```

No compila Go ni npm en el equipo del cliente y no necesita el código fuente.
Los contenedores mantienen `restart: unless-stopped`, y una tarea de Windows
vuelve a levantar NeoPOS al iniciar sesión.

En una instalación nueva, el instalador verifica que existan las tres imágenes
de producción y la carpeta `local/backend` antes de iniciar Compose. También
genera secretos locales para PostgreSQL, MinIO, JWT y las cuentas iniciales; la
contraseña del administrador queda temporalmente en `NeoPOS/admin-credentials.txt`.
Los puertos se publican únicamente en `127.0.0.1`.

Las actualizaciones conservan el volumen de PostgreSQL, crean un respaldo antes
de reemplazar archivos y consultan `neopos-local-manifest.json` antes de bajar el
ZIP completo. Los cambios incompatibles deben marcarse como `breaking` en el
manifiesto para pedir confirmación.

## Seguridad

- Nunca subir `.env` ni credenciales reales.
- Las credenciales de Factus se configuran localmente después de instalar.
- Si una credencial real estuvo alguna vez en un archivo publicado, debe
  revocarse y reemplazarse aunque el archivo ya haya sido corregido.
- Revisar el contenido del ZIP antes de publicar cada release.
- El backend se compila con `-trimpath`, sin símbolos de depuración y sin código
  fuente; el frontend se minifica y no publica sourcemaps.
- Esto reduce la ingeniería inversa, pero no puede impedirla por completo: todo
  código que se ejecuta en el equipo del cliente puede ser inspeccionado. La
  lógica verdaderamente confidencial, las claves de proveedores y las reglas de
  licencia deben permanecer en `neopos-cloud`.
