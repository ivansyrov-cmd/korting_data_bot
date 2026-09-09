# -*- coding: utf-8 -*-
"""Telegram-бот и консольная справка по характеристикам."""
from __future__ import annotations

import html
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from korting_bot.query import answer_query, load_index
from korting_bot.synonyms import load_synonyms

APP_VERSION = "2026-09-09-menu-v12"
START_TEXT = (
    "Привет! Я — гид по характеристикам продуктов KORTING. "
    "Я могу подсказать одну или несколько технических характеристик, "
    "дать прямую ссылку на сайт или выгрузить списком все характеристики продукта. "
    "Я работаю очень просто:\n\n"
    "1. <b>Узнать конкретную характеристику продукта</b>: "
    "«шнур OKB 792 PFX», «компрессор KNFF 80307 SI X». "
    "Текст можно вписать максимально близкий к характеристике: "
    "«длина шнура OKB 792 PFX», «тип компрессора KNFF 80307 SI X». "
    "Если я не могу найти, то попробуй более близкий по смыслу, например "
    "«кабель OKB 792 PFX».\n\n"
    "2. <b>Все характеристики модели одним списком:</b> «ттх и модель».\n\n"
    "3. <b>Получить ссылку на сайт:</b> слово «ссылка», либо «сайт» + «модель».\n\n"
    "Я удобен тем, что могу выгрузить характеристику даже без точного указания её наименования. "
    "Так «шнур» может быть «кабель», а «ссылка» может быть «сайт». "
    "Если не указать точное наименование модели, то я выгружу сразу несколько полей, ссылок, таблиц ттх.\n\n"
    "Итак, поехали!\n"
    "Команды для меня:\n"
    "1. Характеристика и модель\n"
    "2. ТТХ и модель\n"
    "3. Ссылка и модель"
)

TOKEN_ENV_NAMES = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN", "BOT_TOKEN", "TG_TOKEN")
PENDING_TTL_SEC = 10 * 60
MENU_PROMPTS = {
    "spec": "Напишите характеристику и модель, например: шнур OKB 792 PFX",
    "ttx": "Напишите модель, например: OKB 792 CFN",
    "link": "Напишите модель, например: KSI 8259 F",
}

_PENDING: dict[tuple[int, int], tuple[str, float]] = {}


def _token() -> str:
    for name in TOKEN_ENV_NAMES:
        val = (os.environ.get(name) or "").strip()
        if val:
            return val
    return ""


def _reply_chunks(text: str, limit: int = 4000) -> list[str]:
    chunks: list[str] = []
    rest = text or ""
    while rest:
        if len(rest) <= limit:
            chunks.append(rest)
            break
        cut = rest.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        chunks.append(rest[:cut])
        rest = rest[cut:].lstrip("\n")
    return chunks


def _plain(text: str) -> str:
    return html.unescape((text or "").replace("<b>", "").replace("</b>", ""))


def _strip_bot_mention(text: str, username: str | None) -> str:
    t = (text or "").strip()
    if username:
        t = re.sub(rf"@{re.escape(username)}\b", " ", t, flags=re.IGNORECASE)
    else:
        t = re.sub(r"^@\w+\s+", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _is_group(update) -> bool:
    chat = update.effective_chat
    return bool(chat and chat.type in {"group", "supergroup"})


def _addressed_to_bot(update, context, text: str) -> bool:
    if not _is_group(update):
        return True
    username = (context.bot.username or "").lower()
    if username and f"@{username}" in (text or "").lower():
        return True
    msg = update.message
    if not msg:
        return False
    reply = msg.reply_to_message
    if reply and reply.from_user and reply.from_user.id == context.bot.id:
        return True
    for entity in msg.entities or []:
        if entity.type == "text_mention" and entity.user and entity.user.id == context.bot.id:
            return True
    return False


def _pending_key(update) -> tuple[int, int] | None:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return None
    return (chat.id, user.id)


def _set_pending(update, mode: str) -> None:
    key = _pending_key(update)
    if key:
        _PENDING[key] = (mode, time.time())


def _pop_pending(update) -> str | None:
    key = _pending_key(update)
    if not key:
        return None
    item = _PENDING.pop(key, None)
    if not item:
        return None
    mode, started = item
    if time.time() - started > PENDING_TTL_SEC:
        return None
    return mode


def _menu_keyboard():
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Характеристика", callback_data="menu:spec")],
            [InlineKeyboardButton("Список всех ТТХ модели", callback_data="menu:ttx")],
            [InlineKeyboardButton("Ссылка на сайт", callback_data="menu:link")],
        ]
    )


def _apply_menu_mode(mode: str, text: str) -> str:
    low = text.lower().lstrip("/!")
    if mode == "ttx":
        if low.startswith("ттх") or low.startswith("ttx"):
            return text
        return "ТТХ " + text
    if mode == "link":
        if any(low.startswith(w) for w in ("ссылка", "сайт", "линк", "link", "url", "site")):
            return text
        return "ссылка " + text
    return text


def _run_cli(argv: list[str]) -> int:
    if args := argv:
        print(_plain(answer_query(" ".join(args))))
        return 0
    print("Введите запрос (пустая строка — выход).")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            return 0
        print(_plain(answer_query(line)))
        print()
    return 0


def _run_telegram(token: str) -> int:
    from telegram import BotCommand, Update
    from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

    async def post_init(application: Application) -> None:
        print(f"korting bot {APP_VERSION}", flush=True)
        await application.bot.set_my_commands(
            [
                BotCommand("start", "Приветствие и меню"),
                BotCommand("help", "Как пользоваться"),
                BotCommand("ttx", "Список всех ТТХ модели"),
                BotCommand("link", "Ссылка на сайт"),
            ]
        )
        load_synonyms()
        load_index()
        print("catalog ready", flush=True)

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        _pop_pending(update)
        await update.message.reply_text(
            START_TEXT,
            parse_mode="HTML",
            reply_markup=_menu_keyboard(),
        )

    async def _reply(update: Update, text: str) -> None:
        if not update.message:
            return
        for chunk in _reply_chunks(text):
            parse_mode = "HTML" if "<b>" in chunk else None
            many_links = chunk.count("https://") > 1 or chunk.count("http://") > 1
            await update.message.reply_text(
                chunk,
                parse_mode=parse_mode,
                disable_web_page_preview=many_links,
            )

    async def on_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not query.data:
            return
        await query.answer()
        mode = query.data.split(":", 1)[-1]
        prompt = MENU_PROMPTS.get(mode)
        if not prompt:
            return
        _set_pending(update, mode)
        if query.message:
            await query.message.reply_text(prompt)

    async def on_ttx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        model = " ".join(context.args or []).strip()
        if not model:
            _set_pending(update, "ttx")
            await update.message.reply_text(MENU_PROMPTS["ttx"])
            return
        _pop_pending(update)
        await _reply(update, answer_query("ТТХ " + model))

    async def on_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        model = " ".join(context.args or []).strip()
        if not model:
            _set_pending(update, "link")
            await update.message.reply_text(MENU_PROMPTS["link"])
            return
        _pop_pending(update)
        await _reply(update, answer_query("ссылка " + model))

    async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        text = (update.message.text or "").strip()
        if not text:
            return
        mode = _pop_pending(update)
        if not mode and not _addressed_to_bot(update, context, text):
            return
        query = _strip_bot_mention(text, context.bot.username)
        if not query:
            await start(update, context)
            return
        if mode:
            query = _apply_menu_mode(mode, query)
        await _reply(update, answer_query(query))

    app = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("ttx", on_ttx))
    app.add_handler(CommandHandler("link", on_link))
    app.add_handler(CommandHandler("site", on_link))
    app.add_handler(CallbackQueryHandler(on_menu, pattern=r"^menu:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    print(f"korting bot {APP_VERSION}", flush=True)
    token = _token()
    if token:
        return _run_telegram(token)
    return _run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
