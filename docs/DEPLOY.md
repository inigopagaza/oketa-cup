# Guía de Despliegue — OketaCup

> **Nivel**: Principiante total en producción
> **Objetivo**: App accesible desde internet, segura, con deploy automático
> **Stack**: Proxmox VE → LXC Ubuntu 22.04 → Docker → Nginx + Gunicorn + PostgreSQL → Cloudflare Tunnel
> **Dominio**: Gratuito via DuckDNS + Cloudflare
> **CI/CD**: GitHub Actions → SSH → `docker compose pull && up -d`

---

## Visión general de la arquitectura

```
Internet
   │
   ▼
Cloudflare (DNS + SSL + Tunnel gratuito)
   │  túnel cifrado, sin abrir puertos en el router
   ▼
Tu red doméstica
   │
   ▼
Servidor físico (tu máquina borrada)
   └── Proxmox VE (hipervisor bare-metal)
          └── LXC "oketa-cup" (Ubuntu 22.04, 4 GB RAM)
                 └── Docker Compose
                        ├── nginx        (reverse proxy, :80)
                        ├── web          (Gunicorn + Django, :8000)
                        ├── db           (PostgreSQL 16, :5432)
                        └── cloudflared  (túnel hacia Cloudflare)
```

**Por qué este stack:**
- Proxmox te permite tener varios proyectos aislados en la misma máquina
- LXC es más ligero que una VM completa (8 GB RAM → 4 para la app, 4 de margen)
- Cloudflare Tunnel: sin abrir puertos, SSL automático, protección DDoS gratis
- Docker Compose en producción: reproducible, fácil de actualizar

---

## PASO 0 — Antes de empezar

### Lo que necesitas
- [ ] USB de al menos 8 GB (para instalar Proxmox)
- [ ] El servidor conectado por cable ethernet al router (WiFi no recomendado para servidor)
- [ ] Un ordenador adicional para consultar esta guía mientras trabajas
- [ ] Cuenta en GitHub (ya la tienes)
- [ ] Cuenta en Cloudflare (gratuita): https://dash.cloudflare.com/sign-up
- [ ] Cuenta en DuckDNS (gratuita): https://www.duckdns.org

### Variables que usarás a lo largo de la guía
Anótalas en un lugar seguro (gestor de contraseñas):

```
PROXMOX_IP=192.168.1.X        # IP que asignes al servidor en tu red local
LXC_IP=192.168.1.Y            # IP del contenedor LXC
DOMINIO=oketa-cup.duckdns.org # o el que elijas
POSTGRES_PASSWORD=...          # genera con: openssl rand -base64 32
DJANGO_SECRET_KEY=...          # genera con: openssl rand -base64 50
```

---

## PASO 1 — Dominio gratuito

### Opción A: DuckDNS (más rápida, recomendada para empezar)

1. Ve a https://www.duckdns.org e inicia sesión con GitHub
2. Crea un subdominio: p.ej. `oketa-cup` → te da `oketa-cup.duckdns.org`
3. Guarda el **token** que aparece en la página (lo necesitarás para Cloudflare Tunnel)
4. De momento déjalo con la IP que sea — Cloudflare Tunnel lo sobrescribirá

### Opción B: EU.org (dominio de segundo nivel real, gratis pero tarda 1-2 semanas en aprobarse)

1. Ve a https://nic.eu.org y crea una cuenta
2. Solicita un dominio como `oketa.eu.org`
3. Mientras lo aprueban, usa DuckDNS temporalmente

> **Recomendación**: empieza con DuckDNS. Si después quieres algo más "profesional", compra un `.com` por ~10€/año en Cloudflare Registrar (precio de coste, sin margen).

---

## PASO 2 — Instalar Proxmox VE

### 2.1 Descargar y crear el USB de instalación

```bash
# En tu Mac, descarga la ISO de Proxmox VE 8.x:
# https://www.proxmox.com/en/downloads/proxmox-virtual-environment

# Flashea el USB (reemplaza /dev/diskX con tu USB):
diskutil list                           # identifica el USB
diskutil unmountDisk /dev/diskX
sudo dd if=proxmox-ve_8.x.iso of=/dev/rdiskX bs=1m status=progress
```

O usa [Balena Etcher](https://etcher.balena.io) si prefieres interfaz gráfica.

### 2.2 Instalar Proxmox

1. Conecta el USB al servidor, arráncalo y entra en la BIOS (suele ser F2, F12 o DEL)
2. Pon el USB como primer dispositivo de arranque, guarda y reinicia
3. Sigue el instalador de Proxmox:
   - **Target disk**: el disco del servidor (borrará todo)
   - **Country**: Spain / Timezone: Europe/Madrid
   - **Password**: pon una contraseña segura para root
   - **Network**:
     - IP: `192.168.1.X/24` (elige una IP libre en tu red, fuera del DHCP del router)
     - Gateway: `192.168.1.1` (normalmente la IP de tu router)
     - DNS: `1.1.1.1`
4. Instala y reinicia (quita el USB cuando arranque)

### 2.3 Primer acceso a Proxmox

Desde tu Mac, abre el navegador:
```
https://192.168.1.X:8006
```
Acepta el aviso de certificado autofirmado. Usuario: `root`, contraseña: la que pusiste.

### 2.4 Actualizar Proxmox (repositorios sin suscripción)

Abre la consola de Proxmox (Shell en la interfaz web) y ejecuta:

```bash
# Desactivar repositorio de pago y usar el gratuito
sed -i 's|enterprise.proxmox.com/debian/pve|download.proxmox.com/debian/pve|g' \
    /etc/apt/sources.list.d/pve-enterprise.list
echo "deb http://download.proxmox.com/debian/pve bookworm pve-no-subscription" \
    > /etc/apt/sources.list.d/pve-no-subscription.list

# Actualizar el sistema
apt update && apt full-upgrade -y
reboot
```

---

## PASO 3 — Crear el contenedor LXC

### 3.1 Descargar la plantilla Ubuntu 22.04

En la interfaz web de Proxmox:
1. Ve a **local (pve)** → **CT Templates**
2. Haz click en **Templates**
3. Busca `ubuntu-22.04` y descárgala

### 3.2 Crear el contenedor

En la interfaz web, click en **Create CT** (arriba a la derecha):

| Campo | Valor |
|---|---|
| CT ID | 100 |
| Hostname | oketa-cup |
| Password | (contraseña para root del LXC) |
| Template | ubuntu-22.04-standard |
| Disk | 40 GB (en local-lvm) |
| CPU | 2 cores |
| RAM | 4096 MB |
| Swap | 512 MB |
| Network | DHCP o IP fija `192.168.1.Y/24`, GW `192.168.1.1` |

> **IMPORTANTE**: Antes de crear, en la pestaña **Options**, activa **Nesting** (necesario para Docker dentro de LXC).

### 3.3 Configuración adicional para Docker en LXC

En la **Shell de Proxmox** (no la del LXC), edita la config del contenedor:

```bash
nano /etc/pve/lxc/100.conf
```

Añade estas líneas al final:

```
lxc.apparmor.profile: unconfined
lxc.cap.drop:
lxc.cgroup2.devices.allow: a
lxc.mount.auto: proc:rw sys:rw
```

Guarda y arranca el contenedor:
```bash
pct start 100
```

### 3.4 Entrar al contenedor

```bash
pct enter 100
```

O desde tu Mac por SSH:
```bash
ssh root@192.168.1.Y
```

---

## PASO 4 — Configurar Ubuntu en el LXC

Ejecuta todo esto dentro del contenedor:

```bash
# Actualizar sistema
apt update && apt upgrade -y

# Instalar utilidades básicas
apt install -y curl git nano ufw fail2ban

# Crear usuario no-root para la app
adduser deploy
usermod -aG sudo deploy

# Instalar Docker (método oficial)
curl -fsSL https://get.docker.com | sh
usermod -aG docker deploy

# Instalar Docker Compose plugin
apt install -y docker-compose-plugin

# Verificar instalación
docker --version
docker compose version
```

### 4.1 Configurar el firewall (UFW)

```bash
# Reglas básicas
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh          # puerto 22
ufw allow 80/tcp       # HTTP (Nginx lo necesita internamente)
# NO abrir 443 - Cloudflare Tunnel gestiona el HTTPS

ufw enable
ufw status
```

### 4.2 Configurar fail2ban (protección contra ataques por fuerza bruta)

```bash
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime  = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true
port    = ssh
logpath = %(sshd_log)s
EOF

systemctl enable fail2ban
systemctl start fail2ban
```

---

## PASO 5 — Preparar la aplicación para producción

### 5.1 `docker-compose.prod.yml`

Crea este fichero en la raíz de tu repositorio (ya existe el directorio `docker/`):

```yaml
# docker/docker-compose.prod.yml
services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-oketa_cup}
      POSTGRES_USER: ${POSTGRES_USER:-oketa}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-oketa}"]
      interval: 10s
      timeout: 5s
      retries: 5

  web:
    image: ghcr.io/${GITHUB_REPOSITORY}:latest
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      DJANGO_SETTINGS_MODULE: config.settings.production
      DATABASE_URL: postgres://${POSTGRES_USER:-oketa}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB:-oketa_cup}
      DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY}
      ALLOWED_HOSTS: ${ALLOWED_HOSTS}
    command: >
      sh -c "python manage.py migrate --noinput &&
             python manage.py collectstatic --noinput &&
             gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2"
    volumes:
      - static_files:/app/staticfiles
      - media_files:/app/media

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    depends_on:
      - web
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.prod.conf:/etc/nginx/conf.d/default.conf:ro
      - static_files:/var/www/static:ro
      - media_files:/var/www/media:ro

  cloudflared:
    image: cloudflare/cloudflared:latest
    restart: unless-stopped
    command: tunnel --no-autoupdate run
    environment:
      TUNNEL_TOKEN: ${CLOUDFLARE_TUNNEL_TOKEN}
    depends_on:
      - nginx

volumes:
  postgres_data:
  static_files:
  media_files:
```

### 5.2 Nginx para producción

```nginx
# docker/nginx/nginx.prod.conf
upstream django {
    server web:8000;
}

server {
    listen 80;
    server_name _;

    client_max_body_size 10M;

    location /static/ {
        alias /var/www/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /var/www/media/;
    }

    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
```

### 5.3 Dockerfile multi-stage (actualizar el existente)

```dockerfile
# docker/backend/Dockerfile

# ── Stage 1: builder ───────────────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /app
RUN pip install uv

COPY backend/pyproject.toml backend/uv.lock* ./
RUN uv sync --frozen --no-dev

# ── Stage 2: runtime ───────────────────────────────────────────────
FROM python:3.13-slim AS runtime

# Usuario sin root
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copiar solo el venv del builder
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copiar el código
COPY backend/ .

# Carpetas necesarias
RUN mkdir -p staticfiles media && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000
```

### 5.4 `config/settings/production.py`

```python
# backend/config/settings/production.py
import os
from .base import *  # noqa: F401, F403

DEBUG = False

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",")

# Base de datos vía DATABASE_URL
import dj_database_url  # pip install dj-database-url
DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        conn_max_age=600,
        ssl_require=False,  # conexión interna Docker, sin SSL necesario
    )
}

# Seguridad
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"

# Archivos estáticos
STATIC_ROOT = BASE_DIR / "staticfiles"  # noqa: F405

# Logs a stdout (Docker los captura)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}
```

> **Nota**: añade `dj-database-url` a `pyproject.toml` con `uv add dj-database-url`.

---

## PASO 6 — GitHub Container Registry (imagen Docker)

La imagen del backend se construirá automáticamente en GitHub y se descargará en el servidor (no necesitas construirla en el servidor).

### 6.1 Activar GitHub Container Registry

El repositorio debe ser público o tener el paquete configurado. No requiere configuración extra en repositorios públicos.

### 6.2 Workflow de build y push de la imagen

```yaml
# .github/workflows/ci.yml  (añade este job al existente o crea uno nuevo)
# Este workflow construye y publica la imagen en cada merge a develop/main

name: Build & Push Docker image

on:
  push:
    branches: [main, develop]

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          file: docker/backend/Dockerfile
          push: true
          tags: |
            ghcr.io/${{ github.repository }}:latest
            ghcr.io/${{ github.repository }}:${{ github.sha }}
```

---

## PASO 7 — GitHub Actions: deploy automático

### 7.1 Generar clave SSH para el deploy

En tu Mac:
```bash
ssh-keygen -t ed25519 -C "github-deploy@oketa-cup" -f ~/.ssh/oketa_deploy
# Pulsa Enter (sin passphrase para que GitHub Actions pueda usarla)
```

### 7.2 Autorizar la clave en el servidor

En el LXC (usuario `deploy`):
```bash
su - deploy
mkdir -p ~/.ssh && chmod 700 ~/.ssh
# Pega el contenido de ~/.ssh/oketa_deploy.pub en el servidor:
echo "CONTENIDO_DE_oketa_deploy.pub" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

### 7.3 Añadir secretos en GitHub

Ve a tu repositorio → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Nombre | Valor |
|---|---|
| `DEPLOY_HOST` | `192.168.1.Y` (IP del LXC) |
| `DEPLOY_USER` | `deploy` |
| `DEPLOY_KEY` | contenido de `~/.ssh/oketa_deploy` (la clave privada) |
| `POSTGRES_PASSWORD` | contraseña generada con `openssl rand -base64 32` |
| `DJANGO_SECRET_KEY` | clave generada con `openssl rand -base64 50` |
| `CLOUDFLARE_TUNNEL_TOKEN` | (lo obtienes en el Paso 8) |

### 7.4 Workflow de deploy

```yaml
# .github/workflows/deploy.yml
name: Deploy to production

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    needs: []   # añade aquí el job de tests si quieres que pasen primero

    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          key: ${{ secrets.DEPLOY_KEY }}
          script: |
            set -e
            cd /home/deploy/oketa-cup

            # Actualizar el código
            git pull origin main

            # Descargar la nueva imagen
            docker compose -f docker/docker-compose.prod.yml pull

            # Aplicar migraciones y reiniciar
            docker compose -f docker/docker-compose.prod.yml run --rm web \
              python manage.py migrate --noinput

            # Reiniciar servicios
            docker compose -f docker/docker-compose.prod.yml up -d --remove-orphans

            echo "Deploy completado ✓"
```

---

## PASO 8 — Cloudflare Tunnel

### 8.1 Añadir tu dominio a Cloudflare

1. Ve a https://dash.cloudflare.com → **Add a site**
2. Introduce tu dominio DuckDNS: `oketa-cup.duckdns.org`
   - Si DuckDNS no aparece como opción, necesitarás un dominio propio. En ese caso:
   - Ve a DuckDNS → copia los nameservers de Cloudflare → pégalos en DuckDNS (no es posible, DuckDNS no permite cambiar NS)
   - **Alternativa real**: crea el túnel con un subdominio de `trycloudflare.com` para pruebas, o usa Cloudflare con un dominio propio
   - **Solución práctica**: Compra un dominio barato en Cloudflare Registrar (~10€/año para `.com`) y añádelo directamente

> **Nota importante**: Cloudflare Tunnel con URL permanente requiere un dominio que gestiones en Cloudflare. DuckDNS no permite delegación de DNS. **Recomendación**: compra un dominio barato en Cloudflare (el más económico) — es la opción más sencilla y segura a largo plazo. Para probar, `trycloudflare.com` funciona sin dominio pero la URL cambia cada vez.

### 8.2 Crear el túnel en Cloudflare

1. Ve a **Cloudflare Dashboard** → **Zero Trust** → **Networks** → **Tunnels**
2. Click en **Create a tunnel**
3. Nombre: `oketa-cup-home`
4. Selecciona **Docker** como entorno
5. Cloudflare te da un comando con el token:
   ```
   cloudflared tunnel run --token eyJhIjoiXXXXX...
   ```
6. Copia ese token → guárdalo como secreto `CLOUDFLARE_TUNNEL_TOKEN` en GitHub

### 8.3 Configurar el tunnel para apuntar a Nginx

En la misma página del túnel, en **Public Hostname**:

| Campo | Valor |
|---|---|
| Subdomain | (vacío o `www`) |
| Domain | tu dominio |
| Service Type | HTTP |
| URL | `nginx:80` |

Cloudflare añade HTTPS automáticamente — no necesitas gestionar certificados.

---

## PASO 9 — Primer despliegue manual

Haz esto una vez para arrancar todo. Los siguientes serán automáticos vía GitHub Actions.

### 9.1 En el LXC (como usuario `deploy`)

```bash
su - deploy

# Clonar el repositorio
git clone https://github.com/TU_USUARIO/oketa-cup.git
cd oketa-cup

# Crear el fichero de variables de entorno
cat > .env << 'EOF'
POSTGRES_DB=oketa_cup
POSTGRES_USER=oketa
POSTGRES_PASSWORD=TU_POSTGRES_PASSWORD
DJANGO_SECRET_KEY=TU_DJANGO_SECRET_KEY
ALLOWED_HOSTS=tu-dominio.com,www.tu-dominio.com
CLOUDFLARE_TUNNEL_TOKEN=TU_TUNNEL_TOKEN
GITHUB_REPOSITORY=tu-usuario/oketa-cup
EOF

chmod 600 .env   # solo el propietario puede leerlo
```

### 9.2 Arrancar los servicios

```bash
cd /home/deploy/oketa-cup

# Construir o descargar imagen y arrancar
docker compose -f docker/docker-compose.prod.yml --env-file .env up -d

# Ver logs para confirmar que todo va bien
docker compose -f docker/docker-compose.prod.yml logs -f
```

### 9.3 Crear el superusuario de Django

```bash
docker compose -f docker/docker-compose.prod.yml exec web \
  python manage.py createsuperuser
```

### 9.4 Cargar los datos iniciales

```bash
docker compose -f docker/docker-compose.prod.yml exec web \
  python manage.py load_teams

docker compose -f docker/docker-compose.prod.yml exec web \
  python manage.py load_fixtures

docker compose -f docker/docker-compose.prod.yml exec web \
  python manage.py setup_bracket
```

---

## PASO 10 — Backups automáticos de PostgreSQL

```bash
# En el LXC, como root o deploy
mkdir -p /home/deploy/backups

cat > /home/deploy/backup_db.sh << 'EOF'
#!/bin/bash
set -euo pipefail
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/deploy/backups"
COMPOSE="docker compose -f /home/deploy/oketa-cup/docker/docker-compose.prod.yml"

$COMPOSE exec -T db pg_dump -U oketa oketa_cup | \
    gzip > "$BACKUP_DIR/oketa_cup_$DATE.sql.gz"

# Borrar backups de más de 30 días
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete

echo "Backup completado: oketa_cup_$DATE.sql.gz"
EOF

chmod +x /home/deploy/backup_db.sh

# Programar en cron: todos los días a las 3:00
(crontab -l 2>/dev/null; echo "0 3 * * * /home/deploy/backup_db.sh >> /home/deploy/backups/backup.log 2>&1") | crontab -
```

---

## PASO 11 — Seguridad adicional

### SSH más seguro

```bash
# En el LXC, editar /etc/ssh/sshd_config:
sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
systemctl restart sshd
```

> **¡Importante!**: haz esto solo después de confirmar que puedes acceder con la clave SSH.

### Actualizaciones automáticas de seguridad

```bash
apt install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
# Selecciona "Yes"
```

### Variables de entorno — nunca en git

El fichero `.env` está en `.gitignore`. Verifica:
```bash
grep ".env" /home/deploy/oketa-cup/.gitignore
```

---

## PASO 12 — Proxmox: acceso seguro al panel de administración

Por defecto Proxmox escucha en `:8006`. Para no exponer esto a internet:

1. Accede solo desde la red local: `https://192.168.1.X:8006`
2. O usa Tailscale/WireGuard para acceder remotamente al panel de Proxmox
3. **Nunca** expongas el puerto 8006 a internet

### Backups de Proxmox

En la interfaz web de Proxmox:
- **Datacenter** → **Backup** → **Add**
- Schedule: `0 4 * * 0` (domingos a las 4:00)
- Selecciona el LXC 100
- Mode: Snapshot
- Storage: local

---

## Checklist final antes de abrir a los usuarios

- [ ] La app carga en `https://tu-dominio.com`
- [ ] El login funciona
- [ ] Las migraciones se aplicaron (`docker compose exec web python manage.py showmigrations`)
- [ ] Los fixtures están cargados (equipos y partidos)
- [ ] El setup_bracket se ejecutó
- [ ] Las traducciones funcionan (castellano/euskara)
- [ ] Los backups diarios están programados (`crontab -l`)
- [ ] fail2ban está activo (`fail2ban-client status sshd`)
- [ ] UFW está activo (`ufw status`)
- [ ] El deploy automático funciona: haz un commit en `main` y verifica que GitHub Actions lo despliega
- [ ] Los logs no muestran errores: `docker compose logs --tail=50`

---

## Comandos de mantenimiento útiles

```bash
# Ver todos los contenedores y su estado
docker compose -f docker/docker-compose.prod.yml ps

# Ver logs en tiempo real
docker compose -f docker/docker-compose.prod.yml logs -f web

# Reiniciar un servicio
docker compose -f docker/docker-compose.prod.yml restart web

# Ejecutar comando Django
docker compose -f docker/docker-compose.prod.yml exec web python manage.py shell

# Restaurar un backup
gunzip -c /home/deploy/backups/oketa_cup_20260611_030000.sql.gz | \
  docker compose -f docker/docker-compose.prod.yml exec -T db \
  psql -U oketa oketa_cup

# Actualizar manualmente (sin esperar a GitHub Actions)
cd /home/deploy/oketa-cup
git pull origin main
docker compose -f docker/docker-compose.prod.yml pull
docker compose -f docker/docker-compose.prod.yml up -d
```

---

## Resolución de problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `502 Bad Gateway` en Nginx | Gunicorn no arrancó | `docker compose logs web` |
| Error de migración al arrancar | Base de datos no lista | Revisar healthcheck de `db` |
| Cloudflare Tunnel desconectado | Token incorrecto | Verificar `CLOUDFLARE_TUNNEL_TOKEN` |
| `DisallowedHost` en Django | ALLOWED_HOSTS incompleto | Añadir el dominio a `.env` |
| Docker no arranca en LXC | Falta configuración nesting | Verificar `/etc/pve/lxc/100.conf` |
| GitHub Actions falla al hacer SSH | Clave SSH incorrecta | Regenerar y añadir de nuevo |
