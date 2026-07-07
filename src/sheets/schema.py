"""
Схема листов Google Sheets — единственное место, где перечислены названия
колонок (раздел 13 ТЗ). writer.py и state_storage.py ссылаются сюда,
а не дублируют списки колонок у себя.
"""

from __future__ import annotations

# --- Vacancies (раздел 13.2) ------------------------------------------------

# A. Системные поля — заполняет и обновляет агент
VACANCIES_SYSTEM_FIELDS = [
    "job_id",
    "canonical_job_id",
    "company_name",
    "company_normalized",
    "job_title",
    "job_title_normalized",
    "primary_track",
    "matched_tracks",
    "track_1_score",
    "track_2_score",
    "track_3_score",
    "relevance_score",
    "match_class",
    "seniority_estimate",
    "industry",
    "company_priority",
    "industry_interest_score",
    "location_raw",
    "city",
    "country",
    "work_format",
    "remote_scope",
    "geography_status",
    "employment_type",
    "department",
    "date_posted",
    "first_seen",
    "last_seen",
    "last_changed",
    "result_status",
    "vacancy_status",
    "source_name",
    "source_type",
    "source_url",
    "canonical_url",
    "discovered_via",
    "why_matched",
    "positive_signals",
    "negative_signals",
    "concerns",
    "manual_review_required",
    "last_checked",
]

# B. Пользовательские поля — агент НЕ перезаписывает при обновлении
# существующей строки (раздел 13.5)
VACANCIES_USER_FIELDS = [
    "application_status",
    "decision_date",
    "application_date",
    "decision_note",
    "cv_version",
    "cover_letter_version",
    "next_action",
    "next_action_date",
    "user_notes",
]

# C. Технические поля показа/синхронизации
VACANCIES_TECHNICAL_FIELDS = [
    "shown_to_user",
    "first_shown_date",
    "last_shown_date",
    "row_created_at",
    "row_updated_at",
]

VACANCIES_COLUMNS = VACANCIES_SYSTEM_FIELDS + VACANCIES_USER_FIELDS + VACANCIES_TECHNICAL_FIELDS

# --- Runs (раздел 13.1) -----------------------------------------------------

RUNS_COLUMNS = [
    "run_id",
    "started_at",
    "finished_at",
    "timezone",
    "sources_planned",
    "sources_checked",
    "sources_successful",
    "sources_partial",
    "sources_failed",
    "jobs_discovered_raw",
    "jobs_after_deduplication",
    "new_relevant_jobs",
    "updated_jobs",
    "reopened_jobs",
    "manual_review_jobs",
    "run_status",
    "run_note",
]

# --- Source Logs (раздел 13.1) ---------------------------------------------

SOURCE_LOGS_COLUMNS = [
    "run_id",
    "source_name",
    "source_type",
    "source_url",
    "run_status",
    "jobs_found",
    "error_type",
    "error_message",
    "attempts",
    "last_successful_run",
    "consecutive_failures",
    "checked_at",
]

# --- Lists (раздел 13.1) — служебные значения для выпадающих списков -------

LISTS_SHEET_VALUES = {
    "application_status": [
        "new", "reviewing", "apply", "applied", "interview",
        "saved_for_later", "not_interested", "rejected", "declined_by_me", "closed",
    ],
    "vacancy_status": ["active", "closed", "unclear"],
    "match_class": ["excellent", "strong", "manual_review", "reject"],
    "geography_status": [
        "Lithuania compatible",
        "Remote from Lithuania confirmed",
        "Remote EU/EEA compatible",
        "Remote Europe — eligibility unclear",
        "UK remote — manual validation",
        "Ireland remote — manual validation",
        "Remote only within employer country",
        "Relocation possible",
        "Relocation required",
        "Incompatible geography",
        "Location unclear",
    ],
    "work_format": ["onsite", "hybrid", "remote", "unclear"],
    "primary_track": ["track_1", "track_2", "track_3"],
    "next_action": [],  # свободный текст, список оставлен пустым намеренно
}
