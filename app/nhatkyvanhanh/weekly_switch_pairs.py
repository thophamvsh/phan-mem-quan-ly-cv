import unicodedata


WORKING_STATUS = "lam_viec"
STANDBY_STATUS = "du_phong"


def _normalize_label(value):
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    without_accents = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return " ".join(without_accents.casefold().split())


COMPLEMENTARY_GROUPS = {
    _normalize_label("Bơm nước làm mát"),
    _normalize_label("Bơm dầu điều tốc"),
    _normalize_label("Bơm dầu áp lực điều tốc"),
    _normalize_label("Bơm cấp dầu điều tốc"),
}


def opposite_weekly_status(value):
    return {
        WORKING_STATUS: STANDBY_STATUS,
        STANDBY_STATUS: WORKING_STATUS,
    }.get(value, "")


def is_complementary_weekly_group(value):
    return _normalize_label(value) in COMPLEMENTARY_GROUPS


def weekly_pair_key(row):
    if not is_complementary_weekly_group(row.nhom_thiet_bi):
        return None
    area_key = (
        f"area:{row.khu_vuc_id}"
        if row.khu_vuc_id
        else f"legacy:{_normalize_label(row.to_may)}"
    )
    return area_key, _normalize_label(row.nhom_thiet_bi)


def find_weekly_pair(rows, target):
    key = weekly_pair_key(target)
    if key is None:
        return []
    return [row for row in rows if weekly_pair_key(row) == key]


def validate_weekly_pairs(rows, *, require_complete=False):
    groups = {}
    for row in rows:
        key = weekly_pair_key(row)
        if key is not None:
            groups.setdefault(key, []).append(row)

    for members in groups.values():
        group_name = members[0].nhom_thiet_bi
        area_name = (
            members[0].ten_khu_vuc_snapshot
            or getattr(members[0].khu_vuc, "ten_khu_vuc", "")
            or members[0].to_may
        )
        if len(members) != 2:
            return (
                False,
                f"Nhóm {group_name} tại {area_name} phải có đúng 2 thiết bị.",
            )

        statuses = [member.trang_thai for member in members]
        if not any(statuses) and not require_complete:
            continue
        if set(statuses) != {WORKING_STATUS, STANDBY_STATUS}:
            return (
                False,
                f"Nhóm {group_name} tại {area_name} phải có đúng một thiết bị "
                "Làm việc và một thiết bị Dự phòng.",
            )

    return True, ""
