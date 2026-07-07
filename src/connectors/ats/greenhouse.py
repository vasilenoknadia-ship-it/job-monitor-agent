"""
Greenhouse connector (раздел 24, п.8 — ATS-платформы).

Greenhouse отдаёт публичный JSON без авторизации:
  GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true

board_token — обычно slug компании, тот же, что виден в URL карьерной
страницы: https://boards.greenhouse.io/{board_token}

Этот коннектор сознательно НЕ делает нормализацию, canonical resolution
или дедупликацию — это отдельные модули дальше по пайплайну (раздел 3.2).
Его единственная задача — превратить ответ Greenhouse в список RawVacancy.
"""

from __future__ import annotations

from datetime import datetime, date

import httpx

from connectors.base import BaseConnector, ConnectorError
from models.vacancy import RawVacancy, SourceType, VacancyLifecycleStatus, WorkFormat

GREENHOUSE_API_URL = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"


class GreenhouseConnector(BaseConnector):
    """Один экземпляр = один board_token (= одна компания)."""

    source_name = "Greenhouse"

    def __init__(self, company_name: str, board_token: str, timeout: float = 15.0):
        self.company_name = company_name
        self.board_token = board_token
        self.timeout = timeout

    def fetch(self) -> list[RawVacancy]:
        url = GREENHOUSE_API_URL.format(board_token=self.board_token)
        try:
            response = httpx.get(url, params={"content": "true"}, timeout=self.timeout)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ConnectorError(
                self.source_name,
                f"HTTP {exc.response.status_code} для board_token={self.board_token}",
            ) from exc
        except httpx.RequestError as exc:
            raise ConnectorError(
                self.source_name, f"Сетевая ошибка для board_token={self.board_token}: {exc}"
            ) from exc

        payload = response.json()
        jobs = payload.get("jobs", [])

        raw_vacancies: list[RawVacancy] = []
        for job in jobs:
            raw_vacancies.append(self._to_raw_vacancy(job))
        return raw_vacancies

    def _to_raw_vacancy(self, job: dict) -> RawVacancy:
        location_raw = (job.get("location") or {}).get("name", "") or ""
        departments = job.get("departments") or []
        department = departments[0]["name"] if departments else None

        date_posted: date | None = None
        updated_at = job.get("updated_at")
        if updated_at:
            try:
                date_posted = datetime.fromisoformat(
                    updated_at.replace("Z", "+00:00")
                ).date()
            except ValueError:
                date_posted = None

        job_id = f"greenhouse_{self.board_token}_{job['id']}"
        absolute_url = job.get("absolute_url", "")

        return RawVacancy(
            job_id=job_id,
            company_name=self.company_name,
            job_title=job.get("title", "").strip(),
            location_raw=location_raw,
            # country/city/work_format: Greenhouse не отдаёт их структурированно —
            # это заполнит normalizer (модуль 3), парсинг location_raw.
            work_format=WorkFormat.UNCLEAR,
            employment_type=None,
            department=department,
            date_posted=date_posted,
            date_discovered=datetime.utcnow(),
            source_name=f"{self.company_name} (Greenhouse)",
            source_type=SourceType.ATS,
            source_url=absolute_url,
            canonical_url=absolute_url,  # Greenhouse-страница компании и есть canonical
            canonical_job_id=str(job["id"]),
            job_description=(job.get("content") or ""),
            company_career_url=f"https://boards.greenhouse.io/{self.board_token}",
            status=VacancyLifecycleStatus.ACTIVE,
        )


def load_greenhouse_connectors_from_sources_config(sources_yaml_notes: str) -> None:
    """
    Заглушка-напоминание: board_token для каждой компании нужно указать явно,
    Greenhouse его нигде не публикует кроме самого URL. Практический способ —
    завести в company_watchlist трека (или в отдельном config/sources/*.yaml)
    поле `greenhouse_board_token` для тех компаний из watchlist, которые
    реально используют Greenhouse. Здесь оставлено как заметка для Фазы 4
    ("добавляете источники по одному"), чтобы не плодить в коде компании
    захардкоженными.
    """
    raise NotImplementedError(
        "Board tokens конкретных компаний должны прийти из конфига, "
        "не из кода — см. docstring."
    )
