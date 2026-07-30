# Publicar una release de NeoPOS

Este documento describe el flujo vigente para publicar NeoPOS Local desde el
repositorio público `neopos-installer`.

## Cómo funciona

- `neopos-local` contiene el código privado y se usa para construir las
  imágenes Docker de producción.
- `neopos-installer` contiene el instalador, el desinstalador y el archivo
  `neopos-local.zip`.
- El workflow `.github/workflows/build.yml` se ejecuta únicamente cuando se
  publica un tag con formato `v*`.
- GitHub Actions valida el ZIP, compila los ejecutables de Windows y Linux y
  crea la release de GitHub con los alias estables.

## 1. Elegir la versión

Usa una versión nueva. No reutilices un tag ya publicado.

```bash
cd /ruta/neopos-installer
git ls-remote --tags origin 'refs/tags/v*'
```

Ejemplo:

```bash
export RELEASE_VERSION=v0.1.22
```

## 2. Validar `neopos-local`

Ejecuta las pruebas desde el repositorio privado:

```bash
cd /ruta/neopos-local/local/backend
go test ./...

cd ../frontend
npm ci
npm run typecheck
npm run build

cd /ruta/neopos-local
docker compose config --quiet
```

## 3. Construir el paquete de producción

El paquete debe contener imágenes Docker ya compiladas; el equipo del cliente
no debe compilar Go ni npm.

```bash
cd /ruta/neopos-local
docker compose build --no-cache api printer frontend
```

Etiqueta y exporta las imágenes con la misma versión de la release:

```bash
mkdir -p /tmp/neopos-release-${RELEASE_VERSION}/images

docker tag neopos-local-api:latest neopos-local-api:${RELEASE_VERSION}
docker tag neopos-local-printer:latest neopos-local-printer:${RELEASE_VERSION}
docker tag neopos-local-frontend:latest neopos-local-frontend:${RELEASE_VERSION}

docker save -o /tmp/neopos-release-${RELEASE_VERSION}/images/api.tar \
  neopos-local-api:${RELEASE_VERSION}
docker save -o /tmp/neopos-release-${RELEASE_VERSION}/images/printer.tar \
  neopos-local-printer:${RELEASE_VERSION}
docker save -o /tmp/neopos-release-${RELEASE_VERSION}/images/frontend.tar \
  neopos-local-frontend:${RELEASE_VERSION}
```

El ZIP final debe incluir como mínimo:

```text
Abrir_NeoPOS.bat
docker-compose.yml
images/api.tar
images/printer.tar
images/frontend.tar
init.sql
local/backend/.env.example
release-images.json
release-manifest.json
start.ps1
start.sh
```

`docker-compose.yml`, `release-images.json` y `release-manifest.json` deben
usar exactamente `${RELEASE_VERSION}`. El ZIP no puede contener código fuente,
`.env` con secretos, `node_modules`, el directorio `.git` ni archivos de
desarrollo.

Inspección básica:

```bash
unzip -l /ruta/neopos-local/releases/neopos-local.zip
unzip -t /ruta/neopos-local/releases/neopos-local.zip
```

## 4. Copiar y validar el artefacto en el instalador

Transfiere únicamente el ZIP de producción:

```bash
cp /ruta/neopos-local/releases/neopos-local.zip \
  /ruta/neopos-installer/neopos-local.zip

cd /ruta/neopos-installer
RELEASE_VERSION=${RELEASE_VERSION} \
  python3 scripts/stamp_neopos_release.py \
  neopos-local.zip neopos-local-manifest.json
```

`stamp_neopos_release.py` comprueba que el ZIP:

- tenga todos los archivos requeridos;
- conserve los volúmenes `postgres-data` y `minio-data`;
- no contenga código fuente ni enlaces simbólicos;
- tenga imágenes Docker declaradas y versionadas correctamente;
- coincida con la versión de la release;
- no esté corrupto.

Si esta validación falla, no continúes con el commit.

## 5. Crear el commit y el tag

Valida el repositorio y agrega el bundle junto con su manifiesto:

```bash
python3 -m py_compile main.py scripts/stamp_neopos_release.py
git diff --check
git status

git add neopos-local.zip neopos-local-manifest.json
git add main.py uninstaller.py .github/workflows/build.yml scripts/  # si cambiaron
git commit -m "release: ${RELEASE_VERSION} installer bundle"
git tag -a "${RELEASE_VERSION}" -m "NeoPOS Installer ${RELEASE_VERSION}"
git push origin main "${RELEASE_VERSION}"
```

El `push` del tag es obligatorio: un push únicamente a `main` no inicia el
workflow de publicación.

## 6. Qué publica GitHub Actions

El workflow crea estos assets:

- `NeoPOS-Installer-${RELEASE_VERSION}.exe`;
- `NeoPOS-Uninstaller-${RELEASE_VERSION}.exe`;
- `NeoPOS-Installer-Linux-${RELEASE_VERSION}`;
- `NeoPOS-Uninstaller-Linux-${RELEASE_VERSION}`;
- `NeoPOS-Installer.exe` y `NeoPOS-Installer-Linux` como alias estables;
- `neopos-local.zip`;
- `neopos-local-manifest.json`.

La release se marca como la última (`latest`). El instalador usa primero el
paquete Docker embebido y los instaladores antiguos pueden descargarlo desde:

```text
https://github.com/termijow/neopos-installer/releases/latest/download/neopos-local.zip
```

## 7. Verificar la publicación

Espera a que los jobs `build-windows`, `build-linux` y `release` terminen con
éxito. Luego verifica los archivos publicados:

```bash
curl -fL -o /tmp/neopos-local-${RELEASE_VERSION}.zip \
  "https://github.com/termijow/neopos-installer/releases/download/${RELEASE_VERSION}/neopos-local.zip"
unzip -t /tmp/neopos-local-${RELEASE_VERSION}.zip

curl -fsSL \
  "https://api.github.com/repos/termijow/neopos-installer/releases/tags/${RELEASE_VERSION}" \
  | jq -r '.assets[].name'
```

La release también debe estar visible en:

```text
https://github.com/termijow/neopos-installer/releases
```

## Seguridad

- Nunca publiques `.env`, contraseñas, tokens ni credenciales de proveedores.
- Revisa el contenido del ZIP antes de subirlo.
- No publiques el código fuente de `neopos-local`.
- No reutilices tags existentes; si una release falla, corrige el problema y
  usa una nueva versión.
