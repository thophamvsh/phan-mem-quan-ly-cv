import time
from datetime import timedelta

from django.utils import timezone

from ...storage import save_exchange
from .report_service import (
    build_leadership_production_report,
    build_leadership_rainfall_weather_report,
    build_leadership_weekly_limit_report,
    build_leadership_event_report,
    build_leadership_event_statistics_report,
)


def production_report_response(*, user, session_id, content, provider, selected_model, start_time, source, report_date=None):
    report_date = report_date or (timezone.localdate() - timedelta(days=1))
    assistant_message = build_leadership_production_report(report_date)
    latency_ms = int((time.time() - start_time) * 1000)
    save_exchange(
        user=user,
        session_id=session_id,
        user_message=content,
        assistant_message=assistant_message,
        model=selected_model,
        total_tokens=0,
        cost_usd=0,
        tools_called=0,
        latency_ms=latency_ms,
        meta={
            "reservoir_detected": False,
            "tools_called": 0,
            "provider": provider,
            "leadership_menu_choice": "production_report",
            "production_report_source": source,
            "report_date": report_date.isoformat(),
        },
    )
    return {
        "session_id": session_id,
        "response": assistant_message,
        "provider": provider,
        "model": selected_model,
        "total_tokens": 0,
        "cost_usd": 0.0,
        "latency_ms": latency_ms,
        "tools_called": 0,
    }


def rainfall_weather_report_response(*, user, session_id, content, provider, selected_model, start_time, source):
    assistant_message = build_leadership_rainfall_weather_report()
    latency_ms = int((time.time() - start_time) * 1000)
    save_exchange(
        user=user,
        session_id=session_id,
        user_message=content,
        assistant_message=assistant_message,
        model=selected_model,
        total_tokens=0,
        cost_usd=0,
        tools_called=0,
        latency_ms=latency_ms,
        meta={
            "reservoir_detected": False,
            "tools_called": 0,
            "provider": provider,
            "leadership_menu_choice": "rainfall_weather_report",
            "rainfall_weather_report_source": source,
        },
    )
    return {
        "session_id": session_id,
        "response": assistant_message,
        "provider": provider,
        "model": selected_model,
        "total_tokens": 0,
        "cost_usd": 0.0,
        "latency_ms": latency_ms,
        "tools_called": 0,
    }


def weekly_limit_report_response(*, user, session_id, content, provider, selected_model, start_time, source):
    assistant_message = build_leadership_weekly_limit_report()
    latency_ms = int((time.time() - start_time) * 1000)
    save_exchange(
        user=user,
        session_id=session_id,
        user_message=content,
        assistant_message=assistant_message,
        model=selected_model,
        total_tokens=0,
        cost_usd=0,
        tools_called=0,
        latency_ms=latency_ms,
        meta={
            "reservoir_detected": False,
            "tools_called": 0,
            "provider": provider,
            "leadership_menu_choice": "weekly_limit_report",
            "weekly_limit_report_source": source,
        },
    )
    return {
        "session_id": session_id,
        "response": assistant_message,
        "provider": provider,
        "model": selected_model,
        "total_tokens": 0,
        "cost_usd": 0.0,
        "latency_ms": latency_ms,
        "tools_called": 0,
    }


def event_report_response(*, user, session_id, content, provider, selected_model, start_time, source):
    assistant_message = build_leadership_event_report()
    latency_ms = int((time.time() - start_time) * 1000)
    save_exchange(
        user=user,
        session_id=session_id,
        user_message=content,
        assistant_message=assistant_message,
        model=selected_model,
        total_tokens=0,
        cost_usd=0,
        tools_called=0,
        latency_ms=latency_ms,
        meta={
            "reservoir_detected": False,
            "tools_called": 0,
            "provider": provider,
            "leadership_menu_choice": "event_report",
            "event_report_source": source,
        },
    )
    return {
        "session_id": session_id,
        "response": assistant_message,
        "provider": provider,
        "model": selected_model,
        "total_tokens": 0,
        "cost_usd": 0.0,
        "latency_ms": latency_ms,
        "tools_called": 0,
    }


def event_statistics_response(*, user, session_id, content, provider, selected_model, start_time, source, request):
    if request.needs_time_clarification:
        assistant_message = (
            f"Anh/chị muốn thống kê sự kiện của {request.plant_name} trong khoảng thời gian nào, "
            "hay muốn hiển thị tất cả?"
        )
    else:
        assistant_message = build_leadership_event_statistics_report(
            plant_code=request.plant_code,
            plant_name=request.plant_name,
            start_date=request.start_date,
            end_date=request.end_date,
            all_time=request.all_time,
            include_details=request.include_details,
        )

    latency_ms = int((time.time() - start_time) * 1000)
    save_exchange(
        user=user,
        session_id=session_id,
        user_message=content,
        assistant_message=assistant_message,
        model=selected_model,
        total_tokens=0,
        cost_usd=0,
        tools_called=0,
        latency_ms=latency_ms,
        meta={
            "reservoir_detected": False,
            "tools_called": 0,
            "provider": provider,
            "leadership_menu_choice": "event_statistics",
            "event_statistics_source": source,
            "plant_code": request.plant_code,
            "start_date": request.start_date.isoformat() if request.start_date else "",
            "end_date": request.end_date.isoformat() if request.end_date else "",
            "all_time": request.all_time,
            "needs_time_clarification": request.needs_time_clarification,
        },
    )
    return {
        "session_id": session_id,
        "response": assistant_message,
        "provider": provider,
        "model": selected_model,
        "total_tokens": 0,
        "cost_usd": 0.0,
        "latency_ms": latency_ms,
        "tools_called": 0,
    }
