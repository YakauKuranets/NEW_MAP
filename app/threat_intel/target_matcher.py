# -*- coding: utf-8 -*-
"""
Модуль сопоставления найденных утечек с целевыми объектами мониторинга.
"""

from __future__ import annotations

from typing import Dict, List

from app.darknet.models import DarknetPost


class TargetMatcher:
    """Сопоставляет утечки с целевыми email-адресами, доменами и ключевыми словами."""

    def __init__(self):
        self.target_emails: list[str] = []
        self.target_domains: list[str] = []
        self.target_keywords: list[str] = []
        self._load_targets()

    def _load_targets(self):
        self.target_emails = [
            'admin@example.com',
            'security@company.com',
        ]
        self.target_domains = [
            'example.com',
            'company.org',
        ]
        self.target_keywords = [
            'secret project',
            'confidential document',
        ]

    def find_matches(self, post: DarknetPost) -> List[Dict]:
        matches: list[dict] = []
        content = post.content or ''
        indicators = post.indicators or {}

        for email in self.target_emails:
            if email in content:
                matches.append({'type': 'email_match', 'value': email, 'context': self._extract_context(content, email)})

        for domain in self.target_domains:
            if domain in content:
                matches.append({'type': 'domain_match', 'value': domain, 'context': self._extract_context(content, domain)})

        for keyword in self.target_keywords:
            if keyword.lower() in content.lower():
                matches.append({'type': 'keyword_match', 'value': keyword, 'context': self._extract_context(content, keyword)})

        if indicators and 'emails' in indicators:
            for indicator_email in indicators['emails']:
                if indicator_email in self.target_emails:
                    matches.append({'type': 'indicator_email_match', 'value': indicator_email, 'context': 'extracted from post'})

        return matches

    def _extract_context(self, text: str, target: str, window: int = 100) -> str:
        pos = text.find(target)
        if pos == -1:
            return ""
        start = max(0, pos - window)
        end = min(len(text), pos + len(target) + window)
        return text[start:end]
