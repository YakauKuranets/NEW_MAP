"""Celery worker entrypoint.

Запуск:
    celery -A celery_worker.celery worker --loglevel=info
"""

import asyncio
import logging

from app import create_app
from app.extensions import celery_app

# Импорты для асинхронного аудита
from app.video.security_audit.async_auditor import (
    AsyncSecurityAuditor,
    AsyncProxyPool,
    PasswordGenerator,
    TargetDevice
)
from app.video.security_audit.discovery_adapter import detect_camera_comprehensive
from app.video.security_audit.vuln_check import VulnerabilityScanner
from app.video.models import CameraAuditResult
from app.extensions import db

flask_app = create_app()
flask_app.app_context().push()

celery = celery_app

celery.autodiscover_tasks(["app"])


@celery.task
def run_audit_task(task_id, ip, port=None, username='admin', password=None, proxy_list=None, use_vuln_check=True):
    """
    Фоновая задача для аудита камеры.
    Если порт не указан, сначала выполняется комплексное обнаружение.
    """
    from app import create_app  # повторно импортируем для контекста (на всякий случай)
    app = create_app()
    with app.app_context():
        result = CameraAuditResult.query.filter(
            CameraAuditResult.details['task_id'].astext == task_id
        ).first()
        if not result:
            return

        # === 1. Обнаружение камеры, если порт не указан ===
        if port is None:
            try:
                detected = asyncio.run(detect_camera_comprehensive(ip, login=username, password=password))
            except Exception as e:
                result.success = False
                result.details = {"error": f"Discovery failed: {str(e)}", "status": "failed"}
                db.session.commit()
                return

            if not detected:
                result.success = False
                result.details = {"error": "Camera not found on any common port", "status": "failed"}
                db.session.commit()
                return

            ip = detected.ip
            port = detected.port
            target_vendor = detected.vendor
            auth_type = detected.auth_type or 'basic'
        else:
            target_vendor = None
            auth_type = 'basic'

        target = TargetDevice(ip=ip, port=port, vendor=target_vendor)

        # === 2. Проверка уязвимостей ===
        if use_vuln_check:
            vuln = VulnerabilityScanner(target)
            vuln_result = vuln.scan()
            if vuln_result:
                result.success = True
                result.method = vuln_result['method']
                result.password_found = vuln_result.get('password', '')
                result.details = {"vuln_data": vuln_result, "status": "completed"}
                db.session.commit()
                return

        # === 3. Асинхронный брутфорс ===
        proxy_pool = AsyncProxyPool(initial_proxies=proxy_list or [])
        gen = PasswordGenerator(vendor=target_vendor)
        auditor = AsyncSecurityAuditor(
            target=target,
            proxy_pool=proxy_pool,
            password_gen=gen,
            username=username,
            auth_type=auth_type,
            concurrency=50
        )
        try:
            found = asyncio.run(auditor.run())
        except Exception as e:
            result.success = False
            result.details = {"error": f"Bruteforce failed: {str(e)}", "status": "failed"}
            db.session.commit()
            return

        result.success = bool(found)
        result.password_found = found
        result.method = 'bruteforce' if found else 'none'
        result.details = {"status": "completed"}
        db.session.commit()
