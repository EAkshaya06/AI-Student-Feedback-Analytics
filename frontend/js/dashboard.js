const charts = {};
let staffRole = "";

document.addEventListener("DOMContentLoaded", initializeDashboard);

async function initializeDashboard() {
  try {
    const session = await refreshSession();
    if (!session.authenticated) return window.location.assign("/login?next=%2Fdashboard");
    staffRole = session.role || "faculty";
    document.getElementById("dashboardWelcome").textContent = staffRole === "admin"
      ? "Administrator view · historical data, live submissions, and evidence-backed insights."
      : `Faculty view · live submissions assigned to ${session.email}.`;
    if (staffRole === "faculty") {
      const source = document.getElementById("sourceFilter");
      [...source.options].filter((option) => option.value !== "live").forEach((option) => option.remove());
      source.value = "live";
      document.getElementById("facultyFilter").disabled = true;
    } else {
      document.getElementById("facultyAdminSection").hidden = false;
    }
    const datesEnabled = ["live", "all"].includes(document.getElementById("sourceFilter").value);
    document.getElementById("dateFromFilter").disabled = !datesEnabled;
    document.getElementById("dateToFilter").disabled = !datesEnabled;
    document.getElementById("applyFiltersButton").addEventListener("click", loadDashboard);
    document.getElementById("refreshButton").addEventListener("click", loadDashboard);
    document.getElementById("resetFiltersButton").addEventListener("click", resetFilters);
    document.getElementById("sourceFilter").addEventListener("change", sourceChanged);
    document.getElementById("pdfButton").addEventListener("click", downloadReport);
    document.getElementById("logoutButton").addEventListener("click", signOut);
    await loadDashboard();
    if (staffRole === "admin") await loadFacultyAccounts();
  } catch (error) {
    showDashboardError(error.message || "The dashboard could not be opened.");
  }
}

async function sourceChanged() {
  ["departmentFilter", "yearFilter", "semesterFilter", "subjectFilter", "facultyFilter"].forEach((id) => {
    document.getElementById(id).value = "";
  });
  document.getElementById("dateFromFilter").value = "";
  document.getElementById("dateToFilter").value = "";
  const supportsDates = ["live", "all"].includes(document.getElementById("sourceFilter").value);
  document.getElementById("dateFromFilter").disabled = !supportsDates;
  document.getElementById("dateToFilter").disabled = !supportsDates;
  await loadDashboard();
}

function currentQuery() {
  const query = new URLSearchParams({ source: document.getElementById("sourceFilter").value });
  const fields = {
    department: "departmentFilter",
    academic_year: "yearFilter",
    semester: "semesterFilter",
    subject: "subjectFilter",
    faculty: "facultyFilter",
    date_from: "dateFromFilter",
    date_to: "dateToFilter",
  };
  Object.entries(fields).forEach(([key, id]) => {
    const value = document.getElementById(id).value;
    if (value) query.set(key, value);
  });
  return query.toString();
}

async function loadDashboard() {
  const status = document.getElementById("dashboardStatus");
  status.classList.remove("error");
  status.textContent = "Updating dashboard…";
  document.getElementById("filterState").textContent = "Loading selected data…";
  try {
    const query = currentQuery();
    const response = await apiRequest(`/api/analytics?${query}`);
    const analytics = await response.json();
    if (response.status === 401) return window.location.assign("/login?next=%2Fdashboard");
    if (!response.ok || !analytics.success) throw new Error(analytics.message || "Analytics could not be loaded.");
    updateFilterOptions(analytics.filter_options || {});
    renderDashboard(analytics);
    await loadRecentFeedback(query);
    if (staffRole === "admin") await loadFacultyAccounts();
    status.textContent = "Dashboard updated.";
  } catch (error) {
    status.textContent = error.message || "Unable to load dashboard data.";
    status.classList.add("error");
    document.getElementById("filterState").textContent = "Could not load the selected data.";
  }
}

function updateFilterOptions(options) {
  const selectConfig = [
    ["departmentFilter", options.department || [], "All departments"],
    ["yearFilter", options.academic_year || [], "All academic years"],
    ["semesterFilter", options.semester || [], "All semesters"],
    ["subjectFilter", options.subject || [], "All subjects"],
    ["facultyFilter", options.faculty || [], "All faculty"],
  ];
  for (const [id, values, placeholder] of selectConfig) {
    const select = document.getElementById(id);
    const selected = select.value;
    select.replaceChildren(new Option(placeholder, ""));
    values.forEach((value) => select.add(new Option(value, value)));
    select.value = values.includes(selected) ? selected : "";
    if (!(staffRole === "faculty" && id === "facultyFilter")) select.disabled = values.length === 0;
  }
}

function renderDashboard(data) {
  const counts = data.sentiment || {};
  document.getElementById("totalFeedback").textContent = Number(data.total || 0).toLocaleString();
  document.getElementById("positiveFeedback").textContent = `${data.positive_percentage || 0}%`;
  document.getElementById("neutralFeedback").textContent = `${data.neutral_percentage || 0}%`;
  document.getElementById("negativeFeedback").textContent = `${data.negative_percentage || 0}%`;
  document.getElementById("filterState").textContent = `${Number(data.total || 0).toLocaleString()} records · ${data.data_source_label || "Selected source"}`;
  document.getElementById("sourceDescription").textContent = `${data.data_source_label || "Selected data"}. Sentiment percentages use ${Number(data.sentiment_total || 0)} analyzable comments. Sources are combined only when the combined option is selected.`;
  const notes = [...(data.notes || [])];
  if (Number(data.unsupported_sentiment_count || 0) > 0) {
    notes.push(`${Number(data.unsupported_sentiment_count)} comment${Number(data.unsupported_sentiment_count) === 1 ? " was" : "s were"} excluded from sentiment percentages because the language could not be analyzed reliably.`);
  }
  document.getElementById("dataSourceNote").textContent = notes.join(" ");

  drawChart("sentimentChart", "doughnut", Object.keys(counts), [{ label: "Feedback", data: Object.values(counts), backgroundColor: ["#2a8178", "#a8b4c2", "#d65d5d"] }], "sentimentEmpty");
  const aspects = data.aspect_distribution || {};
  drawChart("aspectChart", "bar", Object.keys(aspects), sentimentDatasets(aspects), "aspectEmpty", { indexAxis: "y", scales: { x: { stacked: true, beginAtZero: true }, y: { stacked: true } } });
  drawGroupedChart("departmentChart", data.department_analysis || {}, "departmentEmpty");
  drawGroupedChart("semesterChart", data.semester_analysis || {}, "semesterEmpty");
  drawGroupedChart("subjectChart", data.subject_analysis || {}, "subjectEmpty");
  const monthly = data.monthly_trend || {};
  drawChart("trendChart", "line", Object.keys(monthly), sentimentDatasets(monthly), "trendEmpty", { scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } });
  const categories = data.sentiment_by_category || {};
  drawChart("categoryChart", "bar", Object.keys(categories), sentimentDatasets(categories), "categoryEmpty", { indexAxis: "y", scales: { x: { stacked: true, beginAtZero: true }, y: { stacked: true } } });
  const emotion = data.emotion || {};
  drawChart("emotionChart", "doughnut", Object.keys(emotion), [{ label: "Feedback", data: Object.values(emotion), backgroundColor: palette }], "emotionEmpty");
  renderInsights(data.insights || {});
  renderSemesterAspectTable(data.aspect_by_semester || []);
  loadRecommendations(currentQuery());
}

const palette = ["#2a8178", "#a8b4c2", "#d65d5d", "#4f78b8", "#d7a947", "#775da8", "#4a968b", "#ca8051", "#5480a6", "#6f8791"];

function sentimentDatasets(groups) {
  return [
    { label: "Positive", data: Object.values(groups).map((item) => Number(item.positive || 0)), backgroundColor: "#2a8178" },
    { label: "Neutral", data: Object.values(groups).map((item) => Number(item.neutral || 0)), backgroundColor: "#a8b4c2" },
    { label: "Negative", data: Object.values(groups).map((item) => Number(item.negative || 0)), backgroundColor: "#d65d5d" },
  ];
}

function drawGroupedChart(id, grouped, emptyId) {
  const labels = Object.keys(grouped);
  const datasets = sentimentDatasets(grouped);
  drawChart(id, "bar", labels, datasets, emptyId, { scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } } } });
}

function drawChart(id, type, labels, datasets, emptyId, extraOptions = {}) {
  const canvas = document.getElementById(id);
  const empty = document.getElementById(emptyId);
  const hasData = labels.length > 0 && datasets.some((dataset) => dataset.data.some((value) => Number(value) > 0));
  canvas.hidden = !hasData;
  empty.hidden = hasData;
  if (!hasData) {
    if (charts[id]) charts[id].destroy();
    charts[id] = null;
    return;
  }
  if (typeof Chart === "undefined") {
    canvas.hidden = true;
    empty.hidden = false;
    empty.textContent = "Chart.js did not load. Refresh the page to try again.";
    return;
  }
  if (charts[id]) charts[id].destroy();
  const defaultOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: type !== "line" || datasets.length > 1, position: "bottom" } },
    scales: type === "doughnut" ? undefined : { y: { beginAtZero: true, ticks: { precision: 0 } } },
  };
  charts[id] = new Chart(canvas, { type, data: { labels, datasets }, options: mergeOptions(defaultOptions, extraOptions) });
}

function mergeOptions(base, extra) {
  return {
    ...base,
    ...extra,
    plugins: { ...(base.plugins || {}), ...(extra.plugins || {}) },
    scales: extra.scales || base.scales,
  };
}

function renderInsights(insights) {
  const container = document.getElementById("insightsContainer");
  const blocks = [];
  if (insights.trend) blocks.push(`<div class="insight-item"><span>📈</span><div><strong>Trend</strong><p>${escapeHTML(insights.trend.message)}</p></div></div>`);
  (insights.strengths || []).forEach((item) => blocks.push(renderEvidenceItem("Strength", item, "✓")));
  (insights.improvement_areas || []).forEach((item) => blocks.push(renderEvidenceItem("Concern", item, "↗")));
  container.innerHTML = blocks.length ? blocks.join("") : '<p class="empty-state">There is not enough aspect-level evidence to summarize this selection.</p>';
}

function renderEvidenceItem(kind, item, icon) {
  const evidence = (item.evidence || []).map((quote) => `<blockquote>“${escapeHTML(quote)}”</blockquote>`).join("");
  return `<div class="insight-item"><span aria-hidden="true">${icon}</span><div><strong>${escapeHTML(kind)} · ${escapeHTML(item.aspect)} (${Number(item.mentions)} mentions)</strong>${evidence || '<p>No quote available.</p>'}</div></div>`;
}

function renderSemesterAspectTable(rows) {
  const container = document.getElementById("aspectSemesterTable");
  if (!rows.length) {
    container.innerHTML = '<p class="empty-state">There is not enough aspect and semester metadata for this comparison.</p>';
    return;
  }
  container.innerHTML = `<div class="table-scroll"><table class="feedback-table"><thead><tr><th>Aspect</th><th>Semester</th><th>Positive</th><th>Neutral</th><th>Negative</th><th>Total mentions</th></tr></thead><tbody>${rows.map((row) => `<tr><td>${escapeHTML(row.aspect)}</td><td>${escapeHTML(row.semester)}</td><td>${Number(row.positive)}</td><td>${Number(row.neutral)}</td><td>${Number(row.negative)}</td><td>${Number(row.total)}</td></tr>`).join("")}</tbody></table></div>`;
}

async function loadRecommendations(query) {
  const container = document.getElementById("recommendations");
  try {
    const response = await apiRequest(`/api/recommendations?${query}`);
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.message || "Summary could not be loaded.");
    const rows = (data.recommendations || []).map((item) => `
      <div class="insight-item"><span>↗</span><div><strong>${escapeHTML(item.topic)} · ${Number(item.mentions)} comments</strong><p>${escapeHTML(item.suggestion)}</p>${(item.evidence || []).map((quote) => `<blockquote>“${escapeHTML(quote)}”</blockquote>`).join("")}</div></div>`);
    const strengths = (data.insights?.strengths || []).map((item) => `<div class="insight-item"><span>✓</span><div><strong>${escapeHTML(item.aspect)} · ${Number(item.mentions)} positive mentions</strong>${(item.evidence || []).map((quote) => `<blockquote>“${escapeHTML(quote)}”</blockquote>`).join("")}</div></div>`);
    container.innerHTML = [...strengths, ...rows].join("") || '<p class="empty-state">No aspect-level strengths or concerns can be supported by this selection yet.</p>';
  } catch (error) {
    container.textContent = error.message || "Unable to load insights.";
  }
}

async function loadRecentFeedback(query) {
  const container = document.getElementById("feedbackTableContainer");
  try {
    const response = await apiRequest(`/api/feedback?${query}&limit=10`);
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.message || "Feedback could not be loaded.");
    if (!data.data?.length) {
      container.innerHTML = '<p class="empty-state">No feedback records match these filters.</p>';
      return;
    }
    const rows = data.data.slice(0, 10).map((item) => `
      <tr><td>${escapeHTML(item.feedback)}</td><td>${escapeHTML(item.department || "—")}</td><td>${escapeHTML(item.subject || item.category || "—")}</td><td><span class="sentiment-pill ${item.sentiment_supported ? escapeHTML(item.sentiment) : "unsupported"}">${item.sentiment_supported ? escapeHTML(item.sentiment) : "Not analyzed"}</span></td><td>${escapeHTML(item.source === "live" ? "Live submission" : "Historical/demo")}</td></tr>`).join("");
    container.innerHTML = `<div class="table-scroll"><table class="feedback-table"><thead><tr><th>Feedback</th><th>Department</th><th>Subject / category</th><th>Sentiment</th><th>Source</th></tr></thead><tbody>${rows}</tbody></table></div><p class="field-hint">Showing up to 10 of ${Number(data.count).toLocaleString()} authorized records.</p>`;
  } catch (error) {
    container.textContent = error.message || "Unable to load feedback.";
  }
}

function resetFilters() {
  ["departmentFilter", "yearFilter", "semesterFilter", "subjectFilter", "facultyFilter", "dateFromFilter", "dateToFilter"].forEach((id) => {
    document.getElementById(id).value = "";
  });
  loadDashboard();
}

function downloadReport() {
  window.location.assign(`/api/report.pdf?${currentQuery()}`);
}

async function signOut() {
  try {
    await apiRequest("/api/auth/logout", { method: "POST" });
  } finally {
    window.location.assign("/login");
  }
}

async function loadFacultyAccounts() {
  const container = document.getElementById("facultyAccountsList");
  if (!container || staffRole !== "admin") return;
  try {
    const response = await apiRequest("/api/admin/users");
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.message || "Faculty accounts could not be loaded.");
    container.innerHTML = data.users.length
      ? `<div class="table-scroll"><table class="feedback-table"><thead><tr><th>Staff login</th><th>Assigned faculty key</th><th>Status</th></tr></thead><tbody>${data.users.map((row) => `<tr><td>${escapeHTML(row.email)}</td><td>${escapeHTML(row.faculty_key || "—")}</td><td>${row.active ? "Active" : "Paused"}</td></tr>`).join("")}</tbody></table></div>`
      : '<p class="empty-state">No faculty accounts have been created yet.</p>';
  } catch (error) {
    container.textContent = error.message || "Faculty accounts could not be loaded.";
  }
}

function showDashboardError(message) {
  const status = document.getElementById("dashboardStatus");
  status.textContent = message;
  status.classList.add("error");
}

