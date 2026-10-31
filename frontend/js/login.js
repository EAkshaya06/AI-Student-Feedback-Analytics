document.getElementById("loginForm").addEventListener("submit", async event => {
    event.preventDefault();
    const button = event.currentTarget.querySelector("button[type=submit]");
    const error = document.getElementById("loginError");
    button.disabled = true; button.textContent = "Signing in…"; error.textContent = "";
    try {
        const response = await fetch("/api/auth/login", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({email:document.getElementById("email").value,password:document.getElementById("password").value})});
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.message || "Sign in failed. Check your details and try again.");
        window.location.assign(data.user.role === "admin" ? "/dashboard" : "/insights");
    } catch (e) { error.textContent = e.message === "Failed to fetch" ? "The sign-in service is unavailable. Start the app server and try again." : e.message; }
    finally { button.disabled = false; button.innerHTML = 'Sign in <span aria-hidden="true">→</span>'; }
});
