const escapeHTML = value => {
    const node = document.createElement("span");
    node.textContent = String(value ?? "");
    return node.innerHTML;
};

function getFeedbackInput() {
    const email = document.getElementById("facultyEmailField").value.trim().toLowerCase();
    const comments = document.getElementById("feedbackText").value
        .split(/\r?\n/)
        .map(comment => comment.trim())
        .filter(Boolean);
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new Error("Enter a valid teacher email address.");
    if (!comments.length) throw new Error("Paste at least one student comment, one per line.");
    if (comments.length > 25) throw new Error("Analyze up to 25 comments at a time.");
    if (comments.some(comment => comment.length > 5000) || comments.join("").length > 20000) {
        throw new Error("Keep each comment under 5,000 characters and the total under 20,000 characters.");
    }
    return {
        teacher_email: email || "",
        comments,
        department: document.getElementById("departmentField").value.trim(),
        course: document.getElementById("courseField").value.trim()
    };
}

function showAnalysis(data, submitted = false) {
    const aspects = (data.aspects || []).map(item =>
        "<article class='aspect-result'><div><strong>" + escapeHTML(item.aspect) +
        "</strong><span class='sentiment-pill " + escapeHTML(item.sentiment) + "'>" +
        escapeHTML(item.sentiment) + "</span></div><p>" +
        (item.evidence || []).map(escapeHTML).join(" · ") +
        "</p><small>" + (item.mentions ? item.mentions + " comment(s) · " : "") +
        "Confidence " + Math.round((item.confidence || 0) * 100) + "%</small></article>"
    ).join("");
    const counts = data.sentiment_counts || {};
    const summaryCounts = "<div class='batch-counts'>" +
        "<span>" + (counts.positive || 0) + " positive</span>" +
        "<span>" + (counts.neutral || 0) + " neutral</span>" +
        "<span>" + (counts.negative || 0) + " negative</span>" +
        "<span>" + (counts.mixed || 0) + " mixed</span></div>";
    const commentResults = (data.results || []).map((item, index) =>
        "<article class='batch-comment'><div><strong>Comment " + (index + 1) +
        "</strong><span class='sentiment-pill " + escapeHTML(item.sentiment) + "'>" +
        escapeHTML(item.sentiment) + "</span></div><p>" + escapeHTML(item.feedback) + "</p>" +
        ((item.aspects || []).length ? "<small>" + item.aspects.map(aspect =>
            escapeHTML(aspect.aspect) + ": " + escapeHTML(aspect.sentiment)
        ).join(" · ") + "</small>" : "") + "</article>"
    ).join("");
    const emailLine = data.teacher_email
        ? "<p class='report-teacher'>Teacher: " + escapeHTML(data.teacher_email) + " · " +
          (data.total || 0) + " student comment(s)</p>"
        : "";
    document.getElementById("analysisResult").innerHTML =
        "<section class='analysis-summary'><span class='eyebrow'>" +
        (submitted ? "Feedback received" : "Evidence-based analysis") +
        "</span><h2>" + escapeHTML(data.sentiment) + " overall <span class='confidence'>" +
        Math.round((data.confidence || 0) * 100) + "% confidence</span></h2>" +
        emailLine +
        (data.confidence < .6 ? "<p class='low-confidence'>Analysis confidence is low. Review the original comments before drawing conclusions.</p>" : "") +
        summaryCounts +
        "<p>Method: " + escapeHTML(data.method || "Explainable phrase analysis") +
        ". Results are estimates, not a perfect understanding of every sentence.</p>" +
        "<h3>Teaching aspects</h3><div class='aspect-results'>" +
        (aspects || "<p>No configured teaching aspect matched these comments.</p>") +
        "</div>" +
        (commentResults ? "<h3 class='batch-heading'>Comment-by-comment results</h3><div class='batch-results'>" +
            commentResults + "</div>" : "") +
        (submitted ? "<p class='success-note'>" + escapeHTML(data.message) + "</p>" : "") +
        "</section>";
}

async function analyzeFeedback() {
    let payload;
    try {
        payload = getFeedbackInput();
    } catch (error) {
        document.getElementById("analysisResult").textContent = error.message;
        return;
    }
    const button = document.getElementById("analyzeButton");
    button.disabled = true;
    button.textContent = "Analyzing…";
    try {
        const response = await fetch("/api/analyze", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || "Analysis failed.");
        showAnalysis(data);
    } catch (error) {
        document.getElementById("analysisResult").textContent = error.message;
    } finally {
        button.disabled = false;
        button.textContent = "Analyze comments";
    }
}

async function submitFeedback() {
    let payload;
    try {
        payload = getFeedbackInput();
    } catch (error) {
        document.getElementById("analysisResult").textContent = error.message;
        return;
    }
    const button = document.getElementById("submitButton");
    button.disabled = true;
    button.textContent = "Submitting…";
    try {
        const response = await fetch("/api/feedback", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({...payload, anonymous: true})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || "Submission failed.");
        showAnalysis({
            ...data.analysis,
            teacher_email: payload.teacher_email,
            message: data.message
        }, true);
    } catch (error) {
        document.getElementById("analysisResult").textContent = error.message;
    } finally {
        button.disabled = false;
        button.textContent = "Submit feedback";
    }
}
