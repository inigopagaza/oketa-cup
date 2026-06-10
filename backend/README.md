# Backend Oketa Cup

## Sincronización automática con football-data.org

Se ha añadido el comando:

```bash
python manage.py sync_football_data
```

Opciones útiles:

```bash
python manage.py sync_football_data --dry-run
python manage.py sync_football_data --season 2026
python manage.py sync_football_data --status FINISHED
```

Variables de entorno necesarias (en `backend/.env` para local y en el entorno del servidor para producción):

- `FOOTBALL_DATA_API_KEY`
- `FOOTBALL_DATA_BASE_URL` (por defecto: `https://api.football-data.org/v4`)
- `FOOTBALL_DATA_COMPETITION_CODE` (por defecto: `WC`)
- `FOOTBALL_DATA_TIMEOUT_SECONDS` (por defecto: `20`)
- `FOOTBALL_DATA_USE_API_STANDINGS` (por defecto: `True`)
- `FOOTBALL_DATA_AUTO_CREATE_KNOCKOUT` (por defecto: `True`)

El comando actualiza automáticamente `home_score`, `away_score`, `is_finished`,
`decided_in_90`, `penalties_winner`, y además asigna `home_team`/`away_team`
en cruces de eliminatoria cuando la API ya trae emparejamientos.

Si no existe un partido de eliminatoria en la base de datos y
`FOOTBALL_DATA_AUTO_CREATE_KNOCKOUT=True`, el comando lo crea automáticamente.

Cuando un partido pasa a finalizado, recalcula puntuación (`process_match_result`).
Para grupos, por defecto aplica clasificación oficial desde
`/competitions/WC/standings` (`process_group_completion_from_standings`).

## Ejecución cada hora (cron)

Ejemplo de cron en servidor Linux (cada hora):

```cron
0 * * * * cd /app && /app/.venv/bin/python manage.py sync_football_data --status FINISHED >> /var/log/oketa-sync.log 2>&1
```

Si usas Docker, programa el cron en el host para ejecutar el comando dentro del contenedor web.
