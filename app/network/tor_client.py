# -*- coding: utf-8 -*-
"""Tor proxy client for anonymous OSINT network egress.

Модуль обеспечивает маршрутизацию HTTP/HTTPS запросов через Tor SOCKS5 proxy.
Поддерживает обновление identity (NEWNYM) через Tor ControlPort.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class TorProxyClient:
    """HTTP-клиент с маршрутизацией через Tor (SOCKS5).

    Args:
        tor_host: хост Tor SOCKS proxy (обычно 127.0.0.1)
        tor_port: порт Tor SOCKS proxy (обычно 9050)
        control_port: порт Tor ControlPort (обычно 9051)
        password: пароль для аутентификации на ControlPort
        timeout_sec: таймаут запроса по умолчанию
    """

    def __init__(
        self,
        tor_host: str = "127.0.0.1",
        tor_port: int = 9050,
        control_port: int = 9051,
        password: Optional[str] = None,
        timeout_sec: float = 10.0,
    ) -> None:
        self.tor_host = tor_host
        self.tor_port = int(tor_port)
        self.control_port = int(control_port)
        self.password = password
        self.timeout_sec = float(timeout_sec)
        self.session: requests.Session = requests.Session()
        self._init_session()

    def _init_session(self) -> None:
        """Configure requests session with Tor SOCKS5 proxy and retries."""
        retries = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]),
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.proxies = {
            "http": f"socks5h://{self.tor_host}:{self.tor_port}",
            "https": f"socks5h://{self.tor_host}:{self.tor_port}",
        }

    def renew_identity(self, wait_sec: float = 5.0) -> bool:
        """Request new Tor circuit (NEWNYM) via ControlPort."""
        try:
            from stem import Signal
            from stem.control import Controller

            with Controller.from_port(address=self.tor_host, port=self.control_port) as controller:
                if self.password:
                    controller.authenticate(password=self.password)
                else:
                    controller.authenticate()
                controller.signal(Signal.NEWNYM)
            time.sleep(max(0.0, float(wait_sec)))
            logger.info("Tor identity renewed")
            return True
        except Exception as exc:
            logger.error("Failed to renew Tor identity: %s", exc)
            return False

    def get_current_ip(self) -> Optional[str]:
        """Return current egress IP as seen through Tor."""
        try:
            response = self.session.get("https://httpbin.org/ip", timeout=self.timeout_sec)
            response.raise_for_status()
            payload = response.json() if response.content else {}
            origin = payload.get("origin")
            return str(origin) if origin else None
        except Exception as exc:
            logger.error("Failed to get current Tor IP: %s", exc)
            return None

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        """Perform HTTP request through Tor proxy."""
        kwargs.setdefault("timeout", self.timeout_sec)
        return self.session.request(method=method, url=url, **kwargs)

    def close(self) -> None:
        """Close underlying requests session."""
        try:
            self.session.close()
        except Exception:
            pass
