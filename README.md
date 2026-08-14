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

## Historial de versiones estables

| Versión | Resumen incluido en la release |
|---|---|
| `v0.3.9` | Soporte para reportes y exportación PDF de facturas electrónicas, gestión y reportes de sesiones de inventario con movimientos auditados, y soporte para pagos fiados con mejor gestión de métodos de pago. |
| `v0.3.8` | Añade pagos divididos por múltiples medios, cortesías y comidas de empleados con autorización e inventario auditado, flujo completo de factura electrónica Factus/DIAN (CUFE, correo, estado y PDF), y actualizaciones seguras con backup obligatorio y conservación de datos. |
| `v0.3.7` | Muestra en Configuración el resumen de cambios de la actualización antes de descargar el instalador oficial. |
| `v0.3.6` | Muestra la versión instalada al pie de Configuración, incorpora un estado local de versión y publica automáticamente estas notas en GitHub. |
| `v0.3.5` | Publica una versión estable para probar el aviso automático de actualización desde `v0.3.4`, conservando las protecciones de licencia, backups, telemetría e IA. |
| `v0.3.4` | Protege la licencia ya instalada, elimina reinicios accidentales del asistente, restaura backups transaccionalmente, prueba el Error Catcher central y valida las rutas generadas por la IA. |
| `v0.3.3` | Añade monitoreo central de errores, panel de vencimientos y renovaciones, comprobantes PDF y correcciones del panel QA y la sesión Cloud. |
| `v0.3.2` | Añade Cortesías y Consumo de Empleado, backups funcionales, fallback del asistente IA e idempotencia para evitar facturas duplicadas. |

Este historial es informativo. La fuente que consume el actualizador es
`neopos-local-manifest.json`, incluido también dentro de `neopos-local.zip`.
Las versiones preliminares (`alpha`, `beta`, `rc` o `nightly`) no se ofrecen a
los restaurantes.

## Proceso para publicar una release

Los siguientes comandos se ejecutan desde la máquina de desarrollo que tiene
acceso al repositorio privado `neopos-local`. Cada release debe usar un número
estable con el formato exacto `vMAJOR.MINOR.PATCH`, por ejemplo `v0.3.7`.

### 0. Definir la versión y su resumen

Antes de compilar, se actualizan en `neopos-local`:

- `local/backend/internal/platform/config/config.go`, con la versión por defecto;
- `local/backend/.env.example`, con `APP_VERSION`;
- `release-manifest.json`, con `app_version` y `release_notes`.

`release_notes` debe explicar en lenguaje de usuario qué agrega o corrige esa
versión. No se debe dejar el texto genérico. También se debe indicar
correctamente si la migración es aditiva o incompatible. Ejemplo:

```json
{
  "app_version": "v0.3.7",
  "database_migration": "additive",
  "breaking_changes": false,
  "release_notes": "Muestra el resumen de cambios antes de descargar una actualización."
}
```

El workflow convierte este mismo resumen en el cuerpo visible de la release de
GitHub. Así el actualizador, el ZIP, el manifiesto público y la página de la
release muestran la misma información.

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
RELEASE_VERSION=v0.3.7 python3 scripts/build_release.py
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
unzip -p releases/neopos-local.zip release-manifest.json
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
RELEASE_VERSION=v0.3.7 python3 scripts/stamp_neopos_release.py \
  neopos-local.zip neopos-local-manifest.json
python3 scripts/render_release_notes.py \
  neopos-local-manifest.json /tmp/neopos-release-notes.md
python3 -m py_compile main.py scripts/stamp_neopos_release.py \
  scripts/render_release_notes.py
python3 -m unittest discover -s tests -v
git diff --check
git status

git add README.md main.py build_windows.bat .github/workflows/build.yml \
  scripts/ tests/ neopos-local.zip neopos-local-manifest.json
git commit -m "release: v0.3.7"
git tag -a v0.3.7 -m "Release v0.3.7"
git push origin main v0.3.7
```

El tag activa `.github/workflows/build.yml`. GitHub Actions:

- compila el instalador Windows con PyInstaller;
- compila el desinstalador Windows con una opción explícita para conservar o borrar los datos;
- compila el instalador Linux;
- valida el paquete NeoPOS Local;
- publica nombres versionados, por ejemplo `NeoPOS-Installer-v0.1.10.exe`;
- publica también los alias estables `NeoPOS-Installer.exe` y `NeoPOS-Installer-Linux`;
- publica `neopos-local.zip` y su manifiesto de compatibilidad.

### 6. Validar la publicación

```bash
curl -fL -o /tmp/NeoPOS-Installer-v0.3.7.exe \
  https://github.com/termijow/neopos-installer/releases/download/v0.3.7/NeoPOS-Installer-v0.3.7.exe

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
genera secretos locales para PostgreSQL, MinIO, JWT, la firma de licencias y las cuentas iniciales. Las
credenciales locales quedan en `NeoPOS/admin-credentials.txt` y también en
`Descargas/admin-credentials.txt` (o `Escritorio/admin-credentials.txt` si
Descargas no está disponible). La cuenta de NeoPOS Cloud se utiliza únicamente
para validar la licencia, el negocio y la sede. Las credenciales locales son
independientes y Cloud nunca entrega ni sincroniza hashes de contraseña hacia
el equipo local.
Los puertos se publican únicamente en `127.0.0.1`.

La comprobación de virtualización en Windows es únicamente informativa: si
PowerShell no puede leerla o la reporta como desactivada, el instalador muestra
un aviso y permite que Docker valide por sí mismo si puede iniciar.

La release también publica `NeoPOS-Uninstaller.exe`. El modo normal retira los
contenedores, la tarea de inicio y las imágenes de NeoPOS, pero conserva la BD.
La casilla de borrado elimina además los volúmenes PostgreSQL/MinIO, la
configuración y los respaldos locales. Docker Desktop/Engine y recursos de
otros proyectos no se eliminan por defecto.

El desinstalador conserva Docker Desktop/Engine y los recursos de otros
proyectos por defecto. Incluye una casilla separada para invocar el
desinstalador oficial de Docker, pero nunca ejecuta `docker system prune` ni
borra explícitamente contenedores, imágenes o volúmenes de otros proyectos.

La licencia ya no se solicita durante la instalación de Docker. Al abrir
NeoPOS Local por primera vez, la pantalla de activación solicita el correo y
la contraseña de NeoPOS Cloud, el código de licencia, la empresa y la sede; la
activación validada queda guardada en la base de datos local.

El instalador Windows solicita permisos de administrador mediante UAC desde el
inicio. Esto permite crear la tarea de recuperación automática de NeoPOS sin
tener que ejecutarlo manualmente con clic derecho como administrador.

En Linux, el instalador solicita la contraseña `sudo` una sola vez al comenzar
la instalación o reparación. El campo está enmascarado y la contraseña se pasa
a `sudo` por la entrada estándar: no se incorpora a los argumentos del proceso,
no se escribe en los logs ni se guarda en disco. Si Docker Engine está detenido,
el instalador intenta iniciar `docker.service`; si el usuario no tiene acceso a
`/var/run/docker.sock`, las operaciones Docker necesarias se ejecutan con esos
permisos administrativos. Los mensajes y tiempos de espera de Docker Desktop se
reservan exclusivamente para Windows.

Las actualizaciones conservan los volúmenes nombrados `postgres-data` y
`minio-data`, crean un respaldo antes de reemplazar archivos y consultan
`neopos-local-manifest.json` antes de bajar el ZIP completo. El instalador no
ejecuta `docker compose down -v`, por lo que los datos no se eliminan durante
una actualización. Los cambios incompatibles deben marcarse como `breaking` en
el manifiesto para pedir confirmación.

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
