from __future__ import annotations

from typing import Any

from app.diagnostics.coordinator import TaskCoordinator


class ExtendedTaskCoordinator(TaskCoordinator):
    """Расширение планировщика: добавляет IoT/OT/Auto категории."""

    def plan_tasks(self, target: Any) -> list[dict[str, Any]]:
        base = super().plan_tasks(target)
        t = (getattr(target, "type", "") or "").lower()
        identifier = getattr(target, "identifier", "")

        extra: list[dict[str, Any]] = []
        if t == "zigbee":
            extra.append({"type": "zigbee_scan", "priority": 5, "params": {"target": identifier}})
        elif t == "zwave":
            extra.append({"type": "zwave_scan", "priority": 5, "params": {"target": identifier}})
        elif t == "lorawan":
            extra.append({"type": "lorawan_monitor", "priority": 5, "params": {"target": identifier}})
        elif t == "modbus":
            extra.append({"type": "modbus_scan", "priority": 5, "params": {"target": identifier}})
        elif t == "mqtt":
            extra.append({"type": "mqtt_check", "priority": 5, "params": {"target": identifier}})
        elif t == "can":
            extra.append({"type": "can_inspect", "priority": 5, "params": {"target": identifier}})

        return sorted([*base, *extra], key=lambda x: int(x.get("priority", 100)))
