"""Celery worker entrypoint.

Запуск:
    celery -A celery_worker.celery worker --loglevel=info
"""

from app import create_app
from app.extensions import celery_app

flask_app = create_app()
flask_app.app_context().push()

celery = celery_app

celery.autodiscover_tasks(["app"])
