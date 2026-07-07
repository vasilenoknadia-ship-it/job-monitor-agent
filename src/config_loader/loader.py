"""
Config loader (модуль 1, раздел 2 ТЗ).

Задача: читать YAML-файлы треков и источников и отдавать их дальше по
пайплайну как проверенные объекты — а не сырые dict'ы. Никакой бизнес-логики
здесь быть не должно: если track_classifier захочет узнать "какой у трека
watchlist компаний" — он спрашивает это у TrackConfig, а не парсит YAML сам.

Контракт треков и источников — раздел 2 ТЗ. Обязательные ключи из контракта
проверяются здесь at load-time, чтобы сломанный конфиг падал сразу при
старте пайплайна, а не где-то в середине classifier'а.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Обязательные ключи контракта трека (раздел 2)
TRACK_CONTRACT_KEYS = (
    "track_id",
    "track_name",
    "target_titles",
    "conditional_titles",
    "required_context_signals",
    "positive_signals",
    "negative_signals",
    "explicit_exclusions",
    "seniority_rules",
    "geography_rules",
    "company_watchlist",
    "scoring_rules",
    "output_explanation_fields",
)

# Обязательные ключи контракта источников (раздел 2)
SOURCES_CONTRACT_KEYS = (
    "sources",
    "ats_platforms",
    "source_priority_rules",
    "canonical_source_rules",
    "freshness_rules",
    "fallback_rules",
)


class ConfigValidationError(Exception):
    """Конфиг не соответствует контракту из раздела 2 ТЗ."""


@dataclass
class TrackConfig:
    """Обёртка над одним track_*.yaml. Данные доступны как есть, плюс
    несколько удобных аксессоров, которыми будет пользоваться classifier."""

    raw: dict
    source_path: Path

    @property
    def track_id(self) -> str:
        return self.raw["track_id"]

    @property
    def track_name(self) -> str:
        return self.raw["track_name"]

    @property
    def company_watchlist(self) -> list[dict]:
        return self.raw.get("company_watchlist", [])

    @property
    def target_titles(self) -> list[str]:
        return self.raw.get("target_titles", [])

    @property
    def explicit_exclusions(self) -> list[str]:
        return self.raw.get("explicit_exclusions", [])

    def watchlist_company_names(self) -> set[str]:
        """Нормализованные (lower) имена компаний из watchlist — удобно
        для быстрой проверки 'эта компания вообще в списке?'."""
        return {
            c["name"].strip().lower()
            for c in self.company_watchlist
            if isinstance(c, dict) and "name" in c
        }


@dataclass
class SourcesConfig:
    """Обёртка над source_monitoring.yaml."""

    raw: dict
    source_path: Path

    @property
    def sources(self) -> list[dict]:
        return self.raw.get("sources", [])

    @property
    def ats_platforms(self) -> list[dict]:
        return self.raw.get("ats_platforms", [])

    def sources_by_type(self, source_type: str) -> list[dict]:
        return [s for s in self.sources if s.get("source_type") == source_type]


@dataclass
class AppConfig:
    """Всё, что нужно пайплайну за один load(): треки + источники."""

    tracks: list[TrackConfig] = field(default_factory=list)
    sources: SourcesConfig | None = None

    def track_by_id(self, track_id: str) -> TrackConfig:
        for t in self.tracks:
            if t.track_id == track_id:
                return t
        raise KeyError(f"Track '{track_id}' не найден среди загруженных конфигов")


def _validate_contract(data: dict, required_keys: tuple[str, ...], path: Path) -> None:
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise ConfigValidationError(
            f"{path}: отсутствуют обязательные ключи контракта: {missing}"
        )


def load_track_config(path: Path) -> TrackConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    _validate_contract(data, TRACK_CONTRACT_KEYS, path)
    return TrackConfig(raw=data, source_path=path)


def load_sources_config(path: Path) -> SourcesConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    _validate_contract(data, SOURCES_CONTRACT_KEYS, path)
    return SourcesConfig(raw=data, source_path=path)


def load_all(config_dir: str | Path = "config") -> AppConfig:
    """Точка входа: сканирует config/tracks/*.yaml и config/sources/*.yaml.

    Требования ТЗ (раздел 2): общий движок не должен содержать
    захардкоженные списки компаний/тайтлов — поэтому здесь мы просто
    сканируем директорию, а не перечисляем имена файлов явно. Добавление
    нового трека = добавление нового .yaml файла, без правки кода.
    """
    config_dir = Path(config_dir)
    tracks_dir = config_dir / "tracks"
    sources_dir = config_dir / "sources"

    if not tracks_dir.exists():
        raise FileNotFoundError(f"Не найдена директория треков: {tracks_dir}")
    if not sources_dir.exists():
        raise FileNotFoundError(f"Не найдена директория источников: {sources_dir}")

    track_files = sorted(tracks_dir.glob("*.yaml"))
    if not track_files:
        raise ConfigValidationError(f"В {tracks_dir} не найдено ни одного трека (*.yaml)")

    tracks = [load_track_config(p) for p in track_files]

    source_files = sorted(sources_dir.glob("*.yaml"))
    if not source_files:
        raise ConfigValidationError(f"В {sources_dir} не найдено ни одного файла источников")
    # MVP: один файл источников. Если появится несколько — здесь нужно
    # будет смёрджить их, а не просто взять последний.
    sources = load_sources_config(source_files[-1])

    return AppConfig(tracks=tracks, sources=sources)


if __name__ == "__main__":
    # Быстрая ручная проверка: python -m config_loader.loader
    cfg = load_all()
    print(f"Загружено треков: {len(cfg.tracks)}")
    for t in cfg.tracks:
        print(f"  - {t.track_id}: {t.track_name} ({len(t.company_watchlist)} компаний в watchlist)")
    print(f"Источников: {len(cfg.sources.sources)}, ATS-платформ: {len(cfg.sources.ats_platforms)}")
