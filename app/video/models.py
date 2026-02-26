from app.extensions import db
from datetime import datetime

class CameraAuditResult(db.Model):
    __tablename__ = 'camera_audit_results'
    id = db.Column(db.Integer, primary_key=True)
    target_ip = db.Column(db.String(45), nullable=False, index=True)
    target_port = db.Column(db.Integer, default=80)
    vendor = db.Column(db.String(100))
    model = db.Column(db.String(100))
    username = db.Column(db.String(50))
    password_found = db.Column(db.String(255))
    method = db.Column(db.String(50))  # 'vuln', 'bruteforce', 'none'
    success = db.Column(db.Boolean, default=False)
    details = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
