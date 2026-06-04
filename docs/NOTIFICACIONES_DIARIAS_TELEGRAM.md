# Notificaciones Diarias Del Mundial En Telegram (Guía Educativa + Código)

## 1. Objetivo

Implementar un envío diario automático a Telegram con:

- partidos del día
- resultados del día que ya estén cargados

Requisitos funcionales:

- hora de envío: 10:00
- zona horaria: Europe/Madrid
- fecha de inicio: 11 de junio de 2026

Requisitos técnicos:

- servicio separado en Docker
- no impactar al servicio web principal
- código sencillo de mantener

---

## 2. Arquitectura Recomendada

Arquitectura en producción:

- servicio web actual (Django + Gunicorn)
- nuevo servicio notifier (Django command runner)
- ambos comparten base de datos PostgreSQL

Flujo:

1. El contenedor notifier despierta cada minuto.
2. Comprueba si son las 10:00 en Madrid.
3. Comprueba que la fecha sea >= 2026-06-11.
4. Si no se envió aún hoy, construye mensaje y lo envía a Telegram.
5. Guarda log de envío para idempotencia.

---

## 3. Preparación En Telegram

## 3.1 Crear bot

1. En Telegram, abre BotFather.
2. Ejecuta /newbot.
3. Guarda el token.

## 3.2 Crear grupo y añadir bot

1. Crea grupo (o reutiliza uno).
2. Añade el bot al grupo.
3. Dale permiso para enviar mensajes.

# Notificaciones Diarias Del Mundial En Telegram (Guia Educativa + Codigo Base)

## 1. Objetivo

Disenar una integracion para enviar todos los dias a las 10:00 (hora de Madrid) un mensaje de Telegram con:

- Partidos del dia
- Resultados del dia que ya esten guardados

Condicion de arquitectura:

- El envio debe correr en un contenedor separado para no afectar al servicio web principal.

---

## 2. Arquitectura Recomendada

### 2.1 Componentes

1. Backend Django existente (consulta de partidos).
2. Servicio notificador separado (mismo codigo Django, comando distinto).
3. Bot de Telegram (API oficial).
4. Grupo o canal de Telegram donde enviar mensajes.

### 2.2 Flujo

1. Scheduler del notificador se despierta cada dia.
2. A las 10:00 Europe/Madrid ejecuta comando de envio.
3. El comando construye el resumen desde la tabla Match.
4. Envia el texto usando Telegram Bot API.
5. Registra logs y evita duplicados por fecha.

---

## 3. Preparacion De Telegram

### 3.1 Crear bot

1. Abrir BotFather en Telegram.
2. Ejecutar /newbot.
3. Guardar BOT_TOKEN.

### 3.2 Obtener chat_id del grupo

1. Meter el bot en el grupo.
2. Enviar cualquier mensaje en ese grupo.
3. Consultar actualizaciones del bot:

```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/getUpdates"
```

4. Buscar chat.id del grupo (suele ser negativo, ejemplo -1001234567890).

Nota:

- Si el grupo tiene privacidad activa y no aparecen mensajes, desactivar temporalmente privacy mode en BotFather con /setprivacy.

---

## 4. Variables De Entorno

Anadir en entorno de produccion:

- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- TELEGRAM_ENABLED=true
- TELEGRAM_DRY_RUN=false
- TELEGRAM_START_DATE=2026-06-11
- TZ=Europe/Madrid

Recomendacion:

- Mantener TELEGRAM_DRY_RUN=true durante pruebas iniciales.

---

## 5. Dependencias Python

Para este enfoque hacen falta dos paquetes:

- httpx (cliente HTTP para Telegram API)
- apscheduler (scheduler diario)

Ejemplo en pyproject.toml:

```toml
dependencies = [
  "dj-database-url>=3.1.2",
  "django>=6.0.5",
  "django-cors-headers>=4.9.0",
  "djangorestframework>=3.17.1",
  "djangorestframework-simplejwt>=5.5.1",
  "drf-spectacular>=0.29.0",
  "gunicorn>=26.0.0",
  "httpx>=0.28.1",
  "psycopg2-binary>=2.9.12",
  "python-decouple>=3.8",
  "apscheduler>=3.10.4",
  "whitenoise>=6.12.0",
]
```

---

## 6. Codigo Base Recomendado

Los siguientes fragmentos son una base realista para integrar en este repo.

### 6.1 Servicio para construir el mensaje

Archivo sugerido:

- backend/apps/tournament/services/daily_telegram_summary.py

```python
from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.db.models import QuerySet

from apps.tournament.models import Match

MADRID_TZ = ZoneInfo("Europe/Madrid")


def _today_bounds(day: date) -> tuple[datetime, datetime]:
   start = datetime.combine(day, time.min, tzinfo=MADRID_TZ)
   end = datetime.combine(day, time.max, tzinfo=MADRID_TZ)
   return start, end


def _matches_for_day(day: date) -> QuerySet[Match]:
   start, end = _today_bounds(day)
   return (
      Match.objects.select_related("home_team", "away_team")
      .filter(scheduled_at__range=(start, end))
      .order_by("scheduled_at")
   )


def build_daily_summary(day: date) -> str:
   matches = list(_matches_for_day(day))

   if not matches:
      return f"Mundial 2026 - {day:%d/%m/%Y}\n\nHoy no hay partidos."

   pending: list[str] = []
   finished: list[str] = []

   for m in matches:
      home = m.home_team.code if m.home_team_id else "TBD"
      away = m.away_team.code if m.away_team_id else "TBD"
      hour = m.scheduled_at.astimezone(MADRID_TZ).strftime("%H:%M")
      phase = m.get_phase_display()

      if m.is_finished and m.home_score is not None and m.away_score is not None:
         finished.append(f"- {home} {m.home_score}-{m.away_score} {away} ({phase})")
      else:
         pending.append(f"- {hour} {home} vs {away} ({phase})")

   lines = [f"Mundial 2026 - {day:%A %d/%m/%Y}", ""]

   if pending:
      lines.append("Partidos de hoy:")
      lines.extend(pending)
      lines.append("")

   if finished:
      lines.append("Resultados ya cargados hoy:")
      lines.extend(finished)
      lines.append("")

   return "\n".join(lines).strip()
```

### 6.2 Cliente Telegram

Archivo sugerido:

- backend/apps/tournament/services/telegram_client.py

```python
from __future__ import annotations

import os

import httpx


class TelegramConfigError(RuntimeError):
   pass


def send_telegram_message(text: str) -> None:
   token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
   chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
   dry_run = os.environ.get("TELEGRAM_DRY_RUN", "false").lower() == "true"

   if not token or not chat_id:
      raise TelegramConfigError("Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID")

   if dry_run:
      print("[DRY_RUN] Mensaje Telegram no enviado:")
      print(text)
      return

   url = f"https://api.telegram.org/bot{token}/sendMessage"
   payload = {
      "chat_id": chat_id,
      "text": text,
      "disable_web_page_preview": True,
   }

   with httpx.Client(timeout=15.0) as client:
      response = client.post(url, json=payload)
      response.raise_for_status()
      data = response.json()
      if not data.get("ok"):
         raise RuntimeError(f"Telegram API error: {data}")
```

### 6.3 Comando manual de envio

Archivo sugerido:

- backend/apps/tournament/management/commands/send_daily_telegram_summary.py

```python
from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand

from apps.tournament.services.daily_telegram_summary import build_daily_summary
from apps.tournament.services.telegram_client import send_telegram_message


class Command(BaseCommand):
   help = "Envia el resumen diario del Mundial a Telegram"

   def add_arguments(self, parser):
      parser.add_argument("--date", type=str, default="", help="Formato YYYY-MM-DD")

   def handle(self, *args, **options):
      day = date.fromisoformat(options["date"]) if options["date"] else date.today()
      text = build_daily_summary(day)
      send_telegram_message(text)
      self.stdout.write(self.style.SUCCESS("Resumen enviado correctamente"))
```

### 6.4 Scheduler diario en proceso separado

Archivo sugerido:

- backend/apps/tournament/management/commands/run_telegram_notifier.py

```python
from __future__ import annotations

import os
import signal
import sys
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from django.core.management.base import BaseCommand

from apps.tournament.services.daily_telegram_summary import build_daily_summary
from apps.tournament.services.telegram_client import send_telegram_message


class Command(BaseCommand):
   help = "Lanza scheduler diario para Telegram a las 10:00 Europe/Madrid"

   def handle(self, *args, **options):
      tz = ZoneInfo(os.environ.get("TZ", "Europe/Madrid"))
      enabled = os.environ.get("TELEGRAM_ENABLED", "true").lower() == "true"
      start_date = date.fromisoformat(os.environ.get("TELEGRAM_START_DATE", "2026-06-11"))

      if not enabled:
         self.stdout.write("TELEGRAM_ENABLED=false. Saliendo.")
         return

      sent_dates: set[str] = set()

      def job() -> None:
         now = datetime.now(tz)
         today = now.date()

         if today < start_date:
            print(f"Aun no inicia ventana de envios ({start_date.isoformat()}).")
            return

         if today.isoformat() in sent_dates:
            print(f"Resumen ya enviado hoy: {today.isoformat()}")
            return

         text = build_daily_summary(today)
         send_telegram_message(text)
         sent_dates.add(today.isoformat())
         print(f"Resumen enviado para {today.isoformat()}")

      scheduler = BackgroundScheduler(timezone=tz)
      scheduler.add_job(job, trigger="cron", hour=10, minute=0, id="telegram_daily_summary")
      scheduler.start()

      print("Notifier Telegram iniciado. Esperando ejecuciones...")

      def _shutdown(*_):
         scheduler.shutdown(wait=False)
         sys.exit(0)

      signal.signal(signal.SIGTERM, _shutdown)
      signal.signal(signal.SIGINT, _shutdown)

      while True:
         time.sleep(5)
```

Nota educativa:

- Este ejemplo guarda idempotencia en memoria (set).
- En produccion real, mejor guardar fecha enviada en BD para resistir reinicios.

---

## 7. Integracion En Docker Compose De Produccion

Ejemplo de nuevo servicio notifier en docker/docker-compose.prod.yml:

```yaml
  notifier:
   image: ghcr.io/${GITHUB_REPOSITORY}:latest
   restart: unless-stopped
   depends_on:
     - db
   environment:
     DJANGO_SETTINGS_MODULE: config.settings.production
     DATABASE_URL: ${DATABASE_URL:-postgres://${POSTGRES_USER:-oketa}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB:-oketa_cup}}
     DB_NAME: ${POSTGRES_DB:-oketa_cup}
     DB_USER: ${POSTGRES_USER:-oketa}
     DB_PASSWORD: ${POSTGRES_PASSWORD}
     DB_HOST: db
     DB_PORT: "5432"
     SECRET_KEY: ${DJANGO_SECRET_KEY}
     DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY}
     TZ: ${TZ:-Europe/Madrid}
     TELEGRAM_ENABLED: ${TELEGRAM_ENABLED:-true}
     TELEGRAM_DRY_RUN: ${TELEGRAM_DRY_RUN:-true}
     TELEGRAM_START_DATE: ${TELEGRAM_START_DATE:-2026-06-11}
     TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
     TELEGRAM_CHAT_ID: ${TELEGRAM_CHAT_ID}
   command: >
     sh -c "python manage.py migrate --noinput &&
          python manage.py run_telegram_notifier"
```

Puntos importantes:

- Usa la misma imagen del backend para simplificar CI/CD.
- No expone puertos.
- Corre en proceso separado y aislado del servicio web.

---

## 8. Pruebas Recomendadas

### 8.1 Prueba local sin envio real

```bash
export TELEGRAM_DRY_RUN=true
python manage.py send_daily_telegram_summary --date 2026-06-11
```

Resultado esperado:

- El comando imprime el mensaje y no llama a Telegram API.

### 8.2 Prueba con envio real

```bash
export TELEGRAM_DRY_RUN=false
python manage.py send_daily_telegram_summary --date 2026-06-11
```

Resultado esperado:

- Mensaje recibido en el grupo/canal configurado.

### 8.3 Prueba scheduler

Configurar temporalmente job cada minuto para validar logs y envio, luego volver a 10:00.

---

## 9. Endurecimiento Para Produccion

1. Persistir idempotencia por fecha en BD (tabla de envios).
2. Reintentos con backoff en errores de red.
3. Alertar fallo por logs centralizados.
4. Limitar longitud del mensaje y partir en bloques si supera limites.
5. Test unitarios de formato de mensaje y filtros por fecha.

---

## 10. Resumen Final

Con Telegram, la integracion es oficial, estable y facil de operar.

La receta recomendada para este proyecto es:

1. Construir resumen diario desde Match.
2. Enviar con Telegram Bot API.
3. Ejecutar scheduler diario en contenedor notifier independiente.
4. Activar envio real desde 2026-06-11 a las 10:00 Europe/Madrid.

Con esto se logra automatizacion diaria sin ensuciar el servicio web principal.

- usar supercronic o cron del host
- lanzar solo python manage.py send_daily_telegram_summary a las 10:00

Ventaja:

- proceso más predecible y menos lógica de reloj en código

---

## 7. Pruebas Manuales Recomendadas

## 7.1 Prueba de formato (sin envío)

```bash
python manage.py send_daily_telegram_summary --dry-run --date 2026-06-11
```

## 7.2 Prueba de envío real puntual

```bash
python manage.py send_daily_telegram_summary --date 2026-06-11 --force
```

## 7.3 Validar idempotencia

Lanzar dos veces seguidas sin --force y comprobar que la segunda se omite.

---

## 8. Buenas Prácticas De Producción

1. Un único replicado del servicio notifier.
2. Alertas de logs para fallos de envío.
3. No incluir token en logs.
4. Mantener mensaje corto para legibilidad en móvil.
5. Añadir tests unitarios del builder de resumen.

---

## 9. Resumen De Implementación

Para tenerlo funcionando con mínimo riesgo:

1. Crear modelo DailyNotificationLog + migración.
2. Crear daily_summary.py, telegram_client.py y comandos management.
3. Añadir variables TELEGRAM_* al entorno de producción.
4. Añadir servicio notifier en docker/docker-compose.prod.yml.
5. Probar dry-run, luego envío real, luego ejecución automática.

Con esto tienes integración Telegram oficial, servicio aislado y operación diaria reproducible.
