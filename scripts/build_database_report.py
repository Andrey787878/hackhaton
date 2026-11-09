"""Build the database PDF in the supplied report's exact eight-page layout.

Retained PDF/DOCX are read-only design authorities. The builder preserves their
font sizes, line baselines, indents, headings, cover, image boxes and footers.
Run from the repository: python scripts/build_database_report.py
Requires requirements-report.txt and original Windows fonts; --font-dir overrides.
"""
from __future__ import annotations
import argparse
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
from docx import Document
import pdfplumber
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'docs/mini-report-backend.pdf'
REFERENCE_DOCX = ROOT / 'docs/mini-report-backend.docx'
REFERENCE_SHA256 = '6d1a63f64661b7c5982bbea31e2687e3b33a2758b5a1e4ce987c8b7a0096ab2b'
FIGURES = ROOT / 'docs/database'
GITHUB = 'https://github.com/Andrey787878/hackhaton'

def register_fonts(folder):
    for name, filename in [('Times','times.ttf'),('TimesBold','timesbd.ttf'),('CalibriBold','calibrib.ttf'),('CourierNew','cour.ttf')]:
        pdfmetrics.registerFont(TTFont(name,str(folder/filename)))

def font_name(source):
    if 'CourierNew' in source:return 'CourierNew'
    if 'Calibri' in source:return 'CalibriBold'
    return 'TimesBold' if 'Bold' in source else 'Times'

def normalize(value):return re.sub(r'[\s\-\u00ad]','',value)

def read_template():
    if hashlib.sha256(REFERENCE.read_bytes()).hexdigest()!=REFERENCE_SHA256:
        raise ValueError('Retained PDF differs from the supplied reference.')
    pages,lines=[],[]
    with pdfplumber.open(REFERENCE) as pdf:
        if len(pdf.pages)!=8:raise ValueError('Expected eight reference pages.')
        for number,page in enumerate(pdf.pages):
            pages.append({'width':page.width,'height':page.height,'footer':[c for c in page.chars if c['top']>780],'images':page.images})
            for line in page.extract_text_lines():
                if line['top']<780:lines.append({**line,'page':number})
    position,slots=0,[]
    for index,paragraph in enumerate(Document(REFERENCE_DOCX).paragraphs):
        if not paragraph.text.strip():continue
        target,matched,accumulated=normalize(paragraph.text),[],''
        while accumulated!=target:
            line=lines[position];position+=1;matched.append(line)
            accumulated+=normalize(line['text'])
            if not target.startswith(accumulated):raise ValueError(f'Paragraph mapping failed: {index}')
        slots.append({'id':index,'text':paragraph.text,'lines':matched})
    if position!=len(lines):raise ValueError('Unmapped reference text.')
    return pages,slots

def verify_evidence(folder):
    result=json.loads((folder/'database.json').read_text(encoding='utf-8'))
    tests=(folder/'tests.txt').read_text(encoding='utf-8')
    migrations=(folder/'migrations.txt').read_text(encoding='utf-8')
    before=json.loads((folder/'tables.json').read_text(encoding='utf-8'))
    after=json.loads((folder/'tables-after-restart.json').read_text(encoding='utf-8'))
    passed=re.search(r'\b(\d+) passed\b',tests)
    if (not str(result['server_version']).startswith('17.') or not result['schema_matches_models']
        or not passed or re.search(r'\b\d+ (failed|errors?)\b',tests)
        or 'Running upgrade  -> 20260409_0000' not in migrations or '20260928_0008' not in migrations
        or before!=after or set(result.get('persistence',{}).values())!={'passed'}):
        raise ValueError('Successful PostgreSQL 17 Docker evidence is required.')
    return int(passed.group(1))

def replacement_text(passed):
    return {
9:'по разработке базы данных веб-приложения',
26:'Цель работы — интегрировать PostgreSQL с бэкендом платформы онлайн-хакатонов, настроить подключение, миграции и постоянное хранение данных пользователей, команд, решений и оценок.',
27:'Подготовлена база из 17 прикладных таблиц с 32 внешними ключами и 7 CHECK-ограничениями. Проверены миграции, транзакции и сохранение данных при перезапуске контейнера. Составлены ER-диаграммы и описание модулей работы с БД.',
29:'Код и файлы базы данных опубликованы в GitHub в ветке dev после слияния отдельной ветки database/postgresql. Ссылка на миграции:',
30:GITHUB+'/tree/dev/alembic/versions',
31:'ORM-модели находятся в app/models.py, конфигурация — в app/config.py и app/db.py. В репозитории размещены Docker Compose, проверки и описание БД. Локальные секреты исключены из Git.',
33:'PostgreSQL 17 выбран как реляционная СУБД: связанные сущности платформы требуют внешних ключей, уникальности и атомарных транзакций. База запускается в Docker из образа postgres:17.',
34:'SQLAlchemy 2.x описывает ORM-модели и управляет сессиями. Драйвер psycopg 3 соединяет Python с PostgreSQL. Alembic последовательно применяет девять миграций схемы и начальных ролей.',
35:'Docker Compose запускает PostgreSQL, API, MinIO и сервис миграций. Том pgdata сохраняет данные; API ожидает готовности БД и успешного завершения миграций. Архивы хранятся в MinIO, их метаданные — в SQL. Соединения используют UTC и pool_pre_ping. Pytest проверяет целостность, запись и чтение данных; GitHub Actions запускает полный проект и тесты в Docker.',
37:'HTTP-запрос проходит через маршрут FastAPI, проверку доступа и сервис бизнес-логики. Сервис работает с сессией SQLAlchemy; psycopg передаёт SQL в PostgreSQL. Модели, настройки и миграции отделены от обработчиков запросов. Основные модули представлены ниже.',
38:'hackhaton/\n├── app/\n│   ├── config.py             параметры PostgreSQL\n│   ├── db.py                 соединение и сессии\n│   ├── models.py             ORM-модели и связи\n│   ├── dependencies.py       выдача сессии запросу\n│   ├── *_service.py          запросы и транзакции\n│   └── health_routes.py      проверка соединения\n├── alembic/\n│   ├── env.py                подключение и метаданные\n│   └── versions/             миграции схемы\n├── scripts/                  настройка и проверка БД\n├── tests/test_database.py    ограничения и транзакции\n├── docs/DATABASE.md          таблицы и ER-диаграммы\n├── .github/workflows/        Docker-проверка\n├── Dockerfile, docker-compose.yml\n├── compose.database.yml, compose.test.yml\n└── requirements.txt          ORM и драйвер PostgreSQL',
39:'users и auth_sessions хранят учётные записи и сессии; roles, permissions, role_user, permission_role — права. hackathons, cases, criteria описывают события; teams, team_members, invites — команды. submissions, stored_objects, expert_assignments, scores и notifications отвечают за решения, файлы, оценки и уведомления.',
41:'На рисунках 1–3 приведены ER-диаграммы основных таблиц и связей. На рисунках 4–6 показаны журнал успешных миграций, результат проверки схемы и заполненные данные из Docker-прогона PostgreSQL 17.',
42:'На рисунке 1 показаны связи хакатонов, кейсов, критериев, команд, участников и приглашений.',
44:'Рисунок 1 – ER-диаграмма: хакатоны и команды',
45:'На рисунке 2 показаны решения, файлы, назначения экспертов, оценки и журнал уведомлений.',
47:'Рисунок 2 – ER-диаграмма: решения и оценки',
48:'На рисунке 3 показаны пользователи, сессии, роли и разрешения.',
50:'Рисунок 3 – ER-диаграмма: пользователи и права',
51:'На рисунке 4 показано успешное выполнение миграций в Docker.',
53:'Рисунок 4 – Журнал миграций PostgreSQL в Docker',
54:'На рисунке 5 приведён результат проверки PostgreSQL: схема соответствует ORM-моделям, запись, чтение и откат транзакции успешны.',
56:'Рисунок 5 – Проверка схемы и транзакций базы данных',
57:'На рисунке 6 показаны строки таблицы scores тестовой БД после Docker-прогона: оценки связаны с экспертами и критериями.',
59:'Рисунок 6 – Пример заполненной таблицы scores',
60:f'В Docker успешно выполнены {passed} интеграционных тестов, включая 10 проверок БД. Проверены внешние ключи, уникальность, даты, состав команд, содержимое решений и диапазон оценок. alembic check не обнаружил расхождений схемы и моделей. Снимки таблиц до и после перезапуска контейнера PostgreSQL совпали.',
62:'PostgreSQL интегрирован с бэкендом платформы. Миграции, связи и ограничения проверены в Docker. Подтверждено сохранение данных в томе pgdata. Ветка database/postgresql слита в dev. Запуск воспроизводится через Docker Compose.',
    }

def break_lines(value,widths,font,size):
    words=value.split()
    @lru_cache(None)
    def measure(a,b):return pdfmetrics.stringWidth(' '.join(words[a:b]),font,size)
    @lru_cache(None)
    def solve(start,row):
        if row==len(widths):return (0,()) if start==len(words) else (float('inf'),())
        best=(float('inf'),())
        for end in range(start+1,len(words)+1):
            natural=measure(start,end)
            if natural>widths[row]+0.2:break
            last=row==len(widths)-1
            if last and end!=len(words):continue
            if not last and end==len(words):continue
            gap=(widths[row]-natural)/max(1,end-start-1)
            penalty=max(0,0.3-natural/widths[row])**2*100 if last else gap**2
            remaining,partition=solve(end,row+1)
            if penalty+remaining<best[0]:best=(penalty+remaining,(' '.join(words[start:end]),)+partition)
        return best
    score,result=solve(0,0)
    if score==float('inf'):raise ValueError(f'Content cannot fit {len(widths)} template lines: {value}')
    return list(result)

def copy_characters(output,characters):
    for char in characters:
        output.setFont(font_name(char['fontname']),char['size'])
        output.drawString(char['matrix'][4],char['matrix'][5],char['text'])

def build(args):
    register_fonts(args.font_dir)
    pages,slots=read_template()
    replacements=replacement_text(verify_evidence(args.evidence_dir))
    centered={9,44,47,50,53,56,59}
    page_slots={n:[s for s in slots if s['lines'][0]['page']==n] for n in range(8)}
    image_files={3:['report-figure-1.png'],4:['report-figure-2.png'],5:['report-figure-3.png'],6:['report-figure-4.png','report-figure-5.png'],7:['report-figure-6.png']}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    output=canvas.Canvas(str(args.output),pagesize=(pages[0]['width'],pages[0]['height']))
    output.setTitle('Мини-отчёт по разработке базы данных платформы хакатонов')
    output.setAuthor('Команда № 3, ПИ41Б')
    for number,page in enumerate(pages):
        for slot in page_slots[number]:
            index,original=slot['id'],slot['lines']
            if index not in replacements:
                for line in original:copy_characters(output,line['chars'])
                continue
            value=replacements[index]
            font='CourierNew' if index==38 else 'Times'
            size=original[0]['chars'][0]['size']
            if index==38:
                wrapped=value.splitlines()
                if len(wrapped)!=len(original):raise ValueError('Tree must have eighteen reference lines.')
            else:
                widths=tuple(552.65-line['x0'] for line in original)
                if index in centered:widths=tuple(467.55 for _ in original)
                wrapped=break_lines(value,widths,font,size)
            for row,(text,line) in enumerate(zip(wrapped,original)):
                natural=pdfmetrics.stringWidth(text,font,size)
                x,y=line['x0'],line['chars'][0]['matrix'][5]
                if natural>552.65-x+0.2 and index not in centered:raise ValueError(f'Paragraph {index} exceeds reference margin.')
                if index in centered:x=(85.1+552.65-natural)/2
                content=output.beginText(x,y);content.setFont(font,size);content.setWordSpace(0)
                if index not in centered|{30,38} and row<len(wrapped)-1:
                    content.setWordSpace((552.65-x-natural)/max(1,text.count(' ')))
                content.textOut(text);output.drawText(content)
                if index==30:output.linkURL(value,(x,y-3,x+natural,y+size),relative=0,thickness=0)
        for image,name in zip(page['images'],image_files.get(number,[])):
            output.drawImage(ImageReader(str(FIGURES/name)),image['x0'],page['height']-image['bottom'],width=image['width'],height=image['height'],mask='auto')
        copy_characters(output,page['footer']);output.showPage()
    output.save();print(args.output)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-dir',type=Path,default=FIGURES/'evidence')
    parser.add_argument('--font-dir',type=Path,default=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts')
    parser.add_argument('--output',type=Path,default=ROOT/'docs/mini-report-database.pdf')
    build(parser.parse_args())
