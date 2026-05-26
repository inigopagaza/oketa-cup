# Notas de despliegue: CSRF, Cloudflare Tunnel y LXC

Este documento resume el incidente reciente de produccion (error 403 CSRF) y los ajustes aplicados para dejar el despliegue estable en LXC + Docker + Cloudflare Tunnel.

## Resumen rapido

Sintoma principal:
- La web cargaba, pero al hacer login o cambiar idioma devolvia `403 CSRF verification failed`.

Causa raiz:
- Django en produccion requiere origen confiable para peticiones seguras (HTTPS) con CSRF.
- Al estar detras de Nginx + Cloudflare Tunnel, el esquema/origen no llegaba siempre en condiciones correctas.
- Faltaba configurar de forma robusta `CSRF_TRUSTED_ORIGINS` en entorno de produccion.

## Que se ha cambiado

### 1) Ajustes en Django `production.py`

Archivo: `backend/config/settings/production.py`

Cambios relevantes:
- Limpieza de `ALLOWED_HOSTS` (evita valores vacios o con espacios).
- Nuevo soporte para variable de entorno `CSRF_TRUSTED_ORIGINS`.
- Fallback automatico: si no hay variable, construir `https://<host>` para cada host de `ALLOWED_HOSTS`.
- `USE_X_FORWARDED_HOST = True` para respetar host reenviado por proxy.

Objetivo:
- Evitar rechazos CSRF en formularios (login, set_language, etc.) cuando la app esta detras de proxy/tunel.

### 2) Ajustes en Nginx

Archivo: `docker/nginx/nginx.prod.conf`

Cambios relevantes:
- `proxy_set_header X-Forwarded-Host $host;`
- `proxy_set_header X-Forwarded-Proto https;`

Objetivo:
- Forzar contexto HTTPS correcto hacia Django cuando la entrada real es por Cloudflare Tunnel.

### 3) Ajustes en Docker Compose

Archivo: `docker/docker-compose.prod.yml`

Cambios relevantes:
- Variable de entorno nueva en `web`:
  - `CSRF_TRUSTED_ORIGINS: ${CSRF_TRUSTED_ORIGINS:-}`

Objetivo:
- Permitir configurar origenes confiables desde `.env` sin rebuild de imagen.

## Variables recomendadas en `.env` (produccion)

Ejemplo:

```env
ALLOWED_HOSTS=tu-dominio.eus,www.tu-dominio.eus
CSRF_TRUSTED_ORIGINS=https://tu-dominio.eus,https://www.tu-dominio.eus
```

Notas:
- Sin protocolo en `ALLOWED_HOSTS`.
- Con `https://` en `CSRF_TRUSTED_ORIGINS`.
- Separar varios valores por coma.

## Comandos aplicados en servidor

```bash
cd ~/oketa-cup
git pull origin develop
docker compose -f docker/docker-compose.prod.yml --env-file .env up -d --force-recreate web nginx
```

## Relacion con otros fixes hechos durante el incidente

Tambien se corrigieron puntos adicionales de despliegue:

- Carga de fixtures en LXC:
  - Montaje de datos para comandos de gestion (`/data`) con path correcto.
- Ejecucion de comandos Django en LXC:
  - Uso de `docker compose run --rm --no-deps web ...` por limitaciones de AppArmor en algunos `exec`.

## Checklist de validacion final

1. Login funciona sin 403.
2. Cambio de idioma funciona sin 403.
3. `docker compose ... logs --tail=100 web` no muestra errores de CSRF recurrentes.
4. `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS` reflejan exactamente los dominios publicos reales.

## Troubleshooting rapido

Si vuelve a aparecer 403 CSRF:

1. Verifica `.env`:
- `ALLOWED_HOSTS` contiene dominio(s) correctos.
- `CSRF_TRUSTED_ORIGINS` incluye `https://` y los mismos dominios.

2. Aplica cambios:
```bash
docker compose -f docker/docker-compose.prod.yml --env-file .env up -d --force-recreate web nginx
```

3. Prueba en ventana privada del navegador (evita cookies antiguas).

4. Revisa logs:
```bash
docker compose -f docker/docker-compose.prod.yml --env-file .env logs --tail=120 web
docker compose -f docker/docker-compose.prod.yml --env-file .env logs --tail=120 nginx
```
