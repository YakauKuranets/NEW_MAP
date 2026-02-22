#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Map v12 Telegram bot (read-only admin tools + user wizard).

Features:
- User wizard to submit a point: address/coords -> description -> access type -> reporter surname
- Admin login inside bot (username+password) that stores cookie session
- Read-only admin menu:
    [Summary] [Active] [Approved] [Rejected] [Addresses (paged)] [Find request by ID]
- Robust fallbacks when backend does not provide /admin/summary or returns other shapes
- No approve/reject actions in the bot (view-only)

Env:
  BOT_TOKEN            required
  MAP_API_URL          default http://localhost:5000
  BOT_API_KEY          optional (used in /api/bot/markers and header fallback)
  ADMIN_TELEGRAM_IDS   optional comma-separated whitelist for header-based admin fallback
"""

from __future__ import annotations

import os

from env_loader import load_dotenv_like

# Load .env if present
load_dotenv_like()

import re
import json
import logging
import asyncio
import time
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List
from telegram.error import TelegramError, BadRequest, Forbidden
import requests
import base64  # used for encoding category filters in pagination
from io import BytesIO
# Импортируем наш сервис распознавания голоса, который мы создали ранее
from app.services.voice_service import process_voice_message
from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
)
from telegram.ext import (
    ApplicationBuilder,
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("map-v12-bot")

# Глобальный обработчик ошибок, чтобы не было "No error handlers are registered"
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Глобальный обработчик ошибок Telegram-бота.

    Здесь мы отдельно подсвечиваем ошибки Telegram API (Forbidden / BadRequest /
    другие TelegramError), чтобы в логах было понятно, что это не баг бизнес-логики,
    а проблема взаимодействия с самим Telegram (например, chat not found, бот заблокирован
    пользователем и т.п.).
    """
    err = context.error
    try:
        update_repr = getattr(update, "to_dict", lambda: update)()
    except Exception:
        update_repr = repr(update)

    if isinstance(err, TelegramError):
        # Специальный лог для ошибок Telegram API
        msg = f"Telegram API error: {err}"
        if isinstance(err, BadRequest) and "chat not found" in str(err).lower():
            msg += " (возможно, пользователь удалил чат или заблокировал бота)"
        if isinstance(err, Forbidden):
            msg += " (доступ запрещён: пользователь мог заблокировать бота или закрыть чат)"

        log.warning("%s. Update=%s", msg, update_repr)
    else:
        # Все остальные ошибки логируем с трейсбеком
        log.exception(
            "Unhandled exception while handling update %s",
            update_repr,
            exc_info=err,
        )


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
# Сначала пробуем MAP_BOT_TOKEN (для нашего проекта),
# если его нет — берём BOT_TOKEN (для совместимости).
RAW_TOKEN = os.getenv("MAP_BOT_TOKEN") or os.getenv("BOT_TOKEN") or ""
BOT_TOKEN: str = RAW_TOKEN.strip()

MAP_API_URL: str = os.getenv("MAP_API_URL", "http://127.0.0.1:8000").rstrip("/")
BOT_API_KEY: Optional[str] = os.getenv("BOT_API_KEY")

ADMIN_TELEGRAM_IDS = {
    int(x) for x in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",") if x.strip().isdigit()
}

if not BOT_TOKEN:
    raise RuntimeError("MAP_BOT_TOKEN / BOT_TOKEN is not set")


# ---------------------------------------------------------------------------
# Diagnostics helpers
# ---------------------------------------------------------------------------
def _backend_probe(base: str) -> tuple[bool, str]:
    """Пробный запрос к backend, чтобы быстро понять, куда бот "стучится" и жив ли сервер."""
    base = (base or "").rstrip("/")
    if not base:
        return False, "MAP_API_URL пустой"
    # Пытаемся по самым вероятным endpoint'ам (в разных сборках могут отличаться)
    candidates = ["/ready", "/health", "/"]
    last_err = ""
    for path in candidates:
        url = base + path
        try:
            r = requests.get(url, timeout=3)
            return True, f"{path} -> {r.status_code}"
        except Exception as e:
            last_err = str(e)
    return False, f"нет ответа (последняя ошибка: {last_err})"


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Самодиагностика бота: /ping"""
    if not update.message:
        return
    ok, details = await asyncio.to_thread(_backend_probe, MAP_API_URL)
    await update.message.reply_text(
        "Ping backend:\n"
        f"MAP_API_URL: {MAP_API_URL}\n"
        f"Status: {'OK' if ok else 'FAIL'} ({details})"
    )

# ---------------------------------------------------------------------------
# Conversation states
# ---------------------------------------------------------------------------
# Conversation states for user wizard:
# PLACE -> DESCRIPTION -> ACCESS -> PHOTO -> SURNAME
PLACE, DESCRIPTION, ACCESS, PHOTO, SURNAME = range(5)

# Состояние для ввода сообщения администратору через кнопку "✉️ Написать админу"
CHAT_INPUT = 30

ADMIN_LOGIN_USER, ADMIN_LOGIN_PASS, ADMIN_MENU, ADMIN_WAIT_APP_ID_VIEW = range(10, 14)
# Состояние не используется, но зарезервировано для поддержки чата в будущем
CHAT = 20

# ---------------------------------------------------------------------------
# UI labels
# ---------------------------------------------------------------------------
BTN_ADD = "➕ Добавить точку"
BTN_SERVICE = "🛡️ Служба"
BTN_BACK = "⬅️ Назад"
BTN_CANCEL = "❌ Отмена"

# Service-gate helpers ("Служба по заявке")
BTN_SERVICE_REQUEST = "📝 Подать заявку"
BTN_SERVICE_STATUS = "ℹ️ Статус заявки"
BTN_HOME = "⬅️ В меню"

BTN_ADMIN_LOGIN = "🔐 Вход в административную учётную запись"
BTN_ADMIN_MENU = "🛠 Админ-меню"
BTN_ADMIN_HOME = "⬅️ В главное меню"
BTN_ADMIN_LOGOUT = "🚪 Выход из админ-аккаунта"

# Кнопки для общения с администратором через меню бота
# Кнопка просмотра переписки с админом
BTN_CHAT_HOME = "💬 Моя переписка"
BTN_MSG_HOME = "✉️ Написать админу"
BTN_CHAT_EXIT = "⛔️ Выйти из чата"

# Уведомления пользователя (переключатель в меню бота)
BTN_NOTIFY_PREFIX = "🔔 Уведомления"
BTN_MY_REQS = "📋 Мои заявки"
BTN_SHIFT_START = "🟢 Начать службу"
BTN_SHIFT_END   = "🔴 Закончить службу"
BTN_CHECKIN     = "✅ Я на месте"
BTN_LIVE_HELP   = "📡 Live‑трекинг"
BTN_LIVE_STOP   = "⛔ Остановить трекинг"
BTN_BREAK_REQ   = "🍽 Обед (запрос)"
BTN_SOS         = "🆘 SOS"
BTN_DUTY_BACK   = "↩ Назад"
BTN_CONNECT    = "📲 Подключить DutyTracker"
BTN_STATS = "📊 Сводка"
BTN_PENDING = "🟡 Активные заявки"
BTN_APPROVED = "✅ Одобренные"
BTN_REJECTED = "❌ Отклонённые"
BTN_APP = "🔎 Заявка по ID"
BTN_ADDRS = "📍 Адреса (подробно)"

# Подробное приветствие для команды /start. Объясняет, что умеет бот
# и как им пользоваться. Это сообщение будет отправлено пользователю
# при нажатии /start или при входе в бот.
TEXT_GREET = (
    "Map v12 — бот для добавления точек на карту и служебных действий.\n\n"
    "Главное меню:\n"
    f"• {BTN_ADD} — мастер добавления объекта.\n"
    f"• {BTN_SERVICE} — служебные функции (доступ по заявке).\n"
    f"• {BTN_ADMIN_LOGIN} — вход администратора.\n\n"
    "🧭 Добавить точку:\n"
    "1) Нажмите «➕ Добавить точку».\n"
    "2) Адрес или координаты.\n"
    "3) Описание → тип доступа → (опционально) фото → фамилия.\n\n"
    "🛡️ Служба (по заявке):\n"
    "1) Нажмите «🛡️ Служба».\n"
    "2) Если доступа нет — «📝 Подать заявку».\n"
    "3) После подтверждения появятся кнопки: смена, отбивка, live‑трекинг, обед, SOS и подключение DutyTracker.\n\n"
    "📲 DutyTracker:\n"
    "• В «Службе» нажмите «📲 Подключить DutyTracker» — бот выдаст ссылку для автоконфига и код привязки.\n\n"
    "Команды (если нужно): /add, /service, /connect, /chat, /msg, /my, /help."
)

BOT_COMMANDS_USER: list[tuple[str, str]] = [
    ("start", "Запустить бота и показать меню"),
    ("add", "Добавить новую точку"),
    ("service", "🛡️ Служба (по заявке)"),
    ("my", "Мои заявки"),
    ("chat", "История переписки с админом"),
    ("msg", "Написать администратору"),
    ("help", "Справка по возможностям бота"),
    ("connect", "Подключить Android DutyTracker (bootstrap)"),
    ("sos", "🆘 SOS — экстренный сигнал оператору"),
]

BOT_COMMANDS_ADMIN_EXTRA: list[tuple[str, str]] = [
    ("stats", "Админ: сводка"),
    ("pending", "Админ: активные заявки"),
    ("approved", "Админ: одобренные заявки"),
    ("rejected", "Админ: отклонённые заявки"),
    ("app", "Админ: заявка по ID"),
]


async def post_init(application: Application) -> None:
    """Настройка меню /команд (список команд в Telegram).

    Важно: это НЕ reply-клавиатура (кнопки внизу), а список команд,
    который показывается в Telegram в разделе "Меню".

    По требованию — делаем его минимальным для обычных пользователей,
    а расширенный набор показываем только админам (по chat-scope),
    если известны их Telegram ID.
    """
    # Минимум для всех
    default_commands = [
        BotCommand("start", "Показать меню"),
        BotCommand("add", "Добавить новую точку"),
        BotCommand("service", "Служба (по заявке)"),
    ]

    # Расширенный набор для админа (команды работают всегда, но здесь — видимость в меню)
    admin_commands = [
        *default_commands,
        BotCommand("stats", "Админ: сводка"),
        BotCommand("pending", "Админ: активные заявки"),
        BotCommand("approved", "Админ: одобренные заявки"),
        BotCommand("rejected", "Админ: отклонённые заявки"),
    ]

    try:
        await application.bot.set_my_commands(default_commands)
        log.info("Default bot commands set")
    except TelegramError as e:
        log.warning("Failed to set default bot commands: %s", e)

    # Если заданы ADMIN_TELEGRAM_IDS — покажем админам расширенный список
    try:
        from telegram import BotCommandScopeChat
        ids_raw = os.environ.get("ADMIN_TELEGRAM_IDS", "").strip()
        if ids_raw:
            ids = []
            for part in ids_raw.replace(";", ",").split(","):
                part = part.strip()
                if part:
                    ids.append(int(part))
            for chat_id in ids:
                try:
                    await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id))
                except Exception as e:
                    log.warning("Failed to set admin commands for %s: %s", chat_id, e)
    except Exception:
        pass

    # -----------------------
# --------------------------------------------
    # Notifications: start periodic polling job.
    #
    # В python-telegram-bot JobQueue зависит от optional extra
    # `python-telegram-bot[job-queue]`. Если он не установлен, то
    # `application.job_queue` будет None и попытка вызвать run_repeating
    # приведёт к AttributeError.
    #
    # Поэтому:
    #  - если JobQueue доступен -> используем run_repeating
    #  - если нет -> запускаем лёгкий asyncio-loop через application.create_task
    # -------------------------------------------------------------------
    try:
        if getattr(application, "job_queue", None) is not None:
            application.job_queue.run_repeating(notify_poll_job, interval=15, first=15)
            application.job_queue.run_repeating(duty_notify_poll_job, interval=15, first=20)
            log.info("notify_poll_job scheduled via JobQueue")
        else:
            application.create_task(_notify_poll_loop(application))
            log.info("notify_poll_job scheduled via asyncio loop (no JobQueue)")
    except Exception:
        log.exception("Failed to start notify polling")


def kb(rows) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)

# ---------------------------------------------------------------------------
# Notify prefs (user-side notifications toggle)
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NOTIFY_PREFS_FILE = os.path.join(BASE_DIR, "data", "notify_prefs.json")


def _load_notify_prefs() -> dict:
    try:
        if os.path.exists(NOTIFY_PREFS_FILE):
            with open(NOTIFY_PREFS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception:
        log.exception("Failed to load notify prefs")
    return {}


def _save_notify_prefs(prefs: dict) -> None:
    try:
        os.makedirs(os.path.dirname(NOTIFY_PREFS_FILE), exist_ok=True)
        with open(NOTIFY_PREFS_FILE, "w", encoding="utf-8") as f:
            json.dump(prefs, f, ensure_ascii=False, indent=2)
    except Exception:
        log.exception("Failed to save notify prefs")


def get_notify_enabled(user_id: Optional[str]) -> bool:
    if not user_id:
        return True
    prefs = _load_notify_prefs()
    val = prefs.get(str(user_id))
    # default ON
    return True if val is None else bool(val)


def set_notify_enabled(user_id: str, enabled: bool) -> None:
    prefs = _load_notify_prefs()
    prefs[str(user_id)] = bool(enabled)
    _save_notify_prefs(prefs)


def notify_btn_label(user_id: Optional[str]) -> str:
    enabled = get_notify_enabled(user_id)
    return f"{BTN_NOTIFY_PREFIX}: {'Вкл' if enabled else 'Выкл'}"


def chat_btn_label(unread: int = 0) -> str:
    """Подпись кнопки "Моя переписка" с бейджем непрочитанных."""
    try:
        n = int(unread or 0)
    except Exception:
        n = 0
    if n > 0:
        return f"{BTN_CHAT_HOME} ({n})"
    return BTN_CHAT_HOME


async def chat_mode_kb_for(uid: Optional[str], context: ContextTypes.DEFAULT_TYPE) -> ReplyKeyboardMarkup:
    """Клавиатура внутри режима чата (Выход + Моя переписка с бейджем).

    В режиме чата пользователи могут получить ответ от админа и важно, чтобы
    кнопка "Моя переписка" показывала актуальное количество непрочитанных.
    """
    unread = 0
    if uid:
        try:
            unread = await get_unread_cached(str(uid), context=context, force=False)
        except Exception:
            unread = 0
    return kb([[BTN_CHAT_EXIT], [chat_btn_label(unread)]])

def home_kb(is_admin: bool) -> ReplyKeyboardMarkup:
    """Главное меню (упрощённое).

    По требованию: оставляем только
      1) "Добавить точку"
      2) "Служба" (все служебные кнопки внутри)
      3) "Вход/Админ-меню"

    Остальные функции остаются доступными через команды (/chat, /my, /msg и т.п.),
    но не захламляют клавиатуру.
    """
    second = BTN_ADMIN_MENU if is_admin else BTN_ADMIN_LOGIN
    return kb([
        [BTN_ADD],
        [BTN_SERVICE],
        [second],
    ])


def _is_admin_user(update: Update) -> bool:
    """Единая проверка админского статуса для формирования клавиатур."""
    return is_admin_logged(update) or _is_admin_whitelisted(update)


# --- Кэш непрочитанных для кнопки "Моя переписка" ---
UNREAD_CACHE_TTL_SEC = 30

async def _fetch_unread_for_user(uid: str) -> int:
    """Запросить с бэка количество непрочитанных ответов админа для пользователя."""
    try:
        url = f"{MAP_API_URL}/api/chat/{uid}/unread_user"
        r = await asyncio.to_thread(requests.get, url, headers=_api_headers(), timeout=10)
        r.raise_for_status()
        data = r.json() if r.text.strip() else {}
        return int((data or {}).get("unread_for_user") or 0)
    except Exception:
        return 0

async def get_unread_cached(uid: Optional[str], context: Optional[ContextTypes.DEFAULT_TYPE] = None, force: bool = False) -> int:
    """Получить unread_for_user с TTL-кэшем (чтобы не дёргать API на каждое сообщение)."""
    if not uid:
        return 0
    now = time.time()
    cache = None
    if context is not None:
        cache = context.application.bot_data.setdefault("unread_cache", {})
    else:
        # fallback — глобально
        global _UNREAD_CACHE_FALLBACK
        try:
            _UNREAD_CACHE_FALLBACK
        except NameError:
            _UNREAD_CACHE_FALLBACK = {}
        cache = _UNREAD_CACHE_FALLBACK

    item = cache.get(uid) if isinstance(cache, dict) else None
    if (not force) and item and isinstance(item, dict):
        ts = float(item.get("ts") or 0)
        if now - ts <= UNREAD_CACHE_TTL_SEC:
            try:
                return int(item.get("count") or 0)
            except Exception:
                return 0

    count = await _fetch_unread_for_user(uid)
    if isinstance(cache, dict):
        cache[uid] = {"count": int(count), "ts": now}
    return int(count)

async def home_kb_for(update: Update, context: ContextTypes.DEFAULT_TYPE, is_admin: Optional[bool] = None) -> ReplyKeyboardMarkup:
    """Главное меню (без бейджей, чтобы не дёргать API лишний раз)."""
    flag = _is_admin_user(update) if is_admin is None else bool(is_admin)
    return home_kb(flag)




def split_telegram_text(text: str, limit: int = 3900) -> list[str]:
    """Режет длинный текст на части, чтобы не словить Telegram 'Text is too long'.

    Telegram ограничивает длину одного сообщения ~4096 символами.
    Мы берём небольшой запас (limit=3900) и режем по границам строк.
    """
    if not text:
        return [""]
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    buf: list[str] = []
    buf_len = 0
    for line in text.split("\n"):
        # +1 for newline
        add_len = len(line) + (1 if buf else 0)
        if buf_len + add_len > limit:
            if buf:
                parts.append("\n".join(buf))
                buf = [line]
                buf_len = len(line)
            else:
                # очень длинная строка — режем грубо
                for i in range(0, len(line), limit):
                    parts.append(line[i:i+limit])
                buf = []
                buf_len = 0
        else:
            if buf:
                buf_len += 1
            buf.append(line)
            buf_len += len(line)
    if buf:
        parts.append("\n".join(buf))
    return parts

PLACE_KB = kb([[BTN_BACK, BTN_CANCEL]])
DESCRIPTION_KB = kb([[BTN_BACK], [BTN_CANCEL]])
SURNAME_KB = kb([[BTN_BACK], [BTN_CANCEL]])
PHOTO_KB = kb([[BTN_BACK], [BTN_CANCEL]])
ACCESS_REPLY_KB = kb([[BTN_BACK], [BTN_CANCEL]])

def admin_menu_kb() -> ReplyKeyboardMarkup:
    return kb([
        [BTN_STATS, BTN_PENDING],
        [BTN_APPROVED, BTN_REJECTED],
        [BTN_ADDRS],
        [BTN_APP],
        [BTN_ADMIN_LOGOUT],
        [BTN_ADMIN_HOME],
    ])


# ---------------------------------------------------------------------------
# "Служба" по заявке: bot -> server (/api/service/access/*)
# ---------------------------------------------------------------------------

def _service_headers(uid: Optional[str] = None) -> Dict[str, str]:
    h = _api_headers()
    if uid:
        h["X-Telegram-Id"] = str(uid)
    return h


async def _service_get_status(uid: str) -> str:
    """Вернуть guest/pending/officer/admin/denied.

    Если BOT_API_KEY не задан — возвращаем guest (и даём подсказку на экране при входе в меню).
    """
    if not BOT_API_KEY:
        return "guest"
    url = f"{MAP_API_URL}/api/service/access/status"

    def _do():
        r = requests.get(url, headers=_service_headers(uid), params={"tg_user_id": uid}, timeout=10)
        try:
            data = r.json() if r.text.strip() else {}
        except Exception:
            data = {}
        return str((data or {}).get("status") or "guest").strip() or "guest"

    return await asyncio.to_thread(_do)


async def _service_request_access(uid: str, note: str = "") -> str:
    """Создать/обновить заявку (переводит в pending, если нет officer/admin)."""
    if not BOT_API_KEY:
        return "guest"
    url = f"{MAP_API_URL}/api/service/access/request"
    payload = {"tg_user_id": uid, "note": (note or "")[:256]}

    def _do():
        r = requests.post(url, headers=_service_headers(uid), json=payload, timeout=10)
        try:
            data = r.json() if r.text.strip() else {}
        except Exception:
            data = {}
        return str((data or {}).get("status") or "pending").strip() or "pending"

    return await asyncio.to_thread(_do)


async def _mobile_connect_request(uid: str, note: str = "", base_url: str = "") -> Dict[str, Any]:
    """Создать/переоткрыть заявку на привязку DutyTracker."""
    if not BOT_API_KEY:
        return {"ok": False, "error": "BOT_API_KEY_missing"}

    url = f"{MAP_API_URL}/api/mobile/connect/request"
    payload: Dict[str, Any] = {"tg_user_id": uid}
    if note:
        payload["note"] = (note or "")[:256]
    if base_url:
        payload["base_url"] = (base_url or "")[:256]

    def _do():
        r = requests.post(url, headers=_service_headers(uid), json=payload, timeout=10)
        try:
            data = r.json() if r.text.strip() else {}
        except Exception:
            data = {}
        data["_http_status"] = r.status_code
        return data

    return await asyncio.to_thread(_do)


async def _mobile_connect_status(uid: str, issue: bool = False) -> Dict[str, Any]:
    """Получить статус заявки. Если issue=True и статус approved — сервер выдаст новый bootstrap токен."""
    if not BOT_API_KEY:
        return {"ok": False, "error": "BOT_API_KEY_missing"}

    url = f"{MAP_API_URL}/api/mobile/connect/status"
    params = {"tg_user_id": uid}
    if issue:
        params["issue"] = "1"

    def _do():
        r = requests.get(url, headers=_service_headers(uid), params=params, timeout=10)
        try:
            data = r.json() if r.text.strip() else {}
        except Exception:
            data = {}
        data["_http_status"] = r.status_code
        return data

    return await asyncio.to_thread(_do)

def service_kb(status: str) -> ReplyKeyboardMarkup:
    s = (status or "guest").strip().lower()
    if s in {"officer", "admin"}:
        return kb([
            [BTN_CONNECT],
            [BTN_SHIFT_START, BTN_SHIFT_END],
            [BTN_CHECKIN, BTN_LIVE_HELP],
            [BTN_LIVE_STOP, BTN_BREAK_REQ],
            [BTN_SOS],
            [BTN_HOME],
        ])
    # guest/pending/denied
    if s == "pending":
        return kb([
            [BTN_SERVICE_STATUS],
            [BTN_HOME],
        ])
    return kb([
        [BTN_SERVICE_REQUEST],
        [BTN_SERVICE_STATUS],
        [BTN_HOME],
    ])


def _service_status_human(status: str) -> str:
    s = (status or "guest").strip().lower()
    if s == "admin":
        return "admin"
    if s == "officer":
        return "officer"
    if s == "pending":
        return "pending"
    if s == "denied":
        return "denied"
    return "guest"


async def _ensure_service_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """True только для officer/admin. Иначе показывает подсказку, как подать заявку."""
    u = update.effective_user
    if not u:
        return False
    uid = str(u.id)
    status = await _service_get_status(uid)
    s = _service_status_human(status)
    if s in {"officer", "admin"}:
        return True

    # Пользователь не в службе — показываем куда нажимать
    msg = (
        "Доступ к \"Службе\" не выдан.\n"
        "Нажмите \"🛡️ Служба\" → \"📝 Подать заявку\" и дождитесь подтверждения администратора."
    )
    if not BOT_API_KEY:
        msg += "\n\n⚠️ BOT_API_KEY не настроен в боте (без него заявки/статус работать не будут)."

    if update.effective_message:
        await update.effective_message.reply_text(msg, reply_markup=service_kb(s))
    return False


# ---------------------------------------------------------------------------
# Handlers — Service menu
# ---------------------------------------------------------------------------

async def service_enter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
    u = update.effective_user
    if not u:
        return
    uid = str(u.id)
    status = await _service_get_status(uid)
    s = _service_status_human(status)

    if not BOT_API_KEY:
        await update.effective_message.reply_text(
            "⚠️ В боте не задан BOT_API_KEY.\n"
            "Служба по заявке не будет работать, пока вы не зададите BOT_API_KEY в окружении.",
            reply_markup=service_kb(s),
        )
        return

    if s in {"officer", "admin"}:
        await update.effective_message.reply_text(
            "🛡️ Служба: доступ подтверждён.",
            reply_markup=service_kb(s),
        )
        return

    if s == "pending":
        await update.effective_message.reply_text(
            "🛡️ Служба: заявка уже отправлена и ожидает подтверждения администратора.",
            reply_markup=service_kb(s),
        )
        return

    if s == "denied":
        await update.effective_message.reply_text(
            "🛡️ Служба: доступ отклонён. Вы можете подать заявку повторно.",
            reply_markup=service_kb("guest"),
        )
        return

    await update.effective_message.reply_text(
        "🛡️ Служба доступна только после подтверждения администратора.\n"
        "Нажмите \"📝 Подать заявку\".",
        reply_markup=service_kb(s),
    )


async def service_request_btn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
    u = update.effective_user
    if not u:
        return
    uid = str(u.id)
    status = await _service_request_access(uid, note=f"tg:{u.username or ''}")
    s = _service_status_human(status)
    if s in {"officer", "admin"}:
        await update.effective_message.reply_text(
            "✅ Доступ к службе уже выдан.",
            reply_markup=service_kb(s),
        )
        return
    await update.effective_message.reply_text(
        "🟡 Заявка отправлена. Ожидайте подтверждения администратора.",
        reply_markup=service_kb("pending"),
    )


async def service_status_btn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
    u = update.effective_user
    if not u:
        return
    uid = str(u.id)
    status = await _service_get_status(uid)
    s = _service_status_human(status)
    txt = {
        "guest": "Статус: нет доступа (нужно подать заявку).",
        "pending": "Статус: заявка на рассмотрении.",
        "officer": "Статус: доступ к службе выдан (officer).",
        "admin": "Статус: администратор.",
        "denied": "Статус: отклонено администратором.",
    }.get(s, f"Статус: {s}")
    await update.effective_message.reply_text(txt, reply_markup=service_kb(s))


async def home_btn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await go_home(update, context)


async def cmd_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет историю переписки с администратором.

    Пользователь должен отправить команду /chat. Бот запрашивает у
    сервера список сообщений и выводит их в читаемом виде. Администратор
    отправляет сообщения через веб‑интерфейс, которые отображаются в
    чате. Чтобы отправить новое сообщение администратору, используйте
    команду /msg <текст>.
    """
    u = update.effective_user
    if not u or not update.message:
        return
    user_id = str(u.id)
    await _send_chat_history(context=context, chat_id=update.message.chat_id, user_id=user_id)


def _normalize_history_payload(data: Any) -> list[dict]:
    """Нормализует ответ API истории чата до списка сообщений."""
    if isinstance(data, dict):
        if 'messages' in data:
            return data.get('messages') or []
        if 'items' in data:
            return data.get('items') or []
        # fallback
        try:
            return list(data.values())
        except Exception:
            return []
    return data or []


def _format_chat_lines(msgs: list[dict], limit: int = 20) -> tuple[str, int]:
    """Форматирует последние сообщения. Возвращает текст и cursor последнего admin-сообщения."""
    lines: list[str] = []
    last_admin_id = 0
    for m in (msgs or [])[-limit:]:
        sender = 'Админ' if m.get('sender') == 'admin' else 'Вы'
        text = m.get('text') or ''
        created = m.get('created_at')
        ts = ''
        if created:
            try:
                dt = datetime.fromisoformat(created)
                ts = dt.strftime('%d.%m %H:%M')
            except Exception:
                ts = str(created)
        prefix = f"[{ts}] " if ts else ""
        lines.append(f"{prefix}{sender}: {text}")

        if m.get('sender') == 'admin':
            try:
                mid = int(m.get('id') or 0)
                if mid > last_admin_id:
                    last_admin_id = mid
            except Exception:
                pass
    return "\n".join(lines), last_admin_id


async def _ack_admin_seen(user_id: str, cursor: int) -> None:
    """Помечает admin-сообщения как "увиденные" (чтобы не приходили снова уведомления)."""
    if not user_id or not str(user_id).isdigit():
        return
    try:
        cur = int(cursor or 0)
    except Exception:
        cur = 0
    if cur <= 0:
        return
    try:
        ack_url = f"{MAP_API_URL}/api/chat/{user_id}/seen_admin"
        await asyncio.to_thread(
            requests.post,
            ack_url,
            json={"cursor": cur},
            headers=_api_headers(),
            timeout=10,
        )
    except Exception:
        # не критично
        log.debug("_ack_admin_seen failed for user=%s", user_id, exc_info=True)


async def _send_chat_history(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: str) -> None:
    """Отправить историю чата в указанный chat_id (работает и из callback)."""
    app = context.application
    try:
        url = f"{MAP_API_URL}/api/chat/{user_id}"
        r = await asyncio.to_thread(requests.get, url, timeout=15)
        r.raise_for_status()
        data = r.json() if r.text.strip() else []
        msgs = _normalize_history_payload(data)
    except Exception:
        log.exception("Failed to fetch chat history")
        await app.bot.send_message(chat_id=chat_id, text="Не удалось получить историю чата. Попробуйте позже.")
        return

    if not msgs:
        await app.bot.send_message(
            chat_id=chat_id,
            text="Нет сообщений. Чтобы написать администратору, нажмите «✉️ Написать админу» или используйте /msg <текст>.",
        )
        return

    text_out, last_admin_id = _format_chat_lines(msgs, limit=20)
    for part in split_telegram_text(text_out):
        await app.bot.send_message(chat_id=chat_id, text=part)

    # Важно: если пользователь открыл переписку — считаем, что он увидел ответы админа.
    await _ack_admin_seen(user_id=user_id, cursor=last_admin_id)

    # Обновим кэш (чтобы кнопка "Моя переписка (N)" сразу показала 0)
    try:
        await get_unread_cached(user_id, context=context, force=True)
    except Exception:
        pass


async def cmd_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет сообщение администратору.

    Использование: /msg текст сообщения. Сообщение будет сохранено в БД
    и отправлено администратору через WebSocket (и через интерфейс чата).
    После отправки бот подтвердит доставку.
    """
    u = update.effective_user
    if not u or not update.message:
        return
    # Извлекаем текст после команды '/msg '
    text = update.message.text or ''
    # Удаляем '/msg' и пробел
    if text.lower().startswith('/msg'):
        text = text[4:].lstrip()
    if not text:
        await update.message.reply_text("Введите текст после команды /msg")
        return
    user_id = str(u.id)
    try:
        url = f"{MAP_API_URL}/api/chat/{user_id}"
        profile = {
            'username': u.username,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'display_name': ('@' + u.username) if u.username else (u.full_name or u.first_name or ''),
        }
        r = requests.post(url, json={'text': text, 'sender': 'user', 'user': profile}, timeout=15)
        r.raise_for_status()
    except Exception:
        log.exception("Failed to send chat message")
        await update.message.reply_text("Не удалось отправить сообщение. Попробуйте позже.")
        return
    await update.message.reply_text(
        "Сообщение отправлено администратору. Ответ придёт в этот чат.\n"
        "Вы всегда можете посмотреть историю командой /chat.",
    )

# ---------------------------------------------------------------------------
# Chat interaction via buttons
# ---------------------------------------------------------------------------
async def btn_chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выводит историю переписки по кнопке "💬 Моя переписка".

    Просто делегирует вызов стандартной команды /chat.
    """
    # Используем существующий обработчик для /chat
    await cmd_chat(update, context)


async def toggle_notify_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Переключатель уведомлений пользователя.

    Пока это только настройка (ON/OFF), которую позже используем для
    системы уведомлений (push + polling).
    """
    u = update.effective_user
    if not u or not update.message:
        return
    uid = str(u.id)
    enabled = not get_notify_enabled(uid)
    set_notify_enabled(uid, enabled)
    await update.message.reply_text(
        f"Уведомления: {'ВКЛ ✅' if enabled else 'ВЫКЛ 🚫'}.",
        reply_markup=await home_kb_for(update, context, _is_admin_user(update)),
    )


async def cb_chat_open(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inline-кнопка: открыть переписку из уведомления."""
    q = update.callback_query
    if not q:
        return
    await q.answer()
    u = q.from_user
    if not u:
        return
    await _send_chat_history(context=context, chat_id=q.message.chat_id, user_id=str(u.id))


async def cb_chat_reply_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inline-кнопка: перейти в режим ответа админу (включает ConversationHandler)."""
    q = update.callback_query
    if not q:
        return ConversationHandler.END
    await q.answer()
    # Входим в режим чата так же, как по кнопке "✉️ Написать админу"
    context.user_data["chat_mode"] = True
    u = q.from_user
    uid = str(u.id) if u else None
    await q.message.reply_text(
        "Вы вошли в чат с администратором.\n\n"
        "✍️ Пишите сообщения — я отправлю их админу.\n"
        "⛔️ Чтобы выйти, нажмите кнопку «Выйти из чата».\n\n"
        "Также можно нажать «Моя переписка», чтобы посмотреть последние сообщения.",
        reply_markup=await chat_mode_kb_for(uid, context),
    )
    return CHAT_INPUT


async def cb_chat_notify_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inline-кнопка: выключить уведомления."""
    q = update.callback_query
    if not q:
        return
    await q.answer()
    u = q.from_user
    if not u:
        return
    uid = str(u.id)
    set_notify_enabled(uid, False)
    try:
        await q.message.reply_text(
            "Уведомления выключены 🚫\n"
            "Чтобы включить обратно — нажмите кнопку «🔔 Уведомления» в меню.",
            reply_markup=await home_kb_for(update, context, _is_admin_user(update)),
        )
    except Exception:
        pass



# ---------------------------------------------------------------------------
# Notifications (polling): bot periodically checks backend for new admin replies
# ---------------------------------------------------------------------------

def _api_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if BOT_API_KEY:
        headers["X-API-KEY"] = BOT_API_KEY
    return headers


async def notify_poll_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Периодическая задача: прислать пользователям уведомления об ответе админа.

    Схема (система C):
      1) Сервер ведёт счётчик unread_for_user и cursor last_notified_admin_msg_id.
      2) Бот раз в N секунд спрашивает /api/chat/notify_targets (кто ждёт уведомления).
      3) Для каждого user_id запрашивает /api/chat/<id>/pending_admin и присылает текст.
      4) После успешной отправки подтверждает /api/chat/<id>/ack_admin.
    """
    app = context.application
    url = f"{MAP_API_URL}/api/chat/notify_targets"
    try:
        # requests блокирует event-loop, поэтому уводим в thread
        resp = await asyncio.to_thread(requests.get, url, headers=_api_headers(), timeout=10)
        resp.raise_for_status()
        targets = resp.json() if resp.text.strip() else []
        if not isinstance(targets, list):
            targets = []
    except Exception:
        log.exception("notify_poll_job: failed to fetch targets")
        return

    for t in targets:
        try:
            uid = str((t or {}).get("user_id") or "")
            if not uid.isdigit():
                continue
            if not get_notify_enabled(uid):
                # пользователь отключил уведомления
                continue

            # берём порцию новых сообщений от админа
            pend_url = f"{MAP_API_URL}/api/chat/{uid}/pending_admin"
            r2 = await asyncio.to_thread(
                requests.get,
                pend_url,
                headers=_api_headers(),
                params={"limit": 20},
                timeout=10,
            )
            r2.raise_for_status()
            pdata = r2.json() if r2.text.strip() else {}
            msgs = pdata.get("messages") or []
            cursor = pdata.get("cursor") or 0
            if not msgs:
                continue

            # Собираем компактное уведомление без спама.
            # Показать 1-3 последних сообщения, а для остального — кнопку "Открыть переписку".
            sample = msgs[-3:] if len(msgs) > 3 else msgs
            lines: list[str] = [f"💬 Администратор ответил ({len(msgs)} новых):"]
            for m in sample:
                txt = (m.get("text") or "").strip()
                if not txt:
                    continue
                if len(txt) > 500:
                    txt = txt[:500] + "…"
                lines.append(f"• {txt}")
            if len(msgs) > len(sample):
                lines.append(f"… и ещё {len(msgs) - len(sample)}")
            lines.append("")
            lines.append("Выберите действие ниже 👇")
            out = "\n".join(lines)

            ikb = InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Открыть переписку", callback_data="chat:open")],
                [
                    InlineKeyboardButton("✉️ Ответить", callback_data="chat:reply"),
                    InlineKeyboardButton("🔕 Выключить", callback_data="chat:notify_off"),
                ],
            ])

            # Отправляем одним сообщением, чтобы не плодить части и не ломать UX.
            # Telegram ограничивает 4096 символов — у нас текст заведомо короткий.
            await app.bot.send_message(
                chat_id=int(uid),
                text=out,
                reply_markup=ikb,
                disable_web_page_preview=True,
            )

            # подтверждаем, что уведомили пользователя
            ack_url = f"{MAP_API_URL}/api/chat/{uid}/ack_admin"
            await asyncio.to_thread(
                requests.post,
                ack_url,
                json={"cursor": cursor},
                headers=_api_headers(),
                timeout=10,
            )
            # Обновим кэш непрочитанных (бейдж в меню обновится при следующем показе меню)
            try:
                await get_unread_cached(uid, context=context, force=True)
            except Exception:
                pass

        except Forbidden:
            # пользователь заблокировал бота — не спамим ошибками
            log.warning("notify_poll_job: user %s blocked the bot", uid)
        except Exception:
            log.exception("notify_poll_job: failed for user=%s", t)


async def _notify_poll_loop(application: Application, interval: int = 15) -> None:
    """Fallback polling loop for environments where JobQueue is unavailable.

    Some installations of python-telegram-bot don't include the optional
    job-queue dependencies (APScheduler). In this case application.job_queue
    is None and we can't call run_repeating.

    We run the same notify_poll_job logic in a light asyncio loop.
    """
    from types import SimpleNamespace

    while True:
        try:
            ctx = SimpleNamespace(application=application)
            await notify_poll_job(ctx)  # type: ignore[arg-type]
            await duty_notify_poll_job(ctx)  # type: ignore[arg-type]
        except Exception:
            log.exception("_notify_poll_loop: error")
        await asyncio.sleep(interval)


async def _send_chat_history_to(chat_id: int, user_id: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправить историю переписки пользователю (унифицировано для callback и кнопок)."""
    try:
        url = f"{MAP_API_URL}/api/chat/{user_id}"
        r = await asyncio.to_thread(requests.get, url, timeout=15)
        r.raise_for_status()
        data = r.json() if r.text.strip() else []
        if isinstance(data, dict):
            msgs = data.get('messages') or data.get('items') or list(data.values())
        else:
            msgs = data or []
    except Exception:
        log.exception("Failed to fetch chat history")
        await context.application.bot.send_message(chat_id=chat_id, text="Не удалось получить историю чата. Попробуйте позже.")
        return

    if not msgs:
        await context.application.bot.send_message(
            chat_id=chat_id,
            text="Нет сообщений. Нажмите «✉️ Написать админу», чтобы начать диалог.",
        )
        return

    # Форматируем последние 20 сообщений
    lines: list[str] = []
    last_admin_id = 0
    for m in msgs[-20:]:
        sender = 'Админ' if m.get('sender') == 'admin' else 'Вы'
        text = (m.get('text') or '').strip()
        mid = int(m.get('id') or 0)
        if m.get('sender') == 'admin' and mid > last_admin_id:
            last_admin_id = mid
        created = m.get('created_at')
        ts = ''
        if created:
            try:
                dt = datetime.fromisoformat(created)
                ts = dt.strftime('%d.%m %H:%M')
            except Exception:
                ts = str(created)
        prefix = f"[{ts}] " if ts else ""
        lines.append(f"{prefix}{sender}: {text}")

    text_out = "\n".join(lines)
    for part in split_telegram_text(text_out):
        await context.application.bot.send_message(chat_id=chat_id, text=part)

    # Помечаем ответы админа как "виденные" (чтобы счётчик unread_for_user не рос)
    if last_admin_id > 0:
        try:
            ack_url = f"{MAP_API_URL}/api/chat/{user_id}/seen_admin"
            await asyncio.to_thread(
                requests.post,
                ack_url,
                json={"cursor": last_admin_id},
                headers=_api_headers(),
                timeout=10,
            )
        except Exception:
            log.warning("Failed to ack admin seen for user %s", user_id)
        else:
            # обновим кэш непрочитанных
            try:
                await get_unread_cached(user_id, context=context, force=True)
            except Exception:
                pass


async def chat_inline_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inline-кнопки из уведомления: открыть переписку / ответить / выключить уведомления."""
    q = update.callback_query
    if not q:
        return
    try:
        await q.answer()
    except Exception:
        pass
    user = q.from_user
    if not user:
        return
    uid = str(user.id)
    data = q.data or ""

    # chat_id берём из сообщения с кнопками
    chat_id = q.message.chat_id if q.message else int(uid)

    if data == "chat:open":
        await _send_chat_history_to(chat_id=chat_id, user_id=uid, context=context)
        return

    if data == "chat:reply":
        # Включаем режим чата и показываем подсказку
        context.user_data["chat_mode"] = True
        await context.application.bot.send_message(
            chat_id=chat_id,
            text=(
                "Вы в чате с администратором.\n"
                "✍️ Пишите сообщение — я отправлю админу.\n"
                "⛔️ Чтобы выйти, нажмите «Выйти из чата»."
            ),
            reply_markup=await chat_mode_kb_for(uid, context),
        )
        return

    if data == "chat:notify_off":
        set_notify_enabled(uid, False)
        await context.application.bot.send_message(
            chat_id=chat_id,
            text="Уведомления выключены 🔕. Включить можно в меню бота (🔔 Уведомления).",
            reply_markup=await home_kb_for(update, context, _is_admin_user(update)),
        )
        return

async def ask_admin_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Войти в режим чата с администратором.

    В этом режиме любое отправленное пользователем сообщение уходит админу.
    Выход — по кнопке "⛔️ Выйти из чата".
    """
    # Флаг режима чата (на случай, если понадобится в других обработчиках)
    context.user_data["chat_mode"] = True

    await update.message.reply_text(
        "Вы вошли в чат с администратором.\n\n"
        "✍️ Пишите сообщения — я отправлю их админу.\n"
        "⛔️ Чтобы выйти, нажмите кнопку «Выйти из чата».\n\n"
        "Также можно нажать «Моя переписка», чтобы посмотреть последние сообщения.",
        reply_markup=await chat_mode_kb_for(str(update.effective_user.id), context)
    )
    return CHAT_INPUT


async def exit_chat_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выйти из режима чата и вернуть главное меню."""
    context.user_data["chat_mode"] = False
    u = update.effective_user
    uid = str(u.id) if u else None
    await update.message.reply_text(
        "Вы вышли из чата.",
        reply_markup=await home_kb_for(update, context, _is_admin_user(update)),
    )
    return ConversationHandler.END


async def chat_show_history_in_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать историю переписки, оставаясь в режиме чата."""
    await cmd_chat(update, context)
    return CHAT_INPUT

async def send_admin_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отправить сообщение админу и остаться в режиме чата."""
    u = update.effective_user
    if not u or not update.message:
        return ConversationHandler.END
    text = (update.message.text or '').strip()
    if not text:
        await update.message.reply_text(
            "Сообщение не может быть пустым. Попробуйте снова или нажмите «Выйти из чата».",
            reply_markup=await chat_mode_kb_for(str(update.effective_user.id), context),
        )
        return CHAT_INPUT
    user_id = str(u.id)
    try:
        url = f"{MAP_API_URL}/api/chat/{user_id}"
        profile = {
            'username': u.username,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'display_name': ('@' + u.username) if u.username else (u.full_name or u.first_name or ''),
        }
        r = requests.post(url, json={'text': text, 'sender': 'user', 'user': profile}, timeout=15)
        r.raise_for_status()
    except Exception:
        log.exception("Failed to send chat message via button")
        await update.message.reply_text(
            "Не удалось отправить сообщение. Попробуйте снова позже.",
            reply_markup=await chat_mode_kb_for(str(update.effective_user.id), context)
        )
        return CHAT_INPUT
    await update.message.reply_text(
        "✅ Отправлено админу.",
        reply_markup=await chat_mode_kb_for(str(update.effective_user.id), context)
    )
    return CHAT_INPUT


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать историю переписки с администратором (короткий алиас к /chat)."""
    await cmd_chat(update, context)



async def cmd_my_requests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать заявки пользователя, созданные через бота.

    Выводит небольшую сводку по статусам и список последних заявок
    в компактном виде. Это улучшенная версия /my, чтобы пользователю
    было проще понимать, что сейчас с его заявками происходит.
    """
    u = update.effective_user
    if not u:
        return
    user_id = str(u.id)
    try:
        url = f"{MAP_API_URL}/api/bot/my-requests/{user_id}"
        headers: Dict[str, str] = {}
        if BOT_API_KEY:
            headers["X-API-KEY"] = BOT_API_KEY
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json() if r.text.strip() else {}
    except Exception:
        log.exception("Failed to load user requests")
        if update.message:
            await update.message.reply_text(
                "Не удалось получить список ваших заявок. Попробуйте позже.",
                reply_markup=await home_kb_for(update, context),
            )
        return

    items = data.get("items") or []
    if not items:
        if update.message:
            await update.message.reply_text(
                "У вас пока нет заявок, созданных через бота.",
                reply_markup=await home_kb_for(update, context),
            )
        return

    # Подсчёт статусов для краткой сводки
    total = len(items)
    counters: Dict[str, int] = {"pending": 0, "approved": 0, "rejected": 0, "cancelled": 0}
    for it in items:
        st = (it.get("status") or "pending").lower()
        if st not in counters:
            counters[st] = counters.get(st, 0) + 1
        else:
            counters[st] += 1

    status_labels = {
        "pending": "🟡 в ожидании",
        "approved": "✅ одобрены",
        "rejected": "❌ отклонены",
        "cancelled": "⛔ отменены",
    }

    lines: list[str] = [f"Ваши заявки (всего: {total}):"]

    # Собираем строку сводки по статусам
    summary_parts: list[str] = []
    for key in ["pending", "approved", "rejected", "cancelled"]:
        cnt = counters.get(key) or 0
        if not cnt:
            continue
        label = status_labels.get(key, key)
        summary_parts.append(f"{label}: {cnt}")
    if summary_parts:
        lines.append(" / ".join(summary_parts))

    # Далее выводим последние 10 заявок
    lines.append("")
    for it in items[:10]:
        st = (it.get("status") or "pending").lower()
        status_human = {
            "pending": "ожидает рассмотрения",
            "approved": "одобрена",
            "rejected": "отклонена",
            "cancelled": "отменена",
        }.get(st, st)
        name = it.get("name") or "—"
        pid = it.get("id") or "—"

        created_raw = it.get("created_at") or it.get("ts") or ""
        created_part = ""
        if created_raw:
            created_str = str(created_raw).replace("T", " ")
            created_part = f" · {created_str[:16]}"

        lines.append(f"• #{pid} — {name} ({status_human}){created_part}")

    if total > 10:
        lines.append(f"Показаны последние 10 из {total} заявок.")

    if update.message:
        await update.message.reply_text(
            "\n".join(lines),
            reply_markup=await home_kb_for(update, context),
        )
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Краткая справка по возможностям бота."""
    if update.message:
        await update.message.reply_text(
            "Команды и кнопки:\n"
            "• «➕ Добавить точку» — мастер добавления объекта.\n"
            "• «🛡️ Служба» — служебные функции (доступ по заявке).\n"
            "• «🔐 Вход в административную учётную запись» — вход админа.\n\n"
            "Команды: /add, /service, /connect, /my, /chat, /msg, /help.",
            reply_markup=await home_kb_for(update, context),
        )


def access_inline_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("Локальный доступ", callback_data="access:local"),
            InlineKeyboardButton("Удаленный доступ", callback_data="access:remote"),
        ]]
    )

# ---------------------------------------------------------------------------
# Admin sessions
# ---------------------------------------------------------------------------
ADMIN_SESSIONS: Dict[int, requests.Session] = {}

def _get_admin_session(user_id: int) -> Optional[requests.Session]:
    return ADMIN_SESSIONS.get(user_id)

def _set_admin_session(user_id: int, sess: Optional[requests.Session]) -> None:
    if sess is None:
        ADMIN_SESSIONS.pop(user_id, None)
    else:
        ADMIN_SESSIONS[user_id] = sess

def is_admin_logged(update: Update) -> bool:
    u = update.effective_user
    return bool(u and _get_admin_session(u.id))

def _is_admin_whitelisted(update: Update) -> bool:
    u = update.effective_user
    return bool(u and u.id in ADMIN_TELEGRAM_IDS and BOT_API_KEY)

def _header_fallback(tg_id: int) -> Dict[str, str]:
    h = {"X-Telegram-Id": str(tg_id)}
    if BOT_API_KEY:
        h["X-API-KEY"] = BOT_API_KEY
    return h

async def admin_GET(update: Update, path: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    url = f"{MAP_API_URL}/{path.lstrip('/')}"
    uid = update.effective_user.id if update.effective_user else 0
    sess = _get_admin_session(uid)

    def _do():
        if sess:
            r = sess.get(url, params=params, timeout=15)
            if r.status_code == 403:
                raise PermissionError("Сессия истекла или нет прав")
            r.raise_for_status()
            return r.json() if r.text.strip() else {}
        if _is_admin_whitelisted(update):
            r = requests.get(url, headers=_header_fallback(uid), params=params, timeout=15)
            r.raise_for_status()
            return r.json() if r.text.strip() else {}
        raise PermissionError("Требуется вход в админ-аккаунт")
    return await asyncio.to_thread(_do)

async def admin_POST_login(username: str, password: str) -> tuple[bool, Optional[requests.Session], str]:
    url = f"{MAP_API_URL}/login"
    def _do():
        try:
            s = requests.Session()
            r = s.post(url, json={"username": username, "password": password}, timeout=15)
            if r.status_code == 200:
                j = {}
                try:
                    j = r.json()
                except Exception:
                    pass
                if j.get("status") == "ok":
                    return True, s, ""
            return False, None, r.text
        except Exception as e:
            return False, None, str(e)
    return await asyncio.to_thread(_do)

# ---------------------------------------------------------------------------
# Duty (Наряды): смены, обеды, live-трекинг
# ---------------------------------------------------------------------------

DUTY_BREAK_CB_PREFIX = "duty_break:"



async def _tracker_bootstrap_request(update: Update, label: str = "") -> Dict[str, Any]:
    """Запросить bootstrap-токен на сервере.

    Требует BOT_API_KEY (если включен на сервере).
    Сервер может дополнительно проверять allow-list по X-Telegram-Id.
    """
    uid = update.effective_user.id if update.effective_user else None
    payload = {
        "tg_user_id": str(uid) if uid is not None else None,
        "label": label or f"tg_{uid}",
        # Важно: base_url должен быть LAN/VPN адресом сервера, доступным с телефона.
        "base_url": MAP_API_URL.rstrip("/"),
    }
    url = f"{MAP_API_URL.rstrip('/')}/api/mobile/bootstrap/request"
    headers = _api_headers()
    if uid is not None:
        headers["X-Telegram-Id"] = str(uid)

    def _do():
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        try:
            return r.json() if r.text.strip() else {"ok": False, "error": "empty response", "status": r.status_code}
        except Exception:
            return {"ok": False, "error": r.text, "status": r.status_code}

    return await asyncio.to_thread(_do)


def _build_dutytracker_deeplink(base_url: str, token: str) -> str:
    # Deep-link: dutytracker://bootstrap?base_url=...&token=...
    from urllib.parse import quote
    return f"dutytracker://bootstrap?base_url={quote(base_url, safe='')}&token={quote(token, safe='')}"



def _build_dutytracker_intent_link(base_url: str, token: str) -> str:
    """Более совместимый deep-link через intent:// (Telegram иногда не открывает custom-scheme из кнопки)."""
    from urllib.parse import quote
    # intent://<host>?...#Intent;scheme=<scheme>;package=<package>;end
    q_base = quote(base_url, safe="")
    q_token = quote(token, safe="")
    return (
        "intent://bootstrap"
        f"?base_url={q_base}&token={q_token}"
        "#Intent;scheme=dutytracker;package=com.mapv12.dutytracker;end"
    )


async def cmd_connect(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Подать заявку на привязку Android DutyTracker и (если уже одобрено) выдать ссылку."""
    if not update.message:
        return

    # Доступ только после approve (officer/admin)
    if not await _ensure_service_role(update, context):
        return

    uid = str(update.effective_user.id) if update.effective_user else ""
    if not uid:
        await update.message.reply_text("Не удалось определить Telegram user_id.")
        return

    note = ""
    try:
        if update.effective_user and update.effective_user.username:
            note = f"tg:@{update.effective_user.username}"
        elif update.effective_user and update.effective_user.full_name:
            note = f"tg:{update.effective_user.full_name}"
    except Exception:
        note = ""

    res = await _mobile_connect_request(uid, note=note)
    http_status = int(res.get("_http_status") or 200)

    if http_status == 403:
        await update.message.reply_text("Доступ к подключению DutyTracker запрещён (нет роли «Служба»).")
        return
    if not isinstance(res, dict):
        await update.message.reply_text("Ошибка запроса к серверу (неверный ответ).")
        return

    status = (res.get("status") or "").strip().lower()
    if not status and isinstance(res.get("request"), dict):
        status = (res.get("request", {}).get("status") or "").strip().lower()

    if status in {"pending", ""}:
        await update.message.reply_text(
            "Заявка на подключение DutyTracker отправлена.\n"
            "Ожидайте подтверждения администратора на сайте.\n\n"
            "После подтверждения придёт кнопка «Открыть DutyTracker».\n"
            "Если сообщение не пришло — нажмите «Подключить DutyTracker» ещё раз."
        )
        return

    if status == "denied":
        await update.message.reply_text(
            "Подключение DutyTracker отклонено администратором.\n"
            "Если нужно — нажмите «Подключить DutyTracker» ещё раз, чтобы подать заявку повторно."
        )
        return

    if status == "approved":
        st = await _mobile_connect_status(uid, issue=True)
        if int(st.get("_http_status") or 200) >= 400:
            await update.message.reply_text("Не удалось получить ссылку подключения (ошибка сервера).")
            return

        issued = None
        try:
            issued = (st.get("request") or {}).get("issued")
        except Exception:
            issued = None

        if not issued:
            await update.message.reply_text(
                "Заявка одобрена, но ссылку выдать не удалось.\n"
                "Попробуйте нажать «Подключить DutyTracker» ещё раз."
            )
            return

        token = (issued.get("token") or "").strip()
        base_url = (issued.get("base_url") or MAP_API_URL).rstrip("/")
        pair_code = (issued.get("pair_code") or "").strip()

        link = _build_dutytracker_deeplink(base_url, token)
        intent_link = _build_dutytracker_intent_link(base_url, token)

        # Telegram Bot API НЕ принимает intent:// и custom-scheme в URL для inline-кнопок.
        # Поэтому используем http-страницу на сервере, которая редиректит в приложение.
        from urllib.parse import quote
        open_url = f"{base_url.rstrip('/')}/open/dutytracker?token={quote(token, safe='')}"
        kb_inline = InlineKeyboardMarkup([
            [InlineKeyboardButton("Открыть страницу привязки", url=open_url)],
        ])

        await update.message.reply_text(
            "Подключение DutyTracker:\n"
            f"BASE_URL: {base_url}\n"
            f"PAIR CODE: {pair_code}\n\n"
            "Ссылка для открытия (через браузер) — нажмите кнопку ниже:\n"
            f"{open_url}\n\n"
            "Если браузер не открыл приложение, попробуйте скопировать одну из ссылок ниже и открыть в Chrome/Заметках:\n"
            f"{link}\n\n"
            f"{intent_link}",
            reply_markup=kb_inline,
            disable_web_page_preview=True,
        )
        return

    await update.message.reply_text(f"Неожиданный статус: {status}")

async def _duty_post_json(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST на backend (Flask) с X-API-KEY. Возвращает dict (или {'error': ...})."""
    url = f"{MAP_API_URL.rstrip('/')}{path}"
    def _do():
        r = requests.post(url, json=payload, headers=_api_headers(), timeout=10)
        # backend иногда возвращает пусто
        try:
            return r.json() if r.text.strip() else {}
        except Exception:
            return {"error": r.text, "status": r.status_code}
    return await asyncio.to_thread(_do)


async def cmd_unit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Указать номер наряда / позывной: /unit 123"""
    if not update.message:
        return

    if not await _ensure_service_role(update, context):
        return
    parts = (update.message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text("Пример: /unit 321 (номер наряда/позывной)")
        return
    unit = parts[1].strip()[:64]
    context.user_data["unit_label"] = unit
    payload = {"user_id": update.effective_user.id, "unit_label": unit}
    r = await _duty_post_json("/api/duty/bot/shift/set_unit", payload)
    if r.get("ok"):
        await update.message.reply_text(f"✅ Номер наряда сохранён: {unit}")
    else:
        await update.message.reply_text(f"✅ Номер наряда сохранён локально: {unit}\n(Backend не ответил: {r.get('error')})")


async def cmd_shift_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_service_role(update, context):
        return
    u = update.effective_user
    unit = context.user_data.get("unit_label") or (u.username or f"TG {u.id}")
    payload = {"user_id": u.id, "unit_label": unit}
    r = await _duty_post_json("/api/duty/bot/shift/start", payload)
    if r.get("ok"):
        sid = r.get("shift_id")
        already = r.get("already_active")
        msg = f"🟢 Смена {'уже активна' if already else 'начата'}.\nshift_id: {sid}\nНаряд: {unit}"
        msg += "\n\n📌 Чтобы сменить номер наряда: /unit 123"
        await update.effective_message.reply_text(msg, reply_markup=service_kb("officer"))
    else:
        await update.effective_message.reply_text(f"Ошибка старта смены: {r.get('error') or r}")


async def cmd_shift_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_service_role(update, context):
        return
    u = update.effective_user
    payload = {"user_id": u.id}
    r = await _duty_post_json("/api/duty/bot/shift/end", payload)
    if r.get("ok"):
        context.user_data.pop("duty_tracking_session_id", None)
        await update.effective_message.reply_text("🔴 Смена завершена (если была активна).", reply_markup=service_kb("officer"))
    else:
        await update.effective_message.reply_text(f"Ошибка завершения смены: {r.get('error') or r}")



async def cmd_sos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """🆘 SOS: отправить экстренный сигнал оператору.

    Пытаемся создать SOS по последней известной точке (из live или истории).
    Если точки нет — попросим отправить одноразовую геометку.
    """
    if not await _ensure_service_role(update, context):
        return
    u = update.effective_user
    unit = context.user_data.get("unit_label") or (u.username or f"TG {u.id}")
    payload = {"user_id": u.id, "unit_label": unit, "note": "SOS"}

    r = await _duty_post_json("/api/duty/bot/sos/last", payload)
    if r.get("ok"):
        await update.effective_message.reply_text(
            "🆘 SOS отправлен оператору. Если можешь — продолжай отправлять live‑геопозицию.",
            reply_markup=service_kb("officer"),
        )
        return

    # если backend сказал, что нет последней точки — попросим геометку
    if (r.get("error") == "no_last_location") or r.get("need_location") or (r.get("status") == 409):
        context.user_data["await_duty_sos"] = True
        kb_loc = ReplyKeyboardMarkup(
            [[KeyboardButton("📍 Отправить геометку", request_location=True)], [KeyboardButton(BTN_DUTY_BACK)]],
            resize_keyboard=True
        )
        await update.effective_message.reply_text(
            "🆘 Для SOS нужна геометка.\n\nНажми «📍 Отправить геометку» (одноразово).",
            reply_markup=kb_loc
        )
        return

    await update.effective_message.reply_text(f"Не удалось отправить SOS: {r.get('error') or r}")

async def cmd_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Запросить одноразовую геометку (подтверждение прибытия/дежурства)."""
    if not await _ensure_service_role(update, context):
        return
    context.user_data["await_duty_checkin"] = True
    kb_loc = ReplyKeyboardMarkup(
        [[KeyboardButton("📍 Отправить геометку", request_location=True)], [KeyboardButton(BTN_DUTY_BACK)]],
        resize_keyboard=True
    )
    await update.effective_message.reply_text("Отправь геометку (одноразово).", reply_markup=kb_loc)



async def cmd_duty_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Вернуться в главное меню из duty-режимов (check-in/SOS)."""
    # очистим ожидания
    context.user_data.pop("await_duty_checkin", None)
    context.user_data.pop("await_duty_sos", None)
    context.user_data.pop("await_duty_live", None)
    await update.effective_message.reply_text("Ок.", reply_markup=service_kb("officer"))

async def cmd_live_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_service_role(update, context):
        return
    context.user_data["await_duty_live"] = True
    await update.effective_message.reply_text(
        "📡 Live‑трекинг\n\n"
        "1) Нажми 📎 → Локация\n"
        "2) Выбери «Поделиться геопозицией» (live)\n"
        "3) Укажи время (например 15/60 мин) и отправь\n\n"
        "Бот будет принимать обновления даже при заблокированном экране (пока Telegram отправляет live‑обновления).\n"
        "Остановить можно кнопкой «⛔ Остановить трекинг» или выключив live‑локацию в Telegram.",
        reply_markup=service_kb("officer"))


async def cmd_live_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _ensure_service_role(update, context):
        return
    u = update.effective_user
    sid = context.user_data.get("duty_tracking_session_id")
    payload = {"user_id": u.id}
    if sid:
        payload["session_id"] = sid
    r = await _duty_post_json("/api/duty/bot/tracking/stop", payload)
    if r.get("ok"):
        context.user_data.pop("duty_tracking_session_id", None)
        snap = r.get("snapshot_url")
        txt = "⛔ Трекинг остановлен."
        if snap:
            txt += f"\nСнимок маршрута: {MAP_API_URL.rstrip('/')}{snap}"
        await update.effective_message.reply_text(txt, reply_markup=service_kb("officer"))
    else:
        await update.effective_message.reply_text(f"Ошибка остановки: {r.get('error') or r}")


async def cmd_break_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Кнопка запроса обеда — выдаём inline варианты длительности."""
    if not await _ensure_service_role(update, context):
        return
    kb_inline = InlineKeyboardMarkup([
        [InlineKeyboardButton("15 мин", callback_data=DUTY_BREAK_CB_PREFIX + "15"),
         InlineKeyboardButton("30 мин", callback_data=DUTY_BREAK_CB_PREFIX + "30")],
        [InlineKeyboardButton("45 мин", callback_data=DUTY_BREAK_CB_PREFIX + "45"),
         InlineKeyboardButton("60 мин", callback_data=DUTY_BREAK_CB_PREFIX + "60")],
    ])
    await update.effective_message.reply_text("🍽 Запросить обед. Выбери длительность:", reply_markup=kb_inline)


async def on_break_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q:
        return
    data = q.data or ""
    if not data.startswith(DUTY_BREAK_CB_PREFIX):
        return
    await q.answer()
    # Защита на уровне бота (сервер также вернёт 403 без прав)
    uid = str(update.effective_user.id) if update.effective_user else ""
    st = await _service_get_status(uid) if uid else "guest"
    if _service_status_human(st) not in {"officer", "admin"}:
        if q.message:
            await q.message.reply_text("Нет доступа к \"Службе\". Подайте заявку через 🛡️ Служба.")
        return
    try:
        mins = int(data.split(":", 1)[1])
    except Exception:
        mins = 30
    u = update.effective_user
    unit = context.user_data.get("unit_label") or (u.username or f"TG {u.id}")
    payload = {"user_id": u.id, "duration_min": mins, "unit_label": unit}
    r = await _duty_post_json("/api/duty/bot/break/request", payload)
    if r.get("ok"):
        bid = r.get("break_id")
        await q.message.reply_text(f"Запрос обеда отправлен ✅ (#{bid}). Ожидай подтверждения оператора.")
    else:
        await q.message.reply_text(f"Ошибка запроса обеда: {r.get('error') or r}")


async def handle_duty_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Принимаем location и отправляем на backend (checkin / live)."""
    msg = update.effective_message
    if not msg or not msg.location:
        return
    u = update.effective_user
    unit = context.user_data.get("unit_label") or (u.username or f"TG {u.id}")

    # PTB: live_period хранится в Message (для live-location).
    live_period = getattr(msg, "live_period", None)
    is_live = bool(live_period)

    # одноразовая локация может быть либо check-in, либо SOS (если ждём)
    await_checkin = bool(context.user_data.get("await_duty_checkin"))
    await_sos = bool(context.user_data.get("await_duty_sos"))
    if not is_live and (not await_checkin) and (not await_sos):
        return

    lat = msg.location.latitude
    lon = msg.location.longitude
    acc = getattr(msg.location, "horizontal_accuracy", None) if hasattr(msg.location, "horizontal_accuracy") else None
    ts = (getattr(msg, "edit_date", None) or getattr(msg, "date", None))
    ts_iso = ts.isoformat() if ts else None

    if is_live:
        # Live принимаем только если пользователь явно включал live‑режим через кнопку,
        # либо если мы ждём SOS (чтобы создать SOS по первой live‑точке).
        if not context.user_data.get("await_duty_live") and not await_sos:
            return
        # если мы ждали SOS, но пользователь отправил live‑локацию — создадим SOS по первой live‑точке
        if await_sos:
            context.user_data["await_duty_sos"] = False
            payload_sos = {"user_id": u.id, "unit_label": unit, "lat": lat, "lon": lon, "accuracy_m": acc, "note": "SOS", "ts": ts_iso}
            rs = await _duty_post_json("/api/duty/bot/sos", payload_sos)
            # отвечаем только на первую отправку live (не на каждое редактирование координат)
            if not getattr(msg, "edit_date", None) and rs.get("ok"):
                await msg.reply_text("🆘 SOS отправлен. Live‑трекинг продолжается…", reply_markup=service_kb("officer"))

        payload = {"user_id": u.id, "unit_label": unit, "lat": lat, "lon": lon, "accuracy_m": acc, "is_live": True, "message_id": msg.message_id, "ts": ts_iso}
        r = await _duty_post_json("/api/duty/bot/live_location", payload)
        if r.get("ok"):
            sid = r.get("session_id")
            if sid:
                context.user_data["duty_tracking_session_id"] = sid
        return

    # SOS (одноразовая геометка)
    if await_sos:
        context.user_data["await_duty_sos"] = False
        payload = {"user_id": u.id, "unit_label": unit, "lat": lat, "lon": lon, "accuracy_m": acc, "note": "SOS", "ts": ts_iso}
        r = await _duty_post_json("/api/duty/bot/sos", payload)
        if r.get("ok"):
            await msg.reply_text("🆘 SOS отправлен оператору.", reply_markup=service_kb("officer"))
        else:
            await msg.reply_text(f"Ошибка SOS: {r.get('error') or r}", reply_markup=service_kb("officer"))
        return

    # одноразовая отбивка
    context.user_data["await_duty_checkin"] = False
    payload = {"user_id": u.id, "unit_label": unit, "lat": lat, "lon": lon, "accuracy_m": acc, "note": "checkin", "ts": ts_iso}
    r = await _duty_post_json("/api/duty/bot/checkin", payload)
    if r.get("ok"):
        await msg.reply_text("✅ Отбивка принята.", reply_markup=service_kb("officer"))
    else:
        await msg.reply_text(f"Ошибка отбивки: {r.get('error') or r}", reply_markup=service_kb("officer"))


async def duty_notify_poll_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Периодическая задача: прислать пользователям duty-уведомления (обед, подтверждения и т.п.)."""
    if not MAP_API_URL:
        return

    url_targets = f"{MAP_API_URL.rstrip('/')}/api/duty/notify_targets"
    try:
        r = await asyncio.to_thread(requests.get, url_targets, headers=_api_headers(), timeout=10)
        r.raise_for_status()
        targets = r.json() if r.text.strip() else []
    except Exception:
        return

    for t in targets:
        try:
            uid = int(t.get("user_id"))
        except Exception:
            continue
        pend_url = f"{MAP_API_URL.rstrip('/')}/api/duty/{uid}/pending"
        try:
            r2 = await asyncio.to_thread(requests.get, pend_url, headers=_api_headers(), timeout=10)
            r2.raise_for_status()
            items = r2.json() if r2.text.strip() else []
        except Exception:
            continue
        if not items:
            continue

        ack_ids = []
        for it in items:
            nid = it.get("id")
            text = it.get("text") or ""
            if not text:
                continue
            try:
                await context.bot.send_message(chat_id=uid, text=text)
                if nid:
                    ack_ids.append(nid)
            except Exception:
                # не будем ack если не дошло
                pass

        if ack_ids:
            ack_url = f"{MAP_API_URL.rstrip('/')}/api/duty/{uid}/ack"
            try:
                await asyncio.to_thread(requests.post, ack_url, headers=_api_headers(), json={"ids": ack_ids}, timeout=10)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------
_COORDS_RE = re.compile(r"^\s*([+-]?\d+(?:[\.,]\d+)?)\s*,\s*([+-]?\d+(?:[\.,]\d+)?)\s*$")

def _geocode_offline_sync(query: str) -> Optional[Tuple[float, float]]:
    base = os.path.dirname(os.path.abspath(__file__))
    cache_file = os.path.join(base, "data", "offline", "geocode.json")
    if not os.path.exists(cache_file):
        return None
    try:
        with open(cache_file, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        q = (query or "").lower()
        for entry in data:
            disp = (entry.get("display_name") or "")
            addr = (entry.get("address") or "")
            if q in disp.lower() or q in addr.lower():
                lat = float(entry.get("lat"))
                lon = float(entry.get("lon"))
                return (lat, lon)
    except Exception as e:
        log.warning("offline geocode failed: %s", e)
    return None

async def _geocode_online(query: str) -> Optional[Tuple[float, float]]:
    def _do_request():
        try:
            params = {"q": query, "format": "json", "limit": 1}
            headers = {"User-Agent": "map-v12-bot"}
            resp = requests.get(
                "https://nominatim.openstreetmap.org/search",
                params=params,
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
        except Exception as e:
            log.warning("online geocode failed: %s", e)
        return None
    return await asyncio.to_thread(_do_request)

async def geocode_address(query: str) -> Optional[Tuple[float, float]]:
    coords = _geocode_offline_sync(query)
    if coords:
        return coords
    return await _geocode_online(query)

# ---------------------------------------------------------------------------
# Map API (user flow)
# ---------------------------------------------------------------------------
async def add_marker_via_api(
    address: str,
    notes: str,
    lat: float,
    lon: float,
    status: str,
    category: str = "Видеонаблюдение",
    reporter_surname: str = "",
    photo_path: Optional[str] = None,
    tg_user_id: Optional[str] = None,
    tg_message_id: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Post a new marker to the Map API.  If photo_path is provided and points
    to a local file, the request will be sent as multipart/form-data with
    the image included.  Otherwise, a JSON request is sent.  Returns
    (success, error_message).
    """
    url = f"{MAP_API_URL}/api/bot/markers"
    headers: Dict[str, str] = {}
    if BOT_API_KEY:
        headers["X-API-KEY"] = BOT_API_KEY
    # Assemble common fields as strings for form or JSON
    data_fields = {
        "name": address or "Без адреса",
        "notes": notes,
        "lat": str(lat),
        "lon": str(lon),
        "status": status,
        "category": category,
        "reporter": json.dumps({"surname": (reporter_surname or "").strip()}),
    }

    # Идентификаторы для идемпотентности/связки с пользователем
    if tg_user_id:
        data_fields["user_id"] = str(tg_user_id)
    if tg_message_id:
        data_fields["message_id"] = str(tg_message_id)
    def _do_post():
        try:
            if photo_path and os.path.isfile(photo_path):
                # Prepare multipart form with file
                files = {"photo": open(photo_path, "rb")}
                # Use data_fields as form fields (not JSON)
                r = requests.post(url, data=data_fields, files=files, headers=headers, timeout=30)
                try:
                    files["photo"].close()
                except Exception:
                    pass
            else:
                # JSON payload
                # reporter field should be a dict here
                payload = {
                    "name": data_fields["name"],
                    "notes": notes,
                    "lat": lat,
                    "lon": lon,
                    "status": status,
                    "category": category,
                    "reporter": {"surname": (reporter_surname or "").strip()},
                }
                if tg_user_id:
                    payload["user_id"] = str(tg_user_id)
                if tg_message_id:
                    payload["message_id"] = str(tg_message_id)
                r = requests.post(url, json=payload, headers=headers, timeout=30)
            # Успех в API считается как 200 OK или 201 Created
            if r.status_code in (200, 201):
                return True, ""

            # Не отдаём пользователю огромную HTML-страницу дебагера Flask
            # (в DEBUG режиме она очень длинная, Telegram режет >4096 символов).
            err_text = ""
            try:
                j = r.json()
                if isinstance(j, dict):
                    err_text = str(j.get("message") or j.get("error") or j)
                else:
                    err_text = str(j)
            except Exception:
                err_text = (r.text or "").strip()

            low = err_text.lower()
            if "<html" in low or "<!doctype" in low:
                err_text = f"HTTP {r.status_code}: ошибка сервера (подробности в логах сервера)."
            # ограничиваем длину, чтобы Telegram точно принял сообщение
            if len(err_text) > 800:
                err_text = err_text[:800] + "…"

            return False, err_text
        except Exception as exc:
            return False, str(exc)
    return await asyncio.to_thread(_do_post)

# ---------------------------------------------------------------------------
# Navigation helpers
# ---------------------------------------------------------------------------
def is_back(update: Update) -> bool:
    txt = (update.message.text if update.message else "") or ""
    return txt.strip() == BTN_BACK

def is_cancel(update: Update) -> bool:
    txt = (update.message.text if update.message else "") or ""
    return txt.strip() == BTN_CANCEL

async def go_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    is_admin = is_admin_logged(update) or _is_admin_whitelisted(update)
    if update.message:
        await update.message.reply_text(TEXT_GREET, reply_markup=await home_kb_for(update, context, is_admin))

# ---------------------------------------------------------------------------
# Handlers — home & user wizard
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Приветствие и показ главного меню.

    Текст зависит от того, авторизован ли администратор. Для обычных
    пользователей показывается стандартная инструкция, для администраторов
    — то же самое с напоминанием про админ-меню.
    """
    is_admin = is_admin_logged(update) or _is_admin_whitelisted(update)
    text = TEXT_GREET
    if is_admin:
        text = TEXT_GREET + (
            "\n\nВы авторизованы как администратор. "
            f"Для перехода в админ‑меню используйте кнопку \"{BTN_ADMIN_MENU}\" "
            "или команды /stats, /pending, /approved, /rejected."
        )
    await update.message.reply_text(text, reply_markup=await home_kb_for(update, context, is_admin))


async def add_start_from_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await add_start(update, context)

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "Шаг 1/5. Укажите местоположение точки.\n"
        "• Введите адрес текстом (улица, дом, город).\n"
        "• Или координаты в формате: 53.9000, 27.5500",
        reply_markup=PLACE_KB,
    )
    return PLACE

# PLACE
async def place_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update):
        await update.message.reply_text("Действие отменено.", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END
    if is_back(update):
        await go_home(update, context)
        return ConversationHandler.END

    raw = (update.message.text or "").strip()
    if not raw:
        await update.message.reply_text(
            "Пустой ввод. Введите адрес или координаты в формате: 53.9000, 27.5500",
            reply_markup=PLACE_KB,
        )
        return PLACE

    m = _COORDS_RE.match(raw)
    if m:
        lat = float(m.group(1).replace(",", "."))
        lon = float(m.group(2).replace(",", "."))
        context.user_data["lat"] = lat
        context.user_data["lon"] = lon
        context.user_data["address"] = ""
    else:
        context.user_data["address"] = raw
        context.user_data.pop("lat", None)
        context.user_data.pop("lon", None)

    await update.message.reply_text(
        "Шаг 2/5. Введите описание (подъезд/камеры/примечания):",
        reply_markup=DESCRIPTION_KB,
    )
    return DESCRIPTION


# DESCRIPTION
async def get_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update):
        await update.message.reply_text("Действие отменено.", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END
    if is_back(update):
        await update.message.reply_text(
            "Шаг 1/5. Укажите местоположение точки.\n"
            "• Введите адрес текстом.\n"
            "• Или координаты: 53.9000, 27.5500",
            reply_markup=PLACE_KB,
        )
        return PLACE

    context.user_data["description"] = (update.message.text or "").strip()
    # Proceed to access selection
    await update.message.reply_text("Шаг 3/5. Выберите тип доступа камеры:", reply_markup=ACCESS_REPLY_KB)
    await update.message.reply_text("Выберите один из вариантов ниже:", reply_markup=access_inline_kb())
    return ACCESS

# ACCESS
async def access_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if not data.startswith("access:"):
        return ACCESS
    choice = data.split(":", 1)[1]
    status = "Локальный доступ" if choice == "local" else "Удаленный доступ"
    context.user_data["status"] = status
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass
    # After selecting access, prompt for photo (optional)
    await query.message.reply_text(
        "Шаг 4/5. Отправьте фото объекта (можно пропустить сообщением 'Пропустить'):",
        reply_markup=PHOTO_KB,
    )
    return PHOTO

def _normalize_status(text: str) -> str:
    t = (text or "").strip().lower()
    return "Удаленный доступ" if "удал" in t else "Локальный доступ"

# PHOTO
async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle the photo upload step.  The user may send a photo (Telegram sends
    it as a list in update.message.photo) or text to skip the step.  If the
    user presses back, return to the access selection.  On cancel, abort.
    """
    # Cancel
    if is_cancel(update):
        await update.message.reply_text("Действие отменено.", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END
    # Back -> return to access state
    if is_back(update):
        # Ask for access again
        await update.message.reply_text(
            "Шаг 3/5. Выберите тип доступа камеры:", reply_markup=ACCESS_REPLY_KB
        )
        await update.message.reply_text(
            "Выберите один из вариантов ниже:", reply_markup=access_inline_kb()
        )
        return ACCESS
    # Handle photo: if user sent an image
    # Note: update.message.photo is a list of PhotoSize; Telegram arranges them by size
    photo_path: Optional[str] = None
    if update.message.photo:
        try:
            photo_file = update.message.photo[-1]
            # Download the file to a temporary path
            file = await photo_file.get_file()
            import tempfile
            tmp_dir = tempfile.mkdtemp(prefix='mapv12_')
            # Use file_unique_id to generate deterministic filename with jpg extension
            fname = f"{photo_file.file_unique_id}.jpg"
            tmp_path = os.path.join(tmp_dir, fname)
            await file.download_to_drive(custom_path=tmp_path)
            photo_path = tmp_path
        except Exception as e:
            log.error("Failed to download photo: %s", e)
            photo_path = None
    else:
        # Check if the user typed a skip command (ru: Пропустить, skip etc.)
        txt = (update.message.text or "").strip().lower()
        if txt in ("пропустить", "skip", "нет", "-"):
            photo_path = None
        else:
            # No photo; treat any other text as skip
            photo_path = None
    # Save path (or None) in context
    context.user_data["photo_file_path"] = photo_path
    # Proceed to final step: reporter surname
    await update.message.reply_text("Шаг 5/5. Укажите фамилию инициатора запроса:", reply_markup=SURNAME_KB)
    return SURNAME

async def access_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update):
        await update.message.reply_text("Действие отменено.", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END
    if is_back(update):
        curr = context.user_data.get("description", "")
        msg = "Вернёмся к описанию.\n"
        if curr:
            msg += f"Текущее: «{curr}»\n"
        msg += "Введите описание:"
        await update.message.reply_text(msg, reply_markup=DESCRIPTION_KB)
        return DESCRIPTION

    status = _normalize_status(update.message.text or "")
    context.user_data["status"] = status
    await update.message.reply_text(
        "Шаг 4/5. Отправьте фото объекта (можно пропустить сообщением 'Пропустить'):",
        reply_markup=PHOTO_KB,
    )
    return PHOTO

# SURNAME (final)
async def get_surname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update):
        await update.message.reply_text("Действие отменено.", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END
    if is_back(update):
        # Return to photo step (step 4)
        await update.message.reply_text(
            "Шаг 4/5. Отправьте фото объекта (можно пропустить сообщением 'Пропустить'):",
            reply_markup=PHOTO_KB,
        )
        return PHOTO

    surname = (update.message.text or "").strip()
    context.user_data["reporter_surname"] = surname

    address = context.user_data.get("address", "")
    notes = context.user_data.get("description", "")
    status = context.user_data.get("status", "Локальный доступ")
    lat = context.user_data.get("lat")
    lon = context.user_data.get("lon")

    if lat is None or lon is None:
        if not address:
            await update.message.reply_text(
                "Адрес пустой. Начните заново: нажмите «Добавить точку».",
                reply_markup=await home_kb_for(update, context, is_admin_logged(update) or _is_admin_whitelisted(update)),
            )
            context.user_data.clear()
            return ConversationHandler.END
        coords = await geocode_address(address)
        if not coords:
            await update.message.reply_text(
                "Не удалось определить координаты по адресу. Попробуйте другой адрес или начните заново.",
                reply_markup=await home_kb_for(update, context, is_admin_logged(update) or _is_admin_whitelisted(update)),
            )
            context.user_data.clear()
            return ConversationHandler.END
        lat, lon = coords

    # Extract optional photo path from context.  May be None if user skipped.
    photo_path = context.user_data.get("photo_file_path")
    ok, err = await add_marker_via_api(
        address,
        notes,
        float(lat),
        float(lon),
        status,
        category=context.user_data.get("category", "Видеонаблюдение"),
        reporter_surname=surname,
        photo_path=photo_path,
        tg_user_id=str(update.effective_user.id) if update.effective_user else None,
        tg_message_id=str(update.message.message_id) if update.message else None,
    )
    # Clean up temporary photo file after upload
    try:
        if photo_path:
            import os, shutil
            if os.path.isfile(photo_path):
                os.remove(photo_path)
            # Also remove the directory if empty
            dirn = os.path.dirname(photo_path)
            try:
                os.rmdir(dirn)
            except Exception:
                pass
    except Exception:
        pass
    if ok:
        await update.message.reply_text(
            "✅ Заявка отправлена. Ожидает подтверждения администратором.",
            reply_markup=await home_kb_for(update, context, is_admin_logged(update) or _is_admin_whitelisted(update)),
        )
    else:
        await update.message.reply_text(
            f"❌ Ошибка добавления точки: {err}",
            reply_markup=await home_kb_for(update, context, is_admin_logged(update) or _is_admin_whitelisted(update)),
        )

    context.user_data.clear()
    return ConversationHandler.END

# cancel
async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Действие отменено.", reply_markup=ReplyKeyboardRemove())
    await start(update, context)
    return ConversationHandler.END

# ---------------------------------------------------------------------------
# Admin: stats with fallback
# ---------------------------------------------------------------------------
async def _stats_with_fallback(update: Update) -> dict:
    try:
        data = await admin_GET(update, "/admin/summary")
        apps = data.get("applications", {})
        addrs = data.get("addresses", {})
        return {
            "active": int(apps.get("active", 0)),
            "approved": int(apps.get("approved", addrs.get("total", 0))),
            "rejected": int(apps.get("rejected", 0)),
            "new_last_7d": apps.get("new_last_7d", "—"),
            "addresses_total": int(addrs.get("total", apps.get("approved", 0))),
        }
    except Exception:
        pass

    # pending
    active = 0
    try:
        d = await admin_GET(update, "/api/requests/count")
        active = int(d.get("count", 0))
    except Exception:
        active = 0

    # approved (fallback to all addresses count)
    approved = 0
    try:
        d = await admin_GET(update, "/admin/addresses", params={"page": 1, "limit": 1})
        if isinstance(d, dict) and "total" in d:
            approved = int(d["total"])
        else:
            lst = await admin_GET(update, "/api/addresses")
            if isinstance(lst, list):
                approved = len(lst)
    except Exception:
        try:
            lst = await admin_GET(update, "/api/addresses")
            if isinstance(lst, list):
                approved = len(lst)
        except Exception:
            approved = 0

    # rejected
    rejected = "—"
    try:
        rej = await admin_GET(update, "/admin/applications", params={"status": "rejected", "limit": 1})
        if isinstance(rej, dict) and "total" in rej:
            rejected = int(rej["total"])
    except Exception:
        pass

    return {
        "active": active,
        "approved": approved,
        "rejected": rejected,
        "new_last_7d": "—",
        "addresses_total": approved,
    }

# ---------------------------------------------------------------------------
# Admin: login & read-only menu
# ---------------------------------------------------------------------------
async def admin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_admin_logged(update) or _is_admin_whitelisted(update):
        return await admin_menu(update, context)
    context.user_data.clear()
    await update.message.reply_text("Введите логин администратора:", reply_markup=kb([[BTN_CANCEL]]))
    return ADMIN_LOGIN_USER

async def admin_login_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update):
        return await cancel_cmd(update, context)
    context.user_data["admin_username"] = (update.message.text or "").strip()
    await update.message.reply_text("Введите пароль:", reply_markup=kb([[BTN_BACK], [BTN_CANCEL]]))
    return ADMIN_LOGIN_PASS

async def admin_login_pass(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update):
        return await cancel_cmd(update, context)
    if is_back(update):
        await update.message.reply_text("Введите логин администратора:", reply_markup=kb([[BTN_CANCEL]]))
        return ADMIN_LOGIN_USER

    password = (update.message.text or "").strip()
    username = context.user_data.get("admin_username", "")
    ok, sess, err = await admin_POST_login(username, password)
    if ok and sess:
        _set_admin_session(update.effective_user.id, sess)
        await update.message.reply_text("Вход выполнен.", reply_markup=ReplyKeyboardRemove())
        return await admin_menu(update, context)

    await update.message.reply_text(
        f"Не удалось войти. {err or ''}\nПопробуйте снова.\n\nВведите логин:",
        reply_markup=kb([[BTN_CANCEL]]),
    )
    return ADMIN_LOGIN_USER

async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Админ-меню (только просмотр):", reply_markup=admin_menu_kb())
    return ADMIN_MENU

async def _print_list(chat, title: str, items: List[dict]):
    """Печатает список в чат, безопасно по длине сообщений Telegram."""
    if not items:
        await chat.send_message(f"{title}: ничего нет.")
        return

    max_len = 3500  # запас до лимита Telegram 4096
    chunk: List[str] = [title]
    cur_len = len(title)

    for it in items:
        line = f"• #{it.get('id')} — {it.get('name') or it.get('title') or '—'}"
        # +1 за перенос строки
        if cur_len + 1 + len(line) > max_len and len(chunk) > 1:
            await chat.send_message("\n".join(chunk))
            chunk = [title]
            cur_len = len(title)
        chunk.append(line)
        cur_len += 1 + len(line)

    if chunk:
        await chat.send_message("\n".join(chunk))

# addresses paging helpers
def _addr_nav_kb(page: int, total: int, limit: int) -> InlineKeyboardMarkup:
    pages = max(1, (total + limit - 1) // limit)
    prev_btn = InlineKeyboardButton("⟵ Назад", callback_data=f"addr:page:{max(1, page-1)}")
    next_btn = InlineKeyboardButton("Вперёд ⟶", callback_data=f"addr:page:{min(pages, page+1)}")
    return InlineKeyboardMarkup([[prev_btn, next_btn]])

def _format_addr_item(it: Dict[str, Any]) -> str:
    name = it.get("name") or it.get("address") or "—"
    lat = it.get("lat")
    lon = it.get("lon")
    cat = it.get("category") or "—"
    status = it.get("status") or "—"
    link = it.get("link") or ""
    notes = it.get("notes") or it.get("description") or "—"
    coords = f"{lat}, {lon}" if (lat is not None and lon is not None) else "—"
    out = [
        f"#{it.get('id')} — {name} ({coords})",
        f"Категория: {cat} | Доступ: {status}",
        f"Описание: {notes}",
    ]
    if link:
        out.append(f"Ссылка: {link}")
    return "\n".join(out)

async def _get_addresses_page(update: Update, page: int, limit: int) -> tuple[List[Dict[str, Any]], int]:
    try:
        data = await admin_GET(update, "/admin/addresses", params={"page": page, "limit": limit})
        if isinstance(data, dict) and "items" in data and "total" in data:
            return list(data["items"]), int(data["total"])
    except Exception:
        pass

    lst: List[Dict[str, Any]] = []
    try:
        data2 = await admin_GET(update, "/api/addresses")
        if isinstance(data2, list):
            lst = data2
    except Exception:
        lst = []
    total = len(lst)
    if total == 0:
        return [], 0
    pages = max(1, (total + limit - 1) // limit)
    page = max(1, min(page, pages))
    start = (page - 1) * limit
    end = start + limit
    return lst[start:end], total

async def admin_addresses_show(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1, limit: int = 10):
    try:
        items, total = await _get_addresses_page(update, page, limit)
        header = f"Адреса (стр. {page}, всего {total})"
        if not items:
            text = header + "\nНичего не найдено."
        else:
            blocks = [_format_addr_item(it) for it in items]
            text = header + "\n\n" + "\n\n".join(blocks)
        kb_inline = _addr_nav_kb(page, total, limit)
        if update.message:
            await update.message.reply_text(text, reply_markup=kb_inline)
        else:
            await update.callback_query.edit_message_text(text, reply_markup=kb_inline)
    except Exception as e:
        msg = f"Ошибка при получении адресов: {e}"
        if update.message:
            await update.message.reply_text(msg)
        else:
            await update.callback_query.answer(msg, show_alert=True)

async def admin_addresses_next_page_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = (q.data or "")
    try:
        _, _, page_str = data.split(":")
        page = max(1, int(page_str))
    except Exception:
        page = 1
    await admin_addresses_show(update, context, page=page, limit=10)

# admin router
async def admin_menu_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    txt = (update.message.text or "").strip()
    if txt == BTN_ADMIN_HOME:
        await start(update, context)
        return ConversationHandler.END
    if txt == BTN_ADMIN_LOGOUT:
        _set_admin_session(update.effective_user.id, None)
        await update.message.reply_text("Вы вышли из админ-аккаунта.", reply_markup=await home_kb_for(update, context, False))
        return ConversationHandler.END
    if txt == BTN_STATS:
        try:
            s = await _stats_with_fallback(update)
            await update.effective_chat.send_message(
                "Сводка:\n"
                f"• Активных: {s['active']}\n"
                f"• Одобренных: {s['approved']}\n"
                f"• Отклонённых: {s['rejected']}\n"
                f"• Новых за 7 дней: {s['new_last_7d']}\n"
                f"• Адресов всего: {s['addresses_total']}"
            )
        except Exception as e:
            await update.effective_chat.send_message(f"Ошибка при получении сводки: {e}")
        return ADMIN_MENU
    if txt == BTN_PENDING:
        try:
            data = await admin_GET(update, "/admin/applications", params={"status": "pending", "limit": 10})
            items = []
            if isinstance(data, dict):
                items = data.get("items", data.get("applications", []))
            elif isinstance(data, list):
                items = data
            await _print_list(update.effective_chat, "Активные заявки:", items)
        except Exception as e:
            await update.effective_chat.send_message(f"Ошибка при получении списка: {e}")
        return ADMIN_MENU
    if txt == BTN_APPROVED:
        try:
            data = await admin_GET(update, "/admin/applications", params={"status": "approved", "limit": 10})
            items = []
            if isinstance(data, dict):
                items = data.get("items", data.get("applications", []))
            elif isinstance(data, list):
                items = data
            await _print_list(update.effective_chat, "Одобренные заявки (последние):", items)
        except Exception as e:
            await update.effective_chat.send_message(f"Ошибка при получении списка: {e}")
        return ADMIN_MENU
    if txt == BTN_REJECTED:
        try:
            data = await admin_GET(update, "/admin/applications", params={"status": "rejected", "limit": 10})
            items = []
            if isinstance(data, dict):
                items = data.get("items", data.get("applications", []))
            elif isinstance(data, list):
                items = data
            if not items:
                await update.effective_chat.send_message(
                    "Отклонённых заявок нет или бэкенд не отдаёт историю."
                )
            else:
                lines = ["Отклонённые заявки (последние):"]
                for it in items:
                    name = it.get("name") or it.get("title") or "—"
                    rid = it.get("id")
                    reason = it.get("rejection_reason") or it.get("reason") or "—"
                    lines.append(f"• #{rid} — {name} | Причина: {reason}")
                await update.effective_chat.send_message("\n".join(lines))
        except Exception as e:
            await update.effective_chat.send_message(
                "Не удалось получить отклонённые заявки. Возможно, на бэкенде нет эндпоинта истории. "
                f"Деталь: {e}"
            )
        return ADMIN_MENU
    if txt == BTN_ADDRS:
        await admin_addresses_show(update, context, page=1, limit=10)
        return ADMIN_MENU
    if txt == BTN_APP:
        await update.message.reply_text("Введите ID заявки:", reply_markup=kb([[BTN_BACK], [BTN_ADMIN_HOME]]))
        return ADMIN_WAIT_APP_ID_VIEW
    return ADMIN_MENU

async def admin_view_app_by_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if (update.message.text or "").strip() == BTN_BACK:
        await update.message.reply_text("Админ-меню:", reply_markup=admin_menu_kb())
        return ADMIN_MENU
    if (update.message.text or "").strip() == BTN_ADMIN_HOME:
        await start(update, context)
        return ConversationHandler.END
    try:
        pid = int((update.message.text or "").strip())
    except Exception:
        await update.message.reply_text("Введите числовой ID или нажмите «Назад».")
        return ADMIN_WAIT_APP_ID_VIEW
    try:
        it = await admin_GET(update, f"/admin/applications/{pid}")
        await update.effective_chat.send_message(
            "Заявка #{id}\n"
            "Название: {name}\n"
            "Статус: {status}\n"
            "Координаты: {lat}, {lon}\n"
            "Причина отклонения: {rr}\n"
            "Адрес-ID (если одобрена): {aid}".format(
                id=it.get("id"),
                name=it.get("name") or "—",
                status=it.get("status") or "—",
                lat=it.get("lat"),
                lon=it.get("lon"),
                rr=it.get("rejection_reason") or it.get("reason") or "—",
                aid=it.get("address_id") or "—",
            )
        )
    except Exception as e:
        await update.effective_chat.send_message(f"Ошибка при чтении заявки: {e}")
    await update.message.reply_text("Админ-меню:", reply_markup=admin_menu_kb())
    return ADMIN_MENU

# ---------------------------------------------------------------------------
# Optional slash commands (read-only duplicates)
# ---------------------------------------------------------------------------
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        s = await _stats_with_fallback(update)
        await update.effective_chat.send_message(
            "Сводка:\n"
            f"• Активных: {s['active']}\n"
            f"• Одобренных: {s['approved']}\n"
            f"• Отклонённых: {s['rejected']}\n"
            f"• Новых за 7 дней: {s['new_last_7d']}\n"
            f"• Адресов всего: {s['addresses_total']}"
        )
    except Exception as e:
        await update.effective_chat.send_message(f"Ошибка: {e}")

async def cmd_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Определяем фильтр: категория или ID зоны через аргументы
        filter_type = None
        filter_value = None
        if context.args:
            first = context.args[0]
            if first.isdigit():
                filter_type = 'zone'
                filter_value = int(first)
            else:
                filter_type = 'category'
                filter_value = first
        await send_applications_list(update, context, status='pending', offset=0, filter_type=filter_type, filter_value=filter_value)
    except Exception as e:
        await update.effective_chat.send_message(f"Ошибка: {e}")

async def cmd_approved(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        filter_type = None
        filter_value = None
        if context.args:
            first = context.args[0]
            if first.isdigit():
                filter_type = 'zone'
                filter_value = int(first)
            else:
                filter_type = 'category'
                filter_value = first
        await send_applications_list(update, context, status='approved', offset=0, filter_type=filter_type, filter_value=filter_value)
    except Exception as e:
        await update.effective_chat.send_message(f"Ошибка: {e}")

async def cmd_rejected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        filter_type = None
        filter_value = None
        if context.args:
            first = context.args[0]
            if first.isdigit():
                filter_type = 'zone'
                filter_value = int(first)
            else:
                filter_type = 'category'
                filter_value = first
        await send_applications_list(update, context, status='rejected', offset=0, filter_type=filter_type, filter_value=filter_value)
    except Exception as e:
        await update.effective_chat.send_message(f"Ошибка: {e}")

async def cmd_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_chat.send_message("Использование: /app <id>")
        return
    try:
        pid = int(context.args[0])
    except Exception:
        await update.effective_chat.send_message("ID должен быть числом.")
        return
    try:
        it = await admin_GET(update, f"/admin/applications/{pid}")
        await update.effective_chat.send_message(
            "Заявка #{id}\n"
            "Название: {name}\n"
            "Статус: {status}\n"
            "Координаты: {lat}, {lon}\n"
            "Причина отклонения: {rr}\n"
            "Адрес-ID (если одобрена): {aid}".format(
                id=it.get("id"),
                name=it.get("name") or "—",
                status=it.get("status") or "—",
                lat=it.get("lat"),
                lon=it.get("lon"),
                rr=it.get("rejection_reason") or it.get("reason") or "—",
                aid=it.get("address_id") or "—",
            )
        )
    except Exception as e:
        await update.effective_chat.send_message(f"Ошибка: {e}")

# ---------------------------------------------------------------------------
# Pagination and enhanced analytics helpers
# ---------------------------------------------------------------------------

# Helpers to encode/decode filter in callback data. Allows to pass either zone
# ID or category name in a compact form. Category names are base64‑encoded to
# avoid delimiter conflicts.

def _encode_filter(filter_type: Optional[str], filter_value: Optional[Any]) -> str:
    """
    Encode filter type and value to a compact string for callback data.
    :param filter_type: 'zone' or 'category' or None
    :param filter_value: int for zone, str for category
    :return: encoded string; 'none' if no filter
    """
    if not filter_type or filter_value is None:
        return 'none'
    if filter_type == 'zone':
        return f'zone:{filter_value}'
    if filter_type == 'category':
        try:
            b = str(filter_value).encode('utf-8')
            code = base64.urlsafe_b64encode(b).decode('ascii')
            return f'cat:{code}'
        except Exception:
            return f'cat:{filter_value}'
    return 'none'


def _decode_filter(encoded: str) -> Tuple[Optional[str], Optional[Any]]:
    """
    Decode filter string from callback data to (filter_type, filter_value).
    :param encoded: string produced by _encode_filter
    :return: ('zone', id) or ('category', name) or (None, None)
    """
    if not encoded or encoded == 'none':
        return (None, None)
    try:
        typ, val = encoded.split(':', 1)
    except Exception:
        return (None, None)
    if typ == 'zone':
        try:
            return ('zone', int(val))
        except Exception:
            return ('zone', None)
    if typ == 'cat':
        try:
            raw = base64.urlsafe_b64decode(val.encode('ascii')).decode('utf-8')
            return ('category', raw)
        except Exception:
            return ('category', val)
    return (None, None)


async def send_applications_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    status: str,
    offset: int = 0,
    filter_type: Optional[str] = None,
    filter_value: Optional[Any] = None,
    limit: int = 10,
    via_callback: bool = False,
) -> None:
    """
    Общий вывод списка заявок с поддержкой фильтра по категории или зоне и
    автопагинацией. Выводит по `limit` элементов. При вызове из callback
    отредактирует существующее сообщение; при обычном вызове отправит
    новое сообщение в чат.
    """
    params: Dict[str, Any] = {'status': status, 'limit': limit, 'offset': max(0, offset)}
    if filter_type == 'zone' and filter_value is not None:
        params['zone_id'] = filter_value
    elif filter_type == 'category' and filter_value:
        params['category'] = filter_value
    data = await admin_GET(update, "/admin/applications", params=params)
    items: List[Any] = []
    if isinstance(data, dict):
        items = data.get("items", data.get("applications", [])) or []
    elif isinstance(data, list):
        items = data
    header_map = {
        'pending': 'Активные заявки:',
        'approved': 'Одобренные заявки:',
        'rejected': 'Отклонённые заявки:',
    }
    header = header_map.get(status, 'Заявки:')
    lines: List[str] = [header]
    if not items:
        if offset == 0:
            if status == 'pending':
                msg = 'Активных заявок нет.'
            elif status == 'approved':
                msg = 'Одобренных заявок нет.'
            else:
                msg = 'Отклонённых заявок нет или история недоступна.'
            if via_callback and update.callback_query:
                await update.callback_query.edit_message_text(msg)
            else:
                await update.effective_chat.send_message(msg)
            return
        else:
            if via_callback and update.callback_query:
                await update.callback_query.answer('Больше записей нет', show_alert=True)
            return
    for it in items:
        rid = it.get('id')
        name = it.get('name') or it.get('title') or '—'
        if status == 'rejected':
            reason = it.get('rejection_reason') or it.get('reason') or '—'
            lines.append(f'• #{rid} — {name} | Причина: {reason}')
        else:
            lines.append(f'• #{rid} — {name}')
    buttons: List[InlineKeyboardButton] = []
    if offset > 0:
        prev_offset = max(0, offset - limit)
        encoded_filter = _encode_filter(filter_type, filter_value)
        buttons.append(InlineKeyboardButton('« Назад', callback_data=f'apps:{status}:{prev_offset}:{encoded_filter}'))
    if len(items) == limit:
        next_offset = offset + limit
        encoded_filter = _encode_filter(filter_type, filter_value)
        buttons.append(InlineKeyboardButton('Вперёд »', callback_data=f'apps:{status}:{next_offset}:{encoded_filter}'))
    reply_markup = InlineKeyboardMarkup([buttons]) if buttons else None
    text = "\n".join(lines)
    if via_callback and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.effective_chat.send_message(text, reply_markup=reply_markup)


async def applications_pagination_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data = q.data or ''
    try:
        _, status, offset_str, filter_encoded = data.split(':', 3)
    except Exception:
        return
    try:
        offset = int(offset_str)
    except Exception:
        offset = 0
    filter_type, filter_value = _decode_filter(filter_encoded)
    await send_applications_list(update, context, status=status, offset=offset, filter_type=filter_type, filter_value=filter_value, via_callback=True)


async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отобразить расширенную сводку аналитики для выбранного периода и зоны.

    Использование: /summary [days] [zone_id]

    - days: количество дней (1..365), по умолчанию 7;
    - zone_id: идентификатор зоны (целое число), опционально.

    Выводит основные метрики и распределения.
    """
    try:
        days: int = 7
        zone_id: Optional[int] = None
        if context.args:
            try:
                days_val = int(context.args[0])
                days = max(1, min(days_val, 365))
            except Exception:
                days = 7
            if len(context.args) >= 2:
                try:
                    zone_id = int(context.args[1])
                except Exception:
                    zone_id = None
        params: Dict[str, Any] = {'days': days}
        if zone_id is not None:
            params['zone_id'] = zone_id
        data = await admin_GET(update, "/analytics/summary", params=params)
        if not isinstance(data, dict):
            await update.effective_chat.send_message("Не удалось получить сводку.")
            return
        lines: List[str] = []
        zone_note = f", зона ID {zone_id}" if zone_id is not None else ""
        lines.append(f"Сводка за последние {days} дней{zone_note}:")
        lines.append(f"Всего адресов: {data.get('total', 0)}")
        lines.append(f"Заявок в ожидании: {data.get('pending', 0)}")
        lines.append(f"Одобрено: {data.get('approved', 0)}")
        lines.append(f"Отклонено: {data.get('rejected', 0)}")
        added = data.get('added_last_n') if 'added_last_n' in data else data.get('added_last_7d')
        if added is not None:
            lines.append(f"Добавлено адресов: {added}")
        by_cat = data.get('by_category') or {}
        if by_cat:
            lines.append("По категориям:")
            for k, v in by_cat.items():
                lines.append(f"  • {k}: {v}")
        by_status = data.get('by_status') or {}
        if by_status:
            lines.append("По доступу:")
            for k, v in by_status.items():
                lines.append(f"  • {k}: {v}")
        by_zone = data.get('by_zone') or {}
        if zone_id is None and by_zone:
            lines.append("По зонам:")
            for k, v in by_zone.items():
                lines.append(f"  • Зона {k}: {v}")
        await update.effective_chat.send_message("\n".join(lines))
    except Exception as e:
        await update.effective_chat.send_message(f"Ошибка: {e}")


# ---------------------------------------------------------------------------
# Voice-to-Action (AI Dispatcher)
# ---------------------------------------------------------------------------
async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик входящих голосовых сообщений."""
    if not update.message or not update.message.voice:
        return

    # Показываем статус "Печатает...", пока ИИ думает
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        # Скачиваем голосовое сообщение в память
        file = await context.bot.get_file(update.message.voice.file_id)
        audio_bytes = await file.download_as_bytearray()

        # Вызываем ИИ-сервис в отдельном потоке, чтобы не блокировать бота
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, process_voice_message, bytes(audio_bytes))

        if "error" in result:
            await update.message.reply_text(f"Не удалось распознать аудио: {result['error']}")
            return

        # Сохраняем данные во временное хранилище пользователя
        context.user_data['voice_req'] = result

        # Клавиатура подтверждения
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да, создать заявку", callback_data="voice_confirm")],
            [InlineKeyboardButton("❌ Отмена", callback_data="voice_cancel")]
        ])

        summary = (
            f"🤖 **ИИ-Диспетчер распознал заявку:**\n\n"
            f"**Категория:** {result.get('category', 'Другое')}\n"
            f"**Адрес:** {result.get('address', 'Не указан')}\n"
            f"**Описание:** {result.get('description', '')}\n\n"
            f"Создать заявку на карте?"
        )
        await update.message.reply_text(summary, reply_markup=kb, parse_mode="Markdown")

    except Exception as e:
        log.exception("Voice handling error")
        await update.message.reply_text("Произошла ошибка при обработке голосового сообщения.")


async def voice_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатия кнопки 'Да, создать заявку'."""
    q = update.callback_query
    await q.answer()

    req = context.user_data.get('voice_req')
    if not req:
        await q.edit_message_text("Данные заявки устарели или утеряны. Отправьте аудио заново.")
        return

    address = req.get("address", "")
    notes = req.get("description", "")
    category = req.get("category", "Другое")

    await q.edit_message_text("⏳ Определяю координаты и создаю заявку...")

    # Пытаемся получить координаты по адресу из голосового
    lat, lon = None, None
    if address and address.lower() != "не указан" and address.lower() != "null":
        coords = await geocode_address(address)
        if coords:
            lat, lon = coords

    if lat is None or lon is None:
        await q.edit_message_text(
            f"❌ ИИ извлек адрес «{address}», но я не смог найти его координаты на карте.\n"
            "Пожалуйста, добавьте заявку вручную через кнопку «➕ Добавить точку»."
        )
        context.user_data.pop('voice_req', None)
        return

    # Отправляем заявку в API (используем существующую функцию)
    ok, err = await add_marker_via_api(
        address=address,
        notes=notes,
        lat=lat,
        lon=lon,
        status="Локальный доступ",  # По умолчанию ставим локальный, модератор поправит
        category=category,
        reporter_surname="ИИ Диспетчер (Голос)",
        tg_user_id=str(update.effective_user.id) if update.effective_user else None,
        tg_message_id=str(q.message.message_id) if q.message else None,
    )

    if ok:
        await q.edit_message_text(f"✅ Голосовая заявка успешно добавлена на карту!\nАдрес: {address}")
    else:
        await q.edit_message_text(f"❌ Ошибка добавления заявки: {err}")

    context.user_data.pop('voice_req', None)


async def voice_cancel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатия кнопки 'Отмена' для голосовой заявки."""
    q = update.callback_query
    await q.answer()
    context.user_data.pop('voice_req', None)
    await q.edit_message_text("Голосовая заявка отменена.")application.add_handler

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    conv_user = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_ADD)}$"), add_start_from_button),
            CommandHandler("add", add_start),
        ],
        states={
            PLACE: [MessageHandler(filters.TEXT & (~filters.COMMAND), place_text)],
            DESCRIPTION: [MessageHandler(filters.TEXT & (~filters.COMMAND), get_description)],
            ACCESS: [
                CallbackQueryHandler(access_button, pattern=r"^access:(local|remote)$"),
                MessageHandler(filters.TEXT & (~filters.COMMAND), access_text),
            ],
            PHOTO: [
                # Accept photo attachments or skip via text.  filters.PHOTO covers incoming images.
                MessageHandler((filters.PHOTO | (filters.TEXT & (~filters.COMMAND))), get_photo),
            ],
            SURNAME: [MessageHandler(filters.TEXT & (~filters.COMMAND), get_surname)],
        },
        fallbacks=[CommandHandler("cancel", cancel_cmd)],
        allow_reentry=True,
    )

    conv_admin = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_ADMIN_LOGIN)}$"), admin_entry),
            MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_ADMIN_MENU)}$"), admin_menu),
        ],
        states={
            ADMIN_LOGIN_USER: [MessageHandler(filters.TEXT & (~filters.COMMAND), admin_login_user)],
            ADMIN_LOGIN_PASS: [MessageHandler(filters.TEXT & (~filters.COMMAND), admin_login_pass)],
            ADMIN_MENU: [
                MessageHandler(filters.TEXT & (~filters.COMMAND), admin_menu_router),
                CallbackQueryHandler(admin_addresses_next_page_cb, pattern=r"^addr:page:\d+$"),
            ],
            ADMIN_WAIT_APP_ID_VIEW: [MessageHandler(filters.TEXT & (~filters.COMMAND), admin_view_app_by_id)],
        },
        fallbacks=[CommandHandler("cancel", cancel_cmd)],
        allow_reentry=True,
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("service", service_enter))
    application.add_handler(CommandHandler("ping", cmd_ping))
    application.add_handler(conv_user)
    application.add_handler(conv_admin)

    # === ДОБАВИТЬ ЭТО ===
    # Обработчик голосовых сообщений
    application.add_handler(MessageHandler(filters.VOICE, handle_voice_message))
    # Обработчики кнопок для голосовой заявки
    application.add_handler(CallbackQueryHandler(voice_confirm_cb, pattern=r"^voice_confirm$"))
    application.add_handler(CallbackQueryHandler(voice_cancel_cb, pattern=r"^voice_cancel$"))
    # ====================

    # "Служба" (по заявке) + возврат в меню
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_SERVICE)}$"), service_enter))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_SERVICE_REQUEST)}$"), service_request_btn))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_SERVICE_STATUS)}$"), service_status_btn))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_HOME)}$"), home_btn))

    # Обработчики меню пользователя
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r"^💬 Моя переписка(?: \(\d+\))?$"), btn_chat_handler))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_NOTIFY_PREFIX)}"), toggle_notify_handler))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_MY_REQS)}$"), cmd_my_requests))
    application.add_handler(CommandHandler("connect", cmd_connect))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_CONNECT)}$"), cmd_connect))
    application.add_handler(CommandHandler("unit", cmd_unit))
    application.add_handler(CommandHandler("sos", cmd_sos))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_SHIFT_START)}$"), cmd_shift_start))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_SHIFT_END)}$"), cmd_shift_end))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_CHECKIN)}$"), cmd_checkin))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_SOS)}$"), cmd_sos))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_LIVE_HELP)}$"), cmd_live_help))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_DUTY_BACK)}$"), cmd_duty_back))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_LIVE_STOP)}$"), cmd_live_stop))
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_BREAK_REQ)}$"), cmd_break_request))
    application.add_handler(CallbackQueryHandler(on_break_cb, pattern=r"^duty_break:\d+$"))
    application.add_handler(MessageHandler(filters.LOCATION, handle_duty_location))
    application.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE & filters.LOCATION, handle_duty_location))

    # Inline-кнопки из уведомлений (открыть переписку / выключить уведомления)
    application.add_handler(CallbackQueryHandler(cb_chat_open, pattern=r"^chat:open$"))
    application.add_handler(CallbackQueryHandler(cb_chat_notify_off, pattern=r"^chat:notify_off$"))

    # Conversation for sending a message to admin via button
    conv_chat = ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_MSG_HOME)}$"), ask_admin_msg),
            CallbackQueryHandler(cb_chat_reply_entry, pattern=r"^chat:reply$"),
        ],
        states={
            CHAT_INPUT: [
                MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_CHAT_EXIT)}$"), exit_chat_mode),
                MessageHandler(filters.TEXT & filters.Regex(r"^💬 Моя переписка(?: \(\d+\))?$"), chat_show_history_in_mode),
                MessageHandler(filters.TEXT & (~filters.COMMAND), send_admin_msg),
            ],
        },
        fallbacks=[
            MessageHandler(filters.TEXT & filters.Regex(f"^{re.escape(BTN_CHAT_EXIT)}$"), exit_chat_mode),
            CommandHandler("cancel", cancel_cmd),
        ],
        allow_reentry=True,
    )
    application.add_handler(conv_chat)

    # Другие команды
    application.add_handler(CommandHandler("stats", cmd_stats))
    application.add_handler(CommandHandler("pending", cmd_pending))
    application.add_handler(CommandHandler("approved", cmd_approved))
    application.add_handler(CommandHandler("rejected", cmd_rejected))
    application.add_handler(CommandHandler("app", cmd_app))

    # Команды для обмена сообщениями с администратором (на случай если пользователь предпочитает команды)
    application.add_handler(CommandHandler("chat", cmd_chat))
    application.add_handler(CommandHandler("history", cmd_history))
    application.add_handler(CommandHandler("msg", cmd_msg))
    application.add_handler(CommandHandler("my", cmd_my_requests))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("faq", cmd_help))

    application.add_error_handler(error_handler)

    log.info("Bot is up. MAP_API_URL=%s", MAP_API_URL)

    # Уведомления запускаются в post_init() (с fallback без JobQueue)
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
