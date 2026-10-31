document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("feedbackForm").addEventListener("submit", submitFeedback);
  document.getElementById("feedbackFile").addEventListener("change", importFeedbackFile);
  document.getElementById("commentColumn").addEventListener("change", renderImportedColumn);
});

let importedRows = null;
let currentBatchId = "";

async function importFeedbackFile(event) {
  const file = event.target.files?.[0];
  const message = document.getElementById("fileMessage");
  const picker = document.getElementById("columnPickerWrap");
  importedRows = null;
  picker.hidden = true;
  if (!file) return;
  if (file.size > 900_000) {
    showFormMessage(message, "Choose a file smaller than 900 KB.", true);
    event.target.value = "";
    return;
  }
  try {
    const contents = (await file.text()).replace(/^\uFEFF/, "");
    const extension = file.name.split(".").pop().toLowerCase();
    if (extension === "txt") {
      const comments = contents.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
      document.getElementById("feedbackText").value = comments.join("\n");
      showFormMessage(message, `${comments.length} comment${comments.length === 1 ? "" : "s"} loaded from the text file.`, false);
      return;
    }
    if (extension !== "csv" && extension !== "tsv") throw new Error("Choose a CSV, TSV, or TXT file.");
    const delimiter = extension === "tsv" ? "\t" : ",";
    const rows = parseDelimited(contents, delimiter);
    if (rows.length < 2 || !rows[0].some((value) => value.trim())) throw new Error("The file needs a header row and at least one comment row.");
    importedRows = rows;
    const selector = document.getElementById("commentColumn");
    selector.replaceChildren();
    rows[0].forEach((heading, index) => {
      const option = document.createElement("option");
      option.value = String(index);
      option.textContent = heading.trim() || `Column ${index + 1}`;
      selector.append(option);
    });
    picker.hidden = false;
    renderImportedColumn();
  } catch (error) {
    showFormMessage(message, error.message || "The selected file could not be read.", true);
    event.target.value = "";
  }
}

function parseDelimited(text, delimiter) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (character === '"') {
      if (quoted && text[index + 1] === '"') {
        cell += '"';
        index += 1;
      } else {
        quoted = !quoted;
      }
    } else if (!quoted && character === delimiter) {
      row.push(cell);
      cell = "";
    } else if (!quoted && (character === "\n" || character === "\r")) {
      if (character === "\r" && text[index + 1] === "\n") index += 1;
      row.push(cell);
      if (row.some((value) => value.trim())) rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += character;
    }
  }
  row.push(cell);
  if (row.some((value) => value.trim())) rows.push(row);
  if (quoted) throw new Error("The file has an unclosed quoted field.");
  return rows;
}

function renderImportedColumn() {
  if (!importedRows) return;
  const column = Number(document.getElementById("commentColumn").value || 0);
  const comments = importedRows.slice(1).map((row) => String(row[column] || "").trim()).filter(Boolean);
  document.getElementById("feedbackText").value = comments.join("\n");
  showFormMessage(document.getElementById("fileMessage"), `${comments.length} comments loaded from the selected column. The file itself will not be uploaded.`, false);
}

async function submitFeedback(event) {
  event.preventDefault();
  const result = document.getElementById("analysisResult");
  const button = document.getElementById("submitFeedbackButton");
  const comments = document.getElementById("feedbackText").value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (!comments.length) return showFormMessage(result, "Add at least one feedback comment.", true);
  if (comments.length > 100) return showFormMessage(result, "Submit up to 100 comments at a time.", true);
  if (comments.some((comment) => comment.length > 20_000)) return showFormMessage(result, "Each comment must be 20,000 characters or fewer.", true);
  if (!currentBatchId) currentBatchId = makeBatchId();

  button.disabled = true;
  button.textContent = "Saving feedback…";
  result.innerHTML = '<div class="loading">Saving your feedback…</div>';
  const metadata = {
    department: document.getElementById("department").value.trim(),
    academic_year: document.getElementById("academicYear").value.trim(),
    semester: document.getElementById("semester").value.trim(),
    subject: document.getElementById("subject").value.trim(),
    section: document.getElementById("section").value.trim(),
    faculty: document.getElementById("faculty").value.trim(),
  };
  try {
    const response = await apiRequest("/api/feedback", {
      method: "POST",
      body: { batch_id: currentBatchId, comments, metadata },
    });
    const data = await response.json();
    if (!response.ok || !data.success) throw new Error(data.message || "Feedback could not be submitted.");
    renderSubmission(result, data);
    document.getElementById("feedbackForm").reset();
    document.getElementById("columnPickerWrap").hidden = true;
    importedRows = null;
    currentBatchId = "";
  } catch (error) {
    showFormMessage(result, error.message || "Could not save feedback. Check your connection and try again.", true);
  } finally {
    button.disabled = false;
    button.textContent = "Submit feedback";
  }
}

function renderSubmission(target, data) {
  const rows = (data.results || []).map((item) => {
    const aspects = (item.aspects || []).map((aspect) => `
      <li><span><strong>${escapeHTML(aspect.aspect)}</strong> · ${escapeHTML(aspect.sentiment)}</span><small>Evidence: ${escapeHTML(aspect.evidence)}</small></li>`).join("");
    const sentimentLabel = item.language_supported
      ? `${item.mixed_opinion ? "Mixed opinion · " : ""}${escapeHTML(item.sentiment)}`
      : "Not analyzed";
    const languageNote = item.language_supported
      ? escapeHTML(item.analysis_note)
      : `${escapeHTML(item.language)} feedback: ${escapeHTML(item.analysis_note)}`;
    return `
      <article class="comment-result">
        <div class="comment-result-meta"><span class="sentiment-pill ${item.language_supported ? escapeHTML(item.sentiment) : "unsupported"}">${sentimentLabel}</span><span>${escapeHTML(item.language)} · ${escapeHTML(item.analysis_method)}</span></div>
        <p>${escapeHTML(item.feedback)}</p>
        ${aspects ? `<ul class="aspect-evidence-list">${aspects}</ul>` : ""}
        <p class="comment-insight">${languageNote}</p>
      </article>`;
  }).join("");
  target.innerHTML = `
    <section class="report-card submission-report">
      <div class="submission-success"><span aria-hidden="true">✓</span><div><h2>Feedback saved</h2><p>${Number(data.count) || 0} comment${Number(data.count) === 1 ? "" : "s"} added to live student submissions. Unsupported language is excluded from sentiment totals.</p></div></div>
      <p class="report-footnote">Your submission does not include a name or email. Sentiment scores are rule-based estimates, not probabilities.</p>
      <div class="comment-results">${rows}</div>
      <p class="staff-link-note"><a href="/login">Staff sign in</a> is required to view dashboard summaries.</p>
    </section>`;
  target.scrollIntoView({ behavior: "smooth", block: "start" });
}

function showFormMessage(target, message, isError) {
  target.textContent = message;
  target.className = `form-message${isError ? " error" : ""}`;
}

function makeBatchId() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (character) => {
    const random = Math.floor(Math.random() * 16);
    return (character === "x" ? random : (random & 3) | 8).toString(16);
  });
}
