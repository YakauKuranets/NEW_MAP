from __future__ import annotations

from typing import Any


class ProfinetAnalyzer:
    """Заглушка анализатора Profinet для будущего расширения."""

    def analyze(self, target: str) -> dict[str, Any]:
        return {
            "target": target,
            "supported": False,
            "note": "Анализатор Profinet пока в режиме заглушки.",
        }
