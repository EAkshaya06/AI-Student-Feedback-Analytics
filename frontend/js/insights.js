const safe = value => { const node = document.createElement("span"); node.textContent = value; return node.innerHTML; };
function themeItems(id, names, summary) {
    const target = document.getElementById(id);
    target.innerHTML = names.length ? names.map(name => `<div class="theme-item"><strong>${safe(name)}</strong><span>${summary[name].mentions} mentions</span></div>`).join("") : '<p class="empty-state">No submitted feedback has evidence for this yet.</p>';
}
async function loadInsights() {
    const status = document.getElementById("insightStatus"); status.textContent = "Loading current insights…";
    try {
        const identity = await fetch("/api/auth/me");
        if (identity.status === 401) { window.location.assign("/login"); return; }
        const identityData = await identity.json();
        document.getElementById("staffName").textContent = identityData.user?.name || "Staff";
        if (identityData.user?.role !== "admin") document.getElementById("adminAnalyticsLink")?.remove();
        const response = await fetch("/api/insights");
        if (!response.headers.get("content-type")?.includes("application/json")) throw new Error("Insight service is unavailable. Start the Flask app to load stored feedback.");
        const data = await response.json(); if (!response.ok || !data.success) throw new Error("Insight data could not be loaded.");
        themeItems("strengths", data.strengths, data.aspects); themeItems("improvements", data.improvement_areas, data.aspects); themeItems("suggestions", data.student_suggestions, data.aspects);
        const grid = document.getElementById("aspectGrid"); const aspects = Object.entries(data.aspects);
        grid.innerHTML = aspects.length ? aspects.map(([name, counts]) => `<article class="aspect-card"><div class="aspect-title"><strong>${safe(name)}</strong><span>${counts.mentions} mentions</span></div><div class="sentiment-counts"><span class="positive">${counts.positive || 0} positive</span><span class="neutral">${counts.neutral || 0} neutral</span><span class="negative">${counts.negative || 0} negative</span><span>${counts.improvement || 0} suggestions</span><span>${counts.mixed || 0} mixed</span></div></article>`).join("") : '<p class="empty-state">No submissions yet. Share a sample response through the student flow to populate this view.</p>';
        status.textContent = `${data.stored_feedback_count} submitted responses · ${data.method}`;
    } catch (error) { status.textContent = error.message; status.classList.add("error"); }
}
document.getElementById("logoutButton")?.addEventListener("click", async () => {
    await fetch("/api/auth/logout", {method:"POST"});
    window.location.assign("/login");
});
document.addEventListener("DOMContentLoaded", loadInsights);
