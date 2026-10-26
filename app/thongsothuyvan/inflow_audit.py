"""Pure read-only audit calculations. Threshold events are candidates, not verified floods."""
import math
import statistics
from datetime import timedelta


def finite(value):
    try:
        if value is None or isinstance(value, bool):
            return None
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError, OverflowError):
        return None


def quantile(values, q):
    values = sorted(values)
    if not values:
        return None
    position = (len(values)-1)*q
    lower = int(position)
    upper = min(lower+1, len(values)-1)
    return values[lower]+(values[upper]-values[lower])*(position-lower)


def distribution(values):
    original = list(values)
    valid = [v for v in map(finite, original) if v is not None]
    return {"rows": len(original), "finite": len(valid), "missing_or_invalid": len(original)-len(valid),
            "negative": sum(v < 0 for v in valid), "zero": sum(v == 0 for v in valid),
            "min": min(valid) if valid else None, "p50": quantile(valid,.5), "p90": quantile(valid,.9),
            "p95": quantile(valid,.95), "p99": quantile(valid,.99), "max": max(valid) if valid else None}


def candidate_events(daily, threshold=300, bridge_days=1):
    valid = {day: value for day, raw in daily.items() if (value := finite(raw)) is not None}
    high = sorted(day for day, value in valid.items() if value > threshold)
    groups = []
    for day in high:
        previous = groups[-1][-1] if groups else None
        gap = (day-previous).days if previous else None
        bridged = previous is not None and gap <= bridge_days+1 and all(previous+timedelta(days=i) in valid for i in range(1,gap))
        if bridged:
            groups[-1].append(day)
        else:
            groups.append([day])
    result=[]
    for days in groups:
        peak=max(days,key=lambda d:valid[d])
        result.append({"start": days[0], "end": days[-1], "span_days": (days[-1]-days[0]).days+1,
                       "days_above_threshold": len(days), "peak_day": peak, "peak_qve": valid[peak]})
    return result


def compare_daily(primary, secondary, absolute_tolerance=1, relative_tolerance=.05):
    common = sorted(set(primary)&set(secondary))
    compared=[]
    for day in common:
        left,right=finite(primary[day]),finite(secondary[day])
        if left is None or right is None:
            continue
        difference=right-left
        # Tolerances select records for review, not automatic corrections.
        tolerance=max(absolute_tolerance,relative_tolerance*abs(left))
        compared.append({"day":day,"hydrology_qve":left,"production_qve":right,"difference":difference,"exceeds_review_tolerance":abs(difference)>tolerance})
    ordered=sorted(compared,key=lambda r:abs(r["difference"]),reverse=True)
    return {"common_dates":len(common),"compared_finite":len(compared),
            "review_tolerance":{"absolute":absolute_tolerance,"relative_to_primary":relative_tolerance},
            "exceeds_review_tolerance":sum(r["exceeds_review_tolerance"] for r in compared),
            "mean_absolute_difference":statistics.mean(abs(r["difference"]) for r in compared) if compared else None,
            "production_minus_hydrology_bias":statistics.mean(r["difference"] for r in compared) if compared else None,
            "largest_differences":ordered[:20]}
