/**
 * IrisIQ Unified Frontend Authentication & API Client
 * Securely manages JWT bearer tokens for legitimate browser sessions.
 * Never stores or auto-logins with hardcoded credentials.
 */
(function () {
    const TOKEN_KEY = "iris_access_token";
    const USER_KEY = "iris_user_info";

    // Preserve native fetch to prevent recursive loops
    const nativeFetch = (typeof window !== "undefined" && window.fetch)
        ? window.fetch.bind(window)
        : globalThis.fetch;

    // Helper to decode JWT payload safely without external dependencies
    function decodeJwtPayload(token) {
        if (!token || typeof token !== "string") return null;
        const parts = token.split(".");
        if (parts.length !== 3) return null;
        try {
            const base64Url = parts[1];
            const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
            const jsonPayload = decodeURIComponent(
                atob(base64)
                    .split("")
                    .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
                    .join("")
            );
            return JSON.parse(jsonPayload);
        } catch (e) {
            return null;
        }
    }

    // Helper to safely extract URL pathname from string, URL, or Request
    function getUrlPathname(resource) {
        try {
            if (!resource) return "";
            if (typeof resource === "string") {
                if (resource.startsWith("/") || resource.startsWith("./")) {
                    return resource.split("?")[0].split("#")[0];
                }
                const parsed = new URL(resource, (typeof window !== "undefined" && window.location) ? window.location.origin : "http://localhost:8000");
                return parsed.pathname;
            }
            if (typeof Request !== "undefined" && resource instanceof Request) {
                const parsed = new URL(resource.url);
                return parsed.pathname;
            }
            if (resource && resource.pathname) {
                return resource.pathname;
            }
            return String(resource);
        } catch (e) {
            return typeof resource === "string" ? resource : "";
        }
    }

    // Check if the endpoint requires IrisIQ JWT authorization
    function isProtectedEndpoint(pathname) {
        if (!pathname) return false;
        // Never authenticate login endpoint
        if (pathname === "/api/auth/login" || pathname.endsWith("/api/auth/login")) {
            return false;
        }
        return (
            pathname.startsWith("/api/") ||
            pathname === "/detect" || pathname.startsWith("/detect/") ||
            pathname === "/enroll" || pathname.startsWith("/enroll/") ||
            pathname === "/verify" || pathname.startsWith("/verify/") ||
            pathname === "/register-frame" || pathname.startsWith("/register-frame/") ||
            pathname === "/report" || pathname.startsWith("/report/") ||
            pathname === "/dashboard" || pathname.startsWith("/dashboard/")
        );
    }

    // Get current token from storage, checking expiration
    function getToken() {
        try {
            const token = localStorage.getItem(TOKEN_KEY);
            if (!token) return null;

            const payload = decodeJwtPayload(token);
            if (payload && payload.exp) {
                const nowSec = Math.floor(Date.now() / 1000);
                if (payload.exp <= nowSec) {
                    console.warn("IrisIQ: Stored token has expired. Clearing session.");
                    localStorage.removeItem(TOKEN_KEY);
                    localStorage.removeItem(USER_KEY);
                    return null;
                }
            }
            return token;
        } catch (e) {
            return null;
        }
    }

    // Get user information from storage or decoded JWT token
    function getUser() {
        try {
            const raw = localStorage.getItem(USER_KEY);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (parsed && typeof parsed === "object") return parsed;
            }
        } catch (e) {}

        const token = getToken();
        if (token) {
            const payload = decodeJwtPayload(token);
            if (payload) {
                return {
                    username: payload.sub,
                    role: payload.role,
                    full_name: payload.full_name || "",
                    email: payload.email || "",
                    exp: payload.exp
                };
            }
        }
        return null;
    }

    // Get user role
    function getRole() {
        const user = getUser();
        return user?.role || null;
    }

    // Helper to attach Authorization header to Request or config object
    function attachAuthHeader(resource, config, token) {
        if (!token) return { resource, config };

        if (typeof Request !== "undefined" && resource instanceof Request) {
            const headers = new Headers(resource.headers);
            headers.set("Authorization", "Bearer " + token);
            const newReq = new Request(resource, { headers });
            return { resource: newReq, config };
        }

        config = config || {};
        if (typeof Headers !== "undefined" && config.headers instanceof Headers) {
            config.headers.set("Authorization", "Bearer " + token);
        } else if (Array.isArray(config.headers)) {
            const idx = config.headers.findIndex(h => h[0].toLowerCase() === "authorization");
            if (idx >= 0) {
                config.headers[idx][1] = "Bearer " + token;
            } else {
                config.headers.push(["Authorization", "Bearer " + token]);
            }
        } else {
            config.headers = config.headers || {};
            config.headers["Authorization"] = "Bearer " + token;
        }

        return { resource, config };
    }

    // Intercept window.fetch to attach Bearer Authorization header for legitimate sessions
    window.fetch = async function (resource, config = {}) {
        const pathname = getUrlPathname(resource);

        // If it is the login route itself, bypass token attachment entirely
        if (pathname === "/api/auth/login" || pathname.endsWith("/api/auth/login")) {
            return nativeFetch(resource, config);
        }

        const isProtected = isProtectedEndpoint(pathname);

        if (isProtected) {
            const token = getToken();
            if (token) {
                const attached = attachAuthHeader(resource, config, token);
                resource = attached.resource;
                config = attached.config;
            }
        }

        const response = await nativeFetch(resource, config);

        // If server returns 401 Unauthorized for a protected route, clean up expired/invalid token
        if (response.status === 401 && isProtected) {
            console.warn("IrisIQ: Authentication token rejected or expired (401). Clearing stored token.");
            localStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(USER_KEY);
        }

        return response;
    };

    // Public API exposed for explicit authentication and role queries
    window.IrisAuth = {
        getToken: getToken,
        getUser: getUser,
        getRole: getRole,
        isAuthenticated: () => !!getToken(),
        isStaff: () => {
            const role = getRole();
            return role === "Admin" || role === "Counselor";
        },
        login: async (username, password) => {
            const loginEndpoint = (typeof window !== "undefined" && window.location && window.location.origin)
                ? (window.location.origin + "/api/auth/login")
                : "/api/auth/login";

            const resp = await nativeFetch(loginEndpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password })
            });

            if (resp.ok) {
                const data = await resp.json();
                if (data.access_token) {
                    localStorage.setItem(TOKEN_KEY, data.access_token);
                    localStorage.setItem(USER_KEY, JSON.stringify(data));
                    updateNavAuthElements();
                    return data;
                }
            }
            const errData = await resp.json().catch(() => ({}));
            throw new Error(errData?.detail || errData?.message || "Login failed");
        },
        clearAuth: () => {
            localStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(USER_KEY);
            updateNavAuthElements();
        }
    };

    // Helper to automatically render navigation login/logout and user badges across pages
    function updateNavAuthElements() {
        if (typeof document === "undefined") return;
        const user = getUser();
        const isAuthenticated = !!getToken();

        // 1. Elements with id "navAuthContainer" or "navAuthItem"
        const containers = document.querySelectorAll("#navAuthContainer, #navAuthItem");
        containers.forEach(el => {
            if (isAuthenticated && user) {
                const badgeClass = user.role === "Admin" ? "bg-warning text-dark" : (user.role === "Counselor" ? "bg-success text-white" : "bg-info text-dark");
                el.innerHTML = `
                    <div class="d-flex align-items-center gap-2">
                        <span class="badge ${badgeClass} py-2 px-3 fw-semibold">
                            <i class="fa-solid fa-user-shield me-1"></i> ${user.role}: ${user.username}
                        </span>
                        <button type="button" class="btn btn-sm btn-outline-danger" onclick="IrisAuth.clearAuth(); window.location.href='login.html';">
                            <i class="fa-solid fa-right-from-bracket me-1"></i> Logout
                        </button>
                    </div>
                `;
            } else {
                const currentPath = (typeof window !== "undefined" && window.location) ? window.location.pathname : "";
                const redirectParam = (currentPath && !currentPath.includes("login.html")) ? `?redirect=${encodeURIComponent(currentPath)}` : "";
                el.innerHTML = `
                    <a href="login.html${redirectParam}" class="btn btn-outline-info btn-sm px-3" id="navAuthBtn">
                        <i class="fa-solid fa-right-to-bracket me-1"></i> Sign In
                    </a>
                `;
            }
        });

        // 2. Dashboard topbar profile update if present
        const dashboardProfile = document.querySelector(".topbar .profile");
        if (dashboardProfile) {
            if (isAuthenticated && user) {
                const nameEl = dashboardProfile.querySelector("strong");
                if (nameEl) nameEl.textContent = `${user.full_name || user.username} (${user.role})`;
                
                if (!document.getElementById("dashboardLogoutBtn")) {
                    const logoutBtn = document.createElement("button");
                    logoutBtn.id = "dashboardLogoutBtn";
                    logoutBtn.className = "btn btn-sm btn-outline-danger ms-3 px-3 py-1";
                    logoutBtn.innerHTML = '<i class="fa-solid fa-right-from-bracket me-1"></i> Logout';
                    logoutBtn.title = "Sign Out";
                    logoutBtn.onclick = () => {
                        window.IrisAuth.clearAuth();
                        window.location.href = "login.html";
                    };
                    dashboardProfile.appendChild(logoutBtn);
                }
            } else {
                if (!document.getElementById("dashboardLoginBtn")) {
                    const loginBtn = document.createElement("a");
                    loginBtn.id = "dashboardLoginBtn";
                    loginBtn.href = "login.html?redirect=/static/dashboard.html";
                    loginBtn.className = "btn btn-sm btn-primary ms-3 px-3 py-1";
                    loginBtn.innerHTML = '<i class="fa-solid fa-right-to-bracket me-1"></i> Sign In';
                    dashboardProfile.appendChild(loginBtn);
                }
            }
        }
    }

    if (typeof document !== "undefined") {
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", updateNavAuthElements);
        } else {
            updateNavAuthElements();
        }
    }
})();

