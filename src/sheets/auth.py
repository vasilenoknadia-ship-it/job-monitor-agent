"""
Авторизация и доступ к Google Spreadsheet (раздел 13 ТЗ).

Ожидает две переменные окружения (см. .env.example):
- GOOGLE_SERVICE_ACCOUNT_JSON: содержимое JSON-ключа сервисного аккаунта
  целиком, одной строкой (именно так их удобно класть в GitHub Secrets).
- SPREADSHEET_ID: ID таблицы из её URL.

Сознательно не поддерживаем чтение ключа из файла на диске — раз секрет
и так хранится в GitHub Secrets/'.env', нет смысла заводить второй способ
его передачи, это только увеличивает площадь для случайной утечки.
"""

from __future__ import annotations

import json
import os

import gspread
from google.oauth2.service_account import Credentials

# Sheets + Drive scope — Drive нужен, чтобы сервисный аккаунт вообще видел
# файл таблицы (см. README, раздел "Google Sheets: настройка доступа").
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


class SheetsConfigError(Exception):
    """Не хватает переменных окружения или ключ невалиден."""


def get_spreadsheet() -> gspread.Spreadsheet:
    raw_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    spreadsheet_id = os.environ.get("SPREADSHEET_ID")

    if not raw_json:
        raise SheetsConfigError("Переменная окружения GOOGLE_SERVICE_ACCOUNT_JSON не задана")
    if not spreadsheet_id:
        raise SheetsConfigError("Переменная окружения SPREADSHEET_ID не задана")

    try:
        service_account_info = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise SheetsConfigError(
            "GOOGLE_SERVICE_ACCOUNT_JSON не является валидным JSON — "
            "проверьте, что весь файл ключа скопирован целиком"
        ) from exc

    credentials = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    client = gspread.authorize(credentials)

    try:
        return client.open_by_key(spreadsheet_id)
    except gspread.exceptions.SpreadsheetNotFound as exc:
        raise SheetsConfigError(
            f"Таблица с ID '{spreadsheet_id}' не найдена, либо сервисный "
            f"аккаунт ({service_account_info.get('client_email')}) не "
            f"добавлен в неё как Editor"
        ) from exc
