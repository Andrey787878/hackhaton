# Платформа онлайн-хакатонов

Реализованы основа бэкенда и пользователи: FastAPI, PostgreSQL, миграции, JWT-сессии,
роли платформы, профиль, создание администратора и демоаккаунтов.
Также добавлены хакатоны, публикация кейсов, критерии и серверная проверка периода
доступа к материалам. Добавлены команды, капитаны, приглашения и вступление по коду.
Сдача URL и/или архива с серверным дедлайном и приватным MinIO добавлена.
Эксперты оценивают назначенные решения; рейтинг кейса рассчитывается автоматически.
Журнал уведомлений и сквозная проверка дополняют серверные сценарии.
Подзадачи и критерии готовности: [план разработки](docs/PLAN.md).

Мини-отчёт по серверной части: [DOCX](docs/mini-report-backend.docx) и
[PDF](docs/mini-report-backend.pdf). Подтверждающие скриншоты находятся в
[docs/figures](docs/figures).

База данных: [схема, ER-диаграммы, миграции и запуск PostgreSQL в Docker](docs/DATABASE.md).
Проверка БД и полного проекта в Docker Compose: [.github/workflows/database.yml](.github/workflows/database.yml).

## Стек

- Python 3.11 + FastAPI — типизированный API и Swagger/OpenAPI.
- Pydantic — валидация запросов и настроек.
- PostgreSQL 17 + SQLAlchemy 2 — постоянное хранение и транзакции.
- Alembic — версионирование схемы БД.
- PyJWT + bcrypt — JWT, refresh rotation и хэширование паролей.
- Docker Compose — воспроизводимый запуск API, БД, MinIO и миграций.
- Pytest + HTTPX — интеграционные тесты с PostgreSQL.
- MinIO/S3 — приватное хранение архивов отдельно от PostgreSQL.

## Запуск

Нужны Python 3 для генерации конфигурации и Docker с Compose v2.
Из корня репозитория:

```bash
python3 scripts/init_env.py
docker compose up --build -d --wait
```

В Windows используйте `python`, если команда `python3` отсутствует.
Скрипт создаёт `.env` со случайными секретами, не перезаписывая существующий файл.
`.env` исключён из Git и Docker-образа. Миграции выполняются автоматически перед API.
Данные PostgreSQL сохраняются в томе `pgdata`, порт БД наружу не публикуется.
При занятом порте 8080 измените `APP_PORT` в `.env`.

- Swagger: http://localhost:8080/docs
- OpenAPI: http://localhost:8080/openapi.json
- Проверка API и БД: http://localhost:8080/api/v1/health

```bash
docker compose ps
docker compose logs api migrate
docker compose down
```

## Проверка авторизации

В Swagger выполните `POST /api/v1/auth/register`:

```json
{
  "username": "DemoUser",
  "email": "demo@example.com",
  "password": "Demo-password-123!",
  "c_password": "Demo-password-123!",
  "birthday": "2000-01-01"
}
```

Это пример для локальной демонстрации, аккаунт автоматически не создаётся.
Вызовите `/api/v1/auth/login` с `username` и `password`, вставьте `access_token`
в **Authorize** и выполните `/api/v1/auth/me`.
`/refresh` обновляет пару токенов; `/out` отзывает текущую сессию,
`/out_all` — все сессии. Повторное использование настоящего старого refresh
отзывает сессии пользователя; токен с неверной подписью не изменяет их.

Логин — от 3 до 64 латинских букв, цифр, `_` или `-`, начинается с буквы или цифры.
`birthday` и `display_name` необязательны. Пароль — от 8 символов,
цифра, строчная и заглавная буквы, спецсимвол; не более 72 байт UTF-8.
Регистрация назначает `participant`. Профиль можно изменить через `PATCH /api/v1/auth/me`.

Административные маршруты `/api/v1/admin` требуют разрешений.
Регистрация не выдаёт административных прав. Роли платформы: `admin`, `organizer`,
`participant`, `expert`. Капитан определяется внутри команды.
Создание администратора и демонстрационных пользователей:

```bash
docker compose exec api python -m app.bootstrap create-admin --username admin --email admin@example.com
docker compose exec api python -m app.bootstrap seed-demo
```

Обе команды запрашивают пароль без вывода. Повторный запуск не меняет существующие
пароли и не повышает права чужим аккаунтам. Матрица прав и инструкции:
[ACCESS_CONTROL.md](docs/ACCESS_CONTROL.md).

## Тесты

Отдельный Compose-проект использует собственные БД, сеть и том:

```bash
docker compose -p hackhaton-tests -f docker-compose.yml -f compose.test.yml run --build --rm test
docker compose -p hackhaton-tests -f docker-compose.yml -f compose.test.yml down -v
```

Последняя команда удаляет только тестовые данные. Тесты создают уникальных
пользователей; не запускайте их с настройками рабочей БД.

## Структура

```text
app/
  main.py               # приложение, подключение маршрутов /api/v1
  config.py             # настройки из окружения
  db.py                 # соединение и сессии SQLAlchemy
  models.py             # ORM-модели пользователей, событий, команд и решений
  schemas.py            # проверка входных данных
  dto.py                # типизированные объекты данных
  auth_routes.py        # маршруты авторизации
  auth_service.py       # регистрация и управление сессиями
  token_service.py      # JWT и хэши refresh
  dependencies.py       # текущий пользователь, проверки доступа
  rbac_routes.py        # административные маршруты
  rbac_service.py       # операции с ролями и разрешениями
  rbac_permissions.py   # идентификаторы разрешений
  health_routes.py      # проверка API и PostgreSQL
  bootstrap.py          # создание администратора и демоаккаунтов оператором
  hackathon_routes.py   # публичный API и управление своими хакатонами
  hackathon_service.py  # публикация, принадлежность объектов, сроки
  hackathon_schemas.py  # валидация дат, кейсов и критериев
  team_routes.py        # команды, приглашения, вступление
  team_service.py       # права капитана, дедлайны, транзакции
  team_schemas.py       # API-схемы команд и кодов
  submission_routes.py  # HTTP-приём, список и приватное скачивание
  submission_service.py # серверный дедлайн и согласование БД с MinIO
  submission_schemas.py # публичные данные сдачи
  storage.py            # S3-адаптер
  storage_bootstrap.py  # создание приватного bucket
  scoring_routes.py     # назначения, оценки и публичный рейтинг
  scoring_service.py    # права экспертов и расчёт итогового балла
  scoring_schemas.py    # валидация оценок и ответы рейтинга
  notification_routes.py  # личный журнал уведомлений и отметка прочтения
  notification_service.py # события предметных транзакций
  notification_schemas.py # ответы журнала
alembic/versions/        # миграции схемы и базовых данных
scripts/init_env.py     # генерация локальной конфигурации
scripts/demo_journey.py # сквозной сценарий через HTTP API
scripts/check_latency.py # локальная проверка p95 обычного GET
tests/                  # интеграционные тесты API с PostgreSQL и MinIO
docs/PLAN.md            # подзадачи до первого отчёта
docs/SOURCE.md          # происхождение кода
Dockerfile              # образы приложения и тестов
Dockerfile.minio        # сборка MinIO из официального исходного кода
docker-compose.yml      # PostgreSQL, MinIO, миграции, API
compose.test.yml        # изолированный тестовый сервис и хранилище
```

Поток запроса: маршрут → проверка данных/доступа → сервис → ORM → PostgreSQL.
Основа: [backend-labs/lb3](https://github.com/Andrey787878/backend-labs/tree/lb3).

Жизненный цикл хакатона, видимость материалов, примеры запросов и формула
будущего рейтинга: [HACKATHONS.md](docs/HACKATHONS.md).
Правила команд и проверка через Swagger: [TEAMS.md](docs/TEAMS.md).
Правила сдачи файлов: [SUBMISSIONS.md](docs/SUBMISSIONS.md).
Назначения экспертов и формула рейтинга: [SCORING.md](docs/SCORING.md).
Уведомления: [NOTIFICATIONS.md](docs/NOTIFICATIONS.md).
Сквозная демонстрация: [DEMO.md](docs/DEMO.md).
