import os
import json
import uuid
import datetime
from aiohttp import web

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")
PROJECTS_FILE = os.path.join(DATA_DIR, "projects.json")
LEADS_FILE = os.path.join(DATA_DIR, "leads.json")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

def load_json(filepath, default):
    if not os.path.exists(filepath):
        save_json(filepath, default)
        return default
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Initial sample projects if empty
initial_projects = [
    {
        "id": "proj-1",
        "title": "Шоукейс & Лидогенератор для Авито",
        "category": "Лидогенерация",
        "price": "от 3 500 ₽",
        "days": "1-2 дня",
        "tag": "Топ продаж",
        "description": "Автономный бот-визитка с интерактивным калькулятором цен (строго от 3 000 ₽), моментальным сбором контактов и мгновенной пересылкой лидов владельцу в Telegram.",
        "features": ["Интерактивный калькулятор", "Защита от флуд-лимитов Telegram", "Мгновенные уведомления администратору", "Сбор ТЗ в 1 клик"],
        "badge": "Хит"
    },
    {
        "id": "proj-2",
        "title": "Магазин цифровых товаров & Промптов",
        "category": "E-Commerce",
        "price": "от 5 000 ₽",
        "days": "2-3 дня",
        "tag": "Каталог",
        "description": "Полноценный интернет-магазин с каталогом, корзиной, приемом оплат и моментальной автоматической выдачей купленного контента или ключей.",
        "features": ["Каталог с категориями", "Корзина и промокоды", "Автовыдача файлов и ссылок", "История покупок"],
        "badge": "Бизнес"
    },
    {
        "id": "proj-3",
        "title": "Support Hub & Helpdesk",
        "category": "Техподдержка",
        "price": "от 4 000 ₽",
        "days": "1-3 дня",
        "tag": "Сервис",
        "description": "Бот службы поддержки с тикет-системой, базой частых вопросов (FAQ) и разделением диалогов по специалистам.",
        "features": ["Тикетная система", "Умный FAQ поиск", "Подключение оператора в диалог", "Оценка качества ответа"],
        "badge": "Сервис"
    },
    {
        "id": "proj-4",
        "title": "Конвертер медиа и документов",
        "category": "Утилиты",
        "price": "от 3 000 ₽",
        "days": "1 день",
        "tag": "Инструмент",
        "description": "Скоростной инструмент для конвертации картинок, PDF и документов с оптимизацией веса файлов.",
        "features": ["Конвертация форматов на лету", "Сжатие без потери качества", "Пакетная обработка"],
        "badge": "Быстрый старт"
    }
]

if not os.path.exists(PROJECTS_FILE):
    save_json(PROJECTS_FILE, initial_projects)

if not os.path.exists(TASKS_FILE):
    save_json(TASKS_FILE, [
        {"id": "t1", "title": "Опубликовать объявление на Авито", "status": "done", "priority": "high", "price": 0, "deadline": "Сегодня"},
        {"id": "t2", "title": "Ответить первому лиду по боту-магазину", "status": "in_progress", "priority": "urgent", "price": 4500, "deadline": "Срочно"},
        {"id": "t3", "title": "Подготовить демо-бота для клиента с Авито", "status": "pending", "priority": "medium", "price": 3000, "deadline": "Завтра"}
    ])

# API Routes
async def get_projects(request):
    projects = load_json(PROJECTS_FILE, [])
    return web.json_response(projects)

async def add_project(request):
    data = await request.json()
    projects = load_json(PROJECTS_FILE, [])
    new_proj = {
        "id": "proj-" + str(uuid.uuid4())[:8],
        "title": data.get("title", "Новый проект"),
        "category": data.get("category", "Разработка"),
        "price": data.get("price", "от 3 000 ₽"),
        "days": data.get("days", "1-3 дня"),
        "tag": data.get("tag", "Telegram Bot"),
        "description": data.get("description", ""),
        "features": [f.strip() for f in data.get("features", "").split(",") if f.strip()],
        "badge": data.get("badge", "Новинка")
    }
    projects.append(new_proj)
    save_json(PROJECTS_FILE, projects)
    return web.json_response({"status": "ok", "project": new_proj})

async def delete_project(request):
    proj_id = request.match_info.get("id")
    projects = load_json(PROJECTS_FILE, [])
    projects = [p for p in projects if p.get("id") != proj_id]
    save_json(PROJECTS_FILE, projects)
    return web.json_response({"status": "ok"})

async def submit_lead(request):
    data = await request.json()
    leads = load_json(LEADS_FILE, [])
    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    new_lead = {
        "id": "lead-" + str(uuid.uuid4())[:8],
        "name": data.get("name", "Аноним"),
        "contact": data.get("contact", ""),
        "budget": data.get("budget", "от 3 000 ₽"),
        "task": data.get("task", ""),
        "date": now,
        "status": "new"
    }
    leads.insert(0, new_lead)
    save_json(LEADS_FILE, leads)
    return web.json_response({"status": "ok", "message": "Заявка успешно отправлена! Мы свяжемся с вами в течение 10 минут."})

async def get_leads(request):
    leads = load_json(LEADS_FILE, [])
    return web.json_response(leads)

async def update_lead_status(request):
    lead_id = request.match_info.get("id")
    data = await request.json()
    leads = load_json(LEADS_FILE, [])
    for lead in leads:
        if lead.get("id") == lead_id:
            lead["status"] = data.get("status", lead["status"])
    save_json(LEADS_FILE, leads)
    return web.json_response({"status": "ok"})

async def get_tasks(request):
    tasks = load_json(TASKS_FILE, [])
    return web.json_response(tasks)

async def add_task(request):
    data = await request.json()
    tasks = load_json(TASKS_FILE, [])
    new_task = {
        "id": "t-" + str(uuid.uuid4())[:8],
        "title": data.get("title", "Задача"),
        "status": data.get("status", "pending"),
        "priority": data.get("priority", "normal"),
        "price": data.get("price", 0),
        "deadline": data.get("deadline", "Скоро")
    }
    tasks.append(new_task)
    save_json(TASKS_FILE, tasks)
    return web.json_response({"status": "ok", "task": new_task})

async def update_task(request):
    task_id = request.match_info.get("id")
    data = await request.json()
    tasks = load_json(TASKS_FILE, [])
    for task in tasks:
        if task.get("id") == task_id:
            task.update(data)
    save_json(TASKS_FILE, tasks)
    return web.json_response({"status": "ok"})

async def delete_task(request):
    task_id = request.match_info.get("id")
    tasks = load_json(TASKS_FILE, [])
    tasks = [t for t in tasks if t.get("id") != task_id]
    save_json(TASKS_FILE, tasks)
    return web.json_response({"status": "ok"})

async def serve_client_site(request):
    return web.FileResponse(os.path.join(STATIC_DIR, "index.html"))

async def serve_workspace(request):
    return web.FileResponse(os.path.join(STATIC_DIR, "workspace.html"))

def create_app():
    app = web.Application()
    app.router.add_get("/", serve_client_site)
    app.router.add_get("/workspace", serve_workspace)
    app.router.add_get("/api/projects", get_projects)
    app.router.add_post("/api/projects", add_project)
    app.router.add_delete("/api/projects/{id}", delete_project)
    app.router.add_post("/api/leads", submit_lead)
    app.router.add_get("/api/leads", get_leads)
    app.router.add_post("/api/leads/{id}/status", update_lead_status)
    app.router.add_get("/api/tasks", get_tasks)
    app.router.add_post("/api/tasks", add_task)
    app.router.add_post("/api/tasks/{id}", update_task)
    app.router.add_delete("/api/tasks/{id}", delete_task)
    app.router.add_static("/static", STATIC_DIR)
    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 8080))
    print(f"==================================================")
    print(f"[*] Клиентский сайт: http://localhost:{port}/")
    print(f"[*] Рабочий пульт (Workspace CRM): http://localhost:{port}/workspace")
    print(f"==================================================")
    web.run_app(app, host="127.0.0.1", port=port)
