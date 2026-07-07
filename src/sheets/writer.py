"""
Google Sheets writer (модуль 9) + state storage (модуль 10), раздел 13 ТЗ.

Ключевые гарантии, за которые отвечает этот модуль:
- Повторный запуск не создаёт повторные строки для тех же вакансий
  (раздел 28, критерий 10) — обновление идёт по job_id, а не append.
- Пользовательские поля (application_status, decision_date, user_notes и
  т.д.) никогда не перезаписываются агентом при обновлении существующей
  строки (раздел 13.5) — кроме самого первого создания строки.
- Порядок колонок соответствует src/sheets/schema.py и не меняется агентом
  автоматически (раздел 13.7).
"""

from __future__ import annotations

import logging
from datetime import date, datetime

import gspread

from models.vacancy import Vacancy
from sheets.schema import (
    LISTS_SHEET_VALUES,
    RUNS_COLUMNS,
    SOURCE_LOGS_COLUMNS,
    VACANCIES_COLUMNS,
    VACANCIES_USER_FIELDS,
)

logger = logging.getLogger(__name__)

SHEET_NAMES = ("Vacancies", "Runs", "Source Logs", "Lists")


# --- инициализация листов ---------------------------------------------------

def ensure_sheets_exist(spreadsheet: gspread.Spreadsheet) -> dict[str, gspread.Worksheet]:
    """Создаёт недостающие листы с заголовками, если их ещё нет.
    Не трогает существующие листы и их данные — только добавляет
    отсутствующее (раздел 13.1)."""
    existing = {ws.title: ws for ws in spreadsheet.worksheets()}
    result: dict[str, gspread.Worksheet] = {}

    for name in SHEET_NAMES:
        if name in existing:
            result[name] = existing[name]
            continue
        ws = spreadsheet.add_worksheet(title=name, rows=1000, cols=60)
        result[name] = ws
        logger.info("Создан лист '%s'", name)

    _ensure_header(result["Vacancies"], VACANCIES_COLUMNS)
    _ensure_header(result["Runs"], RUNS_COLUMNS)
    _ensure_header(result["Source Logs"], SOURCE_LOGS_COLUMNS)
    _ensure_lists_sheet(result["Lists"])

    return result


def _ensure_header(worksheet: gspread.Worksheet, columns: list[str]) -> None:
    first_row = worksheet.row_values(1)
    if first_row:
        # Раздел 13.7: не менять порядок колонок автоматически после
        # запуска. Если заголовок уже есть — доверяем ему и ничего не трогаем,
        # даже если он не совпадает 1-в-1 с текущей схемой (значит схема
        # разошлась с таблицей, и это нужно решать осознанно, а не тихой
        # перезаписью).
        return
    worksheet.update("A1", [columns])
    worksheet.freeze(rows=1)  # раздел 13.7: закрепить первую строку


def _ensure_lists_sheet(worksheet: gspread.Worksheet) -> None:
    first_row = worksheet.row_values(1)
    if first_row:
        return
    headers = list(LISTS_SHEET_VALUES.keys())
    max_len = max((len(v) for v in LISTS_SHEET_VALUES.values()), default=0)
    rows = [headers]
    for i in range(max_len):
        row = []
        for key in headers:
            values = LISTS_SHEET_VALUES[key]
            row.append(values[i] if i < len(values) else "")
        rows.append(row)
    worksheet.update("A1", rows)


# --- сериализация Vacancy -> строка таблицы --------------------------------

def _serialize_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, list):
        # раздел 13.8: списки сохраняются как строки через " | "
        return " | ".join(str(v) for v in value)
    if hasattr(value, "value"):  # enum
        return str(value.value)
    return str(value)


def vacancy_to_row(vacancy: Vacancy) -> list[str]:
    data = vacancy.model_dump()
    track_scores = data.get("track_scores", {}) or {}

    flat = dict(data)
    flat["track_1_score"] = track_scores.get("track_1")
    flat["track_2_score"] = track_scores.get("track_2")
    flat["track_3_score"] = track_scores.get("track_3")

    row = []
    for col in VACANCIES_COLUMNS:
        row.append(_serialize_value(flat.get(col)))
    return row


# --- upsert логика (раздел 8.2, 13.5) --------------------------------------

def upsert_vacancies(worksheet: gspread.Worksheet, vacancies: list[Vacancy]) -> dict:
    """Обновляет существующие строки по job_id и добавляет новые.

    Возвращает статистику для записи в Runs (new/updated count и т.п.
    можно расширить дальше — здесь только базовые счётчики).
    """
    all_values = worksheet.get_all_values()
    if not all_values:
        raise RuntimeError(
            "Лист Vacancies пуст — сначала вызовите ensure_sheets_exist()"
        )

    header = all_values[0]
    job_id_col_idx = header.index("job_id") if "job_id" in header else 0
    user_field_indices = {
        field: header.index(field) for field in VACANCIES_USER_FIELDS if field in header
    }

    existing_row_by_job_id: dict[str, int] = {}
    existing_user_values: dict[str, dict[str, str]] = {}
    for i, row in enumerate(all_values[1:], start=2):  # строка 1 — заголовок
        if len(row) <= job_id_col_idx:
            continue
        job_id = row[job_id_col_idx]
        if not job_id:
            continue
        existing_row_by_job_id[job_id] = i
        existing_user_values[job_id] = {
            field: (row[idx] if idx < len(row) else "")
            for field, idx in user_field_indices.items()
        }

    new_count = 0
    updated_count = 0
    batch_updates: list[gspread.cell.Cell] = []
    rows_to_append: list[list[str]] = []

    for vacancy in vacancies:
        row_values = vacancy_to_row(vacancy)

        if vacancy.job_id in existing_row_by_job_id:
            # Раздел 13.5: сохраняем пользовательские поля как есть —
            # перезаписываем в row_values только системные/технические.
            preserved = existing_user_values[vacancy.job_id]
            for field, idx in user_field_indices.items():
                col_position = VACANCIES_COLUMNS.index(field)
                row_values[col_position] = preserved.get(field, "")

            row_number = existing_row_by_job_id[vacancy.job_id]
            for col_idx, value in enumerate(row_values, start=1):
                batch_updates.append(
                    gspread.cell.Cell(row=row_number, col=col_idx, value=value)
                )
            updated_count += 1
        else:
            rows_to_append.append(row_values)
            new_count += 1

    if batch_updates:
        worksheet.update_cells(batch_updates, value_input_option="USER_ENTERED")
    if rows_to_append:
        worksheet.append_rows(rows_to_append, value_input_option="USER_ENTERED")

    return {"new_relevant_jobs": new_count, "updated_jobs": updated_count}


# --- Runs и Source Logs (простые append, без апдейтов) ----------------------

def append_run(worksheet: gspread.Worksheet, run_data: dict) -> None:
    row = [_serialize_value(run_data.get(col)) for col in RUNS_COLUMNS]
    worksheet.append_row(row, value_input_option="USER_ENTERED")


def append_source_logs(worksheet: gspread.Worksheet, logs: list[dict]) -> None:
    if not logs:
        return
    rows = [
        [_serialize_value(log.get(col)) for col in SOURCE_LOGS_COLUMNS]
        for log in logs
    ]
    worksheet.append_rows(rows, value_input_option="USER_ENTERED")


# --- точка входа для пайплайна ----------------------------------------------

def write_run_results(
    spreadsheet: gspread.Spreadsheet,
    vacancies: list[Vacancy],
    run_data: dict,
    source_logs: list[dict],
) -> dict:
    """Вызывается из pipeline.py вместо write_to_sheets_stub."""
    sheets = ensure_sheets_exist(spreadsheet)

    upsert_stats = {"new_relevant_jobs": 0, "updated_jobs": 0}
    if vacancies:
        upsert_stats = upsert_vacancies(sheets["Vacancies"], vacancies)

    full_run_data = {**run_data, **upsert_stats}
    append_run(sheets["Runs"], full_run_data)
    append_source_logs(sheets["Source Logs"], source_logs)

    logger.info("Записано в Google Sheets: %s", full_run_data)
    return full_run_data
