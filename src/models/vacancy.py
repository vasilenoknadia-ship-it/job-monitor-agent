"""
Единая модель вакансии (раздел 5 ТЗ).

Модель разделена на два "слоя":
- RawVacancy: то, что отдают коннекторы сразу после парсинга источника
  (ещё не нормализовано, не оценено).
- Vacancy: полная модель после normalizer + canonical resolver + dedup +
  classifier + geography validator + scorer. Именно эта модель пишется
  в лист Vacancies.

Оба класса — pydantic, чтобы:
- сразу ловить несоответствия схеме (отсутствующие поля, неверные типы);
- иметь единый .model_dump() для сериализации в строку Google Sheets;
- держать значения по умолчанию в одном месте, а не размазывать по коду.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import ClassVar, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums — везде, где ТЗ фиксирует закрытый список значений
# ---------------------------------------------------------------------------

class WorkFormat(str, Enum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"
    UNCLEAR = "unclear"


class SourceType(str, Enum):
    COMPANY = "company"
    ATS = "ats"
    JOB_BOARD = "job_board"
    AGENCY = "agency"
    AGGREGATOR = "aggregator"


class VacancyLifecycleStatus(str, Enum):
    """Поле `status` из раздела 5 (актуальность вакансии на источнике)."""
    ACTIVE = "active"
    CLOSED = "closed"
    UNCLEAR = "unclear"


class RepostStatus(str, Enum):
    """Раздел 8.2 — статус повторности вакансии между запусками."""
    NEW = "new"
    DUPLICATE = "duplicate"
    UPDATED = "updated"
    REPOSTED = "reposted"
    REOPENED = "reopened"
    CLOSED = "closed"


class GeographyStatus(str, Enum):
    """Раздел 10 — единый набор значений географического классификатора."""
    LITHUANIA_COMPATIBLE = "Lithuania compatible"
    REMOTE_FROM_LITHUANIA_CONFIRMED = "Remote from Lithuania confirmed"
    REMOTE_EU_EEA_COMPATIBLE = "Remote EU/EEA compatible"
    REMOTE_EUROPE_UNCLEAR = "Remote Europe — eligibility unclear"
    UK_REMOTE_MANUAL_VALIDATION = "UK remote — manual validation"
    IRELAND_REMOTE_MANUAL_VALIDATION = "Ireland remote — manual validation"
    REMOTE_ONLY_EMPLOYER_COUNTRY = "Remote only within employer country"
    RELOCATION_POSSIBLE = "Relocation possible"
    RELOCATION_REQUIRED = "Relocation required"
    INCOMPATIBLE_GEOGRAPHY = "Incompatible geography"
    LOCATION_UNCLEAR = "Location unclear"


class MatchClass(str, Enum):
    """Раздел 12 — шкала итогового скоринга."""
    EXCELLENT = "excellent"   # 90-100
    STRONG = "strong"         # 75-89
    MANUAL_REVIEW = "manual_review"  # 60-74
    REJECT = "reject"         # 0-59

    @classmethod
    def from_score(cls, score: int) -> "MatchClass":
        if score >= 90:
            return cls.EXCELLENT
        if score >= 75:
            return cls.STRONG
        if score >= 60:
            return cls.MANUAL_REVIEW
        return cls.REJECT


class ApplicationStatus(str, Enum):
    """Раздел 13.3 — пользовательское поле, агент выставляет только NEW."""
    NEW = "new"
    REVIEWING = "reviewing"
    APPLY = "apply"
    APPLIED = "applied"
    INTERVIEW = "interview"
    SAVED_FOR_LATER = "saved_for_later"
    NOT_INTERESTED = "not_interested"
    REJECTED = "rejected"
    DECLINED_BY_ME = "declined_by_me"
    CLOSED = "closed"


# ---------------------------------------------------------------------------
# RawVacancy — то, что возвращает connector до нормализации
# ---------------------------------------------------------------------------

class RawVacancy(BaseModel):
    """
    Минимум, который обязан вернуть любой connector (раздел 5, поля до
    'После оценки добавляются:'). Поля company_normalized /
    job_title_normalized сюда не входят — их считает normalizer.
    """

    job_id: str
    company_name: str
    job_title: str
    location_raw: str
    country: Optional[str] = None
    city: Optional[str] = None
    work_format: WorkFormat = WorkFormat.UNCLEAR
    remote_scope: Optional[str] = None
    employment_type: Optional[str] = None
    department: Optional[str] = None
    date_posted: Optional[date] = None
    date_discovered: datetime = Field(default_factory=datetime.utcnow)
    source_name: str
    source_type: SourceType
    source_url: str
    canonical_url: Optional[str] = None
    canonical_job_id: Optional[str] = None
    job_description: str = ""
    company_career_url: Optional[str] = None
    status: VacancyLifecycleStatus = VacancyLifecycleStatus.ACTIVE

    @field_validator("job_description")
    @classmethod
    def _strip_description(cls, v: str) -> str:
        return v.strip()


# ---------------------------------------------------------------------------
# Vacancy — полная модель после всего пайплайна (пишется в Google Sheets)
# ---------------------------------------------------------------------------

class Vacancy(RawVacancy):
    """
    Расширяет RawVacancy полями normalizer'а и результатами оценки.
    Порядок групп полей ниже намеренно соответствует разделу 13.2 ТЗ
    (системные / пользовательские / технические), чтобы маппинг на
    колонки Google Sheets был прямым.
    """

    # --- normalizer (раздел 6) ---
    company_normalized: str
    job_title_normalized: str

    # --- track classifier (раздел 11) + scorer (раздел 12) ---
    matched_tracks: list[str] = Field(default_factory=list)
    primary_track: Optional[str] = None
    track_scores: dict[str, Optional[int]] = Field(default_factory=dict)
    relevance_score: Optional[int] = None
    match_class: Optional[MatchClass] = None
    seniority_estimate: Optional[str] = None
    industry: Optional[str] = None
    company_priority: Optional[str] = None
    industry_interest_score: Optional[int] = None

    # --- geography validator (раздел 7, 10) ---
    geography_status: GeographyStatus = GeographyStatus.LOCATION_UNCLEAR
    discovered_via: list[str] = Field(default_factory=list)

    # --- lifecycle / freshness (раздел 8.2, 9) ---
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    last_changed: datetime = Field(default_factory=datetime.utcnow)
    last_checked: datetime = Field(default_factory=datetime.utcnow)
    result_status: RepostStatus = RepostStatus.NEW
    vacancy_status: VacancyLifecycleStatus = VacancyLifecycleStatus.ACTIVE

    # --- объяснение (раздел 13.8) ---
    why_matched: str = ""
    positive_signals: list[str] = Field(default_factory=list)
    negative_signals: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    manual_review_required: bool = False

    # --- B. пользовательские поля — агент НИКОГДА их не перезаписывает
    #     после первого создания строки (раздел 13.5) ---
    application_status: ApplicationStatus = ApplicationStatus.NEW
    decision_date: Optional[date] = None
    application_date: Optional[date] = None
    decision_note: str = ""
    cv_version: str = ""
    cover_letter_version: str = ""
    next_action: str = ""
    next_action_date: Optional[date] = None
    user_notes: str = ""

    # --- C. технические поля показа/синхронизации ---
    shown_to_user: bool = False
    first_shown_date: Optional[date] = None
    last_shown_date: Optional[date] = None
    row_created_at: datetime = Field(default_factory=datetime.utcnow)
    row_updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("why_matched")
    @classmethod
    def _limit_why_matched(cls, v: str) -> str:
        # раздел 13.8: максимум 350 символов
        return v[:350]

    # Поля, которые пользователь заполняет/меняет вручную и которые
    # агент не имеет права перезаписывать при update-е существующей строки
    # (раздел 13.5). Вынесено в constant, чтобы sheets/writer.py и
    # тесты ссылались на один и тот же список, а не дублировали его.
    USER_OWNED_FIELDS: ClassVar[tuple[str, ...]] = (
        "application_status",
        "decision_date",
        "application_date",
        "decision_note",
        "cv_version",
        "cover_letter_version",
        "next_action",
        "next_action_date",
        "user_notes",
    )
