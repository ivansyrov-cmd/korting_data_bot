# -*- coding: utf-8 -*-
"""Telegram-бот и консольная справка по характеристикам."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from korting_bot.query import answer_query, load_index
from korting_bot.synonyms import load_synonyms

START_TEXT = (
    "Справка по характеристикам Korting.\n\n"
    "Напишите модель и свойство, например:\n"
    "длина шнура OKB 792\n"
    "шнур OKB 792\n"
    "глубина KMI 720"
)

TOKEN_ENV_NAMES = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_TOKEN", "BOT_TOKEN", "TG_TOKEN")


def _token() -> str:
    for name in TOKEN_ENV_NAMES:
        val = (os.environ.get(name) or "").strip()
        if val:
            return val
    return ""


def _run_cli(argv: list[str]) -> int:
    if args := argv:
        print(answer_query(" ".join(args)))
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
        print(answer_query(line))
        print()
    return 0


def _run_telegram(token: str) -> int:
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

    async def post_init(application: Application) -> None:
        load_synonyms()
        load_index()

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message:
            await update.message.reply_text(START_TEXT)

    async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        text = (update.message.text or "").strip()
        if not text:
            return
        await update.message.reply_text(answer_query(text))

    app = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    token = _token()
    if token:
        return _run_telegram(token)
    return _run_cli(args)


if __name__ == "__main__":
    sys.exit(main())
