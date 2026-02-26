import os
from datetime import datetime

import shodan
from celery import shared_task

from app.extensions import db
from app.video.models import GlobalCamera


SHODAN_API_KEY = os.environ.get('SHODAN_API_KEY', 'your_key_here')


@shared_task
def scan_shodan_for_cameras(query='product:"Hikvision" OR product:"Dahua"', limit=100):
    """
    Периодическая задача для сбора информации о камерах через Shodan.
    Результаты сохраняются в БД для последующего анализа.
    """
    if not SHODAN_API_KEY or SHODAN_API_KEY == 'your_key_here':
        return 'Ошибка Shodan: SHODAN_API_KEY не задан'

    api = shodan.Shodan(SHODAN_API_KEY)
    try:
        results = api.search(query, limit=limit)
        matches = results.get('matches', [])
        for match in matches:
            ip_value = match.get('ip_str')
            if not ip_value:
                continue

            existing = GlobalCamera.query.filter_by(ip=ip_value).first()
            data = {
                'ip': ip_value,
                'port': match.get('port', 80),
                'vendor': match.get('product'),
                'model': match.get('info'),
                'country': (match.get('location') or {}).get('country_name'),
                'city': (match.get('location') or {}).get('city'),
                'org': match.get('org'),
                'hostnames': match.get('hostnames', []),
                'vulnerabilities': match.get('vulns', []),
            }

            if existing:
                for key, value in data.items():
                    setattr(existing, key, value)
                existing.last_seen = datetime.utcnow()
            else:
                new_cam = GlobalCamera(**data, first_seen=datetime.utcnow())
                db.session.add(new_cam)

        db.session.commit()
        return f"Найдено {results.get('total', 0)} устройств, сохранено {len(matches)}"
    except Exception as e:
        db.session.rollback()
        return f"Ошибка Shodan: {e}"
