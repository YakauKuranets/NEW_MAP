from __future__ import annotations

import os
import uuid

from flask import current_app, jsonify, request
from werkzeug.utils import secure_filename

from app.auth.decorators import jwt_or_api_required
from app.extensions import db
from app.video.models import HandshakeAnalysis

from . import bp

ALLOWED_EXTENSIONS = {"cap", "pcap", "hccapx"}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _get_file_size(file_storage) -> int:
    stream = file_storage.stream
    pos = stream.tell()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(pos)
    return int(size)


@bp.post("/upload")
@jwt_or_api_required
def upload_handshake():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "File type not allowed"}), 400

    max_size = int(current_app.config.get("HANDSHAKE_MAX_FILE_SIZE_BYTES", 10 * 1024 * 1024))
    request_size = int(request.content_length or 0)
    if request_size > max_size:
        return jsonify({"error": "File too large", "maxBytes": max_size}), 413

    file_size = _get_file_size(file)
    if file_size > max_size:
        return jsonify({"error": "File too large", "maxBytes": max_size}), 413

    bssid = (request.form.get("bssid") or "").strip()
    essid = (request.form.get("essid") or "").strip()
    security_type = (request.form.get("security_type") or "WPA2").strip()
    client_id = (request.form.get("client_id") or "").strip() or None

    if not bssid or not essid:
        return jsonify({"error": "bssid and essid required"}), 400

    task_id = str(uuid.uuid4())
    filename = secure_filename(f"{task_id}_{file.filename}")
    upload_folder = current_app.config.get("HANDSHAKE_UPLOAD_FOLDER", "/data/handshakes")
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)

    analysis = HandshakeAnalysis(
        task_id=task_id,
        client_id=client_id,
        bssid=bssid,
        essid=essid,
        security_type=security_type,
        handshake_file=file_path,
        status="pending",
        progress=0,
    )
    db.session.add(analysis)
    db.session.commit()

    from celery_worker import run_handshake_task

    run_handshake_task.delay(task_id, file_path, bssid, essid)

    return jsonify({"taskId": task_id, "status": "pending"}), 202


@bp.get("/result/<task_id>")
@jwt_or_api_required
def get_handshake_result(task_id: str):
    analysis = HandshakeAnalysis.query.filter_by(task_id=task_id).first()
    if not analysis:
        return jsonify({"error": "Task not found"}), 404

    created_at = analysis.created_at.isoformat() if analysis.created_at else None
    return jsonify(
        {
            "taskId": analysis.task_id,
            "status": analysis.status,
            "progress": int(analysis.progress or 0),
            "password": analysis.password_found,
            "createdAt": created_at,
        }
    )
