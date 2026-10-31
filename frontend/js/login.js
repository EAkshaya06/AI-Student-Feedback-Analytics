document.addEventListener("DOMContentLoaded", async () => {
  const form = document.getElementById("loginForm");
  const button = document.getElementById("loginButton");
  const message = document.getElementById("loginMessage");
  try {
    const session = await refreshSession();
    if (session.authenticated) window.location.assign("/dashboard");
  } catch {
    showLoginMessage(message, "The sign-in service is unavailable. Refresh the page and try again.", true);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    button.disabled = true;
    button.textContent = "Signing in…";
    showLoginMessage(message, "Checking your account…", false);
    try {
      const response = await apiRequest("/api/login", {
        method: "POST",
        body: {
          email: document.getElementById("loginEmail").value.trim(),
          password: document.getElementById("loginPassword").value,
          next: new URLSearchParams(window.location.search).get("next") || "/dashboard",
        },
      });
      const data = await response.json();
      if (!response.ok || !data.success) throw new Error(data.message || "Sign-in failed.");
      setCsrfToken(data.csrf_token);
      window.location.assign(data.next || "/dashboard");
    } catch (error) {
      showLoginMessage(message, error.message || "Sign-in failed. Try again.", true);
      button.disabled = false;
      button.textContent = "Sign in";
    }
  });
});

function showLoginMessage(target, text, isError) {
  target.textContent = text;
  target.className = `form-message${isError ? " error" : ""}`;
}
