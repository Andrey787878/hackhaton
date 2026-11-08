"""Собрать мини-отчёт по фронтенду (DOCX) в оформлении отчёта по бэкенду.

Запуск из корня репозитория: python scripts/build_frontend_report.py
Требуется python-docx (requirements-report.txt). PDF получается из DOCX,
например: soffice --headless --convert-to pdf --outdir docs docs/mini-report-frontend.docx
"""
from pathlib import Path
import sys

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_report import font, heading, hyperlink, page_number, text  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "mini-report-frontend.docx"
FIGURES = ROOT / "docs" / "frontend"
BRANCH = "https://github.com/Andrey787878/hackhaton/tree/frontend"
FRONTEND = BRANCH + "/frontend"


def picture(doc, filename, number, caption, width=16.0):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.space_before = Pt(5)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(FIGURES / filename), width=Cm(width))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.first_line_indent = Cm(0)
    cap.paragraph_format.space_before = Pt(3)
    cap.paragraph_format.space_after = Pt(8)
    font(cap.add_run(f"Рисунок {number} – {caption}"), size=14)


def code(doc, value, size=10):
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.line_spacing = 1.0
    p.paragraph_format.space_before = Pt(7)
    p.paragraph_format.space_after = Pt(7)
    font(p.add_run(value), size=size, name="Courier New")


TREE = """frontend/
├── Dockerfile            сборка (Node.js) → раздача (nginx)
├── nginx.conf            SPA, прокси /api → api:8080, лимит 21 МиБ
├── vite.config.ts        dev-прокси /api, настройки Vitest
├── package.json          зависимости и скрипты npm
└── src/
    ├── main.tsx          точка входа: роутер, AuthProvider
    ├── App.tsx           маршруты и защита по ролям
    ├── api/              сервисы работы с REST API
    │   ├── client.ts     fetch, Bearer, refresh, ошибки,
    │   │                 загрузка с прогрессом, скачивание
    │   ├── errors.ts     перевод ошибок FastAPI/Pydantic
    │   ├── types.ts      типы DTO бэкенда
    │   ├── auth.ts       вход, регистрация, профиль
    │   ├── hackathons.ts хакатоны, кейсы, рейтинг,
    │   │                 кабинет организатора
    │   ├── teams.ts      команды, invite-коды, сдачи
    │   ├── scoring.ts    назначения и оценки экспертов
    │   └── notifications.ts  журнал уведомлений
    ├── auth/             AuthContext, RequireAuth,
    │                     хранение пары JWT
    ├── hooks/            useAsync, useInterval, useServerNow
    ├── components/       Layout, Countdown, CriteriaTable,
    │                     Badges, Feedback, Icon
    ├── pages/            страницы приложения (11 модулей)
    ├── utils/            даты, формула оценки, серверные
    │                     часы, валидация, unit-тесты
    └── styles/           палитра и стили интерфейса"""


def build():
    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(3)
    section.right_margin = Cm(1.5)
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.header_distance = Cm(1)
    section.footer_distance = Cm(1)
    section.different_first_page_header_footer = True
    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(14)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.first_line_indent = Cm(1.25)
    normal.paragraph_format.space_after = Pt(0)
    page_number(section.footer.paragraphs[0])
    section.footer.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    for label in ("ФГБОУ ВО «ЮГОРСКИЙ ГОСУДАРСТВЕННЫЙ УНИВЕРСИТЕТ»",
                  "ИНЖЕНЕРНАЯ ШКОЛА ЦИФРОВЫХ ТЕХНОЛОГИЙ"):
        p = text(doc, label, align=WD_ALIGN_PARAGRAPH.CENTER, indent=False)
        p.paragraph_format.space_after = Pt(7)
    for _ in range(6):
        doc.add_paragraph()
    p = text(doc, "МИНИ-ОТЧЁТ", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False)
    p.paragraph_format.space_after = Pt(6)
    font(p.runs[0], bold=True)
    text(doc, "по разработке клиентской части веб-приложения",
         align=WD_ALIGN_PARAGRAPH.CENTER, indent=False)
    p = text(doc, "«Платформа онлайн-хакатонов и соревнований»",
             align=WD_ALIGN_PARAGRAPH.CENTER, indent=False)
    p.paragraph_format.space_after = Pt(18)
    for _ in range(4):
        doc.add_paragraph()
    text(doc, "Выполнили: студенты группы ПИ41Б, команда № 3",
         align=WD_ALIGN_PARAGRAPH.RIGHT, indent=False)
    text(doc, "Полуянов, Бойдаченко, Абдурахман, Борисов",
         align=WD_ALIGN_PARAGRAPH.RIGHT, indent=False)
    text(doc, "Проверил: Исмагулов Милан Ерикович",
         align=WD_ALIGN_PARAGRAPH.RIGHT, indent=False)
    for _ in range(5):
        doc.add_paragraph()
    text(doc, "г. Ханты-Мансийск, 2026 г.", align=WD_ALIGN_PARAGRAPH.CENTER, indent=False)
    doc.add_page_break()

    heading(doc, "1 ЦЕЛЬ И РЕЗУЛЬТАТ РАБОТЫ")
    text(doc, "Цель работы — разработать клиентскую часть платформы онлайн-хакатонов, "
         "которая взаимодействует с серверным API и отображает данные пользователю "
         "в зависимости от его роли.")
    text(doc, "Создано одностраничное веб-приложение HackPulse в тёмной палитре из "
         "оттенков чёрного, синего и красного. Реализованы публичный каталог "
         "хакатонов с обратным отсчётом по серверному времени, кабинет участника "
         "с командами и invite-кодами, сдача ссылки и архива с индикатором "
         "прогресса, кабинет эксперта с оценкой по критериям, кабинет организатора, "
         "публичный рейтинг с автообновлением, журнал уведомлений и профиль. "
         "Закрыты требования FE-01–FE-05 технического задания.")

    heading(doc, "2 ССЫЛКА НА GITHUB")
    text(doc, "Исходный код фронтенд-части размещён в репозитории проекта в ветке "
         "frontend, каталог frontend/. Адрес каталога:")
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0)
    hyperlink(p, FRONTEND, FRONTEND)
    text(doc, "В ветке также находятся Dockerfile и конфигурация nginx для запуска "
         "интерфейса вместе с API командой docker compose up, описание фронтенда "
         "docs/FRONTEND.md и скрипт демонстрационных данных scripts/seed_ui_demo.py.")

    heading(doc, "3 ВЫБРАННЫЙ СТЕК ТЕХНОЛОГИЙ")
    text(doc, "React 18 и TypeScript 5 выбраны для компонентного интерфейса и строгой "
         "типизации: ответы API описаны типами, соответствующими схемам Pydantic "
         "бэкенда. Маршрутизация страниц и проверка ролей выполнены на React Router 7.")
    text(doc, "Сборка и dev-сервер — Vite 8: горячая перезагрузка и прокси /api на "
         "FastAPI, поэтому браузер работает с одним источником и CORS не требуется. "
         "В Docker ту же роль выполняет nginx, который раздаёт собранные файлы "
         "и проксирует запросы к контейнеру API.")
    text(doc, "Стилизация — собственные CSS-файлы с дизайн-токенами без UI-фреймворка: "
         "палитра, адаптивная сетка для мобильных устройств, шрифты Inter и "
         "JetBrains Mono подключены локально через @fontsource. HTTP-клиент написан "
         "на fetch: он добавляет Bearer-токен, однократно обновляет пару токенов "
         "при ответе 401 и переводит ошибки сервера на понятный русский текст. "
         "Загрузка архива выполняется через XMLHttpRequest ради отображения "
         "прогресса. Unit-тесты выполняются в Vitest.")

    heading(doc, "4 СТРУКТУРА ПРОЕКТА")
    text(doc, "Код разделён на слой сервисов API, состояние авторизации, переиспользуемые "
         "хуки и компоненты, страницы и вспомогательные функции. Структура каталогов "
         "приведена ниже.")
    code(doc, TREE)
    text(doc, "Сервисы каталога api/ — единственное место, где формируются HTTP-запросы: "
         "страницы вызывают функции вида teamsApi.join(code) и получают "
         "типизированный результат или ApiError с сообщением для пользователя. "
         "AuthContext хранит текущего пользователя и восстанавливает сессию при "
         "загрузке, RequireAuth закрывает разделы по ролям участника, эксперта "
         "и организатора. Компонент Countdown считает время по смещению часов "
         "устройства относительно GET /api/v1/time, поэтому таймер соответствует "
         "серверному дедлайну.")
    text(doc, "Ключевые страницы: HomePage — каталог хакатонов; HackathonPage — сроки, "
         "кейсы и критерии; TeamPage — состав, управление invite-кодом для капитана "
         "и форма сдачи; ExpertPages — пул назначений и оценка; OrganizerHackathonPage — "
         "кейсы, критерии, публикация и назначение экспертов; LeaderboardPage — "
         "рейтинг. Для страницы итогов на сервер добавлен публичный маршрут "
         "GET /api/v1/hackathons/{id}/leaderboard с тестом.")

    heading(doc, "5 СКРИНШОТЫ ИНТЕРФЕЙСА")
    text(doc, "Скриншоты сделаны в браузере Google Chrome с открытой вкладкой «Сеть» "
         "инструментов разработчика (фильтр Fetch/XHR). В журнале видны запросы "
         "к API /api/v1 с методами и кодами успешных ответов 200 и 201. Интерфейс "
         "запущен в Docker Compose вместе с бэкендом, PostgreSQL и MinIO.")
    figures = (
        ("01-home.png", "Главная страница: каталог опубликованных хакатонов",
         "На рисунке 1 показан каталог хакатонов с фильтром по фазе; приложение "
         "запрашивает список, серверное время и состояние API."),
        ("02-hackathon.png", "Страница хакатона с обратным отсчётом (FE-01)",
         "На рисунке 2 — страница идущего хакатона: сроки в местном времени и UTC, "
         "таймер до дедлайна по серверным часам, кейсы и критерии."),
        ("03-upload-progress.png", "Загрузка архива решения с индикатором прогресса (FE-03)",
         "На рисунке 3 капитан отправляет ссылку и архив 6 МиБ; виден прогресс "
         "загрузки, запрос POST ещё выполняется."),
        ("04-submission-result.png", "Результат сдачи с серверным временем (FE-03)",
         "На рисунке 4 сервер принял решение (POST 201): показаны время сдачи, "
         "имя, размер и контрольная сумма архива, обновлена история сдач."),
        ("05-team-member.png", "Команда глазами участника, не являющегося капитаном (FE-02)",
         "На рисунке 5 участник видит состав и историю, но не видит управления "
         "invite-кодом и формы сдачи."),
        ("06-expert-scoring.png", "Оценка решения экспертом по критериям (FE-04)",
         "На рисунке 6 эксперт выставляет баллы с учётом диапазонов и весов; "
         "PUT-запрос сохранил оценку, итог 84,00 рассчитан сервером."),
        ("07-leaderboard.png", "Публичный рейтинг с автообновлением (FE-05)",
         "На рисунке 7 показан рейтинг завершённого хакатона по кейсу; данные "
         "обновляются каждые 10 секунд."),
        ("08-organizer.png", "Кабинет организатора: назначение экспертов",
         "На рисунке 8 организатор видит команды своего хакатона и назначения "
         "экспертов с итоговыми баллами."),
    )
    for number, (filename, caption, description) in enumerate(figures, 1):
        p = text(doc, description)
        p.paragraph_format.keep_with_next = True
        picture(doc, filename, number, caption)
    p = text(doc, "На рисунке 9 приведена страница хакатона в мобильном браузере "
             "(ширина 390 px): навигация свёрнута в меню, таймер выводится первым.")
    p.paragraph_format.keep_with_next = True
    picture(doc, "09-mobile.png", 9, "Адаптивная вёрстка на мобильном устройстве", width=6.5)

    heading(doc, "6 ЗАКЛЮЧЕНИЕ")
    text(doc, "Клиентская часть реализована и связана с серверным API: все данные "
         "интерфейс получает и изменяет только через /api/v1, права доступа "
         "проверяет сервер. Пройдены сценарии всех ролей: наблюдатель, участник, "
         "капитан, эксперт и организатор. Unit-тесты фронтенда (16) и интеграционные "
         "тесты бэкенда (98) выполняются успешно; production-сборка запускается "
         "в Docker Compose по инструкции README.")
    heading(doc, "СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ")
    for item in (
        "1. Задание 3. Платформа для онлайн-хакатонов и соревнований. URL: https://yusu-source.github.io/GH_pages/03_hackathon.html (дата обращения: 08.11.2026).",
        "2. ГОСТ 7.32—2017. Отчёт о научно-исследовательской работе. Структура и правила оформления.",
        "3. React — документация. URL: https://react.dev (дата обращения: 08.11.2026).",
        "4. Vite — документация. URL: https://vite.dev (дата обращения: 08.11.2026).",
        "5. Репозиторий проекта: https://github.com/Andrey787878/hackhaton.",
    ):
        text(doc, item, indent=False)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
