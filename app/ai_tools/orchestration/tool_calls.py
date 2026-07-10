import json
import re
from types import SimpleNamespace

from .production_policy import is_production_question
from .text import normalize_text


def tool_name(tool_call):
    return getattr(getattr(tool_call, "function", None), "name", "") or ""


def tool_arguments(tool_call):
    raw = getattr(getattr(tool_call, "function", None), "arguments", "") or "{}"
    try:
        return json.loads(raw)
    except Exception:
        return {}


def copy_tool_call_with_arguments(tool_call, arguments):
    return SimpleNamespace(
        id=getattr(tool_call, "id", ""),
        function=SimpleNamespace(
            name=tool_name(tool_call),
            arguments=json.dumps(arguments, ensure_ascii=False),
        ),
    )


def detect_transformer_id(normalized_text):
    match = re.search(r"\btd\s*(91|92|94)\b", normalized_text)
    if match:
        return f"TD{match.group(1)}"

    for number in ("1", "2", "3", "4"):
        if re.search(rf"\bt\s*{number}\b", normalized_text):
            return f"T{number}"
    return None


def detect_transformer_parameter(normalized_text, transformer_id, factory_code):
    transformer_lower = transformer_id.lower()
    if "nac" in normalized_text or "phan ap" in normalized_text or "npa" in normalized_text:
        if factory_code == "SH":
            return f"nac_phan_ap_mba_{transformer_lower}"
        return f"nac_phan_ap_{transformer_lower}"

    if "muc dau" in normalized_text or "dau" in normalized_text:
        if factory_code == "SH":
            return f"muc_dau_mba_{transformer_lower}"
        return f"muc_dau_{transformer_lower}"

    if factory_code == "SH":
        return f"nhiet_do_mba_{transformer_lower}"
    return f"nhiet_do_cuon_day_{transformer_lower}"


def detect_transformer_device_code(normalized_text):
    mentions_transformer = any(
        token in normalized_text
        for token in ("may bien ap", "bien ap", "mba", "transformer")
    )
    if not mentions_transformer:
        return None, None

    factory_code = "VS" if any(token in normalized_text for token in ("vinh son", "vinhson", "vs")) else "SH"
    transformer_id = detect_transformer_id(normalized_text)
    if not transformer_id:
        return None, None

    if factory_code == "SH":
        if transformer_id in {"T1", "T2"}:
            device_code = f"SH.TB.TPP.110.{transformer_id}"
        elif transformer_id in {"T3", "T4"}:
            device_code = f"SH.TB.TPP.22.{transformer_id}"
        elif transformer_id == "TD91":
            device_code = "SH.TB.TD.LV.TD1"
        elif transformer_id == "TD94":
            device_code = "SH.TB.TD.LV.TD2"
        else:
            return None, None
    else:
        if transformer_id in {"T1", "T2"}:
            device_code = f"VS.TB.TPP.{transformer_id}"
        elif transformer_id in {"TD91", "TD92"}:
            device_code = f"VS.TB.TD.LV.TD{1 if transformer_id == 'TD91' else 2}"
        else:
            return None, None

    return device_code, detect_transformer_parameter(normalized_text, transformer_id, factory_code)


def normalize_analysis_tool_call(user_text, tool_call):
    if tool_name(tool_call).lower() != "get_unit_state_profile":
        return tool_call

    normalized_text = normalize_text(user_text)
    device_code, parameter_code = detect_transformer_device_code(normalized_text)
    if not device_code:
        return tool_call

    args = tool_arguments(tool_call)
    args["device_code"] = device_code
    if parameter_code:
        args["parameter_code"] = parameter_code
    return copy_tool_call_with_arguments(tool_call, args)


def normalize_vinhson_production_tool_call(user_text, tool_call):
    name = tool_name(tool_call).lower()
    if not name.startswith("get_vinhson_"):
        return tool_call
    if not is_production_question(user_text):
        return tool_call

    args = tool_arguments(tool_call)
    if args.get("reservoir") in {"Vinh Son -A", "Vinh Son -B", "Vinh Son -C"}:
        args["reservoir"] = "All"
        return copy_tool_call_with_arguments(tool_call, args)
    return tool_call


def dedupe_tool_calls(tool_calls):
    unique = []
    seen = set()
    for tool_call in tool_calls:
        key = (tool_name(tool_call), json.dumps(tool_arguments(tool_call), sort_keys=True, ensure_ascii=False))
        if key in seen:
            continue
        seen.add(key)
        unique.append(tool_call)
    return unique


def select_single_songhinh_rainfall_call(user_text, tool_calls):
    normalized = normalize_text(user_text)
    if "song hinh" not in normalized and "songhinh" not in normalized and "sh" not in normalized:
        return None
    if "mua" not in normalized and "rain" not in normalized:
        return None

    rainfall_calls = [
        tool_call
        for tool_call in tool_calls
        if tool_name(tool_call).startswith("get_songhinh_rainfall_")
    ]
    if not rainfall_calls:
        return None
    if len(rainfall_calls) == 1:
        return rainfall_calls[0]

    def score(tool_call):
        name = tool_name(tool_call)
        args = tool_arguments(tool_call)
        if name == "get_songhinh_rainfall_statistics":
            period_type = args.get("period_type")
            if period_type == "year" and ("nam" in normalized or "year" in normalized):
                return 100
            if period_type == "month" and "thang" in normalized:
                return 95
            if period_type == "week" and "tuan" in normalized:
                return 90
            return 80
        if name == "get_songhinh_rainfall_daily_statistics":
            if "tu ngay" in normalized or "den ngay" in normalized:
                return 75
            return 30
        if name == "get_songhinh_rainfall_range_statistics":
            if "tu thang" in normalized or "den thang" in normalized:
                return 70
            return 25
        return 0

    return max(rainfall_calls, key=score)


def select_single_vinhson_rainfall_call(user_text, tool_calls):
    normalized = normalize_text(user_text)
    if "vinh son" not in normalized and "vinhson" not in normalized and "vs" not in normalized:
        return None
    if "mua" not in normalized and "rain" not in normalized:
        return None

    rainfall_calls = [
        tool_call
        for tool_call in tool_calls
        if tool_name(tool_call).startswith("get_vinhson_rainfall_")
    ]
    if not rainfall_calls:
        return None
    if len(rainfall_calls) == 1:
        return rainfall_calls[0]

    def score(tool_call):
        name = tool_name(tool_call)
        args = tool_arguments(tool_call)
        if name == "get_vinhson_rainfall_statistics":
            period_type = args.get("period_type")
            if period_type == "year" and ("nam" in normalized or "year" in normalized):
                return 100
            if period_type == "month" and "thang" in normalized:
                return 95
            if period_type == "week" and "tuan" in normalized:
                return 90
            return 80
        if name == "get_vinhson_rainfall_daily_statistics":
            if "tu ngay" in normalized or "den ngay" in normalized:
                return 75
            return 30
        if name == "get_vinhson_rainfall_range_statistics":
            if "tu thang" in normalized or "den thang" in normalized:
                return 70
            return 25
        return 0

    return max(rainfall_calls, key=score)


def filter_tool_calls(user_text, tool_calls):
    calls = dedupe_tool_calls(list(tool_calls or []))
    selected_sh_rainfall = select_single_songhinh_rainfall_call(user_text, calls)
    selected_vs_rainfall = select_single_vinhson_rainfall_call(user_text, calls)

    normalized = normalize_text(user_text)
    needs_non_rainfall_data = any(
        keyword in normalized
        for keyword in ("qve", "luu luong", "muc nuoc", "mnh", "san luong")
    )

    filtered = []
    for call in calls:
        name = tool_name(call)
        if name.startswith("get_songhinh_rainfall_"):
            if selected_sh_rainfall:
                if call == selected_sh_rainfall:
                    filtered.append(call)
            else:
                filtered.append(call)
        elif name.startswith("get_vinhson_rainfall_"):
            if selected_vs_rainfall:
                if call == selected_vs_rainfall:
                    filtered.append(call)
            else:
                filtered.append(call)
        else:
            is_sh_call = "songhinh" in name or "songinh" in name
            is_vs_call = "vinhson" in name or "vinh_son" in name

            if needs_non_rainfall_data:
                filtered.append(call)
            else:
                if is_sh_call and selected_sh_rainfall:
                    continue
                if is_vs_call and selected_vs_rainfall:
                    continue
                filtered.append(call)

    return filtered
