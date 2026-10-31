import re
from typing import Any, Dict, List, Tuple

# ============================================================================
# ASPECT DEFINITIONS & PATTERNS (12 ASPECTS PER USER SPECIFICATION)
# ============================================================================

ASPECTS = [
    "Teaching effectiveness",
    "Teaching clarity",
    "Student engagement",
    "Doubt clarification",
    "Subject knowledge",
    "Practical learning",
    "Course organization",
    "Learning environment",
    "Academic support",
    "Industry relevance",
    "Infrastructure",
    "Career opportunities",
]

ASPECT_PATTERNS = {
    "Career opportunities": [
        r"\b(?:internships?|workshops?|seminars?|technical events?|placements?|placement drives?|career opportunities|job opportunities|recruitment|campus drives?|hackathons?|industry visits?)\b",
        r"\b(?:opportunities for students|provides? (?:wonderful|great|excellent|good) opportunities)\b",
    ],
    "Industry relevance": [
        r"\b(?:industry (?:requirements?|standards?|relevance|ready|readiness|trends?|needs?|exposure)|relevant to industry|industry relevant|job market|real-world skills?|modern technolog(?:y|ies)|cutting edge|outdated curriculum|irrelevant to industry)\b",
    ],
    "Academic support": [
        r"\b(?:academic growth|academic support|mentoring|mentorship|mentors?|advisors?|advising|student welfare|counseling|personal attention)\b",
        r"\b(?:genuinely cares?|cares? (?:about|for) students?|guidance for students?|helps? struggling students?|support outside class)\b",
    ],
    "Infrastructure": [
        r"\b(?:infrastructure|facilities?|lab computers?|equipment|wi-?fi|internet connectivity|library|projectors?|smart boards?|air condition(?:ing)?|\bac\b|seating|benches|clean campus|maintenance|washrooms?|broken equipment|computers? frequently crash)\b",
    ],
    "Practical learning": [
        r"\b(?:practicals?|practical sessions?|hands-?on|hands-?on experience|labs?|laboratory|experiments?|applying theoretical concepts|apply(?:ing)? concepts practically|practical application|real-?world applications?|practical exposure|practical training|lab experiments?|lab skills?)\b",
    ],
    "Doubt clarification": [
        r"\b(?:doubts?|clarif(?:y|ies|ied|ying)|clarifications?|clear doubts?|clears? doubts?|resolv(?:e|es|ed|ing) doubts?)\b",
        r"\b(?:willing to clarify|approachable and (?:always )?willing|answers? (?:every )?(?:single )?(?:student )?questions?|clears? all (?:our )?doubts?|doubt clearing|doubt sessions?|available after class)\b",
    ],
    "Student engagement": [
        r"\b(?:engaging|engagement|interactive|interaction|think creatively|explore beyond|curiosity|enthusiasm|active learning|classroom discussions?)\b",
        r"\b(?:encourag(?:e|es|ed|ing) (?:us|students?) to (?:think|participate|ask|explore)|interactive discussions?|monotonous|boring lectures?|dull lectures?)\b",
    ],
    "Subject knowledge": [
        r"\b(?:subject knowledge|deep knowledge|knowledgeable|command over (?:the )?subject|master of (?:the )?subject|conceptual clarity|depth of knowledge|expertise|lacks? subject knowledge)\b",
        r"(?<!applying )\b(?:theoretical concepts?|in-depth theoretical|subject fundamentals?)\b",
    ],
    "Teaching clarity": [
        r"\b(?:clarity|clearly|clear explanation|clear explanations|simple explanation|crystal clear|explains? clearly|explains? concepts|easy to understand|easy to follow|makes? concepts? (?:simple|easy)|confusing explanations?|cannot understand|hard to understand|hard to follow|vague explanations?|unclear explanations?)\b",
    ],
    "Course organization": [
        r"\b(?:curriculum|syllabus|course structure|well structured|well-structured|well organized|well-organized|course organization|schedules?|timetables?|lesson plans?|prepared for class|syllabus coverage|course materials?|disorganized|assignments?|grading|homework|mid-term|examinations?|pace is too rushed|pace of teaching)\b",
    ],
    "Learning environment": [
        r"\b(?:classroom atmosphere|learning environment|supportive atmosphere|friendly environment|campus vibe|class environment|respectful environment|noisy classroom|disturbances? in class|classroom comfort)\b",
    ],
    "Teaching effectiveness": [
        r"\b(?:teachers?|teaching|faculty|professors?|instructors?|educators?|pedagogy|teaching quality|teaching style|teaching methods?|lectures?|delivery|faculty members?|commendable teaching)\b",
    ],
}

# Multi-word positive phrases (with word boundaries)
POSITIVE_PHRASES = [
    r"\bwell explained\b", r"\bexplains well\b", r"\bexplains clearly\b",
    r"\bexplains concepts clearly\b", r"\bexplains properly\b", r"\bclear explanation\b",
    r"\bclear explanations\b", r"\bsimple explanation\b", r"\bcrystal clear\b",
    r"\bgreat teaching\b", r"\bexceptional teaching\b", r"\beffective teaching\b",
    r"\bexcellent teaching\b", r"\bmakes learning easy\b", r"\beasy to understand\b",
    r"\beasy to follow\b", r"\bmakes concepts simple\b", r"\bteaching quality.*is commendable\b",
    r"\bapproachable and always willing\b", r"\bapproachable and willing\b",
    r"\bwilling to clarify\b", r"\balways willing to clarify\b", r"\balways willing to help\b",
    r"\balways ready to help\b", r"\bclears all doubts\b", r"\bclears doubts\b",
    r"\bclarifies doubts\b", r"\balways approachable\b", r"\balways available\b",
    r"\balways supportive\b", r"\bpatiently explains\b", r"\bpatiently answers\b",
    r"\bgenuinely care\b", r"\bgenuinely cares\b", r"\bcare about students\b",
    r"\bcares about students\b", r"\bacademic growth\b", r"\bencourage us\b",
    r"\bencourages us\b", r"\bencourages students\b", r"\bthink creatively\b",
    r"\bexplore beyond\b", r"\bbeyond the syllabus\b", r"\bactive learning\b",
    r"\binteractive sessions\b", r"\binteractive lectures\b", r"\binteractive discussions\b",
    r"\bengaging lectures\b", r"\bwell structured\b", r"\bwell-structured\b",
    r"\bwell organized\b", r"\bwell-organized\b", r"\bwell planned\b",
    r"\bwell prepared\b", r"\brelevant to industry\b", r"\bindustry relevant\b",
    r"\bindustry requirements\b", r"\bindustry standards\b", r"\bmodern technologies\b",
    r"\bcutting edge\b", r"\bpractical sessions are excellent\b", r"\bhands-on experience\b",
    r"\bhands on experience\b", r"\bpractical experience\b", r"\bpractical exposure\b",
    r"\breal-world application\b", r"\breal world application\b", r"\bgain confidence\b",
    r"\bconfidence in applying\b", r"\bapplying theoretical concepts\b", r"\bgreat lab\b",
    r"\bwell equipped\b", r"\bwonderful opportunities\b", r"\bgreat opportunities\b",
    r"\bexcellent opportunities\b", r"\bvaluable workshops\b", r"\bbeneficial seminars\b",
    r"\bcareer growth\b", r"\bcareer opportunities\b", r"\bcampus placements?\b",
    r"\btop notch\b", r"\bhighly recommend\b", r"\bdeep knowledge\b",
    r"\bvery knowledgeable\b", r"\binspiring teacher\b", r"\bhelped me secure\b",
    r"\bvaluable practical skills\b", r"\boutstanding career\b"
]

# Multi-word negative phrases (with word boundaries)
NEGATIVE_PHRASES = [
    r"\bnot clear\b", r"\bnot helpful\b", r"\bnot good\b", r"\bnot approachable\b",
    r"\bnot available\b", r"\bnot organized\b", r"\bnot enough\b", r"\bcannot understand\b",
    r"\bcan't understand\b", r"\bunable to understand\b", r"\bhard to understand\b",
    r"\bdifficult to understand\b", r"\btoo fast\b", r"\bway too fast\b", r"\bvery fast\b",
    r"\bgoing too fast\b", r"\bgoing fast\b", r"\btoo slow\b", r"\bwaste of time\b",
    r"\blacks? subject knowledge\b", r"\blacks? knowledge\b", r"\bdoes not care\b",
    r"\bdoesn't care\b", r"\bno practical\b", r"\black of practical\b",
    r"\bpoor infrastructure\b", r"\boutdated curriculum\b", r"\birrelevant to industry\b",
    r"\bcompletely irrelevant\b", r"\bunfair grading\b", r"\btoo difficult\b",
    r"\bexcessively difficult\b", r"\btoo strict\b", r"\bhard to follow\b",
    r"\bboring lectures\b", r"\bconfusing explanations\b", r"\bnever clarifies\b",
    r"\bdoes not clarify\b", r"\bdoesn't clarify\b", r"\bunwilling to help\b",
    r"\brude behavior\b", r"\bhardly explains\b", r"\brarely available\b",
    r"\bwaste of money\b", r"\bbroken equipment\b", r"\bfrequently crash(?:es)?\b",
    r"\bno campus placement\b", r"\bno internship opportunities\b", r"\bno opportunities\b"
]

POSITIVE_WORDS = {
    "excellent", "outstanding", "exceptional", "superb", "wonderful", "terrific",
    "amazing", "brilliant", "great", "good", "best", "perfect", "fantastic", "commendable",
    "helpful", "approachable", "supportive", "dedicated", "passionate", "caring",
    "patient", "patiently", "friendly", "polite", "kind", "encouraging", "motivating", "inspiring",
    "clear", "clearly", "effective", "useful", "valuable", "beneficial", "productive",
    "informative", "enriching", "engaging", "interactive", "knowledgeable", "expert",
    "structured", "organized", "relevant", "practical", "proficient", "skilled",
    "confidence", "creative", "creatively", "growth", "opportunity", "opportunities",
    "appreciate", "appreciated", "enjoy", "enjoyed", "love", "loved", "satisfying",
    "satisfied", "impressive", "clarify", "clarifies", "clarifying", "understand",
    "understood", "understanding", "well", "helps", "helped", "secure"
}

NEGATIVE_WORDS = {
    "bad", "poor", "terrible", "horrible", "awful", "worst", "useless", "ineffective",
    "unhelpful", "confusing", "unclear", "vague", "difficult", "hard", "complicated",
    "messy", "disorganized", "rushed", "boring", "dull", "monotonous", "strict",
    "harsh", "rude", "unapproachable", "unresponsive", "unavailable", "slow",
    "irrelevant", "outdated", "waste", "problem", "issue", "complaint", "frustrated",
    "frustrating", "disappointed", "disappointing", "lacking", "lack", "broken", "crash",
    "crashes", "unfair", "demanding"
}

NEGATION_TOKENS = {
    "not", "never", "no", "neither", "nor", "cannot", "can't", "doesn't",
    "does not", "didn't", "did not", "won't", "will not", "isn't", "is not",
    "aren't", "are not", "wasn't", "was not", "weren't", "were not", "hardly",
    "scarcely", "barely", "without", "rarely"
}

HINDI_TELUGU_POSITIVE = [
    "बहुत अच्छी", "अच्छा", "अच्छी", "अच्छा समझाते", "बहुत अच्छा", "उत्कृष्ट",
    "బాగా బోధిస్తారు", "చాలా బాగా", "బాగుంది", "మంచిది", "అద్భుతం"
]

HINDI_TELUGU_NEGATIVE = [
    "खराब", "समझ नहीं आया", "बेकार", "कठिन", "बुरा",
    "బాగా లేదు", "అర్థం కాలేదు", "చెడ్డది", "కష్టం"
]

SUGGESTION_PATTERN = re.compile(
    r"\b(should|could|please|more|less|need|needs|wish|suggest|recommend|would help|would be better)\b",
    re.I
)

TEACHER_GUIDANCE = {
    "Teaching effectiveness": {
        "positive": "Continue sustaining the teaching habits students value and ask what helps them learn most.",
        "concern": "Ask students for a concrete example, then choose one teaching change to try and review.",
        "neutral": "Ask students to name one teaching practice that is working and one they would change.",
    },
    "Teaching clarity": {
        "positive": "Build on clear explanations with worked examples and quick checks for understanding.",
        "concern": "Break complex explanations into stepwise examples and pause for understanding checks.",
        "neutral": "Ask which topic needs another example, then revisit it briefly with the class.",
    },
    "Student engagement": {
        "positive": "Keep encouraging active participation, creative thinking, and classroom discussion.",
        "concern": "Incorporate interactive questions, short discussions, and practical prompts to stimulate participation.",
        "neutral": "Introduce low-pressure discussion prompts to encourage more student interaction.",
    },
    "Doubt clarification": {
        "positive": "Maintain the approachable atmosphere and regular opportunities for clarifying questions.",
        "concern": "Dedicate specific time segments for questions and clarify how students can seek help.",
        "neutral": "Reiterate available question channels and verify that all students know how to seek clarification.",
    },
    "Subject knowledge": {
        "positive": "Continue connecting deep conceptual knowledge to real-world context and applications.",
        "concern": "Review core theoretical fundamentals with worked examples and address common sticking points.",
        "neutral": "Check whether students want deeper theoretical coverage or more contextual examples.",
    },
    "Practical learning": {
        "positive": "Keep offering rich hands-on exercises and lab sessions that build student confidence.",
        "concern": "Increase hands-on lab time and guide students through applying theoretical concepts practically.",
        "neutral": "Ask which practical exercises or demonstrations would make concepts easier to apply.",
    },
    "Course organization": {
        "positive": "Maintain the structured curriculum plan, timely syllabus coverage, and organized materials.",
        "concern": "Clarify the course roadmap, maintain consistent pacing, and announce schedule adjustments early.",
        "neutral": "Provide an updated syllabus checklist to help students track course milestones.",
    },
    "Learning environment": {
        "positive": "Preserve the welcoming, respectful, and supportive classroom environment.",
        "concern": "Address classroom climate or noise disruptions to ensure a focused learning atmosphere.",
        "neutral": "Check in with students regarding classroom comfort and learning conditions.",
    },
    "Academic support": {
        "positive": "Continue providing genuine mentoring, student care, and individual academic guidance.",
        "concern": "Provide clearer academic mentoring and guidance for students requiring extra help.",
        "neutral": "Remind students of academic support hours and guidance resources.",
    },
    "Industry relevance": {
        "positive": "Continue aligning curriculum topics with modern industry requirements and job market skills.",
        "concern": "Update course modules with current industry tools, real-world case studies, and modern standards.",
        "neutral": "Incorporate industry guest lectures or real-world problem sets into the curriculum.",
    },
    "Infrastructure": {
        "positive": "Ensure continued maintenance of excellent lab equipment, facilities, and campus resources.",
        "concern": "Report and resolve hardware, software, Wi-Fi, or equipment issues in labs and classrooms.",
        "neutral": "Periodically audit lab systems, software versions, and facility readiness.",
    },
    "Career opportunities": {
        "positive": "Continue facilitating workshops, seminars, internship pathways, and career development events.",
        "concern": "Expand access to technical workshops, internship guidance, and career preparation opportunities.",
        "neutral": "Inform students about upcoming seminars, technical events, and internship openings.",
    },
}

def _sentences(text: str) -> List[str]:
    clean = re.sub(r"\s+", " ", str(text or "")).strip()
    if not clean:
        return []
    # Split by sentence enders first
    raw_sentences = [s.strip() for s in re.split(r"[.!?;\n]+", clean) if s.strip()]
    clauses = []
    for s in raw_sentences:
        # Split on contrastive conjunctions like "but", "however", "although", "whereas", "though", "yet"
        parts = re.split(r"\b(?:but|however|although|whereas|though|yet)\b", s, flags=re.I)
        for part in parts:
            p = part.strip().strip(",- ")
            if p:
                clauses.append(p)
    return clauses or [clean]


def _clause_polarity(clause: str) -> Tuple[str, float, float]:
    lower = clause.lower()
    pos_score = 0.0
    neg_score = 0.0

    # 1. Match multi-word negative regex
    for pattern in NEGATIVE_PHRASES:
        if re.search(pattern, lower):
            neg_score += 2.5

    # 2. Match multi-word positive regex
    for pattern in POSITIVE_PHRASES:
        if re.search(pattern, lower):
            # Check for negation preceding pattern
            match = re.search(pattern, lower)
            start_pos = match.start()
            prefix = lower[max(0, start_pos - 15):start_pos].strip()
            if any(prefix.endswith(neg) for neg in ["not", "never", "no", "hardly", "without"]):
                neg_score += 2.5
            else:
                pos_score += 2.5

    # 3. Multilingual phrase checks
    for p in HINDI_TELUGU_POSITIVE:
        if p in clause:
            pos_score += 2.5
    for p in HINDI_TELUGU_NEGATIVE:
        if p in clause:
            neg_score += 2.5

    # 4. Token-level analysis with negation scope
    words = re.findall(r"[a-z']+", lower)
    neg_scope = 0
    for i, word in enumerate(words):
        if word in NEGATION_TOKENS:
            neg_scope = 3
            continue
        
        # Special case: "explains difficult concepts" -> "difficult" modifies "concepts", not a negative complaint
        if word in ("difficult", "hard") and i + 1 < len(words) and words[i + 1] in ("concept", "concepts", "topics", "problems"):
            if i > 0 and words[i - 1] in ("explains", "clarifies", "teaching", "understands", "tackles"):
                continue  # Skip counting difficult as negative when explained well

        if word in POSITIVE_WORDS:
            if neg_scope > 0:
                neg_score += 1.2
            else:
                pos_score += 1.0
        elif word in NEGATIVE_WORDS:
            if neg_scope > 0:
                pos_score += 0.8  # e.g., "not bad"
            else:
                neg_score += 1.0

        if neg_scope > 0:
            neg_scope -= 1

    # 5. Determine label
    if pos_score > 0 and neg_score > 0:
        if pos_score >= 2.0 * neg_score:
            return "positive", pos_score, neg_score
        elif neg_score >= 2.0 * pos_score:
            return "negative", pos_score, neg_score
        else:
            return "mixed", pos_score, neg_score
    elif pos_score > 0:
        return "positive", pos_score, 0.0
    elif neg_score > 0:
        return "negative", 0.0, neg_score
    else:
        return "neutral", 0.0, 0.0


def analyze(text: str) -> Dict[str, Any]:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return {
            "sentiment": "neutral",
            "confidence": 0.0,
            "aspects": [],
            "strengths": [],
            "improvements": [],
            "suggestions": [],
            "concerns": [],
            "quality": {"short": True},
            "method": "Explainable contextual sentence and phrase rules",
            "review": "The comment is empty.",
            "improvement_suggestions": [],
        }

    clauses = _sentences(text)
    clause_results = []
    clause_labels = []
    total_pos = 0.0
    total_neg = 0.0

    for clause in clauses:
        label, pos, neg = _clause_polarity(clause)
        total_pos += pos
        total_neg += neg
        clause_results.append((clause, label, pos, neg))
        clause_labels.append(label)

    # Has contrastive conjunction like "but", "however"?
    has_contrast = bool(re.search(r"\b(?:but|however|although|whereas|though|yet)\b", text, re.I))

    # Overall sentiment resolution
    if has_contrast and "positive" in clause_labels and "negative" in clause_labels:
        overall = "mixed"
    elif total_pos > 0 and total_neg > 0:
        if total_pos >= 2.2 * total_neg:
            overall = "positive"
        elif total_neg >= 2.2 * total_pos:
            overall = "negative"
        else:
            overall = "mixed"
    elif total_pos > 0:
        overall = "positive"
    elif total_neg > 0:
        overall = "negative"
    else:
        overall = "neutral"

    # Match aspects
    matched_aspects = []
    lower_text = text.lower()

    for aspect in ASPECTS:
        patterns = ASPECT_PATTERNS.get(aspect, [])
        aspect_clauses = []
        for clause, cl_label, cl_pos, cl_neg in clause_results:
            c_lower = clause.lower()
            if any(re.search(pat, c_lower, re.I) for pat in patterns):
                aspect_clauses.append((clause, cl_label, cl_pos, cl_neg))

        if not aspect_clauses and any(re.search(pat, lower_text, re.I) for pat in patterns):
            aspect_clauses.append((text, overall, total_pos, total_neg))

        if aspect_clauses:
            labels = [ac[1] for ac in aspect_clauses if ac[1] != "neutral"]
            if "mixed" in labels or ("positive" in labels and "negative" in labels):
                a_sentiment = "mixed"
            elif "positive" in labels:
                a_sentiment = "positive"
            elif "negative" in labels:
                a_sentiment = "negative"
            else:
                a_sentiment = overall if overall in ("positive", "negative") else "neutral"

            evidence = list(dict.fromkeys(ac[0] for ac in aspect_clauses))
            score_sum = sum(ac[2] + ac[3] for ac in aspect_clauses)
            a_conf = round(min(0.92, 0.70 + 0.05 * score_sum), 2)
            matched_aspects.append({
                "aspect": aspect,
                "sentiment": a_sentiment,
                "confidence": a_conf,
                "evidence": evidence,
            })

    # Calibrated confidence calculation
    signal_strength = total_pos + total_neg
    if overall in ("positive", "negative"):
        confidence = round(min(0.92, 0.72 + 0.03 * signal_strength + 0.01 * len(clauses)), 2)
    elif overall == "mixed":
        confidence = round(min(0.85, 0.68 + 0.03 * signal_strength), 2)
    else:
        confidence = 0.72 if len(text.split()) >= 4 else 0.58

    strengths = [a["aspect"] for a in matched_aspects if a["sentiment"] == "positive"]
    improvements = [a["aspect"] for a in matched_aspects if a["sentiment"] in ("negative", "mixed")]
    suggestions = [a["aspect"] for a in matched_aspects if any(SUGGESTION_PATTERN.search(e) for e in a["evidence"])]
    concerns = [a["aspect"] for a in matched_aspects if a["sentiment"] == "negative"]

    return {
        "sentiment": overall,
        "confidence": confidence,
        "aspects": matched_aspects,
        "strengths": strengths,
        "improvements": improvements,
        "suggestions": suggestions,
        "concerns": concerns,
        "review": review_summary(overall, matched_aspects),
        "improvement_suggestions": teacher_improvement_suggestions(matched_aspects, overall),
        "quality": {"short": len(re.findall(r"\w+", text)) < 3},
        "method": "Explainable contextual sentence and phrase rules",
    }


def _join_aspects(names: List[str]) -> str:
    names = list(dict.fromkeys(names))
    if len(names) < 2:
        return names[0] if names else "the course"
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def review_summary(sentiment: str, aspects: List[Dict[str, Any]]) -> str:
    strengths = [item["aspect"] for item in aspects if item.get("sentiment") == "positive"]
    concerns = [item["aspect"] for item in aspects if item.get("sentiment") in ("negative", "mixed")]
    matched = [item["aspect"] for item in aspects]

    if sentiment == "positive":
        if strengths:
            return f"Positive feedback highlights {_join_aspects(strengths)}."
        return "The comment is positive overall, reflecting general satisfaction."
    if sentiment == "negative":
        if concerns:
            return f"The feedback raises concerns about {_join_aspects(concerns)}."
        return "The comment is negative overall; review the comment text for details."
    if sentiment == "mixed":
        if strengths and concerns:
            return f"The feedback praises {_join_aspects(strengths)} while highlighting concerns in {_join_aspects(concerns)}."
        return "The feedback contains mixed opinions across different aspects."
    if matched:
        return f"The comment references {_join_aspects(matched)} without expressing strong sentiment."
    return "The feedback expresses a neutral or factual observation."


def teacher_improvement_suggestions(aspects: List[Dict[str, Any]], overall_sentiment: str = "neutral") -> List[str]:
    concerns = [item for item in aspects if item.get("sentiment") in ("negative", "mixed")]
    if not concerns:
        if overall_sentiment == "positive":
            strengths = [item.get("aspect") for item in aspects if item.get("sentiment") == "positive"]
            if strengths:
                return [f"Continue sustaining excellence and effective practices in {_join_aspects(strengths)}."]
            return ["Continue sustaining positive learning practices and student engagement."]
        return []

    suggestions = []
    for item in concerns:
        aspect = item.get("aspect")
        guidance = TEACHER_GUIDANCE.get(aspect, {}).get("concern")
        if guidance and guidance not in suggestions:
            suggestions.append(guidance)
    return suggestions[:3]
