"""Explainable, sentence-level teaching feedback analysis.

This deliberately uses transparent phrase rules rather than claiming a trained
general-purpose language model. Aspect results include evidence and confidence.
"""
import re

ASPECTS = {
    "Teaching effectiveness": ["teacher", "teaching", "faculty", "professor"],
    "Teaching clarity": [
        "clearly", "clear explanation", "clear explanations", "explanation", "explanations",
        "explaination", "explainations", "explain", "explains", "explained", "explaining",
        "understand", "understood", "understanding", "confusing", "unclear"
    ],
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

TEACHER_GUIDANCE = {
    "Teaching effectiveness": {
        "positive": "Keep the teaching habits students value and ask what helps them learn most.",
        "concern": "Ask students for a concrete example, then choose one teaching change to try and review.",
        "neutral": "Ask students to name one teaching practice that is working and one they would change.",
    },
    "Teaching clarity": {
        "positive": "Build on the clear explanations with a worked example and a quick check for understanding.",
        "concern": "Break explanations into steps, add a worked example, and pause for questions or a quick understanding check.",
        "neutral": "Ask which topic needs another example, then revisit it briefly and check that students followed.",
    },
    "Subject knowledge": {
        "positive": "Keep connecting subject knowledge to concrete examples and invite follow-up questions.",
        "concern": "Revisit the key concepts with worked examples and invite students to point out where they get stuck.",
        "neutral": "Ask which concept students want clarified and provide a relevant example.",
    },
    "Teaching pace": {
        "positive": "Keep checking that the pace works for students with different starting points.",
        "concern": "Pause between difficult topics, leave time for questions, and recap key ideas before moving on.",
        "neutral": "Ask whether students need more time for questions or a slower review of difficult sections.",
    },
    "Student engagement": {
        "positive": "Keep the activities students enjoy and invite more students to contribute in low-pressure ways.",
        "concern": "Add short discussions, practical examples, or questions that let students take part during class.",
        "neutral": "Ask which class activities help students participate and add one short interactive activity.",
    },
    "Doubt clarification": {
        "positive": "Keep making help accessible and leave a regular moment for questions during class.",
        "concern": "Set aside time for questions and make clear how students can get help between classes.",
        "neutral": "Ask whether students know when and how to get help with questions.",
    },
    "Practical learning": {
        "positive": "Keep using practical examples and build in time for students to try them independently.",
        "concern": "Add guided practice or real-world examples, then give students time to apply the idea themselves.",
        "neutral": "Ask which practical example or exercise would make the topic easier to apply.",
    },
    "Assignments and assessment": {
        "positive": "Keep expectations clear and continue giving feedback students can act on.",
        "concern": "Clarify assessment criteria in advance and explain how marks and feedback are assigned.",
        "neutral": "Ask what part of the assignment or grading criteria is unclear and explain it with an example.",
    },
    "Course organization": {
        "positive": "Keep sharing the course plan and flag schedule changes early.",
        "concern": "Share a clear course plan, keep materials organized, and flag schedule changes early.",
        "neutral": "Ask which course materials or schedule details students find hard to follow.",
    },
    "Learning environment": {
        "positive": "Keep checking that the room and equipment support the planned activities.",
        "concern": "Identify the affected room or equipment and arrange a practical workaround or repair.",
        "neutral": "Ask students to identify the specific room, facility, or equipment issue.",
    },
}

NO_ASPECT_GUIDANCE = "Ask students for one specific example of what helped or hindered learning so the next step can address a clear teaching aspect."


def _join_aspects(names):
    names = list(dict.fromkeys(names))
    if len(names) < 2:
        return names[0] if names else "the teaching experience"
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def review_summary(sentiment, aspects):
    strengths = [item["aspect"] for item in aspects if item.get("sentiment") == "positive"]
    concerns = [item["aspect"] for item in aspects if item.get("sentiment") in ("negative", "mixed", "improvement")]
    matched = [item["aspect"] for item in aspects]

    if sentiment == "positive":
        if strengths:
            return f"Positive feedback highlights {_join_aspects(strengths)}."
        return "The comment is positive overall, but it does not name a specific teaching strength."
    if sentiment == "negative":
        if concerns:
            return f"The feedback raises concerns about {_join_aspects(concerns)}."
        return "The comment is negative overall, but it does not name a specific teaching concern."
    if sentiment == "mixed":
        if strengths and concerns:
            return f"The feedback praises {_join_aspects(strengths)} and raises concerns about {_join_aspects(concerns)}."
        return "The feedback includes both positive and negative views; review the comment evidence for context."
    if matched:
        return f"The comment mentions {_join_aspects(matched)}, but gives too little detail to judge it clearly."
    return "The comment is too general to identify a specific teaching strength or concern."


def teacher_improvement_suggestions(aspects):
    concerns = [item for item in aspects if item.get("sentiment") in ("negative", "mixed", "improvement")]
    candidates = concerns or aspects
    suggestions = []
    for item in candidates:
        aspect = item.get("aspect")
        sentiment = item.get("sentiment")
        guidance_type = "concern" if sentiment in ("negative", "mixed", "improvement") else sentiment
        guidance = TEACHER_GUIDANCE.get(aspect, {}).get(guidance_type)
        if guidance and guidance not in suggestions:
            suggestions.append(guidance)
    return suggestions[:3] or [NO_ASPECT_GUIDANCE]


def _comment_review(sentiment, aspects):
    return review_summary(sentiment, aspects)

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
    if any(p in sentence for p in ["बहुत अच्छी", "अच्छा", "अच्छा समझाते", "బాగా బోధిస్తారు", "చాలా బాగా"]):
        pos += 2
    if any(p in sentence for p in ["खराब", "समझ नहीं आया", "బాగా లేదు", "అర్థం కాలేదు"]):
        neg += 2
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
    return {
        "sentiment": overall,
        "confidence": confidence,
        "aspects": aspect_results,
        "strengths": strengths,
        "improvements": improvements,
        "suggestions": suggestions,
        "concerns": concerns,
        "review": _comment_review(overall, aspect_results),
        "improvement_suggestions": teacher_improvement_suggestions(aspect_results),
        "quality": {"short": len(re.findall(r"\w+", text)) < 3},
        "method": "Explainable sentence and phrase rules",
    }
