# Подтверждение Docker-проверки

- Репозиторий: `Andrey787878/hackhaton`, ветка `database/postgresql`.
- Проверенный коммит реализации: `9aa9fc1632cd6069dd377db25f737ad05aa977a0`.
- [GitHub Actions, запуск 40545681206](https://github.com/Andrey787878/hackhaton/actions/runs/40545681206).
- Задание `database`: успешно; PostgreSQL 17.11, полный проект Docker Compose.
- Результат: **97 passed**, включая 10 проверок БД.

Файлы получены из артефакта `postgresql-docker-verification` этого запуска:

- `migrations.txt` - вывод контейнера migrate со всеми девятью миграциями;
- `database.json` - версия сервера, схема и проверка commit/read/rollback/cleanup;
- `tests.txt` - сборка и полный вывод Pytest;
- `tables.json` - счетчики и примеры строк тестовой базы;
- `tables-after-restart.json` - тот же снимок после перезапуска контейнера БД.

Последние два JSON совпадают. Скриншоты отчета показывают журнал миграций и
табличное представление результатов этого артефакта в локальном просмотрщике.
Тестовые данные получены из реально запущенного PostgreSQL в Docker.
