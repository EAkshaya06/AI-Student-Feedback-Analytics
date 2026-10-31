"""Source-aware staff analytics for historical and live feedback."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, datetime
from typing import Any


SENTIMENTS = ("positive", "neutral", "negative")
FILTER_FIELDS = ("department", "academic_year", "semester", "subject", "faculty")


def _sentiment_label(value: Any) -> tuple[str, bool]:
    label = str(value or "").strip().lower()
    if label in {"1", "1.0", "positive"}:
        return "positive", True
    if label in {"-1", "-1.0", "negative"}:
        return "negative", True
    if label in {"0", "0.0", "neutral"}:
        return "neutral", True
    return "neutral", False


def historical_records(frame, analyze_text) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    rows = []
    for index, raw in enumerate(frame.to_dict(orient="records")):
        text = str(raw.get("feedback_text") or raw.get("text") or raw.get("feedback") or "").strip()
        if not text:
            continue
        sentiment, supported = _sentiment_label(raw.get("sentiment") or raw.get("predicted_sentiment"))
        analysis = analyze_text(text)
        try:
            score = float(raw.get("sentiment_score") or 0)
        except (TypeError, ValueError):
            score = 0.0
        rows.append({
            "id": f"historical-{index}", "feedback": text, "feedback_text": text,
            "department": "", "academic_year": "", "semester": "",
            "subject": "", "section": "", "faculty": "",
            "sentiment": sentiment, "predicted_sentiment": sentiment,
            "sentiment_score": score, "mixed_opinion": analysis.get("mixed_opinion", False),
            "language": analysis.get("language", "Unknown"),
            "language_supported": analysis.get("language_supported", False),
            "sentiment_supported": supported, "analysis_method": "historical_dataset_label",
            "analysis_note": "Historical sentiment label from the packaged dataset; timestamps and academic metadata were not included.",
            "aspects": analysis.get("aspects", []), "emotion": str(raw.get("emotion") or "Not available"),
            "category": str(raw.get("category") or "Uncategorized"), "source": "historical", "created_at": "",
        })
    return rows


def live_records(rows, analyze_text, faculty_key: str | None = None) -> list[dict[str, Any]]:
    records = []
    scoped_key = (faculty_key or "").strip().casefold()
    for source in rows:
        row = dict(source)
        if scoped_key and str(row.get("faculty") or "").strip().casefold() != scoped_key:
            continue
        try:
            analysis = json.loads(row.get("analysis_json") or "{}")
        except (TypeError, json.JSONDecodeError):
            analysis = {}
        metadata = analysis.get("_metadata") or analysis.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        text = str(row.get("feedback_text") or "")
        if not analysis:
            analysis = analyze_text(text)
        sentiment = str(analysis.get("sentiment") or "neutral").lower()
        supported = bool(analysis.get("sentiment_supported", analysis.get("language_supported", True)))
        aspects = analysis.get("aspects") if isinstance(analysis.get("aspects"), list) else []
        records.append({
            "id": row.get("id"), "feedback": text, "feedback_text": text,
            "department": str(row.get("department") or metadata.get("department") or ""),
            "academic_year": str(metadata.get("academic_year") or ""),
            "semester": str(metadata.get("semester") or ""),
            "subject": str(metadata.get("subject") or row.get("course") or ""),
            "section": str(metadata.get("section") or ""),
            "faculty": str(row.get("faculty") or metadata.get("faculty") or ""),
            "sentiment": sentiment, "predicted_sentiment": sentiment,
            "sentiment_score": analysis.get("sentiment_score", 0),
            "mixed_opinion": bool(analysis.get("mixed_opinion", sentiment == "mixed")),
            "language": str(analysis.get("language") or "Unknown"),
            "language_supported": bool(analysis.get("language_supported", supported)),
            "sentiment_supported": supported,
            "analysis_method": str(analysis.get("analysis_method") or analysis.get("method") or "legacy_phrase_rules"),
            "analysis_note": str(analysis.get("analysis_note") or "Automated analysis is an estimate; review original feedback in context."),
            "aspects": aspects, "emotion": "Not analyzed",
            "category": ", ".join(item.get("aspect", "") for item in aspects if item.get("aspect")) or "Unclassified",
            "source": "live", "created_at": str(row.get("created_at") or ""),
        })
    return records


def select_records(args, staff, historical: list[dict[str, Any]], live: list[dict[str, Any]]):
    source = str(args.get("source", "historical")).strip().lower()
    if source not in {"historical", "live", "all"}:
        raise ValueError("Choose historical, live, or all as the data source.")
    is_faculty = staff["role"] == "faculty"
    if is_faculty:
        source = "live"
    available = []
    if source in {"historical", "all"} and not is_faculty:
        available.extend(historical)
    if source in {"live", "all"}:
        available.extend(live)

    filters: dict[str, str] = {"source": source}
    for key in FILTER_FIELDS:
        value = str(args.get(key, "")).strip()
        if value:
            if len(value) > 160:
                raise ValueError(f"{key.replace('_', ' ').title()} filter is too long.")
            filters[key] = value.casefold()
    date_from_text = str(args.get("date_from", "")).strip()
    date_to_text = str(args.get("date_to", "")).strip()
    date_from = date_to = None
    try:
        date_from = date.fromisoformat(date_from_text) if date_from_text else None
        date_to = date.fromisoformat(date_to_text) if date_to_text else None
    except ValueError:
        raise ValueError("Use YYYY-MM-DD for date filters.") from None
    if date_from and date_to and date_from > date_to:
        raise ValueError("The start date must be on or before the end date.")
    if date_from_text:
        filters["date_from"] = date_from_text
    if date_to_text:
        filters["date_to"] = date_to_text

    selected = []
    for record in available:
        if any(str(record.get(key, "")).strip().casefold() != value for key, value in filters.items() if key in FILTER_FIELDS):
            continue
        if date_from or date_to:
            timestamp = str(record.get("created_at") or "")
            if not timestamp:
                continue
            try:
                record_date = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date()
            except ValueError:
                continue
            if date_from and record_date < date_from or date_to and record_date > date_to:
                continue
        selected.append(record)
    notes = []
    if (date_from or date_to) and source in {"historical", "all"}:
        notes.append("Historical/demo records have no timestamps, so date filters include only dated live submissions.")
    options = available
    return selected, filters, notes, options


def _group_counts(records: list[dict[str, Any]], key: str) -> dict[str, dict[str, int]]:
    groups: dict[str, Counter] = defaultdict(Counter)
    for record in records:
        label = str(record.get(key, "")).strip()
        if label and record.get("sentiment_supported", True) and record.get("sentiment") in SENTIMENTS:
            groups[label][record["sentiment"]] += 1
    return {label: {name: int(count.get(name, 0)) for name in SENTIMENTS}
            for label, count in sorted(groups.items(), key=lambda item: item[0].casefold())}


def _evidence(item: dict[str, Any]) -> list[str]:
    value = item.get("evidence") or []
    if isinstance(value, str):
        value = [value]
    return [str(text) for text in value if str(text).strip()]


def _insights(records, aspect_distribution, monthly):
    strengths, concerns = [], []
    for aspect, counts in aspect_distribution.items():
        for label, output, icon in (("positive", strengths, "strength"), ("negative", concerns, "concern")):
            if not counts.get(label):
                continue
            examples = []
            for record in records:
                for item in record.get("aspects", []):
                    if item.get("aspect") == aspect and item.get("sentiment") == label:
                        examples.extend(_evidence(item))
            output.append({"aspect": aspect, "mentions": counts[label], "evidence": list(dict.fromkeys(examples))[:2]})
    strengths.sort(key=lambda item: (-item["mentions"], item["aspect"]))
    concerns.sort(key=lambda item: (-item["mentions"], item["aspect"]))
    months = sorted(monthly)
    trend = None
    if len(months) >= 2:
        previous, current = months[-2:]
        trend = {"from": previous, "to": current, "previous_count": monthly[previous]["total"],
                 "current_count": monthly[current]["total"],
                 "message": f"Feedback volume changed from {monthly[previous]['total']} in {previous} to {monthly[current]['total']} in {current}."}
    return {"strengths": strengths[:5], "improvement_areas": concerns[:5], "trend": trend}


def analytics_payload(records, filters, notes, option_records):
    analyzed = [row for row in records if row.get("sentiment_supported", True) and row.get("sentiment") in SENTIMENTS]
    counts = Counter(row["sentiment"] for row in analyzed)
    total = len(records)
    analyzed_total = len(analyzed)
    sentiment = {name: int(counts.get(name, 0)) for name in SENTIMENTS}
    percentages = {name: round(sentiment[name] * 100 / analyzed_total, 2) if analyzed_total else 0 for name in SENTIMENTS}
    aspect_counts: dict[str, Counter] = defaultdict(Counter)
    for record in records:
        for item in record.get("aspects", []):
            name, label = item.get("aspect"), item.get("sentiment")
            if name and label in SENTIMENTS:
                aspect_counts[name][label] += 1
    aspect_distribution = {name: {label: int(values.get(label, 0)) for label in SENTIMENTS}
                           for name, values in sorted(aspect_counts.items())}
    semester_counts: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for record in records:
        semester = str(record.get("semester", "")).strip()
        if semester:
            for item in record.get("aspects", []):
                if item.get("aspect") and item.get("sentiment") in SENTIMENTS:
                    semester_counts[(item["aspect"], semester)][item["sentiment"]] += 1
    aspect_by_semester = [{"aspect": aspect, "semester": semester,
                           **{label: int(values.get(label, 0)) for label in SENTIMENTS},
                           "total": int(sum(values.get(label, 0) for label in SENTIMENTS))}
                          for (aspect, semester), values in sorted(semester_counts.items())]
    monthly_counts: dict[str, Counter] = defaultdict(Counter)
    for record in records:
        created = record.get("created_at", "")
        if not created:
            continue
        try:
            month = datetime.fromisoformat(created.replace("Z", "+00:00")).strftime("%Y-%m")
        except ValueError:
            continue
        monthly_counts[month]["total"] += 1
        if record.get("sentiment_supported", True) and record.get("sentiment") in SENTIMENTS:
            monthly_counts[month][record["sentiment"]] += 1
    monthly = {month: {**{label: int(values.get(label, 0)) for label in SENTIMENTS}, "total": int(values["total"])}
               for month, values in sorted(monthly_counts.items())}
    category = dict(Counter(row["category"] for row in records if row.get("category")))
    options = {key: sorted({str(row.get(key, "")).strip() for row in option_records if str(row.get(key, "")).strip()}, key=str.casefold)
               for key in FILTER_FIELDS}
    insights = _insights(records, aspect_distribution, monthly)
    source = filters.get("source", "historical")
    return {
        "success": True, "total": total, "sentiment_total": analyzed_total,
        "unsupported_sentiment_count": total - analyzed_total,
        "positive": sentiment["positive"], "neutral": sentiment["neutral"], "negative": sentiment["negative"],
        "positive_percentage": percentages["positive"], "neutral_percentage": percentages["neutral"],
        "negative_percentage": percentages["negative"], "sentiment": sentiment,
        "sentiment_percentages": percentages,
        "emotion": dict(Counter(row["emotion"] for row in records if row.get("emotion") not in {"", "Not available", "Not analyzed"})),
        "category": category, "sentiment_by_category": _group_counts(records, "category"),
        "aspect_distribution": aspect_distribution, "aspect_by_semester": aspect_by_semester,
        "department_analysis": _group_counts(records, "department"),
        "semester_analysis": _group_counts(records, "semester"),
        "subject_analysis": _group_counts(records, "subject"), "monthly_trend": monthly,
        "insights": insights, "filter_options": options, "filters": filters,
        "data_source": source,
        "data_source_label": {"historical": "Historical/demo dataset", "live": "Live student submissions", "all": "Combined historical/demo and live submissions"}[source],
        "notes": notes,
    }

