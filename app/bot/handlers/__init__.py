"""Handlers registry for aiogram 3 bot."""

from aiogram import Dispatcher

from .common import router as common_router


def register_handlers(dp: Dispatcher) -> None:
    """Register all bot routers."""
    dp.include_router(common_router)
