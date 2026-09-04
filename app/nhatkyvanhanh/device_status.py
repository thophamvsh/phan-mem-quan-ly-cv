ALLOWED_DEVICE_STATES = {"dong", "cat", "cat_vtcl", "khac"}


def validate_device_status_snapshot(value, *, plant=None):
    if value in (None, ""):
        return []
    if isinstance(value, list):
        rows = value
        groups = None
    elif isinstance(value, dict):
        if value.get("schema_version") != 2:
            raise ValueError("schema_version phải bằng 2.")
        if not value.get("template_id") or not value.get("template_version"):
            raise ValueError("Snapshot phải có template_id và template_version.")
        groups = value.get("groups")
        if not isinstance(groups, list) or not groups:
            raise ValueError("Snapshot phải có ít nhất một nhóm thiết bị.")
        rows = []
        for group in groups:
            if not isinstance(group, dict) or not str(group.get("id", "")).strip() or not str(group.get("tieu_de", "")).strip():
                raise ValueError("Nhóm thiết bị không hợp lệ.")
            devices = group.get("thiet_bi")
            if not isinstance(devices, list):
                raise ValueError("Danh sách thiết bị trong nhóm không hợp lệ.")
            rows.extend(devices)
    else:
        raise ValueError("Trạng thái thiết bị phải là danh sách hoặc snapshot schema 2.")

    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Mỗi trạng thái thiết bị phải là một đối tượng.")
        code = str(row.get("ma_thiet_bi", "")).strip()
        state = str(row.get("trang_thai", "")).strip()
        if not code or state not in ALLOWED_DEVICE_STATES:
            raise ValueError("Yêu cầu nhập mã thiết bị và trạng thái hợp lệ.")
        normalized = code.casefold()
        if normalized in seen:
            raise ValueError(f"Thiết bị {code} bị trùng.")
        seen.add(normalized)

    if isinstance(value, dict) and plant:
        snapshot_code = str(value.get("nha_may", "")).casefold()
        if snapshot_code and snapshot_code != str(plant.ma_nha_may).casefold():
            raise ValueError("Snapshot không thuộc nhà máy của sổ.")
    return value


def summarize_device_status(snapshot):
    if not snapshot:
        return ""
    if isinstance(snapshot, list):
        groups = [{"tieu_de": "Thiết bị, hệ thống điện", "thiet_bi": snapshot}]
    else:
        groups = snapshot.get("groups", [])
    labels = {"dong": "đóng", "cat": "cắt", "cat_vtcl": "cắt VTCL", "khac": "khác"}
    lines = []
    for group in groups:
        devices = group.get("thiet_bi", [])
        segments = []
        for state in ("dong", "cat", "cat_vtcl", "khac"):
            names = []
            for device in devices:
                if device.get("trang_thai") != state:
                    continue
                name = str(device.get("ma_thiet_bi", "")).strip()
                note = str(device.get("ghi_chu", "")).strip()
                names.append(f"{name} ({note})" if note else name)
            if names:
                segments.append(f"{', '.join(names)} {labels[state]}")
        if segments:
            lines.append(f"{group.get('tieu_de', 'Thiết bị')}: {'; '.join(segments)}.")
    return "\n".join(lines)
