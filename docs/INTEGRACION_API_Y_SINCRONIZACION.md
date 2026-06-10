# Integración de API externa y sincronización automática (football-data.org)

## Objetivo

Automatizar la actualización de resultados del Mundial en Oketa Cup usando
la API de football-data.org para evitar carga manual de marcadores y, además,
usar la clasificación oficial de grupos desde la API.

## Qué se ha implementado

### 1) Servicio aislado de sincronización

Se ha creado un servicio independiente para no romper el flujo existente:

- `backend/apps/tournament/services/football_data_sync.py`

Responsabilidades principales del servicio:

- Consulta partidos en `GET /v4/competitions/WC/matches`.
- Mapea `stage` de API a `Match.phase` local (`GROUP_STAGE`, `LAST_32`, etc.).
- Actualiza partidos locales (`home_score`, `away_score`, `is_finished`).
- Deriva campos de KO:
  - `decided_in_90` desde `score.duration`.
  - `penalties_winner` desde `score.duration == PENALTY_SHOOTOUT` y `score.winner`.
- Cuando un partido queda finalizado, dispara el cálculo de puntos automáticamente.
- Si la API ya publica emparejamientos de KO, actualiza `home_team` y `away_team`.
- Si falta un partido de KO en BD, puede crearlo automáticamente.

### 2) Comando de gestión

Se ha creado:

- `backend/apps/tournament/management/commands/sync_football_data.py`

Uso:

```bash
python manage.py sync_football_data
python manage.py sync_football_data --dry-run
python manage.py sync_football_data --season 2026
python manage.py sync_football_data --status FINISHED
```

Qué hace el comando:

- Ejecuta la sincronización de partidos.
- Recalcula puntuaciones si hay partidos recién finalizados.
- Recalcula grupos con fuente oficial API (por defecto).
- Muestra un resumen final con métricas de ejecución.

### 3) Clasificación de grupos oficial (API)

Se añadió soporte para standings oficiales:

- Endpoint usado: `GET /v4/competitions/WC/standings`
- En scoring se añadió:
  - `process_group_completion_from_standings(...)`

Comportamiento:

- **Por defecto**: usa standings API para top 1 y top 2 del grupo.
- **Fallback**: si falla standings API, usa cálculo local por resultados de partidos.

### 4) Configuración por entorno

En settings:

- `FOOTBALL_DATA_API_KEY`
- `FOOTBALL_DATA_BASE_URL` (default `https://api.football-data.org/v4`)
- `FOOTBALL_DATA_COMPETITION_CODE` (default `WC`)
- `FOOTBALL_DATA_TIMEOUT_SECONDS` (default `20`)
- `FOOTBALL_DATA_USE_API_STANDINGS` (default `True`)
- `FOOTBALL_DATA_AUTO_CREATE_KNOCKOUT` (default `True`)

Archivos actualizados:

- `backend/config/settings/base.py`
- `backend/.env.example`
- `docker/docker-compose.yml`
- `docker/docker-compose.prod.yml`

## Diseño técnico resumido

### Flujo de sincronización

1. Se consulta la API de partidos.
2. Para cada partido API, se intenta encontrar match local por:
   - fase,
   - fecha/hora,
   - grupo (si aplica),
   - equipos (si conocidos).
3. Si no hay match exacto, se aplican fallbacks:
   - tolerancia horaria,
   - placeholders sin equipos en KO (para evitar duplicados).
4. Si no existe y es KO, se crea partido (si está habilitado).
5. Se actualizan campos y, si pasa a finalizado, se recalculan puntos.
6. Para grupos, se aplican standings oficiales de API.

### Idempotencia

El comando está diseñado para ejecutarse repetidamente sin duplicar resultados:

- Si no hay cambios, no escribe en BD.
- El scoring ya borra/recalcula logs relacionados cuando toca.
- Los grupos se recalculan de forma consistente por código de razón/contexto.

## Pasos en Producción

## 0) Requisito de rama

Actualmente los scripts de despliegue apuntan a `main`:

- `scripts/deploy-code-ssh.sh`
- `scripts/deploy-fixtures-ssh.sh`

Si trabajas en `develop`, antes de desplegar hay que asegurar que los cambios están en `main`.

## 1) Variables de entorno en servidor

En el `.env` de producción (el que usa `docker-compose.prod.yml`), añadir:

```env
FOOTBALL_DATA_API_KEY=tu_token_real
FOOTBALL_DATA_BASE_URL=https://api.football-data.org/v4
FOOTBALL_DATA_COMPETITION_CODE=WC
FOOTBALL_DATA_TIMEOUT_SECONDS=20
FOOTBALL_DATA_USE_API_STANDINGS=True
FOOTBALL_DATA_AUTO_CREATE_KNOCKOUT=True
```

## 2) Despliegue de código + migraciones

Usa el script existente:

```bash
./scripts/deploy-code-ssh.sh
```

Ese script ya hace `migrate` durante el despliegue.

## 3) Ejecutar sync manual de comprobación en prod

Después del deploy, recomendable lanzar una ejecución manual:

```bash
docker compose -f docker/docker-compose.prod.yml --env-file .env run --rm --no-deps web python manage.py sync_football_data --dry-run
```

Si el resumen es correcto, ejecutar sin `--dry-run`:

```bash
docker compose -f docker/docker-compose.prod.yml --env-file .env run --rm --no-deps web python manage.py sync_football_data
```

## 4) Cron cada hora

### Opción recomendada: cron en host (llamando docker compose)

Ejemplo (`crontab -e` del usuario deploy):

```cron
0 * * * * cd /home/deploy/oketa-cup && docker compose -f docker/docker-compose.prod.yml --env-file .env run --rm --no-deps web python manage.py sync_football_data >> /var/log/oketa-sync.log 2>&1
```

Notas:

- Ejecuta en el minuto 0 de cada hora.
- `run --rm` crea un contenedor efímero solo para el comando.
- Si prefieres reducir llamadas, se puede usar `--status FINISHED`.

### Rotación de logs (recomendado)

Configurar `logrotate` para `/var/log/oketa-sync.log`.

## 5) Fixtures y bracket (si necesitas reset completo)

Cuando quieras regenerar calendario/base de cruces desde fixtures:

```bash
./scripts/deploy-fixtures-ssh.sh
```

Esto recarga fixtures y reconstruye `next_match` del bracket.

## Validación funcional sugerida (checklist)

1. `sync_football_data --dry-run` devuelve exit code 0.
2. Resumen muestra partidos API y locales razonables.
3. En partidos KO previstos, aparecen equipos asignados automáticamente.
4. En partidos finalizados, se reflejan marcadores y se recalculan puntos.
5. Grupos recalculados con `fuente=api` en resumen.

## Explicación didáctica para clase (versión corta)

- Se separa la integración externa en un servicio propio para no acoplar la lógica de negocio.
- El comando de sincronización orquesta todo y puede ejecutarse de forma periódica.
- Se prioriza dato oficial para standings de grupo (API), pero se mantiene fallback local.
- El proceso es idempotente: se puede lanzar cada hora sin romper consistencia.
- Se parametriza por entorno para no hardcodear secretos y facilitar despliegue.

## Dónde mirar en el código

- Servicio principal: `backend/apps/tournament/services/football_data_sync.py`
- Comando CLI: `backend/apps/tournament/management/commands/sync_football_data.py`
- Scoring grupos API: `backend/apps/pool/services/scoring.py`
- Configuración env: `backend/config/settings/base.py` y `backend/.env.example`
