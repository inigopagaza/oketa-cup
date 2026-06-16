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
        print("[DRY_RUN] Mensaje Telegram (no enviado):")
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
