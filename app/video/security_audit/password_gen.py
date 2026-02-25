# -*- coding: utf-8 -*-
"""Генератор возможных паролей на основе статистики."""

from typing import Iterator, List, Optional


class CredentialGenerator:
    """Генерирует возможные учётные данные для аудита."""

    def __init__(self, vendor: Optional[str] = None):
        self.vendor = vendor
        self.common = self._load_common()

    def _load_common(self) -> List[str]:
        """Возвращает список наиболее распространённых паролей."""
        return [
            'admin', '12345', 'password', '123456', '12345678', '1234',
            'root', 'user', 'service', 'hik12345', 'hikvision', 'dahua',
            'admin123', 'Admin@123', '123456789', '1111', 'abc123',
            'camera', 'ipcam', 'default', 'system', 'manager', 'support'
        ]

    def generate(self, limit: int = 1000) -> Iterator[str]:
        """Генерирует поток паролей (сначала основные, затем мутации)."""
        # Сначала базовые
        for pwd in self.common:
            yield pwd

        # Мутации (добавление года, заглавных букв)
        years = [str(y) for y in range(2020, 2026)]
        for p in self.common[:30]:
            for y in years:
                yield p + y
            yield p.capitalize()
            yield p.upper()

        # Если известен вендор, добавляем комбинации с ним
        if self.vendor:
            yield self.vendor.lower() + '123'
            yield self.vendor.lower() + '@2025'