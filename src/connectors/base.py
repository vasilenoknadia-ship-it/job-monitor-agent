"""
Общий интерфейс коннектора (модуль 2, раздел 3.2 ТЗ).

Любой источник — карьерная страница, ATS, job board, агрегатор — должен
уметь одно: отдать список RawVacancy. Как именно он их достаёт (HTTP JSON,
HTML-парсинг, Playwright) — деталь конкретной реализации, пайплайну
это не важно.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from models.vacancy import RawVacancy


class BaseConnector(ABC):
    """Базовый класс для всех коннекторов."""

    #: человекочитаемое имя источника, попадает в RawVacancy.source_name
    source_name: str = "base"

    @abstractmethod
    def fetch(self) -> list[RawVacancy]:
        """Возвращает список сырых вакансий с этого источника.

        Реализация НЕ должна кидать исключение наружу при обычных сетевых
        ошибках — пайплайн ожидает, что коннектор либо вернёт список
        (возможно пустой), либо кинет ConnectorError с понятным сообщением,
        чтобы это попало в лист Source Logs (раздел 13, лист Source Logs).
        """
        raise NotImplementedError


class ConnectorError(Exception):
    """Ошибка получения данных с источника — должна попасть в Source Logs,
    а не уронить весь запуск пайплайна."""

    def __init__(self, source_name: str, message: str):
        self.source_name = source_name
        self.message = message
        super().__init__(f"[{source_name}] {message}")
