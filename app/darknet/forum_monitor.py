# -*- coding: utf-8 -*-
"""Мониторинг постов darknet-форумов и интеграция с SIEM."""

from app.siem.exporter import SIEMExporter
from app.siem.models import EventSeverity


def emit_new_post_event(post: dict) -> None:
    """Создаёт SIEM-событие при обнаружении нового поста с индикаторами."""
    # При обнаружении нового поста с индикаторами
    if post.get('indicators'):
        exporter = SIEMExporter()
        exporter.create_event(
            source='darknet_monitor',
            category='threat_intel',
            title=f"New darknet post: {post.get('title', 'Unknown')}",
            description=f"Post from {post.get('actor', 'unknown')} on darknet forum",
            severity=EventSeverity.INFO.value,
            indicators=post.get('indicators')
        )
