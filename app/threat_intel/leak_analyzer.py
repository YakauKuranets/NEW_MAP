# -*- coding: utf-8 -*-
"""
Модуль автоматического анализа утечек данных.
Выполняет классификацию, извлечение учётных данных и оценку критичности.
"""

import hashlib
import logging
from collections import Counter
from datetime import datetime
from typing import Dict, List

from app.darknet.models import DarknetPost, LeakedCredential
from app.extensions import db
from app.threat_intel.classifier import LeakClassifier
from app.threat_intel.secret_extractor import SecretExtractor
from app.threat_intel.target_matcher import TargetMatcher

logger = logging.getLogger(__name__)


class LeakAnalyzer:
    """Комплексный анализатор утечек данных."""

    def __init__(self):
        self.secret_extractor = SecretExtractor()
        self.classifier = LeakClassifier()
        self.target_matcher = TargetMatcher()

    def analyze_post(self, post: DarknetPost) -> Dict:
        logger.info("Analyzing post %s from %s", post.id, post.url)

        result = {
            'post_id': post.id,
            'url': post.url,
            'title': post.title,
            'content_preview': post.content[:500] if post.content else '',
            'secrets': [],
            'classification': None,
            'target_matches': [],
            'risk_score': 0,
            'priority': 'LOW',
        }

        if post.content:
            secrets = self.secret_extractor.extract_all(post.content)
            result['secrets'] = secrets

            emails = []
            for secret in secrets:
                if secret.get('email'):
                    emails.append(secret['email'])
                if secret.get('type') in {'password', 'credential'}:
                    raw_password = secret.get('password') or secret.get('value') or ''
                    password_hash = hashlib.sha256(raw_password.encode('utf-8')).hexdigest() if raw_password else None
                    cred = LeakedCredential(
                        post_id=post.id,
                        email=secret.get('email'),
                        username=secret.get('username'),
                        password_hash=password_hash,
                        domain=secret.get('domain'),
                        discovered_at=datetime.utcnow(),
                    )
                    db.session.add(cred)
            if emails:
                post.indicators = {'emails': sorted(set(emails))}

        if post.content:
            classification = self.classifier.classify(post.content, post.title)
            result['classification'] = classification
            result['risk_score'] = classification.get('risk_score', 0)

            if result['risk_score'] >= 70:
                result['priority'] = 'CRITICAL'
            elif result['risk_score'] >= 40:
                result['priority'] = 'HIGH'
            elif result['risk_score'] >= 20:
                result['priority'] = 'MEDIUM'
            else:
                result['priority'] = 'LOW'

        if post.content and post.indicators:
            matches = self.target_matcher.find_matches(post)
            result['target_matches'] = matches

        post.risk_score = int(result['risk_score'])
        post.analysis_result = result
        post.analyzed = True

        db.session.commit()
        return result

    def analyze_batch(self, posts: List[DarknetPost]) -> List[Dict]:
        results = []
        for post in posts:
            try:
                results.append(self.analyze_post(post))
            except Exception as exc:
                logger.error("Failed to analyze post %s: %s", post.id, exc)
                db.session.rollback()
        return results

    def get_statistics(self, hours: int = 24) -> Dict:
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(hours=hours)

        credentials = LeakedCredential.query.filter(LeakedCredential.discovered_at >= cutoff).all()
        domains = Counter([c.domain for c in credentials if c.domain])
        emails = [c.email for c in credentials if c.email]

        return {
            'period_hours': hours,
            'total_credentials': len(credentials),
            'unique_domains': len(domains),
            'top_domains': domains.most_common(10),
            'sample_emails': emails[:20],
        }
