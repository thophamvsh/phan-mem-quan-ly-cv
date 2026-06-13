def sum_record_field(records, field):
    values = []
    for record in records:
        value = getattr(record, field, None)
        if value is not None:
            values.append(float(value))
    if not values:
        return None
    return sum(values)


def fmt_report_number(value):
    if value is None:
        return "-"
    if abs(value - round(value)) < 0.000001:
        return f"{round(value):,}".replace(",", ".")
    return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_report_decimal(value, digits=2):
    if value is None:
        return "-"
    return f"{float(value):,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_report_pct(actual, plan):
    if actual is None or plan is None or plan <= 0:
        return "-"
    return f"{actual / plan * 100:.2f}%"


def fmt_report_direct_pct(value):
    if value is None:
        return "-"
    return f"{float(value):.1f}%".replace(".", ",")


def add_report_totals(totals, metrics):
    for key, value in metrics.items():
        if value is not None:
            totals[key] = (totals.get(key) or 0.0) + value


def as_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def record_value(record, field_name):
    if not record or not field_name:
        return None
    return as_float(getattr(record, field_name, None))
