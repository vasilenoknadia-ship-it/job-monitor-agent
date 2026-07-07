"""
Оркестратор пайплайна (раздел 3.2 ТЗ).

Порядок вызова модулей соответствует нумерации из раздела 3.2:
1. Config loader
2. Source connectors
3. Normalizer
4. Canonical resolver   (пока заглушка — Фаза 3 плана)
5. Deduplication engine (пока заглушка — Фаза 3 плана)
6. Track classifier     (пока заглушка — Фаза 1: один трек)
7. Geography validator  (пока заглушка)
8. Relevance scorer     (пока заглушка)
9. Google Sheets writer (пока заглушка — Фаза 2 плана)
10. State storage       (реализуется вместе с writer'ом)

Сейчас это "вертикальный срез" (Фаза 1 из плана): один источник
(Greenhouse) проходит через реальный normalizer, а остальные этапы —
через no-op заглушки, которые просто возвращают вакансию без изменений.
Так видно всю форму пайплайна, и каждую заглушку можно заменять на
реальную реализацию по одной, не трогая остальной код.
"""

from __future__ import annotations

import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Позволяет запускать `python main.py` из корня репозитория без установки
# пакета — src кладём в sys.path явно, а не полагаемся на PYTHONPATH.
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config_loader.loader import AppConfig, load_all  # noqa: E402
from connectors.base import BaseConnector, ConnectorError  # noqa: E402
from models.vacancy import Vacancy  # noqa: E402
from normalizer.normalizer import normalize  # noqa: E402
from sheets.auth import SheetsConfigError, get_spreadsheet  # noqa: E402
from sheets.writer import write_run_results  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("pipeline")


# --- заглушки для этапов, которые ещё не реализованы (см. docstring) ------

def canonical_resolve_stub(vacancy: Vacancy) -> Vacancy:
    """TODO(Фаза 3): реальная реализация ищет оригинал по правилам
    canonical_source_rules из source_monitoring.yaml. Пока canonical_url
    уже проставлен коннектором (для Greenhouse он и есть canonical)."""
    return vacancy


def deduplicate_stub(vacancies: list[Vacancy]) -> list[Vacancy]:
    """TODO(Фаза 3): реальная реализация — раздел 8 ТЗ. Пока просто убирает
    точные дубли по job_id, чтобы пайплайн не падал на очевидном кейсе."""
    seen: set[str] = set()
    result = []
    for v in vacancies:
        if v.job_id in seen:
            continue
        seen.add(v.job_id)
        result.append(v)
    return result


def classify_stub(vacancy: Vacancy, config: AppConfig) -> Vacancy:
    """TODO(Фаза 1 продолжение): реальный track classifier — раздел 11.
    Пока просто отмечает вакансию как требующую ручного просмотра, чтобы
    ничего не терялось молча, пока классификатора нет."""
    vacancy.manual_review_required = True
    vacancy.concerns.append("track classifier not implemented yet")
    return vacancy


def geography_validate_stub(vacancy: Vacancy) -> Vacancy:
    """TODO: раздел 10 ТЗ."""
    return vacancy


def score_stub(vacancy: Vacancy) -> Vacancy:
    """TODO: раздел 12 ТЗ."""
    return vacancy


# --- сам пайплайн -----------------------------------------------------------

def run() -> None:
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    logger.info("Загружаю конфигурацию треков и источников...")
    config = load_all()
    logger.info(
        "Загружено треков: %d, источников: %d",
        len(config.tracks),
        len(config.sources.sources),
    )

    connectors: list[BaseConnector] = _build_connectors()

    raw_count = 0
    all_vacancies: list[Vacancy] = []
    source_logs: list[dict] = []
    sources_successful = 0
    sources_failed = 0

    for connector in connectors:
        checked_at = datetime.now(timezone.utc)
        try:
            raw_vacancies = connector.fetch()
        except ConnectorError as exc:
            logger.warning("Ошибка источника: %s", exc)
            sources_failed += 1
            source_logs.append({
                "run_id": run_id,
                "source_name": connector.source_name,
                "source_type": getattr(connector, "source_type", ""),
                "source_url": "",
                "run_status": "failed",
                "jobs_found": 0,
                "error_type": type(exc).__name__,
                "error_message": exc.message,
                "attempts": 1,
                "last_successful_run": "",
                "consecutive_failures": 1,
                "checked_at": checked_at,
            })
            continue

        sources_successful += 1
        source_logs.append({
            "run_id": run_id,
            "source_name": connector.source_name,
            "source_type": getattr(connector, "source_type", ""),
            "source_url": "",
            "run_status": "success",
            "jobs_found": len(raw_vacancies),
            "error_type": "",
            "error_message": "",
            "attempts": 1,
            "last_successful_run": checked_at,
            "consecutive_failures": 0,
            "checked_at": checked_at,
        })

        raw_count += len(raw_vacancies)
        for raw in raw_vacancies:
            vacancy = normalize(raw)
            vacancy = canonical_resolve_stub(vacancy)
            all_vacancies.append(vacancy)

    all_vacancies = deduplicate_stub(all_vacancies)

    for i, vacancy in enumerate(all_vacancies):
        vacancy = classify_stub(vacancy, config)
        vacancy = geography_validate_stub(vacancy)
        vacancy = score_stub(vacancy)
        all_vacancies[i] = vacancy

    finished_at = datetime.now(timezone.utc)
    manual_review_jobs = sum(1 for v in all_vacancies if v.manual_review_required)

    run_data = {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "timezone": "Europe/Vilnius",
        "sources_planned": len(connectors),
        "sources_checked": len(connectors),
        "sources_successful": sources_successful,
        "sources_partial": 0,
        "sources_failed": sources_failed,
        "jobs_discovered_raw": raw_count,
        "jobs_after_deduplication": len(all_vacancies),
        "updated_jobs": 0,  # перезаписывается write_run_results() из upsert_stats
        "reopened_jobs": 0,
        "manual_review_jobs": manual_review_jobs,
        "run_status": "success" if sources_failed == 0 else "partial",
        "run_note": "",
    }

    try:
        spreadsheet = get_spreadsheet()
        final_run_data = write_run_results(spreadsheet, all_vacancies, run_data, source_logs)
        logger.info("Готово. %s", final_run_data)
    except SheetsConfigError as exc:
        logger.error(
            "Не удалось записать в Google Sheets (%s). Результаты прогона: %s",
            exc,
            run_data,
        )


def _build_connectors() -> list[BaseConnector]:
    """Фаза 1: пока один Greenhouse-коннектор в качестве примера.

    TODO(Фаза 4): строить список коннекторов из company_watchlist треков +
    поля greenhouse_board_token (или аналогичного) в конфиге компании,
    а не хардкодить здесь конкретные компании.
    """
    from connectors.ats.greenhouse import GreenhouseConnector

    # Пример: реальный board_token нужно проверить на карьерной странице
    # компании (URL вида boards.greenhouse.io/{board_token}).
    return [
        GreenhouseConnector(company_name="Example Company", board_token="example"),
    ]


if __name__ == "__main__":
    run()
