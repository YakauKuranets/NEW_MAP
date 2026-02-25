# -*- coding: utf-8 -*-
"""Менеджер пула прокси для распределения нагрузки."""

import threading
import time
import requests
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class ProxyNode:
    """Прокси-узел с метриками качества."""
    url: str
    failures: int = 0
    avg_response_time: float = 0.0
    last_used: float = 0.0


class ProxyPool:
    """Управление пулом прокси для обхода ограничений."""

    def __init__(self, initial_proxies: List[str] = None, max_failures: int = 3):
        self.proxies: List[ProxyNode] = []
        self.max_failures = max_failures
        self.lock = threading.Lock()
        if initial_proxies:
            self.add_proxies(initial_proxies)

    def add_proxies(self, proxy_urls: List[str]):
        """Добавляет новые прокси в пул."""
        with self.lock:
            for url in proxy_urls:
                if not any(p.url == url for p in self.proxies):
                    self.proxies.append(ProxyNode(url=url))

    def validate_proxy(self, proxy: ProxyNode) -> bool:
        """Проверяет работоспособность прокси и измеряет время ответа."""
        try:
            start = time.time()
            r = requests.get('http://httpbin.org/ip',
                             proxies={'http': proxy.url, 'https': proxy.url},
                             timeout=5)
            if r.status_code == 200:
                proxy.avg_response_time = time.time() - start
                return True
        except:
            pass
        return False

    def refresh_pool(self):
        """Перепроверяет все прокси и удаляет нерабочие."""
        with self.lock:
            alive = []
            for p in self.proxies:
                if self.validate_proxy(p):
                    p.failures = 0
                    alive.append(p)
                else:
                    p.failures += 1
                    if p.failures <= self.max_failures:
                        alive.append(p)
            self.proxies = alive

    def get_best_proxy(self) -> Optional[ProxyNode]:
        """Возвращает лучший прокси (с наименьшим числом ошибок и наименьшим временем ответа)."""
        with self.lock:
            available = [p for p in self.proxies if p.failures <= self.max_failures]
            if not available:
                return None
            available.sort(key=lambda p: (p.failures, p.avg_response_time))
            return available[0]

    def report_failure(self, proxy: ProxyNode):
        """Сообщает о неудаче при использовании прокси."""
        with self.lock:
            proxy.failures += 1