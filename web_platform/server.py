import os
import json
import html
import uuid
import datetime
import asyncio
from aiohttp import web
import aiohttp

try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")

PROJECTS_FILE = os.path.join(DATA_DIR, "projects.json")
LEADS_FILE = os.path.join(DATA_DIR, "leads.json")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
LOCAL_ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")
EXTERNAL_ORDERS_FILE = os.path.abspath(os.path.join(BASE_DIR, "..", "prompt_shop_bot", "data", "orders.json"))

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "Viktor_Dev_2026!7x")
AUTH_COOKIE_NAME = "botcraft_admin_session"

SUPPORT_BOT_TOKEN = os.environ.get("SUPPORT_BOT_TOKEN", "9156937130:AAHk8wFGSEf4y9YN7k1Z5zAkVLKUpjbSvPE")
SHOWCASE_BOT_TOKEN = os.environ.get("SHOWCASE_BOT_TOKEN", "").strip()
if not SHOWCASE_BOT_TOKEN:
    _showcase_env = os.path.abspath(os.path.join(BASE_DIR, "..", "showcase_lead_bot", ".env"))
    if os.path.exists(_showcase_env):
        try:
            with open(_showcase_env, "r", encoding="utf-8") as _f:
                for _line in _f:
                    if _line.strip().startswith("BOT_TOKEN="):
                        SHOWCASE_BOT_TOKEN = _line.strip().split("=", 1)[1].strip()
                        break
        except Exception:
            pass
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8848097502"))
PROXY_URL = os.environ.get("PROXY_URL", "http://127.0.0.1:10809")
WORKSPACE_URL = os.environ.get("WORKSPACE_URL", "https://work-site-1rx5.onrender.com/workspace?token=Viktor_Dev_2026!7x")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# Catalog metadata for prompt_shop_bot products
CATALOG = {
    "instagram_50": {
        "name": "🔥 50 промптов для Instagram-контента",
        "price_rub": 199,
        "price_stars": 50
    },
    "midjourney_30": {
        "name": "🎨 30 промптов для Midjourney (логотипы и дизайн)",
        "price_rub": 299,
        "price_stars": 75
    },
    "mega_pack": {
        "name": "💎 МЕГА-ПАКЕТ: 150 промптов (всё в одном)",
        "price_rub": 499,
        "price_stars": 120
    }
}

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

def load_orders():
    # If the shop bot orders file exists, prioritize it and sync locally
    if os.path.exists(EXTERNAL_ORDERS_FILE):
        orders = load_json(EXTERNAL_ORDERS_FILE, [])
        save_json(LOCAL_ORDERS_FILE, orders)
        return orders
    return load_json(LOCAL_ORDERS_FILE, [])

def save_orders(orders):
    save_json(LOCAL_ORDERS_FILE, orders)
    if os.path.exists(os.path.dirname(EXTERNAL_ORDERS_FILE)):
        try:
            save_json(EXTERNAL_ORDERS_FILE, orders)
        except Exception:
            pass

def enrich_order(o):
    pid = o.get("product_id", "")
    prod = CATALOG.get(pid, {"name": pid, "price_rub": 0, "price_stars": 0})
    user_id = o.get("user_id", 0)
    username = o.get("username", "") or ""
    is_friend = (user_id == 7029478583) or (username.lower() == "backrunner")
    return {
        **o,
        "product_name": prod["name"],
        "price_rub": prod["price_rub"],
        "price_stars": prod["price_stars"],
        "is_friend": is_friend,
        "client_label": f"@{username} (Друг / VIP)" if is_friend else (f"@{username}" if username else f"ID {user_id}")
    }

async def send_telegram_alert(text: str, reply_markup: dict = None, bot_token: str | None = None):
    """Sends notification to Telegram Bot with proxy & flood-limit handling."""
    token = (bot_token or SUPPORT_BOT_TOKEN or "").strip()
    if not token or not ADMIN_ID:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": ADMIN_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    for proxy in [PROXY_URL, None]:
        try:
            timeout = aiohttp.ClientTimeout(total=8)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, proxy=proxy) as resp:
                    if resp.status == 200:
                        return True
                    if resp.status == 429:
                        data = await resp.json()
                        retry_after = data.get("parameters", {}).get("retry_after", 2)
                        await asyncio.sleep(retry_after)
                        async with session.post(url, json=payload, proxy=proxy) as retry_resp:
                            if retry_resp.status == 200:
                                return True
        except Exception:
            continue
    return False


async def send_admin_alert_with_fallback(text: str, reply_markup: dict = None, prefer_showcase: bool = False) -> bool:
    """Отправляет уведомление админу, пробуя основной и запасной токен бота."""
    tokens = [SHOWCASE_BOT_TOKEN, SUPPORT_BOT_TOKEN] if prefer_showcase else [SUPPORT_BOT_TOKEN, SHOWCASE_BOT_TOKEN]
    seen = set()
    for token in tokens:
        if token and token not in seen:
            seen.add(token)
            if await send_telegram_alert(text, reply_markup=reply_markup, bot_token=token):
                return True
    return False


def build_smart_spec(idea: str) -> tuple[str, str, str]:
    """Подбирает тариф, срок и ключевые модули по описанию клиента."""
    low = (idea or "").lower()
    if any(k in low for k in ("ии", "ai", "gpt", "gemini", "нейросет", "mini app", "приложен", "crm")):
        tier, timing = "Сложный проект (от 5 000 ₽)", "3–5 дней"
        modules = "• Модуль ИИ-агента / Mini App веб-интерфейса\n• Интеграция с API / CRM и базой знаний\n• Панель администратора и аналитика заявок"
    elif any(k in low for k in ("магазин", "товар", "доставк", "корзин", "запис", "салон", "клиник", "брон", "оплат")):
        tier, timing = "Бизнес-бот (от 2 500 ₽)", "2–3 дня"
        modules = "• Интерактивный каталог / выбор услуги и слота времени\n• Корзина или форма бронирования с автонапоминаниями\n• База данных SQLite/PostgreSQL и уведомления менеджеру"
    else:
        tier, timing = "Базовый бот (от 1 000 ₽)", "24 часа"
        modules = "• Приветственный экран с УТП и быстрыми кнопками\n• Пошаговый сбор заявки / квиз-квалификация клиента\n• Мгновенная пересылка лидов в ваш Telegram"
    return tier, timing, modules


def build_dev_prompt(
    *,
    source: str,
    idea: str,
    niche: str = "",
    bot_type: str = "",
    modules: str = "",
    timing: str = "",
    price_info: str = "",
    contact: str = "",
) -> str:
    """Формирует готовый промпт для создания Telegram-бота по описанию клиента."""
    inferred_tier, inferred_timing, inferred_modules = build_smart_spec(f"{niche} {idea}")
    final_tier = bot_type or inferred_tier
    final_timing = timing or inferred_timing
    final_modules = modules or inferred_modules

    lines = [
        f"Создай готовый Telegram-бот под ключ по заявке клиента ({source}).",
        "",
        "1. Контекст и задача клиента:",
    ]
    if niche:
        lines.append(f"- Ниша: {niche}")
    if idea:
        lines.append(f"- Описание от клиента: {idea}")
    if final_tier:
        lines.append(f"- Уровень/тариф: {final_tier}")
    if price_info:
        lines.append(f"- Ориентир по бюджету: {price_info}")
    if final_timing:
        lines.append(f"- Срок: {final_timing}")
    if contact:
        lines.append(f"- Контакт заказчика: {contact}")

    lines.extend([
        "",
        "2. Обязательный стек и требования:",
        "- Python 3.11, aiogram 3.x, aiohttp, python-dotenv (виртуальное окружение ..\\prompt_shop_bot\\venv\\Scripts\\python.exe).",
        "- ОС Windows: подготовь requirements.txt, .env (шаблон/переменные), run.bat в ASCII с CRLF без кириллицы.",
        "- Надёжность: цикл переподключения и обработка TelegramRetryAfter при отправке сообщений.",
        "- Удобный UX: понятное главное меню, inline-кнопки, пошаговые FSM-сценарии, пересылка заявок админу (ADMIN_ID).",
        "",
        "3. Функциональные модули, которые нужно реализовать:",
        final_modules,
        "",
        "4. Что выдать в результате:",
        "- Полный рабочий код под ключ (main.py, handlers.py, keyboards.py, config.py, при необходимости db.py).",
        "- Проверенный синтаксис и готовую инструкцию по запуску.",
    ])
    prompt_text = "\n".join(lines)
    if len(prompt_text) > 3800:
        prompt_text = prompt_text[:3800] + "\n..."
    return prompt_text


async def notify_admin_lead_and_prompt(
    lead_text: str,
    prompt_text: str,
    reply_markup: dict = None,
    prefer_showcase: bool = False,
) -> None:
    """Отправляет админу карточку заявки и следом готовый промпт для копирования."""
    await send_admin_alert_with_fallback(lead_text, reply_markup=reply_markup, prefer_showcase=prefer_showcase)
    prompt_msg = (
        "🤖 <b>Готовый промпт для сборки бота</b> (нажмите, чтобы скопировать):\n\n"
        f"<pre>{html.escape(prompt_text)}</pre>"
    )
    await send_admin_alert_with_fallback(prompt_msg, prefer_showcase=prefer_showcase)

# Initial sample projects if empty
initial_projects = [
    {
        "id": "proj-1",
        "folder": "showcase_lead_bot",
        "title": "Шоукейс & Лидогенератор для Авито",
        "category": "Лидогенерация",
        "price": "от 1 500 ₽",
        "days": "1-2 дня",
        "tag": "Топ продаж",
        "badge": "Хит продаж",
        "bot_username": "@showcase_lead_bot",
        "bot_url": "https://t.me/showcase_lead_bot",
        "is_live": True,
        "description": "Автономный бот-визитка с интерактивным калькулятором цен (от 1 000 до 3 000 ₽), моментальным сбором контактов и мгновенной пересылкой лидов владельцу в Telegram.",
        "features": ["Интерактивный расчет стоимости в 1 клик", "Защита от флуд-лимитов Telegram API", "Мгновенные алерты о заявках владельцу", "Пошаговый сбор ТЗ и контактов клиента"],
        "tech": "Python 3.11 · aiogram 3.x · FSM · aiohttp"
    },
    {
        "id": "proj-2",
        "folder": "prompt_shop_bot",
        "title": "Магазин цифровых товаров & Промптов",
        "category": "E-Commerce",
        "price": "от 2 500 ₽",
        "days": "2-3 дня",
        "tag": "Каталог",
        "badge": "Бизнес",
        "bot_username": "@promt_shop_bot",
        "bot_url": "https://t.me/promt_shop_bot",
        "is_live": True,
        "description": "Полноценный интернет-магазин с каталогом, корзиной, приемом оплат в рублях и Telegram Stars, моментальной автоматической выдачей купленного контента.",
        "features": ["Каталог с категориями и описанием товаров", "Корзина покупок и оплата Telegram Stars / Рубли", "Автоматическая моментальная выдача файлов", "Синхронизация заказов с веб-платформой CRM"],
        "tech": "Python 3.11 · aiogram 3.x · SQLite / JSON · Webhooks"
    },
    {
        "id": "proj-3",
        "folder": "support_hub_bot",
        "title": "Support Hub & Helpdesk (Тикеты)",
        "category": "Техподдержка",
        "price": "от 2 000 ₽",
        "days": "1-3 дня",
        "tag": "Сервис",
        "badge": "Сервис",
        "bot_username": "@Viktor_support_bot",
        "bot_url": "https://t.me/Viktor_support_bot",
        "is_live": True,
        "description": "Служба поддержки и тикет-система: разделение обращений, умная база знаний FAQ, подключение живого оператора прямо внутри Telegram.",
        "features": ["Тикетная система с уникальными номерами", "База частых вопросов FAQ с поиском", "Пересылка диалогов оператору в реалтайме", "Рейтинг и оценка качества обслуживания"],
        "tech": "Python 3.11 · aiogram 3.x · aiohttp"
    },
    {
        "id": "proj-4",
        "folder": "converter_bot",
        "title": "Медиа-конвертер и FFmpeg Помощник",
        "category": "Утилиты",
        "price": "от 1 000 ₽",
        "days": "1 день",
        "tag": "Инструмент",
        "badge": "Быстрый старт",
        "bot_username": "@viktor_first_converter_bot",
        "bot_url": "https://t.me/viktor_first_converter_bot",
        "is_live": True,
        "description": "Скоростной инструмент для конвертации картинок (PNG, JPG, WEBP, PDF), видео, аудио и кружочков на базе FFmpeg без потери качества.",
        "features": ["Конвертация форматов на лету без серверов задержки", "Умное сжатие фото, аудио и графики", "Поддержка документов и стикеров Telegram", "Мгновенная отправка готового файла обратно"],
        "tech": "Python 3.11 · FFmpeg · Pillow · aiogram 3.x"
    },
    {
        "id": "proj-5",
        "folder": "ai_content_bot",
        "title": "AI Content & NeuroPost Assistant",
        "category": "Нейросети",
        "price": "от 2 200 ₽",
        "days": "1-2 дня",
        "tag": "AI Новинка",
        "badge": "Инновация",
        "bot_username": "@content_viktor_bot",
        "bot_url": "https://t.me/content_viktor_bot",
        "is_live": True,
        "description": "Умный ассистент-копирайтер: генерация продающих постов по маркетинговым формулам (AIDA, PAS), контент-планов на неделю и промптов для Midjourney.",
        "features": ["Генерация постов по формулам AIDA, PAS, Кейс", "Автосоставление контент-плана на 7 дней по нише", "Генератор вирусных кликабельных заголовков", "Англоязычные 8K-промпты для Midjourney / DALL-E"],
        "tech": "Python 3.11 · aiogram 3.x · Gemini API / NeuroEngine"
    },
    {
        "id": "proj-6",
        "folder": "admin_control_bot",
        "title": "Admin Control & DevOps Watcher",
        "category": "Мониторинг",
        "price": "от 2 000 ₽",
        "days": "1-2 дня",
        "tag": "DevOps",
        "badge": "Инфраструктура",
        "bot_username": "@Viktor_support_bot",
        "bot_url": "https://t.me/Viktor_support_bot",
        "is_live": True,
        "description": "Центр управления и мониторинга: мониторинг доступности серверов, автоматические алерты при сбоях, контроль нагрузки CPU/RAM и удаленный перезапуск.",
        "features": ["Health-check веб-сайтов и Telegram-ботов 24/7", "Экстренные пуш-уведомления при даунтайме", "Мониторинг памяти, диска и системных процессов", "Удаленное управление сервисами из личного чата"],
        "tech": "Python 3.11 · aiohttp · psutil · aiogram 3.x"
    }
]

if not os.path.exists(PROJECTS_FILE):
    save_json(PROJECTS_FILE, initial_projects)

if not os.path.exists(TASKS_FILE):
    save_json(TASKS_FILE, [
        {"id": "t1", "title": "Опубликовать объявление на Авито", "status": "done", "priority": "high", "price": 0, "deadline": "Сегодня"},
        {"id": "t2", "title": "Ответить первому лиду по боту-магазину", "status": "in_progress", "priority": "urgent", "price": 2500, "deadline": "Срочно"},
        {"id": "t3", "title": "Подготовить демо-бота для клиента с Авито", "status": "pending", "priority": "medium", "price": 1500, "deadline": "Завтра"}
    ])

# Auth Verification
def is_authorized(request):
    cookie_token = request.cookies.get(AUTH_COOKIE_NAME)
    header_token = request.headers.get("X-Admin-Token")
    query_token = request.query.get("token")
    return (cookie_token == ADMIN_TOKEN) or (header_token == ADMIN_TOKEN) or (query_token == ADMIN_TOKEN)

def admin_required(handler):
    async def wrapped(request):
        if not is_authorized(request):
            return web.json_response(
                {"error": "Unauthorized", "message": "Доступ запрещен. Требуется авторизация администратора."},
                status=401
            )
        return await handler(request)
    return wrapped

async def check_auth_status(request):
    return web.json_response({"authenticated": is_authorized(request)})

async def auth_login(request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    password = str(data.get("password", "")).strip()
    if password == ADMIN_TOKEN:
        response = web.json_response({"status": "ok", "message": "Авторизация успешна"})
        response.set_cookie(
            AUTH_COOKIE_NAME,
            ADMIN_TOKEN,
            max_age=60 * 60 * 24 * 30, # 30 дней
            httponly=True,
            samesite="Lax",
            path="/"
        )
        return response
    return web.json_response({"status": "error", "message": "Неверный пароль доступа"}, status=401)

async def auth_logout(request):
    response = web.json_response({"status": "ok", "message": "Сессия завершена"})
    response.del_cookie(AUTH_COOKIE_NAME, path="/")
    return response

# Public & Showcase API
async def get_projects(request):
    projects = load_json(PROJECTS_FILE, [])
    return web.json_response(projects)

async def submit_lead(request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Некорректный формат данных."}, status=400)

    name = (data.get("name") or "").strip()
    contact = (data.get("contact") or "").strip()
    task = (data.get("task") or "").strip()
    budget = (data.get("budget") or "от 1 000 ₽").strip()

    if len(name) < 2:
        return web.json_response({
            "ok": False,
            "error": "Пожалуйста, укажите имя (минимум 2 буквы)."
        }, status=400)

    if len(contact) < 4:
        return web.json_response({
            "ok": False,
            "error": "Пожалуйста, укажите корректный контакт (Telegram или телефон)."
        }, status=400)

    leads = load_json(LEADS_FILE, [])
    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    task_text = task or "Консультация и расчет стоимости"
    tier, timing, modules = build_smart_spec(task_text)
    prompt_text = build_dev_prompt(
        source="Сайт BotCraft",
        idea=task_text,
        bot_type=tier,
        modules=modules,
        timing=timing,
        price_info=budget,
        contact=f"{name} ({contact})",
    )
    new_lead = {
        "id": "lead-" + str(uuid.uuid4())[:8],
        "name": name,
        "contact": contact,
        "budget": budget,
        "task": task_text,
        "date": now,
        "status": "new",
        "source": "site",
        "prompt": prompt_text,
    }
    leads.insert(0, new_lead)
    save_json(LEADS_FILE, leads)

    # Real-time alert to Support Hub bot & Admin Telegram
    lead_text = (
        f"🔥 <b>[Сайт BotCraft] Новая заявка на разработку!</b>\n\n"
        f"👤 <b>Имя:</b> {html.escape(new_lead['name'])}\n"
        f"📞 <b>Контакт:</b> <code>{html.escape(new_lead['contact'])}</code>\n"
        f"💰 <b>Бюджет:</b> {html.escape(new_lead['budget'])}\n"
        f"📝 <b>Задача:</b> {html.escape(new_lead['task'])}\n"
        f"🕒 <b>Время:</b> {new_lead['date']}"
    )
    kb = {
        "inline_keyboard": [
            [{"text": "🌐 Открыть Workspace CRM", "url": WORKSPACE_URL}]
        ]
    }
    contact_val = new_lead['contact'].strip()
    if contact_val.startswith("@"):
        tg_user = contact_val.lstrip("@")
        kb["inline_keyboard"].insert(0, [{"text": f"💬 Написать @{tg_user}", "url": f"https://t.me/{tg_user}"}])
    elif contact_val.replace("+", "").replace(" ", "").isdigit():
        clean_phone = contact_val.replace("+", "").replace(" ", "")
        kb["inline_keyboard"].insert(0, [{"text": "📞 Позвонить / Написать", "url": f"tel:{clean_phone}"}])

    asyncio.create_task(notify_admin_lead_and_prompt(lead_text, prompt_text, reply_markup=kb, prefer_showcase=False))

    return web.json_response({"ok": True, "status": "ok", "message": "Заявка успешно отправлена! Мы свяжемся с вами в течение 10 минут."})


async def submit_miniapp(request):
    """Принимает заявки и расчёты из Telegram Mini App, сохраняет в CRM и отправляет админу с готовым промптом."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Некорректный формат данных."}, status=400)

    action = (data.get("action") or "order").strip()
    tg_user = data.get("tg_user") if isinstance(data.get("tg_user"), dict) else {}
    tg_id = tg_user.get("id")
    tg_username = (tg_user.get("username") or "").strip().lstrip("@")
    tg_name = " ".join(
        p for p in [(tg_user.get("first_name") or "").strip(), (tg_user.get("last_name") or "").strip()] if p
    ).strip()

    user_label = f"@{tg_username}" if tg_username else (tg_name or "Гость Mini App")
    user_meta = f"@{html.escape(tg_username)}" if tg_username else "без username"
    if tg_id:
        user_meta += f" (ID: <code>{html.escape(str(tg_id))}</code>" + (f", {html.escape(tg_name)}" if tg_name else "") + ")"
    elif tg_name:
        user_meta += f" ({html.escape(tg_name)})"

    now = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")

    if action == "calc":
        bot_type_raw = str(data.get("bot_type") or "Бот").strip()
        addons_list = [str(a).strip() for a in (data.get("addons") or []) if str(a).strip()]
        addons_raw = ", ".join(addons_list) or "без доп. модулей"
        total = int(data.get("total_rub", 0) or 0)
        disc = int(data.get("discounted_rub", 0) or 0)
        idea_text = f"Нужен {bot_type_raw}. Модули: {addons_raw}."
        price_info = f"от {total:,} ₽ (со скидкой: {disc:,} ₽)"
        contact_raw = (data.get("contact") or "").strip() or user_label

        prompt_text = build_dev_prompt(
            source="Калькулятор Mini App",
            idea=idea_text,
            bot_type=bot_type_raw,
            modules=f"• Модули из калькулятора: {addons_raw}",
            price_info=price_info,
            contact=contact_raw,
        )
        lead_text = (
            f"📱 <b>Расчёт из Mini App!</b>\n\n"
            f"👤 {user_meta}\n"
            f"📌 <b>Уровень:</b> {html.escape(bot_type_raw)}\n"
            f"⚙️ <b>Модули:</b> {html.escape(addons_raw)}\n"
            f"💰 <b>Итого:</b> от {total:,} ₽ (со скидкой: {disc:,} ₽)\n"
            f"🕒 <b>Время:</b> {now}"
        )
        new_lead = {
            "id": "lead-" + str(uuid.uuid4())[:8],
            "name": tg_name or user_label,
            "contact": contact_raw,
            "budget": price_info,
            "task": idea_text,
            "date": now,
            "status": "new",
            "source": "miniapp_calc",
            "prompt": prompt_text,
        }
    else:
        niche_raw = str(data.get("niche") or "Не указана").strip()
        idea_raw = str(data.get("idea") or "").strip()
        if len(idea_raw) < 3:
            return web.json_response({"ok": False, "error": "Опишите задачу хотя бы в нескольких словах."}, status=400)
        contact_raw = str(data.get("contact") or "").strip() or user_label
        tier, timing, modules = build_smart_spec(f"{niche_raw} {idea_raw}")

        prompt_text = build_dev_prompt(
            source="Заявка из Mini App",
            niche=niche_raw,
            idea=idea_raw,
            bot_type=tier,
            modules=modules,
            timing=timing,
            price_info=tier,
            contact=contact_raw,
        )
        lead_text = (
            f"🚀 <b>ЗАЯВКА ИЗ MINI APP!</b>\n\n"
            f"👤 {user_meta}\n"
            f"🏷 <b>Ниша:</b> {html.escape(niche_raw)}\n"
            f"📝 <b>Задача:</b> {html.escape(idea_raw)}\n"
            f"📞 <b>Контакт:</b> <code>{html.escape(contact_raw)}</code>\n"
            f"💰 <b>Оценка:</b> {html.escape(tier)} ({html.escape(timing)})\n"
            f"🕒 <b>Время:</b> {now}"
        )
        new_lead = {
            "id": "lead-" + str(uuid.uuid4())[:8],
            "name": tg_name or user_label,
            "contact": contact_raw,
            "budget": tier,
            "task": f"[{niche_raw}] {idea_raw}",
            "date": now,
            "status": "new",
            "source": "miniapp_order",
            "prompt": prompt_text,
        }

    leads = load_json(LEADS_FILE, [])
    leads.insert(0, new_lead)
    save_json(LEADS_FILE, leads)

    kb = {
        "inline_keyboard": [
            [{"text": "🌐 Открыть Workspace CRM", "url": WORKSPACE_URL}]
        ]
    }
    if tg_username:
        kb["inline_keyboard"].insert(0, [{"text": f"💬 Написать @{tg_username}", "url": f"https://t.me/{tg_username}"}])
    elif contact_raw.startswith("@"):
        clean_u = contact_raw.lstrip("@")
        kb["inline_keyboard"].insert(0, [{"text": f"💬 Написать @{clean_u}", "url": f"https://t.me/{clean_u}"}])

    asyncio.create_task(notify_admin_lead_and_prompt(lead_text, prompt_text, reply_markup=kb, prefer_showcase=True))

    return web.json_response({
        "ok": True,
        "status": "ok",
        "message": "Заявка отправлена! Разработчик уже получил ТЗ и скоро напишет вам.",
    })

# Protected Admin API
@admin_required
async def add_project(request):
    data = await request.json()
    projects = load_json(PROJECTS_FILE, [])
    new_proj = {
        "id": "proj-" + str(uuid.uuid4())[:8],
        "title": data.get("title", "Новый проект"),
        "category": data.get("category", "Разработка"),
        "price": data.get("price", "от 1 000 ₽"),
        "days": data.get("days", "1-3 дня"),
        "tag": data.get("tag", "Telegram Bot"),
        "description": data.get("description", ""),
        "features": [f.strip() for f in data.get("features", "").split(",") if f.strip()],
        "badge": data.get("badge", "Новинка")
    }
    projects.append(new_proj)
    save_json(PROJECTS_FILE, projects)
    return web.json_response({"status": "ok", "project": new_proj})

@admin_required
async def delete_project(request):
    proj_id = request.match_info.get("id")
    projects = load_json(PROJECTS_FILE, [])
    projects = [p for p in projects if p.get("id") != proj_id]
    save_json(PROJECTS_FILE, projects)
    return web.json_response({"status": "ok"})

@admin_required
async def get_leads(request):
    leads = load_json(LEADS_FILE, [])
    return web.json_response(leads)

@admin_required
async def update_lead_status(request):
    lead_id = request.match_info.get("id")
    data = await request.json()
    leads = load_json(LEADS_FILE, [])
    for lead in leads:
        if lead.get("id") == lead_id:
            lead["status"] = data.get("status", lead["status"])
    save_json(LEADS_FILE, leads)
    return web.json_response({"status": "ok"})

# Orders API
@admin_required
async def get_orders(request):
    orders = load_orders()
    enriched = [enrich_order(o) for o in reversed(orders)]
    return web.json_response(enriched)

@admin_required
async def update_order_status(request):
    order_id = int(request.match_info.get("id"))
    data = await request.json()
    new_status = data.get("status")
    orders = load_orders()
    target_order = None
    for o in orders:
        if o.get("id") == order_id:
            if new_status:
                o["status"] = new_status
            target_order = enrich_order(o)
            break
    if target_order:
        save_orders(orders)
        status_labels = {
            "pending": "⏳ Ожидает оплаты/проверки",
            "paid": "💳 Оплачен",
            "delivered": "✅ Доставлен / Выдан",
            "cancelled": "❌ Отменен"
        }
        alert_text = (
            f"🔄 <b>Статус заказа #{order_id} изменен в CRM:</b>\n"
            f"📌 Статус: <b>{status_labels.get(new_status, new_status)}</b>\n"
            f"👤 Клиент: <b>{target_order['client_label']}</b>\n"
            f"📦 Товар: <b>{target_order['product_name']}</b>\n"
            f"💰 Сумма: <b>{target_order['price_rub']} ₽</b>"
        )
        asyncio.create_task(send_telegram_alert(alert_text))
        return web.json_response({"status": "ok", "order": target_order})
    return web.json_response({"status": "error", "message": "Order not found"}, status=404)

@admin_required
async def get_crm_stats(request):
    leads = load_json(LEADS_FILE, [])
    orders = load_orders()
    tasks = load_json(TASKS_FILE, [])
    
    total_leads = len(leads)
    new_leads = sum(1 for l in leads if l.get("status") == "new")
    
    total_orders = len(orders)
    pending_orders = sum(1 for o in orders if o.get("status") == "pending")
    delivered_orders = sum(1 for o in orders if o.get("status") == "delivered")
    
    revenue = 0
    for o in orders:
        if o.get("status") in ("paid", "delivered"):
            pid = o.get("product_id")
            revenue += CATALOG.get(pid, {}).get("price_rub", 0)
    for t in tasks:
        if t.get("status") == "done":
            revenue += int(t.get("price", 0) or 0)

    return web.json_response({
        "total_leads": total_leads,
        "new_leads": new_leads,
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "delivered_orders": delivered_orders,
        "total_revenue": revenue
    })

@admin_required
async def get_tasks(request):
    tasks = load_json(TASKS_FILE, [])
    return web.json_response(tasks)

@admin_required
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

@admin_required
async def update_task(request):
    task_id = request.match_info.get("id")
    data = await request.json()
    tasks = load_json(TASKS_FILE, [])
    for task in tasks:
        if task.get("id") == task_id:
            task.update(data)
    save_json(TASKS_FILE, tasks)
    return web.json_response({"status": "ok"})

@admin_required
async def delete_task(request):
    task_id = request.match_info.get("id")
    tasks = load_json(TASKS_FILE, [])
    tasks = [t for t in tasks if t.get("id") != task_id]
    save_json(TASKS_FILE, tasks)
    return web.json_response({"status": "ok"})

# Page views
async def serve_client_site(request):
    return web.FileResponse(os.path.join(STATIC_DIR, "index.html"))

async def serve_miniapp(request):
    return web.FileResponse(os.path.join(STATIC_DIR, "miniapp.html"))

async def serve_workspace(request):
    response = web.FileResponse(os.path.join(STATIC_DIR, "workspace.html"))
    if request.query.get("token") == ADMIN_TOKEN:
        response.set_cookie(
            AUTH_COOKIE_NAME,
            ADMIN_TOKEN,
            max_age=60 * 60 * 24 * 30,
            httponly=True,
            samesite="Lax",
            path="/"
        )
    return response

def create_app():
    app = web.Application()
    
    # Static pages
    app.router.add_get("/", serve_client_site)
    app.router.add_get("/miniapp", serve_miniapp)
    app.router.add_get("/workspace", serve_workspace)
    
    # Auth endpoints
    app.router.add_get("/api/auth/check", check_auth_status)
    app.router.add_post("/api/auth/login", auth_login)
    app.router.add_post("/api/auth/logout", auth_logout)

    # Public APIs
    app.router.add_get("/api/projects", get_projects)
    app.router.add_post("/api/leads", submit_lead)
    app.router.add_post("/api/miniapp/submit", submit_miniapp)
    
    # Protected Admin APIs
    app.router.add_get("/api/stats", get_crm_stats)
    app.router.add_get("/api/orders", get_orders)
    app.router.add_post("/api/orders/{id}/status", update_order_status)
    app.router.add_post("/api/projects", add_project)
    app.router.add_delete("/api/projects/{id}", delete_project)
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
    print("==================================================")
    print(f"[*] Клиентский сайт: http://localhost:{port}/")
    print(f"[*] Рабочий пульт (Workspace CRM): http://localhost:{port}/workspace")
    print(f"[*] Токен доступа: {ADMIN_TOKEN}")
    print("==================================================")
    web.run_app(app, host="0.0.0.0", port=port)
