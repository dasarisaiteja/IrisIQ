/**
 * IrisIQ Unified Frontend Authentication & API Client
 * Automatically manages JWT bearer tokens for seamless browser interactions.
 */
(function () {
    const TOKEN_KEY = "iris_access_token";
    const USER_KEY = "iris_user_info";

    // Auto-login helper using seeded credentials
    async function ensureToken() {
        let token = localStorage.getItem(TOKEN_KEY);
        if (token) return token;

        try {
            const resp = await fetch("/api/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    username: "admin",
                    password: "Admin@IrisIQ2026!"
                })
            });
            if (resp.ok) {
                const data = await resp.json();
                if (data.access_token) {
                    localStorage.setItem(TOKEN_KEY, data.access_token);
                    localStorage.setItem(USER_KEY, JSON.stringify(data));
                    return data.access_token;
                }
            }
        } catch (e) {
            console.warn("IrisIQ Auto-auth initialization notice:", e);
        }
        return null;
    }

    // Intercept window.fetch to attach Bearer Authorization header
    const nativeFetch = window.fetch;
    window.fetch = async function (resource, config = {}) {
        let token = localStorage.getItem(TOKEN_KEY);
        if (!token) {
            token = await ensureToken();
        }

        const isApiUrl = typeof resource === "string" && (
            resource.startsWith("/api/") ||
            resource.startsWith("/detect") ||
            resource.startsWith("/enroll") ||
            resource.startsWith("/verify") ||
            resource.startsWith("/register-frame") ||
            resource.startsWith("/report") ||
            resource.startsWith("/dashboard")
        );

        if (token && isApiUrl) {
            config = config || {};
            if (config.headers instanceof Headers) {
                if (!config.headers.has("Authorization")) {
                    config.headers.set("Authorization", "Bearer " + token);
                }
            } else if (Array.isArray(config.headers)) {
                if (!config.headers.some(h => h[0].toLowerCase() === "authorization")) {
                    config.headers.push(["Authorization", "Bearer " + token]);
                }
            } else {
                config.headers = config.headers || {};
                if (!config.headers["Authorization"] && !config.headers["authorization"]) {
                    config.headers["Authorization"] = "Bearer " + token;
                }
            }
        }

        let response = await nativeFetch(resource, config);

        // If token expired, renew once and retry
        if (response.status === 401 && isApiUrl) {
            localStorage.removeItem(TOKEN_KEY);
            token = await ensureToken();
            if (token) {
                if (config.headers instanceof Headers) {
                    config.headers.set("Authorization", "Bearer " + token);
                } else if (!Array.isArray(config.headers)) {
                    config.headers["Authorization"] = "Bearer " + token;
                }
                response = await nativeFetch(resource, config);
            }
        }

        return response;
    };

    // Initialize token immediately
    ensureToken();
})();
