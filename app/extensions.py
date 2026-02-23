"""
Инициализация расширений Flask.

В этом модуле размещаются объекты, которые будут использованы
приложением: например SQLAlchemy. Отделение расширений в
отдельный файл помогает избежать циклических импортов и
облегчает тестирование.
"""

from __future__ import annotations

from celery import Celery
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Инициализируем объект SQLAlchemy без привязки к конкретному приложению.
# Приложение привязывается в create_app() (см. app/__init__.py).
db = SQLAlchemy()

# Celery-приложение инициализируется через init_celery(app).
celery_app = Celery(__name__)


def init_celery(app: Flask) -> Celery:
    """Привязать Celery к конфигу Flask-приложения."""
    celery_app.conf.update(
        broker_url=app.config["CELERY_BROKER_URL"],
        result_backend=app.config["CELERY_RESULT_BACKEND"],
        task_ignore_result=True,
        broker_connection_retry_on_startup=True,
    )

    class FlaskTask(celery_app.Task):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return super().__call__(*args, **kwargs)

    celery_app.Task = FlaskTask
    return celery_app
