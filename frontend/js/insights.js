const safe = value => {
    const node = document.createElement("span");
    node.textContent = String(value ?? "");
    return node.innerHTML;
};

let editingStaffId = null;
let facultyKeyEdited = false;

function themeItems(id, names, summary) {
    const target = document.getElementById(id);
    target.innerHTML = names.length
        ? names.map(name => `<div class="theme-item"><strong>${safe(name)}</strong><span>${summary[name].mentions} mentions</span></div>`).join("")
        : '<p class="empty-state">No submitted feedback has evidence for this yet.</p>';
}

async function requestAdminData(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: { "Content-Type": "application/json", ...(options.headers || {}) }
    });
    if (response.status === 401) {
        window.location.assign("/login");
        throw new Error("Your administrator session expired. Sign in again.");
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.success) {
        throw new Error(data.message || "The administrator request could not be completed.");
    }
    return data;
}

function setAdminStatus(id, message, isError = false) {
    const status = document.getElementById(id);
    status.textContent = message;
    status.classList.toggle("error", isError);
}

async function loadStaffAccounts() {
    const container = document.getElementById("staffAccountList");
    setAdminStatus("staffAccountStatus", "Loading staff accounts…");
    try {
        const data = await requestAdminData("/api/admin/users");
        container.innerHTML = data.users.length ? `
            <table class="admin-table">
                <thead><tr><th>Name</th><th>Email</th><th>Faculty key</th><th>Status</th><th>Actions</th></tr></thead>
                <tbody>${data.users.map(user => `
                    <tr class="${user.active ? "" : "account-inactive"}">
                        <td>${safe(user.name)}</td><td>${safe(user.email)}</td><td>${safe(user.faculty_key)}</td>
                        <td><span class="account-status ${user.active ? "" : "inactive"}">${user.active ? "Active" : "Paused"}</span></td>
                        <td><button class="quiet-btn" type="button" data-staff-action="edit" data-user-id="${user.id}">Edit</button>
                            <button class="${user.active ? "quiet-btn" : "primary-btn"}" type="button" data-staff-action="toggle" data-user-id="${user.id}" data-active="${user.active}">${user.active ? "Pause" : "Reactivate"}</button></td>
                    </tr>`).join("")}</tbody>
            </table>` : '<p class="admin-empty">No staff accounts yet. Add the first staff member above.</p>';
        setAdminStatus("staffAccountStatus", `${data.users.length} staff account(s). Teachers use the one-time email sign-in.`);
    } catch (error) {
        container.textContent = "Staff accounts could not be loaded.";
        setAdminStatus("staffAccountStatus", error.message, true);
    }
}

async function loadAuditLog() {
    const container = document.getElementById("auditLogList");
    setAdminStatus("auditLogStatus", "Loading audit history…");
    try {
        const data = await requestAdminData("/api/admin/audit-log?limit=50");
        container.innerHTML = data.events.length ? `
            <table class="admin-table">
                <thead><tr><th>Time</th><th>Staff member</th><th>Action</th><th>Target</th><th>Details</th></tr></thead>
                <tbody>${data.events.map(event => `
                    <tr><td>${safe(new Date(event.created_at).toLocaleString())}</td>
                        <td>${safe(event.actor_email)}</td><td>${safe(event.action.replaceAll("_", " "))}</td>
                        <td>${safe(event.target_email)}</td><td class="audit-details">${safe(JSON.stringify(event.details || {}))}</td></tr>`).join("")}</tbody>
            </table>` : '<p class="admin-empty">No audit events yet.</p>';
        setAdminStatus("auditLogStatus", `Showing ${data.events.length} recent event(s).`);
    } catch (error) {
        container.textContent = "Audit history could not be loaded.";
        setAdminStatus("auditLogStatus", error.message, true);
    }
}

function resetStaffForm() {
    editingStaffId = null;
    facultyKeyEdited = false;
    document.getElementById("staffAccountForm").reset();
    document.getElementById("staffSaveButton").textContent = "Add staff account";
    document.getElementById("staffCancelEdit").hidden = true;
    setAdminStatus("staffAccountStatus", "Staff can request a one-time sign-in link from the staff sign-in page.");
}

async function loadInsights() {
    const status = document.getElementById("insightStatus");
    status.textContent = "Loading current insights…";
    status.classList.remove("error");
    try {
        const identity = await fetch("/api/auth/me");
        if (identity.status === 401) { window.location.assign("/login"); return; }
        const identityData = await identity.json();
        if (!identity.ok || !identityData.success) throw new Error("Your staff session could not be checked. Sign in again.");
        document.getElementById("staffName").textContent = identityData.user?.name || "Staff";
        const isAdmin = identityData.user?.role === "admin";
        if (!isAdmin) document.getElementById("adminAnalyticsLink")?.remove();
        document.getElementById("adminTools").hidden = !isAdmin;

        const response = await fetch("/api/insights");
        if (!response.headers.get("content-type")?.includes("application/json")) throw new Error("Insight service is unavailable. Start the Flask app to load stored feedback.");
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error("Insight data could not be loaded.");
        themeItems("strengths", data.strengths, data.aspects);
        themeItems("improvements", data.improvement_areas, data.aspects);
        themeItems("suggestions", data.student_suggestions, data.aspects);
        const grid = document.getElementById("aspectGrid");
        const aspects = Object.entries(data.aspects);
        grid.innerHTML = aspects.length ? aspects.map(([name, counts]) => `<article class="aspect-card"><div class="aspect-title"><strong>${safe(name)}</strong><span>${counts.mentions} mentions</span></div><div class="sentiment-counts"><span class="positive">${counts.positive || 0} positive</span><span class="neutral">${counts.neutral || 0} neutral</span><span class="negative">${counts.negative || 0} negative</span><span>${counts.improvement || 0} suggestions</span><span>${counts.mixed || 0} mixed</span></div></article>`).join("") : '<p class="empty-state">No submissions yet. Share a sample response through the student flow to populate this view.</p>';
        status.textContent = `${data.stored_feedback_count} submitted responses · ${data.method}`;
        if (isAdmin) await Promise.all([loadStaffAccounts(), loadAuditLog()]);
    } catch (error) {
        status.textContent = error.message;
        status.classList.add("error");
    }
}

document.getElementById("staffAccountForm")?.addEventListener("submit", async event => {
    event.preventDefault();
    const button = document.getElementById("staffSaveButton");
    button.disabled = true;
    try {
        const payload = {
            name: document.getElementById("staffNameInput").value.trim(),
            email: document.getElementById("staffEmailInput").value.trim(),
            faculty_key: document.getElementById("staffFacultyKeyInput").value.trim()
        };
        const isEditing = editingStaffId !== null;
        await requestAdminData(isEditing ? `/api/admin/users/${editingStaffId}` : "/api/admin/users", {
            method: isEditing ? "PATCH" : "POST",
            body: JSON.stringify(payload)
        });
        resetStaffForm();
        setAdminStatus("staffAccountStatus", isEditing ? "Staff account updated." : "Staff account added.");
        await Promise.all([loadStaffAccounts(), loadAuditLog()]);
    } catch (error) {
        setAdminStatus("staffAccountStatus", error.message, true);
    } finally {
        button.disabled = false;
    }
});

document.getElementById("staffCancelEdit")?.addEventListener("click", resetStaffForm);
document.getElementById("staffEmailInput")?.addEventListener("input", event => {
    if (!facultyKeyEdited) document.getElementById("staffFacultyKeyInput").value = event.currentTarget.value.trim().toLowerCase();
});
document.getElementById("staffFacultyKeyInput")?.addEventListener("input", () => {
    facultyKeyEdited = true;
});
document.getElementById("staffAccountList")?.addEventListener("click", async event => {
    const button = event.target.closest("[data-staff-action]");
    if (!button) return;
    const userId = button.dataset.userId;
    if (button.dataset.staffAction === "edit") {
        try {
            const data = await requestAdminData("/api/admin/users");
            const user = data.users.find(item => String(item.id) === userId);
            if (!user) return;
            editingStaffId = user.id;
            facultyKeyEdited = true;
            document.getElementById("staffNameInput").value = user.name;
            document.getElementById("staffEmailInput").value = user.email;
            document.getElementById("staffFacultyKeyInput").value = user.faculty_key;
            document.getElementById("staffSaveButton").textContent = "Save changes";
            document.getElementById("staffCancelEdit").hidden = false;
            setAdminStatus("staffAccountStatus", `Editing ${user.email}.`);
            document.getElementById("staffNameInput").focus();
        } catch (error) {
            setAdminStatus("staffAccountStatus", error.message, true);
        }
        return;
    }
    const active = button.dataset.active === "true";
    button.disabled = true;
    try {
        await requestAdminData(`/api/admin/users/${userId}`, {
            method: "PATCH", body: JSON.stringify({active: !active})
        });
        setAdminStatus("staffAccountStatus", active ? "Account paused; outstanding sign-in links were revoked." : "Account reactivated.");
        await Promise.all([loadStaffAccounts(), loadAuditLog()]);
    } catch (error) {
        setAdminStatus("staffAccountStatus", error.message, true);
    } finally {
        button.disabled = false;
    }
});

document.getElementById("refreshAuditLog")?.addEventListener("click", loadAuditLog);
document.getElementById("logoutButton")?.addEventListener("click", async () => {
    try { await fetch("/api/auth/logout", {method:"POST"}); } finally { window.location.assign("/login"); }
});
document.addEventListener("DOMContentLoaded", loadInsights);
