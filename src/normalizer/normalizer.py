"""
Normalizer (модуль 3, раздел 6 ТЗ).

Это первая, минимально рабочая версия — покрывает базовые правила из
раздела 6. Более тонкие случаи (специфичные суффиксы юрлиц по странам,
редкие варианты написания городов) стоит добавлять по мере того, как
они реально встретятся в данных, а не пытаться предугадать всё заранее.
"""

from __future__ import annotations

import re

from models.vacancy import RawVacancy, Vacancy

# Раздел 6: "удалить юридические суффиксы и вариации регистра"
_LEGAL_SUFFIXES = re.compile(
    r"\b(uab|ltd\.?|llc|inc\.?|gmbh|ag|s\.?a\.?|oy|ab|bv|plc)\b\.?",
    re.IGNORECASE,
)

_MULTISPACE = re.compile(r"\s+")


def normalize_company_name(name: str) -> str:
    cleaned = _LEGAL_SUFFIXES.sub("", name)
    cleaned = cleaned.replace("&", "and")
    cleaned = _MULTISPACE.sub(" ", cleaned).strip().lower()
    return cleaned


def normalize_job_title(title: str) -> str:
    # раздел 6: нормализовать дефисы и варианты ecommerce/e-commerce/e commerce
    t = title.lower()
    t = re.sub(r"\be[\s\-]?commerce\b", "ecommerce", t)
    t = t.replace("-", " ")
    t = _MULTISPACE.sub(" ", t).strip()
    return t


def normalize(raw: RawVacancy) -> Vacancy:
    """Строит Vacancy из RawVacancy, добавляя нормализованные поля.

    Остальные поля (track scores, geography_status и т.д.) остаются со
    значениями по умолчанию — их заполнят следующие этапы пайплайна
    (classifier, geography validator, scorer).
    """
    data = raw.model_dump()
    return Vacancy(
        **data,
        company_normalized=normalize_company_name(raw.company_name),
        job_title_normalized=normalize_job_title(raw.job_title),
    )
