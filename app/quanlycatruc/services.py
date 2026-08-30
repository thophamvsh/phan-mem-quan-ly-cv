import calendar
import math
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from .models import DieuChinhNhanSuCaTruc, KipTruc, LichSuLichTruc, LichTrucCa, NgayTrucCa, ThanhVienKipTruc


def _jd_from_date(dd, mm, yy):
    a = (14 - mm) // 12
    y = yy + 4800 - a
    m = mm + 12 * a - 3
    jd = dd + ((153 * m + 2) // 5) + 365 * y + y // 4 - y // 100 + y // 400 - 32045
    if jd < 2299161:
        jd = dd + ((153 * m + 2) // 5) + 365 * y + y // 4 - 32083
    return jd


def _get_new_moon_day(k, time_zone=7.0):
    T = k / 1236.85
    T2 = T * T
    T3 = T2 * T
    dr = math.pi / 180
    Jd1 = 2415020.75933 + 29.53058868 * k + 0.0001178 * T2 - 0.000000155 * T3
    Jd1 += 0.00033 * math.sin((166.56 + 132.87 * T - 0.009173 * T2) * dr)
    M = 359.2242 + 29.10535608 * k - 0.0000333 * T2 - 0.00000347 * T3
    Mpr = 306.0253 + 385.81691806 * k + 0.0107306 * T2 + 0.00001236 * T3
    F = 21.2964 + 390.67050646 * k - 0.0016528 * T2 - 0.00000239 * T3
    C1 = (0.1734 - 0.000393 * T) * math.sin(M * dr) + 0.0021 * math.sin(2 * M * dr)
    C1 -= 0.4068 * math.sin(Mpr * dr) + 0.0161 * math.sin(2 * Mpr * dr)
    C1 -= 0.0004 * math.sin(3 * Mpr * dr)
    C1 += 0.0104 * math.sin(2 * F * dr) - 0.0051 * math.sin((M + Mpr) * dr)
    C1 -= 0.0074 * math.sin((M - Mpr) * dr) + 0.0004 * math.sin((2 * F + M) * dr)
    C1 -= 0.0004 * math.sin((2 * F - M) * dr) - 0.0006 * math.sin((2 * F + Mpr) * dr)
    C1 += 0.0010 * math.sin((2 * F - Mpr) * dr) + 0.0005 * math.sin((2 * Mpr + M) * dr)
    JdNew = Jd1 + C1
    return int(JdNew + 0.5 + time_zone / 24.0)


def _get_sun_longitude(jdn, time_zone=7.0):
    T = (jdn - 2451545.5 - time_zone / 24.0) / 36525
    T2 = T * T
    dr = math.pi / 180
    M = 357.52910 + 35999.05030 * T - 0.0001559 * T2 - 0.00000048 * T * T2
    L0 = 280.46645 + 36000.76983 * T + 0.0003032 * T2
    DL = (1.914600 - 0.004817 * T - 0.000014 * T2) * math.sin(M * dr)
    DL += (0.019993 - 0.000101 * T) * math.sin(2 * M * dr) + 0.000290 * math.sin(3 * M * dr)
    L = (L0 + DL) * dr
    L = L - math.pi * 2 * int(L / (math.pi * 2))
    return int(L / (math.pi / 6))


def _get_lunar_month_11(yy, time_zone=7.0):
    off = _jd_from_date(31, 12, yy) - 2415021
    k = int(off / 29.530588853)
    nm = _get_new_moon_day(k, time_zone)
    sun_long = _get_sun_longitude(nm, time_zone)
    if sun_long >= 9:
        nm = _get_new_moon_day(k - 1, time_zone)
    return nm


def _get_leap_month_offset(a11, time_zone=7.0):
    k = int((a11 - 2415021.076998695) / 29.530588853 + 0.5)
    last = 0
    i = 1
    arc = _get_sun_longitude(_get_new_moon_day(k, time_zone), time_zone)
    while True:
        last = arc
        k += 1
        arc = _get_sun_longitude(_get_new_moon_day(k, time_zone), time_zone)
        if arc == last:
            return i
        i += 1
        if i >= 14:
            break
    return 0


def convert_solar_to_lunar(dd, mm, yy, time_zone=7.0):
    day_number = _jd_from_date(dd, mm, yy)
    k = int((day_number - 2415021.076998695) / 29.530588853)
    month_start = _get_new_moon_day(k + 1, time_zone)
    if month_start > day_number:
        month_start = _get_new_moon_day(k, time_zone)
    else:
        k += 1
    a11 = _get_lunar_month_11(yy, time_zone)
    b11 = a11
    if a11 >= month_start:
        lunar_year = yy
        a11 = _get_lunar_month_11(yy - 1, time_zone)
    else:
        lunar_year = yy + 1
        b11 = _get_lunar_month_11(yy + 1, time_zone)
    lunar_day = day_number - month_start + 1
    diff = int((month_start - a11) / 29)
    lunar_leap = False
    lunar_month = diff + 11
    if b11 - a11 > 365:
        leap_month_diff = _get_leap_month_offset(a11, time_zone)
        if diff >= leap_month_diff:
            lunar_month = diff + 10
            if diff == leap_month_diff:
                lunar_leap = True
    if lunar_month > 12:
        lunar_month -= 12
    if lunar_month >= 11 and diff < 4:
        lunar_year -= 1
    return lunar_day, lunar_month, lunar_year, lunar_leap


def abbreviated_staff_names(names):
    """Return stable, readable labels and expand initials when labels collide."""
    unique_names = list(dict.fromkeys(name.strip() for name in names if name and name.strip()))
    parts_by_name = {name: name.split() for name in unique_names}

    def candidate(name, middle_count=0):
        parts = parts_by_name[name]
        if len(parts) == 1:
            return parts[0]
        initials = [parts[0][0].upper()]
        if middle_count:
            initials.extend(part[0].upper() for part in parts[1:-1][:middle_count])
        return ".".join([*initials, parts[-1]])

    result = {name: candidate(name) for name in unique_names}
    max_middle = max((max(len(parts) - 2, 0) for parts in parts_by_name.values()), default=0)
    for middle_count in range(1, max_middle + 1):
        collisions = {}
        for name, label in result.items():
            collisions.setdefault(label.casefold(), []).append(name)
        duplicated = {name for group in collisions.values() if len(group) > 1 for name in group}
        if not duplicated:
            break
        for name in duplicated:
            result[name] = candidate(name, middle_count)
    collisions = {}
    for name, label in result.items():
        collisions.setdefault(label.casefold(), []).append(name)
    for group in collisions.values():
        if len(group) > 1:
            for name in group:
                result[name] = name
    return result


def custom_schedule_staff_labels(days):
    staff_by_day = {}
    all_names = []
    for day in days:
        staff_by_day[day.id] = {}
        for period in ("ca_ngay", "ca_dem", "hanh_chinh"):
            staff = actual_shift_staff(day, period)
            staff_by_day[day.id][period] = staff
            all_names.extend(member["ho_ten"] for member in staff)
    labels = abbreviated_staff_names(all_names)
    return {
        day_id: {
            period: "\n".join(labels[member["ho_ten"]] for member in staff)
            for period, staff in periods.items()
        }
        for day_id, periods in staff_by_day.items()
    }


def _team_for_period(day, period):
    return {
        DieuChinhNhanSuCaTruc.LoaiCa.CA_NGAY: day.kip_ca_ngay,
        DieuChinhNhanSuCaTruc.LoaiCa.CA_DEM: day.kip_ca_dem,
        DieuChinhNhanSuCaTruc.LoaiCa.HANH_CHINH: day.kip_hanh_chinh,
    }[period]


def actual_shift_staff(day, period, include_adjustment=None):
    team = _team_for_period(day, period)
    schedule_snapshot = day.lich_truc.snapshot_nhan_su or {}
    has_team_snapshot = bool(team and team.ma_kip in schedule_snapshot)
    snapshot_members = schedule_snapshot.get(team.ma_kip, []) if team else []
    memberships = ThanhVienKipTruc.objects.filter(
        kip_truc=team,
        dang_hoat_dong=True,
        tu_ngay__lte=day.ngay,
    ).filter(models.Q(den_ngay__isnull=True) | models.Q(den_ngay__gte=day.ngay)).select_related("nhan_su", "user", "user__profile")
    daily_hc_mode = day.che_do_phan_cong_hc if period == DieuChinhNhanSuCaTruc.LoaiCa.HANH_CHINH else None
    if daily_hc_mode == NgayTrucCa.CheDoPhanCongHC.KHONG_BO_TRI:
        snapshot_members = []
        has_team_snapshot = True
    elif daily_hc_mode == NgayTrucCa.CheDoPhanCongHC.TUY_CHINH:
        snapshot_members = [
            {
                "nhan_su_id": item.nhan_su_id,
                "user_id": item.nhan_su.user_id,
                "ho_ten": item.nhan_su.ho_ten,
                "vai_tro": item.vai_tro,
            }
            for item in day.phan_cong_hc.select_related("nhan_su")
        ]
        has_team_snapshot = True
    staff = {
        (f"n:{member['nhan_su_id']}" if member.get("nhan_su_id") else f"u:{member.get('user_id')}"): {
            **member,
            "nguon": "phuong_an_chuyen_de",
        }
        for member in snapshot_members
    }
    for member in ([] if has_team_snapshot else memberships):
        profile = getattr(member.user, "profile", None) if member.user_id else None
        name = member.nhan_su.ho_ten if member.nhan_su_id else (getattr(profile, "full_name", "") or member.user.get_full_name() or member.user.username)
        key = f"n:{member.nhan_su_id}" if member.nhan_su_id else f"u:{member.user_id}"
        staff[key] = {"nhan_su_id": member.nhan_su_id, "user_id": member.user_id, "ho_ten": name, "vai_tro": member.vai_tro, "nguon": "lich_goc"}

    adjustments = list(day.dieu_chinh_nhan_su.filter(loai_ca=period, trang_thai=DieuChinhNhanSuCaTruc.TrangThai.DA_DUYET).select_related("nhan_su_vang", "nhan_su_thay"))
    reverse_swaps = list(day.dieu_chinh_doi_den.filter(loai_ca_doi=period, loai_dieu_chinh=DieuChinhNhanSuCaTruc.LoaiDieuChinh.DOI_CA, trang_thai=DieuChinhNhanSuCaTruc.TrangThai.DA_DUYET).select_related("nhan_su_vang", "nhan_su_thay"))
    if include_adjustment is not None:
        adjustments = [item for item in adjustments if item.pk != include_adjustment.pk]
        reverse_swaps = [item for item in reverse_swaps if item.pk != include_adjustment.pk]
        if include_adjustment.ngay_truc_id == day.id and include_adjustment.loai_ca == period:
            adjustments.append(include_adjustment)
        if include_adjustment.loai_dieu_chinh == DieuChinhNhanSuCaTruc.LoaiDieuChinh.DOI_CA and include_adjustment.ngay_truc_doi_id == day.id and include_adjustment.loai_ca_doi == period:
            reverse_swaps.append(include_adjustment)
    for adjustment in adjustments:
        if adjustment.nhan_su_vang_id:
            staff.pop(f"n:{adjustment.nhan_su_vang_id}", None)
        if adjustment.nhan_su_thay_id:
            staff[f"n:{adjustment.nhan_su_thay_id}"] = {
                "nhan_su_id": adjustment.nhan_su_thay_id,
                "user_id": adjustment.nhan_su_thay.user_id,
                "ho_ten": adjustment.nhan_su_thay.ho_ten,
                "vai_tro": adjustment.vai_tro_thay or ThanhVienKipTruc.VaiTro.TRUC_PHU,
                "nguon": adjustment.get_loai_dieu_chinh_display(),
            }
    for adjustment in reverse_swaps:
        if adjustment.nhan_su_thay_id:
            staff.pop(f"n:{adjustment.nhan_su_thay_id}", None)
        if adjustment.nhan_su_vang_id:
            staff[f"n:{adjustment.nhan_su_vang_id}"] = {
                "nhan_su_id": adjustment.nhan_su_vang_id,
                "user_id": adjustment.nhan_su_vang.user_id,
                "ho_ten": adjustment.nhan_su_vang.ho_ten,
                "vai_tro": adjustment.vai_tro_doi or ThanhVienKipTruc.VaiTro.TRUC_PHU,
                "nguon": adjustment.get_loai_dieu_chinh_display(),
            }
    if period == DieuChinhNhanSuCaTruc.LoaiCa.HANH_CHINH:
        deployments = list(day.dieu_chinh_nhan_su.filter(
            trang_thai=DieuChinhNhanSuCaTruc.TrangThai.DA_DUYET,
            nhan_su_thay__isnull=False,
        ).exclude(loai_ca=DieuChinhNhanSuCaTruc.LoaiCa.HANH_CHINH))
        if include_adjustment is not None and include_adjustment.ngay_truc_id == day.id and include_adjustment.loai_ca != period:
            deployments = [item for item in deployments if item.pk != include_adjustment.pk] + [include_adjustment]
        for deployment in deployments:
            staff.pop(f"n:{deployment.nhan_su_thay_id}", None)

    role_order = {
        ThanhVienKipTruc.VaiTro.TRUONG_CA: 1,
        ThanhVienKipTruc.VaiTro.TRUC_CHINH: 2,
        ThanhVienKipTruc.VaiTro.TRUC_PHU: 3,
        ThanhVienKipTruc.VaiTro.KY_THUAT_VIEN: 4,
        ThanhVienKipTruc.VaiTro.NHAN_VIEN: 5,
    }
    return sorted(
        staff.values(),
        key=lambda member: (role_order.get(member.get("vai_tro"), 99), member.get("ho_ten", "")),
    )


def validate_replacement_availability(adjustment):
    if not adjustment.nhan_su_thay_id or adjustment.loai_dieu_chinh == DieuChinhNhanSuCaTruc.LoaiDieuChinh.DOI_CA:
        return
    other_operation_period = (
        DieuChinhNhanSuCaTruc.LoaiCa.CA_DEM
        if adjustment.loai_ca == DieuChinhNhanSuCaTruc.LoaiCa.CA_NGAY
        else DieuChinhNhanSuCaTruc.LoaiCa.CA_NGAY
    )
    if adjustment.loai_ca != DieuChinhNhanSuCaTruc.LoaiCa.HANH_CHINH:
        other_staff = actual_shift_staff(adjustment.ngay_truc, other_operation_period)
        if any(item["nhan_su_id"] == adjustment.nhan_su_thay_id for item in other_staff):
            raise ValidationError("Người trực thay đã được phân công ở ca vận hành khác cùng ngày.")
    adjacent_date = None
    adjacent_period = None
    if adjustment.loai_ca == DieuChinhNhanSuCaTruc.LoaiCa.CA_NGAY:
        adjacent_date = adjustment.ngay_truc.ngay - timedelta(days=1)
        adjacent_period = DieuChinhNhanSuCaTruc.LoaiCa.CA_DEM
    elif adjustment.loai_ca == DieuChinhNhanSuCaTruc.LoaiCa.CA_DEM:
        adjacent_date = adjustment.ngay_truc.ngay + timedelta(days=1)
        adjacent_period = DieuChinhNhanSuCaTruc.LoaiCa.CA_NGAY
    adjacent_day = NgayTrucCa.objects.filter(lich_truc=adjustment.ngay_truc.lich_truc, ngay=adjacent_date).select_related("kip_ca_ngay", "kip_ca_dem", "kip_hanh_chinh").first() if adjacent_date else None
    if adjacent_day and any(item["nhan_su_id"] == adjustment.nhan_su_thay_id for item in actual_shift_staff(adjacent_day, adjacent_period)):
        raise ValidationError("Người trực thay không đủ thời gian nghỉ giữa ca đêm và ca ngày liền kề.")


def validate_operation_staffing(adjustment):
    required_roles = {ThanhVienKipTruc.VaiTro.TRUONG_CA, ThanhVienKipTruc.VaiTro.TRUC_CHINH, ThanhVienKipTruc.VaiTro.TRUC_PHU}
    shifts = [(adjustment.ngay_truc, adjustment.loai_ca)]
    if adjustment.loai_dieu_chinh == DieuChinhNhanSuCaTruc.LoaiDieuChinh.DOI_CA:
        shifts.append((adjustment.ngay_truc_doi, adjustment.loai_ca_doi))
    for day, period in shifts:
        if period == DieuChinhNhanSuCaTruc.LoaiCa.HANH_CHINH:
            continue
        staff = actual_shift_staff(day, period, include_adjustment=adjustment)
        roles = {member["vai_tro"] for member in staff}
        if len(staff) < 3 or not required_roles.issubset(roles):
            missing = [dict(ThanhVienKipTruc.VaiTro.choices)[role] for role in required_roles - roles]
            detail = f"; thiếu chức danh: {', '.join(missing)}" if missing else ""
            raise ValidationError(f"Ca ngày {day.ngay:%d/%m/%Y} phải có ít nhất 3 người và đủ Trưởng ca, Trực chính, Trực phụ{detail}.")


def _position(current_date, anchor_date, anchor_position, length):
    return (anchor_position + (current_date - anchor_date).days) % length


def _teams_by_code(plant_id, group_id=None):
    queryset = KipTruc.objects.filter(nha_may_id=plant_id, dang_hoat_dong=True)
    if group_id:
        queryset = queryset.filter(nhom_lich_id=group_id)
    teams = {team.ma_kip: team for team in queryset}
    admin_teams = list(queryset.filter(loai_kip=KipTruc.LoaiKip.HANH_CHINH).order_by("thu_tu", "ma_kip"))
    for idx, team in enumerate(admin_teams):
        teams.setdefault(f"HC{idx + 1}", team)
        teams.setdefault(str(idx + 1), team)
    return teams


def _previous_locked_schedule(schedule):
    first_day = date(schedule.nam, schedule.thang, 1)
    previous_day = first_day - timedelta(days=1)
    return LichTrucCa.objects.filter(
        nha_may=schedule.nha_may,
        nhom_lich=schedule.nhom_lich,
        nam=previous_day.year,
        thang=previous_day.month,
        trang_thai__in=[
            LichTrucCa.TrangThai.DA_KHOA,
            LichTrucCa.TrangThai.DANG_AP_DUNG,
            LichTrucCa.TrangThai.DA_DUYET,
        ],
    ).annotate(
        continuation_priority=models.Case(
            models.When(trang_thai=LichTrucCa.TrangThai.DA_KHOA, then=0),
            models.When(trang_thai=LichTrucCa.TrangThai.DANG_AP_DUNG, then=1),
            default=2,
            output_field=models.IntegerField(),
        )
    ).order_by("continuation_priority", "-phien_ban").first()


def _continuation_position(previous_days, cycle, actual_signature, expected_signature):
    """Find the cycle position of the last authoritative day, favouring the latest matching run."""
    if not previous_days:
        return None
    best_position = None
    best_rank = (-1, -1)
    for last_position in range(len(cycle)):
        suffix_matches = 0
        weighted_matches = 0
        suffix_open = True
        for distance, day in enumerate(reversed(previous_days[-len(cycle):])):
            expected = cycle[(last_position - distance) % len(cycle)]
            matches = actual_signature(day) == expected_signature(expected)
            if matches:
                weighted_matches += len(cycle) - distance
                if suffix_open:
                    suffix_matches += 1
            else:
                suffix_open = False
        rank = (suffix_matches, weighted_matches)
        if rank > best_rank:
            best_position, best_rank = last_position, rank
    return best_position if best_rank[0] > 0 else None


@transaction.atomic
def generate_monthly_schedule(schedule_id, actor):
    schedule = LichTrucCa.objects.select_for_update().select_related("mau_chu_ky").get(pk=schedule_id)
    if not schedule.co_the_chinh_sua:
        raise ValidationError("Chỉ được sinh lại lịch dự thảo hoặc lịch bị từ chối.")

    template = schedule.mau_chu_ky
    operation_cycle = schedule.chu_ky_van_hanh_tuy_chon or template.chu_ky_van_hanh
    admin_cycle = schedule.chu_ky_hanh_chinh_tuy_chon or template.chu_ky_hanh_chinh
    teams = _teams_by_code(schedule.nha_may_id, schedule.nhom_lich_id)
    required_codes = {
        code
        for item in operation_cycle
        for code in (item.get("day"), item.get("night")) if code
    } | {
        code
        for item in admin_cycle
        for code in (item.get("team"), item.get("from")) if code
    }
    missing = required_codes - set(teams)
    if missing:
        raise ValidationError(f"Chưa cấu hình đủ kíp: {', '.join(sorted(missing))}.")

    before_count = schedule.danh_sach_ngay.count()
    schedule.danh_sach_ngay.all().delete()
    use_custom_anchor = schedule.che_do_sinh_chu_ky == LichTrucCa.CheDoSinhChuKy.MOC_TUY_CHON
    previous = None if use_custom_anchor else _previous_locked_schedule(schedule)
    previous_days = list(previous.danh_sach_ngay.select_related(
        "kip_ca_ngay", "kip_ca_dem", "kip_hanh_chinh", "kip_hanh_chinh_truoc",
    ).order_by("ngay")) if previous else []
    operation_position = _continuation_position(
        previous_days,
        operation_cycle,
        lambda day: (day.kip_ca_ngay.ma_kip, day.kip_ca_dem.ma_kip, day.la_ngay_chuyen_kip),
        lambda item: (item["day"], item["night"], bool(item.get("transition"))),
    )
    admin_teams = list(KipTruc.objects.filter(
        nha_may_id=schedule.nha_may_id,
        nhom_lich_id=schedule.nhom_lich_id,
        loai_kip=KipTruc.LoaiKip.HANH_CHINH,
        dang_hoat_dong=True,
    ).order_by("thu_tu", "ma_kip"))
    admin_code_to_idx = {}
    for idx, t in enumerate(admin_teams):
        admin_code_to_idx[t.ma_kip] = idx
        admin_code_to_idx[f"HC{idx + 1}"] = idx
        admin_code_to_idx[str(idx + 1)] = idx

    def _norm_admin(code):
        return admin_code_to_idx.get(code, code) if code is not None else None

    admin_position = _continuation_position(
        previous_days,
        admin_cycle,
        lambda day: (
            _norm_admin(day.kip_hanh_chinh.ma_kip),
            _norm_admin(day.kip_hanh_chinh_truoc.ma_kip) if day.kip_hanh_chinh_truoc_id else None,
            day.la_ngay_chuyen_ca_hc,
        ),
        lambda item: (_norm_admin(item["team"]), _norm_admin(item.get("from")), bool(item.get("transition"))),
    )
    continuation_length = min(
        len(operation_cycle),
        len(admin_cycle),
    )
    actual_cycle = previous_days[-continuation_length:] if len(previous_days) >= continuation_length else []
    if schedule.loai_lich == LichTrucCa.LoaiLich.CHUYEN_DE:
        current_dates = [
            schedule.tu_ngay + timedelta(days=offset)
            for offset in range((schedule.den_ngay - schedule.tu_ngay).days + 1)
        ]
    else:
        current_dates = [
            date(schedule.nam, schedule.thang, day_number)
            for day_number in range(1, calendar.monthrange(schedule.nam, schedule.thang)[1] + 1)
        ]
    source_days = {}
    if schedule.lich_thang_goc_id:
        source_days = {
            item.ngay: item
            for item in schedule.lich_thang_goc.danh_sach_ngay.select_related(
                "kip_ca_ngay", "kip_ca_dem", "kip_hanh_chinh", "kip_hanh_chinh_truoc"
            )
        }
    days = []
    for day_number, current in enumerate(current_dates, start=1):
        source_day = source_days.get(current)
        if source_day:
            op_item = {"day": source_day.kip_ca_ngay.ma_kip, "night": source_day.kip_ca_dem.ma_kip, "transition": source_day.la_ngay_chuyen_kip}
            admin_item = {"team": source_day.kip_hanh_chinh.ma_kip, "from": source_day.kip_hanh_chinh_truoc.ma_kip if source_day.kip_hanh_chinh_truoc_id else None, "transition": source_day.la_ngay_chuyen_ca_hc}
        elif schedule.loai_lich == LichTrucCa.LoaiLich.CHUYEN_DE:
            op_item = operation_cycle[_position(current, template.ngay_moc_van_hanh, template.vi_tri_moc_van_hanh, len(operation_cycle))]
            admin_item = admin_cycle[_position(current, template.ngay_moc_hanh_chinh, template.vi_tri_moc_hanh_chinh, len(admin_cycle))]
        else:
            if use_custom_anchor:
                op_index = _position(
                    current, schedule.ngay_moc_chu_ky,
                    schedule.vi_tri_moc_van_hanh, len(operation_cycle),
                )
                admin_index = _position(
                    current, schedule.ngay_moc_chu_ky,
                    schedule.vi_tri_moc_hanh_chinh, len(admin_cycle),
                )
                op_item = operation_cycle[op_index]
                admin_item = admin_cycle[admin_index]
            elif actual_cycle:
                actual_day = actual_cycle[(day_number - 1) % len(actual_cycle)]
                op_item = {
                    "day": actual_day.kip_ca_ngay.ma_kip,
                    "night": actual_day.kip_ca_dem.ma_kip,
                    "transition": actual_day.la_ngay_chuyen_kip,
                }
                admin_item = {
                    "team": actual_day.kip_hanh_chinh.ma_kip,
                    "from": actual_day.kip_hanh_chinh_truoc.ma_kip if actual_day.kip_hanh_chinh_truoc_id else None,
                    "transition": actual_day.la_ngay_chuyen_ca_hc,
                }
            else:
                op_index = (
                    (operation_position + day_number) % len(operation_cycle)
                    if operation_position is not None
                    else _position(current, template.ngay_moc_van_hanh, template.vi_tri_moc_van_hanh, len(operation_cycle))
                )
                admin_index = (
                    (admin_position + day_number) % len(admin_cycle)
                    if admin_position is not None
                    else _position(current, template.ngay_moc_hanh_chinh, template.vi_tri_moc_hanh_chinh, len(admin_cycle))
                )
                op_item = operation_cycle[op_index]
                admin_item = admin_cycle[admin_index]
        previous_admin = teams.get(admin_item.get("from"))
        lunar_day, lunar_month, lunar_year, is_leap = convert_solar_to_lunar(
            current.day, current.month, current.year
        )
        days.append(NgayTrucCa(
            lich_truc=schedule,
            ngay=current,
            ngay_am=lunar_day,
            thang_am=lunar_month,
            nam_am=lunar_year,
            la_thang_nhuan=is_leap,
            kip_ca_ngay=teams[op_item["day"]],
            kip_ca_dem=teams[op_item["night"]],
            kip_hanh_chinh=teams[admin_item["team"]],
            kip_hanh_chinh_truoc=previous_admin,
            la_ngay_chuyen_kip=bool(op_item.get("transition")),
            la_ngay_chuyen_ca_hc=bool(admin_item.get("transition")),
        ))
    NgayTrucCa.objects.bulk_create(days)
    if schedule.trang_thai == LichTrucCa.TrangThai.TU_CHOI:
        schedule.trang_thai = LichTrucCa.TrangThai.DU_THAO
        schedule.ly_do_tu_choi = ""
        schedule.save(update_fields=["trang_thai", "ly_do_tu_choi", "updated_at"])
    LichSuLichTruc.objects.create(lich_truc=schedule, hanh_dong="sinh_lich", du_lieu_truoc={"so_ngay": before_count}, du_lieu_sau={"so_ngay": len(days)}, nguoi_thuc_hien=actor)
    return schedule


def _snapshot_staff(schedule):
    memberships = ThanhVienKipTruc.objects.filter(
        kip_truc__nha_may=schedule.nha_may,
        dang_hoat_dong=True,
        tu_ngay__lte=date(schedule.nam, schedule.thang, calendar.monthrange(schedule.nam, schedule.thang)[1]),
    ).filter(models.Q(den_ngay__isnull=True) | models.Q(den_ngay__gte=date(schedule.nam, schedule.thang, 1))).select_related("kip_truc", "nhan_su", "user", "user__profile")
    if schedule.nhom_lich_id:
        memberships = memberships.filter(kip_truc__nhom_lich=schedule.nhom_lich)
    result = {}
    for member in memberships:
        profile = getattr(member.user, "profile", None) if member.user_id else None
        result.setdefault(member.kip_truc.ma_kip, []).append({
            "user_id": member.user_id,
            "nhan_su_id": member.nhan_su_id,
            "ho_ten": member.nhan_su.ho_ten if member.nhan_su_id else (getattr(profile, "full_name", "") or member.user.get_full_name() or member.user.username),
            "vai_tro": member.vai_tro,
        })
    return result


@transaction.atomic
def transition_schedule(schedule_id, actor, action, reason=""):
    schedule = LichTrucCa.objects.select_for_update().get(pk=schedule_id)
    allowed = {
        "gui_duyet": ({LichTrucCa.TrangThai.DU_THAO, LichTrucCa.TrangThai.TU_CHOI}, LichTrucCa.TrangThai.CHO_DUYET),
        "phe_duyet": ({LichTrucCa.TrangThai.CHO_DUYET}, LichTrucCa.TrangThai.DA_DUYET),
        "tu_choi": ({LichTrucCa.TrangThai.CHO_DUYET}, LichTrucCa.TrangThai.TU_CHOI),
        "ap_dung": ({LichTrucCa.TrangThai.DA_DUYET}, LichTrucCa.TrangThai.DANG_AP_DUNG),
        "khoa": ({LichTrucCa.TrangThai.DA_DUYET, LichTrucCa.TrangThai.DANG_AP_DUNG}, LichTrucCa.TrangThai.DA_KHOA),
    }
    if action not in allowed or schedule.trang_thai not in allowed[action][0]:
        raise ValidationError("Chuyển trạng thái lịch trực không hợp lệ.")
    if action == "tu_choi" and not reason.strip():
        raise ValidationError("Phải nhập lý do từ chối.")
    if action == "ap_dung" and LichTrucCa.objects.filter(
        nha_may=schedule.nha_may,
        thang=schedule.thang,
        nam=schedule.nam,
        trang_thai=LichTrucCa.TrangThai.DANG_AP_DUNG,
    ).exclude(pk=schedule.pk).exists():
        raise ValidationError("Tháng này đã có một phiên bản lịch đang áp dụng.")
    expected = calendar.monthrange(schedule.nam, schedule.thang)[1]
    if action in {"gui_duyet", "phe_duyet"} and schedule.danh_sach_ngay.count() != expected:
        raise ValidationError("Lịch chưa có đủ số ngày của tháng.")

    old_status = schedule.trang_thai
    schedule.trang_thai = allowed[action][1]
    if action == "gui_duyet":
        schedule.ngay_gui_duyet = timezone.now()
    elif action == "phe_duyet":
        schedule.nguoi_duyet = actor
        schedule.ngay_duyet = timezone.now()
        schedule.snapshot_nhan_su = _snapshot_staff(schedule)
        schedule.ly_do_tu_choi = ""
    elif action == "tu_choi":
        schedule.ly_do_tu_choi = reason.strip()
    schedule.save()
    LichSuLichTruc.objects.create(lich_truc=schedule, hanh_dong=action, du_lieu_truoc={"trang_thai": old_status}, du_lieu_sau={"trang_thai": schedule.trang_thai}, ly_do=reason, nguoi_thuc_hien=actor)
    return schedule
