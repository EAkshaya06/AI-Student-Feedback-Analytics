const feedbackText = () => document.getElementById("feedbackText").value.trim();
const escapeHTML = value => { const node = document.createElement("span"); node.textContent = value; return node.innerHTML; };

function showAnalysis(data, submitted = false) {
    const aspects = (data.aspects || []).map(item => `
      <article class="aspect-result"><div><strong>${escapeHTML(item.aspect)}</strong><span class="sentiment-pill ${escapeHTML(item.sentiment)}">${escapeHTML(item.sentiment)}</span></div>
      <p>${(item.evidence || []).map(escapeHTML).join(" · ")}</p><small>Confidence ${Math.round(item.confidence * 100)}%</small></article>`).join("");
    document.getElementById("analysisResult").innerHTML = `
      <section class="analysis-summary"><span class="eyebrow">${submitted ? "Feedback received" : "Evidence-based preview"}</span>
      <h2>${escapeHTML(data.sentiment)} overall <span class="confidence">${Math.round(data.confidence * 100)}% confidence</span></h2>
      ${data.confidence < .6 ? '<p class="low-confidence">Analysis confidence is low. This feedback may contain multiple topics or language outside the current phrase rules.</p>' : ""}
      <p>Method: ${escapeHTML(data.method)}. Results are estimates, not a perfect understanding of every sentence.</p>
      <div class="aspect-results">${aspects || '<p>No configured teaching aspect matched. Your text is retained as written.</p>'}</div>
      ${submitted ? `<p class="success-note">${escapeHTML(data.message)}</p>` : ""}</section>`;
}

async function analyzeFeedback() {
    const text = feedbackText();
    if (!text) { document.getElementById("analysisResult").textContent = "Please enter feedback before previewing."; return; }
    const button = document.getElementById("analyzeButton");
    button.disabled = true; button.textContent = "Analyzing…";
    try {
        const response = await fetch("/api/analyze", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({text})});
        const data = await response.json(); if (!response.ok) throw new Error(data.message || "Analysis failed"); showAnalysis(data);
    } catch (error) { document.getElementById("analysisResult").textContent = error.message; }
    finally { button.disabled = false; button.textContent = "Preview analysis"; }
}

async function submitFeedback() {
    const text = feedbackText();
    if (!text) { document.getElementById("analysisResult").textContent = "Please enter feedback before submitting."; return; }
    const button = document.getElementById("submitButton"); button.disabled = true; button.textContent = "Submitting…";
    const payload = {text, department:document.getElementById("departmentField").value, course:document.getElementById("courseField").value,
        faculty:document.getElementById("facultyField").value, anonymous:true};
    try {
        const response = await fetch("/api/feedback", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
        const data = await response.json(); if (!response.ok) throw new Error(data.message || "Submission failed");
        showAnalysis({...data.analysis, message:data.message}, true);
    } catch (error) { document.getElementById("analysisResult").textContent = error.message; }
    finally { button.disabled = false; button.textContent = "Submit feedback"; }
}
