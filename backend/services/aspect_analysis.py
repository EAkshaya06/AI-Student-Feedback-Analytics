"""Explainable, sentence-level teaching feedback analysis.

This deliberately uses transparent phrase rules rather than claiming a trained
general-purpose language model. Aspect results include evidence and confidence.
"""
import re

ASPECTS = {
    "Teaching effectiveness": ["teacher", "teaching", "faculty", "professor"],
    "Teaching clarity": ["clearly", "clear explanation", "explain", "understand", "understood", "confusing", "unclear"],
    "Subject knowledge": ["knowledge", "expert", "concepts", "conceptual", "subject", "know the subject"],
    "Teaching pace": ["too fast", "very fast", "going fast", "quickly", "slow pace", "too slow", "pace", "rushed"],
    "Student engagement": ["engaging", "interactive", "boring", "participate", "interesting", "motivating"],
    "Doubt clarification": ["doubt", "questions", "helpful", "available", "clarify", "clarification", "responds"],
    "Practical learning": ["practical", "hands-on", "real-world", "real world", "lab", "laboratory", "examples", "practice"],
    "Assignments and assessment": ["assignment", "exam", "assessment", "grading", "marks", "workload", "homework"],
    "Course organization": ["organized", "organization", "course structure", "schedule", "syllabus", "prepared"],
    "Learning environment": ["computer", "equipment", "infrastructure", "classroom", "facility", "facilities", "lab computers"],
}
POSITIVE = {"good", "great", "excellent", "helpful", "clear", "clearly", "useful", "interesting", "engaging", "understand", "understood", "supportive", "effective", "best", "well"}
NEGATIVE = {"bad", "poor", "confusing", "unclear", "difficult", "fast", "quickly", "slow", "boring", "unhelpful", "hard", "problem", "issue", "not", "never", "lack", "lacking"}
SUGGESTION = re.compile(r"\b(should|could|please|more|less|need|needs|wish|suggest|recommend|would help|would be better)\b", re.I)
NEGATION = {"not", "never", "isn't", "wasn't", "doesn't", "don't", "didn't", "cannot", "can't"}

def _sentences(text):
    # Keep conjunctions available to phrase rules while splitting clear clauses.
    return [s.strip() for s in re.split(r"[.!?;\n]+|\bbut\b|\balthough\b|\bhowever\b|\band\s+(?=we need|more\b|they need)", text, flags=re.I) if s.strip()]

def _polarity(sentence):
    words = re.findall(r"[a-z']+", sentence.lower())
    pos = neg = 0
    for i, word in enumerate(words):
        invert = any(w in NEGATION for w in words[max(0, i-3):i])
        if word in POSITIVE:
            if invert: neg += 1
            else: pos += 1
        if word in NEGATIVE:
            if invert: pos += 1
            else: neg += 1
    if pos and neg: return "mixed", pos, neg
    if pos: return "positive", pos, neg
    if neg: return "negative", pos, neg
    return "neutral", pos, neg

def analyze(text):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return {"sentiment":"neutral", "confidence":0.0, "aspects":[], "strengths":[], "improvements":[], "suggestions":[], "concerns":[], "quality":{"short":True}, "method":"Explainable sentence and phrase rules"}
    clauses = _sentences(text)
    aspect_results = []
    for aspect, phrases in ASPECTS.items():
        matches = []
        for clause in clauses:
            lower = clause.lower()
            matched = [p for p in phrases if re.search(r"(?<![a-z])" + re.escape(p) + r"(?![a-z])", lower)]
            if matched:
                label, pos, neg = _polarity(clause)
                if label == "neutral" and SUGGESTION.search(clause):
                    label = "improvement"
                if label == "mixed":
                    # Report a mixed aspect when praise and criticism coexist in one clause.
                    pass
                matches.append((clause, label, pos, neg, matched))
        if matches:
            labels = {m[1] for m in matches}
            if "mixed" in labels or ("positive" in labels and "negative" in labels):
                label = "mixed"
            elif "improvement" in labels:
                label = "improvement"
            else:
                label = next(iter(labels))
            evidence = list(dict.fromkeys(m[0] for m in matches))
            aspect_results.append({"aspect":aspect,"sentiment":label,"confidence":round(min(.78, .54 + .08 * sum(m[2]+m[3] for m in matches)),2),"evidence":evidence})
    overall, pos, neg = _polarity(text)
    if pos and neg: overall = "mixed"
    confidence = round(min(.76, .48 + .06 * (pos+neg) + .02 * max(0, len(clauses)-1)), 2) if pos+neg else .42
    strengths = [a["aspect"] for a in aspect_results if a["sentiment"] == "positive"]
    improvements = [a["aspect"] for a in aspect_results if a["sentiment"] in ("negative", "mixed", "improvement")]
    suggestions = [a["aspect"] for a in aspect_results if any(SUGGESTION.search(e) for e in a["evidence"])]
    concerns = [a["aspect"] for a in aspect_results if a["sentiment"] == "negative" and a["aspect"] == "Learning environment"]
    return {"sentiment":overall,"confidence":confidence,"aspects":aspect_results,"strengths":strengths,"improvements":improvements,"suggestions":suggestions,"concerns":concerns,"quality":{"short":len(re.findall(r"\w+",text)) < 3},"method":"Explainable sentence and phrase rules"}
