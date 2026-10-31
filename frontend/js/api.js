let csrfToken = "";

function apiUrl(path) {
  return path;
}

async function refreshSession() {
  const response = await fetch(apiUrl("/api/session"), { credentials: "same-origin" });
  const data = await response.json();
  csrfToken = data.csrf_token || "";
  return data;
}

async function apiRequest(path, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers || {});
  if (["POST", "PUT", "PATCH", "DELETE"].includes(method)) {
    if (!csrfToken) await refreshSession();
    headers.set("X-CSRF-Token", csrfToken);
    if (options.body && typeof options.body !== "string" && !(options.body instanceof FormData)) {
      headers.set("Content-Type", "application/json");
      options = { ...options, body: JSON.stringify(options.body) };
    }
  }
  return fetch(apiUrl(path), { ...options, method, headers, credentials: "same-origin" });
}

function setCsrfToken(value) {
  csrfToken = value || "";
}

function escapeHTML(value) {
  const element = document.createElement("span");
  element.textContent = String(value ?? "");
  return element.innerHTML;
}
