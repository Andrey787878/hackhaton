"""Build a database mini-report from diagrams and actual Docker CI evidence.

python scripts/build_database_report.py --draft --output report-draft.pdf
python scripts/build_database_report.py --evidence-dir verification \
    --run-url https://github.com/Andrey787878/hackhaton/actions/runs/ID \
    --screenshot docs/database/docker-verification.png --output report.pdf

Requires requirements-report.txt. The final mode refuses missing evidence,
a non-PostgreSQL-17 run, failed tests or a missing screenshot.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "docs" / "database"
GITHUB = "https://github.com/Andrey787878/hackhaton"


def register_fonts() -> None:
    candidates = [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
                  Path("/usr/share/fonts/truetype/msttcorefonts"),
                  Path("/usr/share/fonts/truetype/dejavu")]
    for folder in candidates:
        for regular, bold in [("times.ttf", "timesbd.ttf"),
                              ("Times_New_Roman.ttf", "Times_New_Roman_Bold.ttf"),
                              ("DejaVuSerif.ttf", "DejaVuSerif-Bold.ttf")]:
            if (folder / regular).is_file() and (folder / bold).is_file():
                pdfmetrics.registerFont(TTFont("Report", str(folder / regular)))
                pdfmetrics.registerFont(TTFont("ReportBold", str(folder / bold)))
                pdfmetrics.registerFontFamily("Report", normal="Report", bold="ReportBold")
                return
    raise RuntimeError("Install Times New Roman or DejaVu Serif fonts.")


def evidence(args) -> dict:
    if args.draft:
        return {}
    if not args.evidence_dir or not args.screenshot or not args.run_url:
        raise ValueError("Final report requires evidence directory, screenshot and run URL.")
    data = json.loads((args.evidence_dir / "database.json").read_text(encoding="utf-8"))
    tests = (args.evidence_dir / "tests.txt").read_text(encoding="utf-8")
    migrations = (args.evidence_dir / "migrations.txt").read_text(encoding="utf-8")
    before = json.loads((args.evidence_dir / "tables.json").read_text(encoding="utf-8"))
    after = json.loads((args.evidence_dir / "tables-after-restart.json").read_text(encoding="utf-8"))
    passed = re.search(r"\b(\d+) passed\b", tests)
    if (not str(data["server_version"]).startswith("17.") or not data["schema_matches_models"]
            or not passed or re.search(r"\b\d+ (failed|error|errors)\b", tests)
            or "Running upgrade  -> 20260409_0000" not in migrations
            or "20260928_0008" not in migrations or before != after
            or not args.screenshot.is_file()
            or set(data.get("persistence", {}).values()) != {"passed"}):
        raise ValueError("Docker verification evidence is incomplete or unsuccessful.")
    return {**data, "passed": int(passed.group(1)), "snapshot": before}


def build(args) -> None:
    register_fonts()
    proof = evidence(args)
    width = A4[0] - 4 * cm
    body = ParagraphStyle("Body", fontName="Report", fontSize=14, leading=21,
                          alignment=TA_JUSTIFY, firstLineIndent=1.25 * cm, spaceAfter=7)
    small = ParagraphStyle("Small", parent=body, fontSize=11, leading=14,
                           firstLineIndent=0, alignment=TA_LEFT, spaceAfter=5)
    heading = ParagraphStyle("Heading", parent=body, fontName="ReportBold", alignment=TA_CENTER,
                             firstLineIndent=0, spaceBefore=6, spaceAfter=15, keepWithNext=True)
    center = ParagraphStyle("Center", parent=body, alignment=TA_CENTER, firstLineIndent=0)
    code = ParagraphStyle("Code", fontName="Courier", fontSize=9.3, leading=13, spaceAfter=12)
    story = []

    def p(value, style=body):
        story.append(Paragraph(value, style))

    def h(value):
        p(value, heading)

    def link(label, target):
        p(f'<link href="{escape(target)}" color="#163e70"><u>{escape(label)}</u></link>', small)

    def page():
        story.append(PageBreak())

    def picture(path, max_height, caption):
        image = Image(str(path))
        scale = min(width / image.imageWidth, max_height / image.imageHeight)
        image.drawWidth = image.imageWidth * scale
        image.drawHeight = image.imageHeight * scale
        story.append(image)
        story.append(Spacer(1, 7))
        p(caption, small)

    p('ФГБОУ ВО «ЮГОРСКИЙ ГОСУДАРСТВЕННЫЙ УНИВЕРСИТЕТ»', center)
    p('ИНЖЕНЕРНАЯ ШКОЛА ЦИФРОВЫХ ТЕХНОЛОГИЙ', center)
    story.append(Spacer(1, 3.2 * cm))
    h('МИНИ-ОТЧЕТ')
    p('по проектированию и интеграции базы данных<br/>веб-приложения', center)
    p('«Платформа онлайн-хакатонов и соревнований»', center)
    story.append(Spacer(1, 2.2 * cm))
    p('Выполнили: студенты группы ПИ41Б, команда № 3<br/>Полуянов, Бойдаченко, Абдурахман, Борисов', center)
    p('Проверил: Исмагулов Милан Ерикович', center)
    story.append(Spacer(1, 3 * cm))
    p('г. Ханты-Мансийск, 2026 г.', center)
    page()

    h('1 ЦЕЛЬ И РЕЗУЛЬТАТ РАБОТЫ')
    p('Цель работы - обеспечить надежное хранение данных бэкенда платформы хакатонов в PostgreSQL, '
      'настроить воспроизводимый запуск и подтвердить целостность и сохранение информации.')
    p('Использована существующая схема серверной части из dev: 17 прикладных таблиц, '
      '32 внешних ключа и 7 CHECK-ограничений. Подготовлены проверка схемы и транзакций, '
      '10 тестов БД, Docker-проверка проекта, описание таблиц и ER-диаграммы.')
    if args.draft:
        p('<b>Статус черновика.</b> Изменения подготовлены в локальной ветке database/postgresql. '
          'Публикация в GitHub, Docker-прогон и слияние в dev ожидают права записи. '
          'Успешное выполнение этих действий в данном черновике не утверждается.', small)
    else:
        p(f'Проверка выполнена в Docker Compose с PostgreSQL {escape(str(proof["server_version"]))}. '
          f'Полный набор интеграционных тестов: {proof["passed"]} успешно. '
          'Сохранение данных подтверждено после перезапуска контейнера БД.')
    h('2 ССЫЛКИ НА КОД И ВЫБРАННЫЙ СТЕК')
    link('Репозиторий: Andrey787878/hackhaton', GITHUB)
    link('Отдельная ветка базы данных: database/postgresql', GITHUB + '/tree/database/postgresql')
    for label, path in [('Миграции Alembic', '/tree/dev/alembic/versions'),
                        ('ORM-модели: app/models.py', '/blob/dev/app/models.py'),
                        ('Конфигурация: app/config.py и app/db.py', '/blob/dev/app/db.py'),
                        ('Docker Compose: docker-compose.yml', '/blob/dev/docker-compose.yml')]:
        link(label, GITHUB + path)
    p('PostgreSQL 17 - реляционная СУБД: связи, внешние ключи, индексы и транзакции '
      'подходят для команд, решений и оценок. SQLAlchemy 2.x описывает модели и управляет '
      'сессиями; psycopg 3 служит драйвером подключения. Alembic хранит историю схемы. '
      'Docker Compose запускает PostgreSQL, API, миграции и MinIO.', small)
    page()

    h('3 АРХИТЕКТУРА РАБОТЫ С ДАННЫМИ')
    p('HTTP-запрос проходит через маршрут FastAPI, проверку доступа и сервис бизнес-логики. '
      'Сервис работает с сессией SQLAlchemy, драйвер psycopg передает SQL в PostgreSQL. '
      'Архивы решений находятся в MinIO; база хранит их метаданные.')
    story.append(Preformatted('hackhaton/\n'
        '|-- app/\n'
        '|   |-- config.py          # POSTGRES_*\n'
        '|   |-- db.py              # engine, SessionLocal, UTC\n'
        '|   |-- models.py          # ORM models and constraints\n'
        '|   |-- *_service.py       # queries and transactions\n'
        '|   `-- health_routes.py   # SELECT 1\n'
        '|-- alembic/\n'
        '|   |-- env.py             # connection and metadata\n'
        '|   `-- versions/          # migration history\n'
        '|-- scripts/\n'
        '|   |-- init_env.py\n'
        '|   |-- verify_database.py\n'
        '|   `-- database_snapshot.py\n'
        '|-- tests/test_database.py\n'
        '|-- .github/workflows/database.yml\n'
        '|-- docker-compose.yml\n'
        '|-- compose.database.yml\n'
        '`-- compose.test.yml', code))
    p('Девять миграций создают пользователей и сессии (0000), RBAC (0001), базовые роли '
      '(0002), профиль и роли платформы (0003), хакатоны и кейсы (0004), команды (0005), '
      'решения (0006), оценки (0007) и уведомления (0008). '
      'Актуальная ревизия: 20260928_0008.', small)
    p('В Docker сервис migrate ожидает готовности PostgreSQL и выполняет upgrade head. '
      'API запускается после успешных миграций и настройки MinIO. Данные БД размещаются '
      'в постоянном томе pgdata. Соединения приложения используют UTC, проверку pool_pre_ping '
      'и тайм-аут подключения 5 секунд.', small)
    page()

    h('4 ER-ДИАГРАММЫ БАЗЫ ДАННЫХ')
    p('Схема разделена на три части для читаемости. PK - первичный ключ; FK - внешний '
      'ключ; знак ? - допустим NULL. Стрелка в строке FK указывает таблицу из другой '
      'части схемы. Отношение 1 : 0..N означает одного родителя и произвольное число '
      'дочерних записей.', small)
    picture(FIGURES / 'erd-events.png', 15 * cm,
            'Рисунок 1 - Хакатоны, кейсы, критерии, команды, состав и приглашения.')
    p('Составной FK team_members(team_id, hackathon_id) гарантирует принадлежность '
      'членства нужному хакатону. Уникальность (hackathon_id, user_id) запрещает '
      'участие пользователя в двух командах одного события.', small)
    page()

    h('4 ER-ДИАГРАММЫ БАЗЫ ДАННЫХ (ПРОДОЛЖЕНИЕ)')
    picture(FIGURES / 'erd-submissions.png', 17 * cm,
            'Рисунок 2 - Решения, файлы, назначения экспертов, оценки и уведомления.')
    p('Решение принадлежит команде и кейсу, содержит URL и/или ссылку на архив. '
      'stored_object_id уникален: один объект относится максимум к одному решению. '
      'Оценки связаны с назначением эксперта и критерием. Уведомления ссылаются на '
      'получателя и автора действия; resource_type/resource_id являются логической '
      'ссылкой, а не внешним ключом.', small)
    page()

    h('4 ER-ДИАГРАММЫ БАЗЫ ДАННЫХ (ПРОДОЛЖЕНИЕ)')
    picture(FIGURES / 'erd-access.png', 13 * cm,
            'Рисунок 3 - Пользователи, сессии, роли и разрешения.')
    p('Связи пользователей и ролей, а также ролей и разрешений реализованы отдельными '
      'таблицами M:N. created_by и deleted_by ссылаются на users; на схеме эти повторяющиеся '
      'связи обозначены в строках полей. Логины и email уникальны без учета регистра, '
      'пароли хранятся как bcrypt-хэши, refresh-токены - как хэши.', small)
    p('Основные роли платформы: admin, organizer, participant, expert. Базовые роли '
      'user и guest сохранены для совместимости с RBAC. Создание схемы и начальных '
      'прав выполняется миграциями; учетные записи демонстрации создаются отдельной '
      'командой оператора.', small)
    page()

    h('5 ОСНОВНЫЕ ТАБЛИЦЫ И ЦЕЛОСТНОСТЬ')
    rows = [('Таблица', 'Назначение'),
            ('users', 'Учетные записи и профиль пользователя.'),
            ('auth_sessions', 'JWT-сессии, хэши refresh, сроки и отзыв.'),
            ('roles / permissions', 'Роли и разрешения с авторами изменений.'),
            ('role_user / permission_role', 'Назначения ролей и разрешений, связи M:N.'),
            ('hackathons', 'Организатор, описание и даты события.'),
            ('cases / criteria', 'Задачи, шкалы, веса и порядок критериев.'),
            ('teams / team_members', 'Команды, капитаны и состав участников.'),
            ('invites', 'Хэши кодов приглашений и их отзыв.'),
            ('stored_objects', 'Ключ объекта MinIO, имя, размер и SHA-256.'),
            ('submissions', 'История сдач, автор, URL и/или архив.'),
            ('expert_assignments', 'Назначения экспертов на решения.'),
            ('scores', 'Значения баллов по критериям назначения.'),
            ('notifications', 'Личный журнал событий и отметки прочтения.')]
    cells = [[Paragraph(escape(a), small), Paragraph(escape(b), small)] for a, b in rows]
    table = Table(cells, colWidths=[5.5 * cm, width - 5.5 * cm], repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e7edf4')),
                               ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                               ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#b7c3d0')),
                               ('LEFTPADDING', (0, 0), (-1, -1), 7),
                               ('RIGHTPADDING', (0, 0), (-1, -1), 7),
                               ('TOPPADDING', (0, 0), (-1, -1), 5),
                               ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    story.append(table)
    story.append(Spacer(1, 10))
    p('CHECK-ограничения проверяют даты хакатона, шкалы и веса критериев, размер файла, '
      'наличие содержимого решения и диапазон балла. Уникальные индексы защищают '
      'логины, названия команд, активные приглашения, назначения экспертов и оценки. '
      'FK используют CASCADE, RESTRICT или SET NULL по смыслу связи.', small)
    p('Дедлайн сдачи, права пользователя, принадлежность кейса событию команды и '
      'диапазон оценки конкретного критерия дополнительно проверяются сервисами API.', small)
    page()

    h('6 ПОДТВЕРЖДЕНИЕ РАБОТОСПОСОБНОСТИ')
    if args.draft:
        p('Для окончательного отчета необходимо выполнить Docker-проверку в GitHub Actions '
          'после предоставления права записи в репозиторий. Скриншот успешных миграций '
          'и итог полного набора тестов будут добавлены по результатам реального запуска.')
        p('В этом черновике отсутствуют подтверждения Docker-прогона. Изображения '
          'несуществующего запуска и вымышленные результаты не используются.', small)
    else:
        p(f'Проект поднят через Docker Compose: PostgreSQL {escape(str(proof["server_version"]))}, '
          'API, миграции и MinIO. Все девять миграций выполнены успешно; '
          'alembic check не обнаружил новых операций обновления схемы.')
        picture(args.screenshot, 12 * cm,
                'Рисунок 4 - Консоль успешной Docker-проверки миграций PostgreSQL в GitHub Actions.')
        p(f'Полный прогон: {proof["passed"]} тестов успешно, включая 10 проверок БД. '
          'Проверены FK, регистронезависимая уникальность, даты, принадлежность членства '
          'хакатону, содержимое решения, активные приглашения и диапазон баллов.', small)
        p('Отдельная проверка подтвердила commit, чтение через другое соединение, rollback '
          'и очистку тестовой записи. Снимки заполненных таблиц до и после перезапуска '
          'контейнера PostgreSQL совпали.', small)
        link('Журнал Docker-проверки и артефакт postgresql-docker-verification', args.run_url)
    page()

    h('7 ЗАПУСК И ЗАКЛЮЧЕНИЕ')
    p('Для запуска из корня репозитория необходимо сгенерировать локальную конфигурацию '
      'и запустить Docker Compose. Секреты создаются случайно и исключены из Git.')
    story.append(Preformatted('python scripts/init_env.py\n'
        'docker compose up --build -d --wait\n'
        'docker compose exec -T api python -m alembic check\n'
        'docker compose exec -T api python -m scripts.verify_database', code))
    p('Проверка API и БД: http://localhost:8080/api/v1/health. Для pgAdmin или DBeaver '
      'можно добавить compose.database.yml, который публикует порт базы только на '
      '127.0.0.1. Обычная остановка Compose сохраняет том pgdata.', small)
    if args.draft:
        p('Проектные материалы и проверки подготовлены. Завершение работы требует '
          'публикации отдельной ветки, успешного Docker-прогона, добавления его '
          'скриншота и слияния в dev. После этого черновик заменяется итоговым отчетом.')
    else:
        p('База данных интегрирована с существующим бэкендом. Схема, ограничения, '
          'миграции, постоянное хранение и Docker-запуск проверены. Файлы базы данных '
          'и документация подготовлены в отдельной ветке database/postgresql для dev.')
    h('СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ')
    for label, url in [
        ('1. Репозиторий проекта', GITHUB),
        ('2. PostgreSQL 17: ограничения таблиц', 'https://www.postgresql.org/docs/17/ddl-constraints.html'),
        ('3. SQLAlchemy: сессии и транзакции', 'https://docs.sqlalchemy.org/en/20/orm/session_basics.html'),
        ('4. Alembic: сравнение схемы с моделями', 'https://alembic.sqlalchemy.org/en/latest/autogenerate.html'),
        ('5. Docker Compose: порядок запуска сервисов', 'https://docs.docker.com/compose/how-tos/startup-order/'),
    ]:
        link(label + ' (дата обращения: 27.10.2026)', url)

    def decorate(canvas, doc):
        canvas.saveState()
        if doc.page > 1:
            canvas.setFont('Report', 11)
            canvas.drawCentredString(A4[0] / 2, 1.2 * cm, str(doc.page))
        if args.draft:
            canvas.setFillColor(colors.HexColor('#9c3131'))
            canvas.setFont('Report', 9)
            canvas.drawRightString(A4[0] - 2 * cm, A4[1] - 1.2 * cm, 'ЧЕРНОВИК - Docker-проверка ожидается')
        canvas.restoreState()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(args.output), pagesize=A4, leftMargin=3 * cm,
                            rightMargin=1 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
                            title='Мини-отчет: база данных PostgreSQL платформы хакатонов',
                            author='Команда № 3, ПИ41Б')
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--draft', action='store_true')
    parser.add_argument('--evidence-dir', type=Path)
    parser.add_argument('--run-url')
    parser.add_argument('--screenshot', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    build(parser.parse_args())
