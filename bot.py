# -*- coding: utf-8 -*-
"""Telegram-бот и консольная справка по характеристикам."""
from __future__ import annotations

import html
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from korting_bot.query import answer_query, load_index
from korting_bot.synonyms import load_synonyms

APP_VERSION = "2026-09-09-help-v10"
START_TEXT = (
    "Привет! Я — гид по характеристикам продуктов KORTING. "
    "Я могу подсказать одну или несколько технических характеристик, "
    "дать прямую ссылку на сайт или выгрузить списком все характеристики продукта. "
    "Я работаю очень просто:\n\n"
    "1. Узнать конкретную характеристику продукта, пишите "
    "«шнур OKB 792 PFX», «компрессор KNFF 80307 SI X» или вариации: "
    "«длина шнура OKB 792 PFX», «тип компрессора KNFF 80307 SI X». "
    "Можно не добавлять конкретный цвет модели — тогда я выгружу значения для нескольких моделей.\n\n"
    "2. Узнать полный список ТТХ модели, указанные в карточке на сайте, "
    "пишите «ттх и модель». Без указания цвета - я выгружу несколько таких списков.\n\n"
    "3. ЧТобы получить ссылку на сайт. Напишите «ссылка и модель». "
    "Модель без цвета - несколько ссылок\n\n"
    "Я удобен тем, что могу выгрузить характеристику даже без точного указания её наименования. "
    "Так «шнур» может быть «кабель», а «ссылка» может быть «сайт».\n"
    "Давайте пробовать?\n\n"
    "Команды для меня:\n"
    "1. Характеристика и модель\n"
    "2. ТТХ и модель\n"
    "3. Ссылка и модель"
)

TOKEN_ENV_NAMES = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN", "BOT_TOKEN", "TG_TOKEN")


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
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

    async def post_init(application: Application) -> None:
        print(f"korting bot {APP_VERSION}", flush=True)
        load_synonyms()
        load_index()
        print("catalog ready", flush=True)

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message:
            await update.message.reply_text(START_TEXT)

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

    async def on_ttx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        model = " ".join(context.args or []).strip()
        await _reply(update, answer_query("ТТХ " + model if model else "ТТХ"))

    async def on_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        model = " ".join(context.args or []).strip()
        await _reply(update, answer_query("ссылка " + model if model else "ссылка"))

    async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        text = (update.message.text or "").strip()
        if not text:
            return
        if not _addressed_to_bot(update, context, text):
            return
        query = _strip_bot_mention(text, context.bot.username)
        if not query:
            await _reply(update, START_TEXT)
            return
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
