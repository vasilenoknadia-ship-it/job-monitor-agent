# Job Monitor Agent

Агент ежедневного мониторинга вакансий по трём карьерным трекам
(Amazon/Marketplace, E-commerce Business Ownership, Category/Buying/Commercial).
Полная спецификация — в `Сводное ТЗ` (не входит в этот репозиторий кода,
хранится отдельно). Google Sheets — единственный пользовательский интерфейс
и хранилище состояния на этапе MVP.

## Статус

Фаза 2 из плана выполнена: Google Sheets writer реализован полностью
(`src/sheets/auth.py`, `src/sheets/schema.py`, `src/sheets/writer.py`).
Пайплайн теперь реально создаёт листы `Vacancies`, `Runs`, `Source Logs`,
`Lists` при первом запуске (если их ещё нет), обновляет существующие строки
по `job_id` без создания дублей и никогда не перезаписывает пользовательские
поля (`application_status`, `decision_date`, `user_notes` и т.д.) при
повторном запуске.

Остаются заглушками (`*_stub` в `src/pipeline.py`): canonical resolver,
дедупликация (сейчас только точное совпадение по `job_id`), track classifier,
geography validator, relevance scorer. Это следующие шаги — по одному
модулю за раз.

## Структура репозитория

```
config/
  tracks/                 # правила треков — раздел 2 и 25-27 ТЗ
  sources/                # правила источников — раздел 24 ТЗ
src/
  models/vacancy.py        # единая модель вакансии — раздел 5 ТЗ
  config_loader/           # загрузка и валидация YAML-конфигов
  connectors/               # получение вакансий с источников
    base.py                 # общий интерфейс коннектора
    ats/greenhouse.py        # первый реализованный коннектор
  normalizer/               # нормализация полей — раздел 6 ТЗ
  canonical_resolver/       # поиск оригинала вакансии — раздел 7 (TODO)
  deduplication/            # дедупликация — раздел 8 (TODO)
  classifier/                # оценка по трекам — раздел 11 (TODO)
  geography/                 # географическая классификация — раздел 10 (TODO)
  scorer/                     # итоговый score — раздел 12 (TODO)
  sheets/                     # запись в Google Sheets — раздел 13 (TODO)
  pipeline.py                 # оркестратор всех этапов
main.py                        # точка входа
tests/                          # тесты (pytest)
.github/workflows/daily_run.yml # GitHub Actions: cron + workflow_dispatch
```

## Установка (локально)

```bash
git clone <repo-url>
cd job-monitor-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить реальными значениями, .env не коммитить
```

## Google Sheets: настройка доступа

1. Google Cloud Console → создать проект → включить Google Sheets API и
   Google Drive API.
2. IAM & Admin → Service Accounts → создать сервисный аккаунт.
3. Создать JSON-ключ для сервисного аккаунта (Keys → Add Key → JSON).
   Если организация блокирует создание ключей политикой
   `iam.disableServiceAccountKeyCreation` — отключить эту политику для
   конкретного проекта через IAM & Admin → Organization Policies, либо
   перейти на Workload Identity Federation.
4. Создать Google Spreadsheet с листами `Vacancies`, `Runs`, `Source Logs`,
   `Lists` (раздел 13.1 ТЗ) и расшарить его на email сервисного аккаунта
   (`client_email` из JSON-ключа) с правами Editor.
5. Скопировать Spreadsheet ID из URL таблицы.

## GitHub Actions: секреты

В Settings → Secrets and variables → Actions добавить:
- `GOOGLE_SERVICE_ACCOUNT_JSON` — полное содержимое JSON-ключа сервисного
  аккаунта.
- `SPREADSHEET_ID` — ID таблицы.

## Запуск

Локально:
```bash
python main.py
```

Вручную в GitHub: Actions → Daily job monitoring run → Run workflow
(`workflow_dispatch`).

По расписанию: cron в `.github/workflows/daily_run.yml`, по умолчанию
настроен на ~07:00 Europe/Vilnius (см. комментарий в файле про переход
на летнее время).

## Как добавить новый источник

1. Если это ATS с публичным API — посмотреть, есть ли он уже в
   `config/sources/source_monitoring.yaml` под `ats_platforms`
   (`has_public_api: true`), и написать коннектор по образцу
   `src/connectors/ats/greenhouse.py`.
2. Если публичного API нет — коннектор должен парсить HTML (BeautifulSoup)
   или рендерить страницу (Playwright), но интерфейс тот же:
   класс, унаследованный от `BaseConnector`, с методом `fetch()`,
   возвращающим `list[RawVacancy]`.
3. Зарегистрировать источник в `config/sources/source_monitoring.yaml`
   (секция `sources`), чтобы он был виден в конфигурации, а не только
   в коде.
4. Добавить коннектор в список, который собирает `_build_connectors()`
   в `src/pipeline.py` (в будущем это должно строиться из company_watchlist
   автоматически, а не руками — см. TODO в коде).

## Как добавить новую компанию в watchlist

Добавить объект в `company_watchlist` соответствующего
`config/tracks/track_*.yaml` — код менять не нужно.

## Тесты

```bash
pytest
```

## Приоритеты (раздел 29 ТЗ)

Важнее всего: надёжность, отсутствие дублей, защита пользовательских данных
в Google Sheets, прозрачное объяснение оценки, лёгкое расширение watchlist
и источников. Менее важно на старте: максимум источников, отдельный UI,
мгновенные уведомления, автоматическая подача заявок.
