"""Common bot handlers (aiogram 3)."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from ..keyboards.main import main_menu_keyboard, quick_actions_inline

router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Entry command with Mini App + inline quick actions."""
    await message.answer(
        "🚀 Бот переведен на aiogram 3.\n"
        "Используйте меню ниже для запуска Mini App и быстрых действий.",
        reply_markup=main_menu_keyboard(),
    )
    await message.answer("Быстрые действия:", reply_markup=quick_actions_inline())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Команды:\n"
        "/start — старт\n"
        "/help — помощь\n\n"
        "Inline-кнопки используются для мгновенной связи со штабом."
    )
