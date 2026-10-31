const requestCard = document.getElementById("requestCard");
const verifyCard = document.getElementById("verifyCard");
const linkToken = new URLSearchParams(window.location.search).get("token");

if (linkToken) {
    requestCard.hidden = true;
    verifyCard.hidden = false;
    window.history.replaceState({}, document.title, "/teacher-login");
}

document.getElementById("teacherLinkForm").addEventListener("submit", async event => {
    event.preventDefault();
    const button = event.currentTarget.querySelector("button[type=submit]");
    const message = document.getElementById("teacherLinkMessage");
    button.disabled = true;
    button.textContent = "Sending link…";
    message.textContent = "";
    try {
        const response = await apiRequest("/api/auth/teacher-link", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({email: document.getElementById("teacherEmail").value.trim()})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || "Unable to request a sign-in link.");
        message.textContent = data.message;
    } catch (error) {
        message.textContent = error.message === "Failed to fetch"
            ? "The sign-in service is unavailable. Start the app server and try again."
            : error.message;
    } finally {
        button.disabled = false;
        button.innerHTML = 'Email me a sign-in link <span aria-hidden="true">→</span>';
    }
});

document.getElementById("verifyTeacherLink").addEventListener("click", async event => {
    const button = event.currentTarget;
    const message = document.getElementById("verifyMessage");
    if (!linkToken) {
        message.textContent = "The sign-in link is missing. Request a new one.";
        return;
    }
    button.disabled = true;
    button.textContent = "Verifying link…";
    message.textContent = "";
    try {
        const response = await apiRequest("/api/auth/teacher-link/verify", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({token: linkToken})
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.message || "This link is invalid or has expired.");
        setCsrfToken(data.csrf_token);
        window.location.replace("/insights");
    } catch (error) {
        message.textContent = error.message === "Failed to fetch"
            ? "The sign-in service is unavailable. Start the app server and try again."
            : error.message;
        button.disabled = false;
        button.textContent = "Sign in securely →";
    }
});

