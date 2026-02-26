from typing import Iterator, Optional

class PasswordGenerator:
    COMMON = [
        'admin', '12345', 'password', '123456', '12345678', '1234',
        'root', 'user', 'service', 'hik12345', 'hikvision', 'dahua',
        'admin123', 'Admin@123', '123456789', '1111', 'abc123',
        'camera', 'ipcam', 'default', 'system', 'manager', 'support'
    ]

    def __init__(self, vendor: Optional[str] = None):
        self.vendor = vendor.lower() if vendor else None

    def generate(self, limit: int = 10000) -> Iterator[str]:
        # Базовые
        for pwd in self.COMMON:
            yield pwd

        # Мутации: год
        years = [str(y) for y in range(2020, 2026)]
        for p in self.COMMON[:30]:
            for y in years:
                yield p + y
                yield p + '@' + y
            yield p.capitalize()
            yield p.upper()
        # По вендору
        if self.vendor:
            yield self.vendor + '123'
            yield self.vendor + '@2025'
            yield self.vendor + 'admin'
