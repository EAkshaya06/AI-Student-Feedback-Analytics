"""Explainable sentiment and aspect analysis used by the live Flask app.

This is a compact lexicon pipeline, not a model trained on the included data.
Scores are directional heuristics and must not be read as probabilities.
"""

from __future__ import annotations

import re
from typing import Any


POSITIVE_WORDS = {
    "amazing", "appreciate", "awesome", "best", "better", "brilliant", "clear",
    "clearly", "effective", "enjoy", "enjoyable", "excellent", "fair", "friendly",
    "good", "great", "helpful", "interesting", "knowledgeable", "love",
    "patient", "perfect", "practical", "respectful", "responsive", "simple", "supportive",
    "useful", "understand", "understandable", "wonderful", "well", "engaging", "interactive",
    "organized", "available", "answers", "answered",
}

NEGATIVE_WORDS = {
    "absent", "bad", "boring", "confusing", "confused", "difficult", "disorganized",
    "disappointing", "disappointed", "error", "excessive", "fast", "hard", "horrible",
    "improperly", "late", "little", "slow", "rushed", "unclear", "unfair", "unhelpful",
    "unorganized", "useless", "waste", "worst", "wrong", "poor", "problem", "problems",
    "issue", "issues", "frustrating", "overwhelming",
}

NEGATIONS = {
    "not", "no", "never", "cannot", "can't", "cant", "doesn't", "doesnt", "don't",
    "dont", "didn't", "didnt", "isn't", "isnt", "aren't", "arent", "wasn't", "wasnt",
    "weren't", "werent", "hardly", "without", "lack", "lacks",
}

SPELLING_NORMALIZATIONS = {
    "explaination": "explanation", "explainations": "explanations", "quallity": "quality",
    "teached": "taught", "cleer": "clear", "understnad": "understand",
    "doesnt": "doesn't", "dont": "don't", "didnt": "didn't", "cant": "can't",
}

NEGATIVE_PHRASES = (
    r"\bnot\s+enough\b", r"\bnot\s+(?:give|provide|include)\s+enough\b", r"\btoo\s+(?:fast|slow|difficult|hard|much)\b",
    r"\b(?:could|can)\s+not\s+(?:understand|follow)\b", r"\bno\s+time\s+for\s+questions\b",
    r"\bdoesn['’]?t\s+(?:answer|respond|clarify|explain)\b", r"\bdoes\s+not\s+(?:answer|respond|clarify|explain)\b",
    r"\bdo\s+not\s+(?:answer|respond|clarify|explain)\b", r"\bnot\s+(?:clear|understandable|helpful|organized)\b",
    r"\b(?:does|do|did)\s+not\s+\w+(?:\s+\w+){0,2}\s+properly\b",
    r"\b(?:lack|lacks|lacking)\s+(?:of\s+)?(?:examples|clarity|organization|support)\b",
    r"\bcould\s+be\s+better\b", r"\bnot\s+properly\b",
)

ASPECT_PATTERNS: dict[str, tuple[str, ...]] = {
    "Teaching effectiveness": (r"\beffective(?:ly)?\b", r"\bteaching quality\b", r"\bteaching method\w*\b", r"\binstruction\b"),
    "Teaching clarity": (r"\bexplain\w*\b", r"\bexplanation(?:s)?\b", r"\bclear(?:ly|ness)?\b", r"\bunderstand\w*\b", r"\bconfus\w*\b", r"\bconcept\w*\b"),
    "Subject knowledge": (r"\bknowledgeable\b", r"\bsubject knowledge\b", r"\bexpertise\b", r"\bknows? the subject\b", r"\bmastery\b"),
    "Teaching pace": (r"\bpace\b", r"\bspeed\b", r"\btoo fast\b", r"\btoo slow\b", r"\brushed\b", r"\bslow(?:ly)?\b"),
    "Student engagement": (r"\bengag\w*\b", r"\binteract\w*\b", r"\bboring\b", r"\bparticipat\w*\b", r"\binteresting\b"),
    "Doubt clarification": (r"\bdoubts?\b", r"\bdoubts?\s+(?:are\s+)?(?:cleared|resolved)\b", r"\bquestions?\b", r"\bclarif\w*\b", r"\banswers?\b", r"\brespond\w*\b"),
    "Practical learning": (r"\bpractical\w*\b", r"\bexamples?\b", r"\bhands[- ]on\b", r"\blab(?:oratory)?\b", r"\bapplications?\b", r"\breal[- ]world\b"),
    "Assignments and assessment": (r"\bassignments?\b", r"\bhomework\b", r"\bassessment\b", r"\bexams?\b", r"\btests?\b", r"\bgrading\b", r"\bmarks?\b", r"\bworkload\b"),
    "Course organization": (r"\borganiz\w*\b", r"\bschedule\b", r"\bsyllabus\b", r"\bstructure\b", r"\bdeadline\w*\b", r"\bcourse content\b"),
    "Learning environment": (r"\benvironment\b", r"\bclassroom\b", r"\brespectful\b", r"\bsupportive\b", r"\batmosphere\b", r"\binclusive\b"),
}

_ASPECT_COMPILED = {
    name: tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)
    for name, patterns in ASPECT_PATTERNS.items()
}
_NEGATIVE_COMPILED = tuple(re.compile(pattern, re.IGNORECASE) for pattern in NEGATIVE_PHRASES)

MULTILINGUAL_LEXICONS = {
    "Hindi": {
    "positive": ("बहुत अच्छी तरह", "अच्छी तरह समझाते", "अच्छा पढ़ाते", "स्पष्ट", "उपयोगी", "अच्छे शिक्षक"),
        "negative": ("समझ नहीं", "अच्छा नहीं", "ठीक से नहीं", "बहुत तेज", "बहुत धीमे", "खराब", "उबाऊ", "समझ नहीं आता"),
    },
    "Telugu": {
        "positive": ("చాలా బాగా", "బాగా బోధిస్తారు", "స్పష్టంగా", "ఉపయోగకరంగా", "చక్కగా బోధిస్తారు", "అర్థమవుతుంది"),
        "negative": ("అర్థం కావడం లేదు", "బాగా బోధించరు", "సరిగా కాదు", "చాలా వేగంగా", "నెమ్మదిగా", "బోరింగ్"),
    },
}


def _language(text: str) -> str:
    if re.search(r"[\u0C00-\u0C7F]", text):
        return "Telugu"
    if re.search(r"[\u0900-\u097F]", text):
        return "Hindi"
    if re.search(r"[A-Za-z]", text):
        return "English"
    return "Unsupported"


def _normalize(text: str) -> str:
    normalized = text.lower().replace("’", "'")
    for wrong, right in SPELLING_NORMALIZATIONS.items():
        normalized = re.sub(r"\b" + re.escape(wrong) + r"\b", right, normalized)
    return normalized


def _clauses(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?;])\s+|\s+(?:but|however|although|yet|whereas|though)\s+", text, flags=re.IGNORECASE)
    return [part.strip() for part in parts if part.strip()]


def _score_english(text: str) -> tuple[float, float, float, int]:
    normalized = _normalize(text)
    clauses = _clauses(normalized)
    if len(clauses) > 1:
        parts = [_score_english(clause) for clause in clauses]
        positive = sum(part[1] for part in parts)
        negative = sum(part[2] for part in parts)
        hits = sum(part[3] for part in parts)
        denominator = positive + negative
        return ((positive - negative) / denominator if denominator else 0.0, positive, negative, hits)
    tokens = re.findall(r"[a-z']+", normalized)
    positive = 0.0
    negative = 0.0
    hits = 0
    for index, token in enumerate(tokens):
        polarity = 1 if token in POSITIVE_WORDS else -1 if token in NEGATIVE_WORDS else 0
        if not polarity:
            continue
        hits += 1
        if any(previous in NEGATIONS for previous in tokens[max(0, index - 3):index]):
            polarity *= -1
        if polarity > 0:
            positive += 1.0
        else:
            negative += 1.0
    for pattern in _NEGATIVE_COMPILED:
        matches = len(pattern.findall(normalized))
        negative += matches
        hits += matches
    denominator = positive + negative
    score = (positive - negative) / denominator if denominator else 0.0
    return score, positive, negative, hits


def _label(score: float) -> str:
    if score >= 0.15:
        return "positive"
    if score <= -0.15:
        return "negative"
    return "neutral"


def _aspect_results(clauses: list[str]) -> list[dict[str, Any]]:
    collected: dict[str, list[tuple[str, float]]] = {}
    for clause in clauses:
        normalized = _normalize(clause)
        for aspect, patterns in _ASPECT_COMPILED.items():
            if any(pattern.search(normalized) for pattern in patterns):
                score, _, _, _ = _score_english(clause)
                collected.setdefault(aspect, []).append((clause, score))
    aspects = []
    for aspect, evidence_items in collected.items():
        score = sum(item[1] for item in evidence_items) / len(evidence_items)
        label = _label(score)
        evidence = " … ".join(dict.fromkeys(item[0] for item in evidence_items))
        aspects.append({"aspect": aspect, "sentiment": label, "score": round(score, 2), "evidence": evidence})
    return aspects


def analyze_comment(text: str) -> dict[str, Any]:
    """Analyze one comment and return transparent heuristic results."""
    original = text.strip()
    language = _language(original)
    clauses = _clauses(original)
    if language == "English":
        score, positive, negative, hits = _score_english(original)
        sentiment = _label(score)
        mixed = positive > 0 and negative > 0
        aspects = _aspect_results(clauses)
        return {
            "sentiment": sentiment,
            "sentiment_score": round(score, 2),
            "mixed_opinion": mixed,
            "language": language,
            "language_supported": True,
            "analysis_method": "explainable_english_lexicon",
            "analysis_note": "Rule-based estimate; the score is not a calibrated probability.",
            "aspects": aspects,
            "aspect_note": "Aspect evidence is taken from the matching clause in the original comment.",
            "_polarity_hits": hits,
            "_positive_hits": int(positive),
            "_negative_hits": int(negative),
        }

    lexicon = MULTILINGUAL_LEXICONS.get(language)
    if lexicon:
        normalized = original.replace("ё", "е")
        positive = sum(normalized.count(term) for term in lexicon["positive"])
        negative = sum(normalized.count(term) for term in lexicon["negative"])
        denominator = positive + negative
        score = (positive - negative) / denominator if denominator else 0.0
        sentiment = _label(score)
        supported = denominator > 0
        return {
            "sentiment": sentiment if supported else "neutral",
            "sentiment_score": round(score, 2),
            "mixed_opinion": positive > 0 and negative > 0,
            "language": language,
            "language_supported": supported,
            "analysis_method": "multilingual_phrase_lexicon",
            "analysis_note": "Limited phrase coverage; results may be neutral when the wording is not recognized." if supported else "This language is detected, but the phrase was not recognized reliably, so no sentiment is inferred.",
            "aspects": [],
            "aspect_note": "Aspect-level sentiment is currently supported for English only.",
            "_polarity_hits": denominator,
            "_positive_hits": int(positive),
            "_negative_hits": int(negative),
        }

    return {
        "sentiment": "neutral",
        "sentiment_score": 0.0,
        "mixed_opinion": False,
        "language": language,
        "language_supported": False,
        "analysis_method": "language_guard",
        "analysis_note": "This language cannot be analyzed reliably yet; the neutral label is a placeholder, not an inferred opinion.",
        "aspects": [],
        "aspect_note": "Aspect-level sentiment is unavailable for this language.",
        "_polarity_hits": 0,
        "_positive_hits": 0,
        "_negative_hits": 0,
    }

