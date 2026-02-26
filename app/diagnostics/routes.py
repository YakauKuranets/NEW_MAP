from __future__ import annotations

import tempfile

from flask import Blueprint, jsonify, request, send_file

from app.auth.decorators import api_key_required
from app.diagnostics.models import DiagnosticTarget, DiagnosticsAgent
from app.extensions import db
from app.reports.generator import ReportGenerationError, generate_report

bp = Blueprint("diagnostics_api", __name__)


@bp.get("/tasks")
def list_tasks():
    page = max(int(request.args.get("page", 1)), 1)
    per_page = min(max(int(request.args.get("per_page", 20)), 1), 100)
    q = DiagnosticTarget.query

    status = (request.args.get("status") or "").strip()
    if status:
        q = q.filter(DiagnosticTarget.status == status)

    target_type = (request.args.get("type") or "").strip()
    if target_type:
        q = q.filter(DiagnosticTarget.target_type == target_type)

    pagination = q.order_by(DiagnosticTarget.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify(
        {
            "items": [row.to_dict() for row in pagination.items],
            "page": page,
            "perPage": per_page,
            "total": pagination.total,
            "pages": pagination.pages,
        }
    )


@bp.get("/tasks/<int:task_id>")
def task_details(task_id: int):
    task = DiagnosticTarget.query.get_or_404(task_id)
    return jsonify(task.to_dict())


@bp.post("/tasks")
def create_task():
    payload = request.get_json(silent=True) or {}
    target_type = (payload.get("type") or "").strip().lower()
    identifier = (payload.get("identifier") or "").strip()

    if not target_type or not identifier:
        return jsonify({"error": "type and identifier are required"}), 400

    task = DiagnosticTarget(
        target_type=target_type,
        identifier=identifier,
        status=(payload.get("status") or "pending").strip(),
        context=payload.get("context") or {},
        result=payload.get("result") or {},
        risk_summary=payload.get("riskSummary"),
        recommendations=payload.get("recommendations") or [],
        nonconformities=payload.get("nonconformities") or [],
        feedback=payload.get("feedback") or {},
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201


@bp.get("/tasks/<int:task_id>/report")
@api_key_required
def task_report(task_id: int):
    try:
        output_path = f"{tempfile.gettempdir()}/diagnostic_report_{task_id}.pdf"
        generated = generate_report(task_id, output_path)
    except ReportGenerationError as exc:
        return jsonify({"error": str(exc)}), 503
    return send_file(generated, as_attachment=True, download_name=f"diagnostic_report_{task_id}.pdf")


@bp.get("/agents")
def list_agents():
    return jsonify({"items": [a.to_dict() for a in DiagnosticsAgent.query.order_by(DiagnosticsAgent.id.desc()).all()]})


@bp.post("/agents/<int:agent_id>/command")
def send_agent_command(agent_id: int):
    agent = DiagnosticsAgent.query.get_or_404(agent_id)
    payload = request.get_json(silent=True) or {}
    command = (payload.get("command") or "").strip()
    if not command:
        return jsonify({"error": "command is required"}), 400

    # В базовой реализации просто фиксируем последнюю команду в metadata.
    details = agent.details or {}
    details["lastCommand"] = command
    details["lastCommandPayload"] = payload.get("params") or {}
    agent.details = details
    db.session.add(agent)
    db.session.commit()

    return jsonify({"status": "accepted", "agentId": agent_id, "command": command})
