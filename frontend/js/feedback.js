const escapeHTML = value => {
    const node = document.createElement("span");
    node.textContent = String(value ?? "");
    return node.innerHTML;
};

const MAX_FEEDBACK_FILE_BYTES = 5 * 1024 * 1024;
let importedDelimitedFile = null;

function setFileImportStatus(message, isError = false) {
    const status = document.getElementById("fileImportStatus");
    status.textContent = message;
    status.classList.toggle("error", isError);
}

function isFeedbackColumnHeader(value) {
    const normalized = String(value || "").toLowerCase().replace(/[^a-z0-9]/g, "");
    return /^(student)?(feedback|comments?|reviews?|responses?|remarks?|text|answers?)(comments?|text)?$/.test(normalized);
}

async function readFeedbackFile(file) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    if (bytes[0] === 0xff && bytes[1] === 0xfe) {
        return new TextDecoder("utf-16le").decode(bytes.subarray(2));
    }
    if (bytes[0] === 0xfe && bytes[1] === 0xff) {
        return new TextDecoder("utf-16be").decode(bytes.subarray(2));
    }
    return new TextDecoder("utf-8").decode(bytes).replace(/^\uFEFF/, "");
}

function detectFileDelimiter(text, extension) {
    if (extension === "tsv") return "\t";
    const firstLine = text.split(/\r?\n/, 1)[0] || "";
    const counts = { ",": 0, ";": 0, "\t": 0 };
    let insideQuotes = false;
    for (let index = 0; index < firstLine.length; index += 1) {
        const character = firstLine[index];
        if (character === '"') {
            if (insideQuotes && firstLine[index + 1] === '"') index += 1;
            else insideQuotes = !insideQuotes;
        } else if (!insideQuotes && Object.prototype.hasOwnProperty.call(counts, character)) {
            counts[character] += 1;
        }
    }
    return Object.entries(counts).sort((left, right) => right[1] - left[1])[0][0];
}

function parseDelimitedFeedback(text, delimiter) {
    const rows = [];
    let row = [];
    let field = "";
    let insideQuotes = false;

    for (let index = 0; index < text.length; index += 1) {
        const character = text[index];
        if (character === '"') {
            if (insideQuotes && text[index + 1] === '"') {
                field += '"';
                index += 1;
            } else {
                insideQuotes = !insideQuotes;
            }
        } else if (character === delimiter && !insideQuotes) {
            row.push(field);
            field = "";
        } else if ((character === "\n" || character === "\r") && !insideQuotes) {
            row.push(field);
            if (row.some(cell => cell.trim())) rows.push(row);
            row = [];
            field = "";
            if (character === "\r" && text[index + 1] === "\n") index += 1;
        } else {
            field += character;
        }
    }

    if (insideQuotes) throw new Error("A quoted cell is not closed. Check the CSV or TSV file format.");
    row.push(field);
    if (row.some(cell => cell.trim())) rows.push(row);
    return rows;
}

function validateImportedComments(comments) {
    if (!comments.length) throw new Error("No comments were found in the selected file column.");
    if (comments.length > 25) throw new Error(`This form accepts up to 25 comments; the file has ${comments.length}. Split the file into batches or paste up to 25 comments at a time.`);
    if (comments.some(comment => comment.length > 5000) || comments.join("").length > 20000) {
        throw new Error("Keep each comment under 5,000 characters and the total under 20,000 characters.");
    }
}

function replaceFeedbackComments(comments, fileName) {
    validateImportedComments(comments);
    document.getElementById("feedbackText").value = comments.join("\n");
    setFileImportStatus(`Loaded ${comments.length} comment(s) from ${fileName}. Review or edit them below before continuing.`);
}

function rebuildFeedbackColumnPicker(preferredColumn = null) {
    if (!importedDelimitedFile) return;
    const { rows } = importedDelimitedFile;
    const width = rows.reduce((maximum, row) => Math.max(maximum, row.length), 0);
    const hasHeader = document.getElementById("feedbackHasHeader").checked;
    const headers = hasHeader ? rows[0] : [];
    const select = document.getElementById("feedbackColumnSelect");
    select.replaceChildren();

    for (let column = 0; column < width; column += 1) {
        const option = document.createElement("option");
        option.value = String(column);
        option.textContent = hasHeader && headers[column]?.trim()
            ? headers[column].trim()
            : `Column ${column + 1}`;
        select.appendChild(option);
    }

    const headerColumn = hasHeader
        ? headers.findIndex(isFeedbackColumnHeader)
        : -1;
    const selectedColumn = preferredColumn === null
        ? (headerColumn >= 0 ? headerColumn : 0)
        : Math.min(preferredColumn, width - 1);
    select.value = String(selectedColumn);
}

function applyImportedFeedbackColumn() {
    if (!importedDelimitedFile) return;
    try {
        const hasHeader = document.getElementById("feedbackHasHeader").checked;
        const column = Number(document.getElementById("feedbackColumnSelect").value);
        const dataRows = hasHeader ? importedDelimitedFile.rows.slice(1) : importedDelimitedFile.rows;
        const comments = dataRows
            .map(row => String(row[column] ?? "").replace(/\r\n?/g, "\n").replace(/\n+/g, " ").trim())
            .filter(Boolean);
        replaceFeedbackComments(comments, importedDelimitedFile.fileName);
    } catch (error) {
        setFileImportStatus(error.message, true);
    }
}

async function importFeedbackFile(event) {
    const file = event.currentTarget.files?.[0];
    if (!file) return;
    const extension = file.name.split(".").pop().toLowerCase();
    const picker = document.getElementById("feedbackColumnPicker");
    importedDelimitedFile = null;
    picker.hidden = true;

    if (!["csv", "tsv", "txt"].includes(extension)) {
        setFileImportStatus("Choose a CSV, TSV, or TXT file.", true);
        return;
    }
    if (file.size > MAX_FEEDBACK_FILE_BYTES) {
        setFileImportStatus("Choose a file smaller than 5 MB.", true);
        return;
    }

    setFileImportStatus("Reading the file in your browser…");
    try {
        const text = await readFeedbackFile(file);
        if (extension === "txt") {
            const comments = text.split(/\r\n?|\n/).map(comment => comment.trim()).filter(Boolean);
            replaceFeedbackComments(comments, file.name);
            return;
        }

        const rows = parseDelimitedFeedback(text, detectFileDelimiter(text, extension));
        if (!rows.length) throw new Error("No rows were found in this file.");
        const hasHeader = rows[0].some(isFeedbackColumnHeader);
        importedDelimitedFile = { rows, fileName: file.name };
        document.getElementById("feedbackHasHeader").checked = hasHeader;
        picker.hidden = false;
        rebuildFeedbackColumnPicker();
        applyImportedFeedbackColumn();
    } catch (error) {
        setFileImportStatus(error.message || "Could not read this file.", true);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("feedbackFile")?.addEventListener("change", importFeedbackFile);
    document.getElementById("feedbackHasHeader")?.addEventListener("change", () => {
        rebuildFeedbackColumnPicker();
        applyImportedFeedbackColumn();
    });
    document.getElementById("feedbackColumnSelect")?.addEventListener("change", applyImportedFeedbackColumn);
});

function getFeedbackInput() {
    const email = document.getElementById("facultyEmailField").value.trim().toLowerCase();
    const comments = document.getElementById("feedbackText").value
        .split(/\r?\n/)
        .map(comment => comment.trim())
        .filter(Boolean);
    if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new Error("Enter a valid teacher email address, or leave it blank.");
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
        ).join(" · ") + "</small>" : "") +
        "<p class='batch-review'><strong>Review:</strong> " + escapeHTML(item.review || "No specific review was available for this comment.") + "</p>" +
        "<ul class='comment-guidance'>" + (item.improvement_suggestions || []).map(suggestion =>
            "<li>" + escapeHTML(suggestion) + "</li>"
        ).join("") + "</ul></article>"
    ).join("");
    const teacherSuggestions = (data.improvement_suggestions || []).map(suggestion =>
        "<li>" + escapeHTML(suggestion) + "</li>"
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
        "<div class='analysis-guidance'><article class='overall-review'><h3>Overall review</h3><p>" +
        escapeHTML(data.review || "Review the original comments for context.") +
        "</p></article><article class='teacher-guidance'><h3>What the teacher can improve</h3><ul>" +
        (teacherSuggestions || "<li>Ask students for a specific example so the next step addresses a clear teaching aspect.</li>") +
        "</ul></article></div>" +
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
