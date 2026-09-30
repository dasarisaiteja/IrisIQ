/**
 * IrisIQ Counsellor Guidance Portal Client
 * Strictly adheres to Official IRIS Backend & Frontend Requirements (Phase 6).
 * Handles:
 * - Role authentication & authorization check (Counsellor / Admin only)
 * - API-driven dashboard KPI metrics
 * - Assigned student directory & search filtering
 * - Case details modal with comprehensive scan and assessment status
 * - Clinical counselling notes creation & review
 * - Follow-up consultations scheduling & status updates
 * - Direct navigation to official structured report
 */

(function () {
    "use strict";

    // Application State & Resilient Auth Resolver
    const authClient = (typeof window !== "undefined" && (window.authClient || window.IrisAuth)) || {
        getToken: () => {
            try { return localStorage.getItem("iris_access_token") || localStorage.getItem("token"); } catch(e) { return null; }
        },
        getUser: () => {
            try {
                const raw = localStorage.getItem("iris_user_info");
                if (raw) return JSON.parse(raw);
            } catch(e) {}
            try {
                const token = localStorage.getItem("iris_access_token") || localStorage.getItem("token");
                if (token && token.split(".").length === 3) {
                    const payload = JSON.parse(atob(token.split(".")[1]));
                    return {
                        username: payload.sub,
                        role: payload.role,
                        full_name: payload.full_name || payload.sub
                    };
                }
            } catch(e) {}
            return null;
        },
        getAuthHeaders: () => {
            const t = (typeof window !== "undefined" && window.IrisAuth && window.IrisAuth.getToken()) || localStorage.getItem("iris_access_token") || localStorage.getItem("token");
            return t ? { "Authorization": `Bearer ${t}` } : {};
        },
        logout: () => {
            if (typeof window !== "undefined" && window.IrisAuth) window.IrisAuth.clearAuth();
            try { localStorage.clear(); } catch(e) {}
            window.location.href = "login.html";
        }
    };

    let currentUser = null;
    let assignedStudents = [];
    let followUpsList = [];
    let currentSelectedAsmId = null;
    let currentSelectedStudentName = null;

    // Bootstrap Modal Instances
    let addNoteModalInstance = null;
    let scheduleFollowUpModalInstance = null;
    let studentDetailModalInstance = null;

    // DOM Elements
    const portalWorkspace = document.getElementById("portalWorkspace");
    const unauthorizedBox = document.getElementById("unauthorizedBox");
    const navAuthContainer = document.getElementById("navAuthContainer");

    // Metric Elements
    const metricAssignedStudents = document.getElementById("metricAssignedStudents");
    const metricReportsReady = document.getElementById("metricReportsReady");
    const metricPendingReview = document.getElementById("metricPendingReview");
    const metricActiveFollowUps = document.getElementById("metricActiveFollowUps");

    // Student Directory Elements
    const studentSearchInput = document.getElementById("studentSearchInput");
    const refreshStudentsBtn = document.getElementById("refreshStudentsBtn");
    const assignedStudentsTbody = document.getElementById("assignedStudentsTbody");

    // Follow-ups Elements
    const followUpStatusFilter = document.getElementById("followUpStatusFilter");
    const refreshFollowUpsBtn = document.getElementById("refreshFollowUpsBtn");
    const followUpsTbody = document.getElementById("followUpsTbody");

    // Modal Elements - Note
    const modalNoteAsmId = document.getElementById("modalNoteAsmId");
    const modalNoteStudentName = document.getElementById("modalNoteStudentName");
    const counsellingNoteInput = document.getElementById("counsellingNoteInput");
    const saveNoteSubmitBtn = document.getElementById("saveNoteSubmitBtn");
    const saveNoteSpinner = document.getElementById("saveNoteSpinner");

    // Modal Elements - Follow-up
    const modalFuAsmId = document.getElementById("modalFuAsmId");
    const modalFuStudentName = document.getElementById("modalFuStudentName");
    const fuDatePicker = document.getElementById("fuDatePicker");
    const fuNotesInput = document.getElementById("fuNotesInput");
    const saveFuSubmitBtn = document.getElementById("saveFuSubmitBtn");
    const saveFuSpinner = document.getElementById("saveFuSpinner");

    // Modal Elements - Details
    const studentDetailModalBody = document.getElementById("studentDetailModalBody");

    /**
     * Initializes the Counsellor Portal.
     */
    async function init() {
        // 1. Verify Authentication & Role
        const token = authClient.getToken();
        currentUser = authClient.getUser();

        if (!token || !currentUser) {
            console.warn("IrisIQ: No active session found, redirecting to login.");
            window.location.href = "login.html?redirect=counsellor_dashboard.html";
            return;
        }

        const role = currentUser.role || "";
        const isAuthorized = ["Admin", "Counselor", "Counsellor"].includes(role);

        if (!isAuthorized) {
            if (unauthorizedBox) unauthorizedBox.classList.remove("d-none");
            if (portalWorkspace) portalWorkspace.classList.add("d-none");
            return;
        }

        if (unauthorizedBox) unauthorizedBox.classList.add("d-none");
        if (portalWorkspace) portalWorkspace.classList.remove("d-none");

        // 2. Render Nav Auth Controls
        renderNav();

        // 3. Initialize Modals
        const noteEl = document.getElementById("addNoteModal");
        if (noteEl) addNoteModalInstance = new bootstrap.Modal(noteEl);

        const fuEl = document.getElementById("scheduleFollowUpModal");
        if (fuEl) scheduleFollowUpModalInstance = new bootstrap.Modal(fuEl);

        const detEl = document.getElementById("studentDetailModal");
        if (detEl) studentDetailModalInstance = new bootstrap.Modal(detEl);

        // 4. Setup Event Listeners
        setupEventListeners();

        // 5. Load Data
        await Promise.all([
            loadDashboardMetrics(),
            loadAssignedStudents(),
            loadFollowUps()
        ]);
    }

    /**
     * Renders user info and logout button in header.
     */
    function renderNav() {
        if (!navAuthContainer || !currentUser) return;
        navAuthContainer.innerHTML = `
            <div class="d-flex align-items-center gap-2">
                <div class="text-end d-none d-sm-block">
                    <div class="text-white small fw-bold">${escapeHtml(currentUser.username)}</div>
                    <div class="text-secondary xsmall">${escapeHtml(currentUser.role)}</div>
                </div>
                <button id="logoutBtn" class="btn btn-outline-danger btn-sm rounded-pill px-3">
                    <i class="fa-solid fa-arrow-right-from-bracket me-1"></i> Logout
                </button>
            </div>
        `;

        const logoutBtn = document.getElementById("logoutBtn");
        if (logoutBtn) {
            logoutBtn.addEventListener("click", () => {
                authClient.logout();
                window.location.href = "login.html";
            });
        }
    }

    /**
     * Sets up UI event handlers.
     */
    function setupEventListeners() {
        if (studentSearchInput) {
            studentSearchInput.addEventListener("input", filterStudentsTable);
        }

        if (refreshStudentsBtn) {
            refreshStudentsBtn.addEventListener("click", async () => {
                refreshStudentsBtn.disabled = true;
                await Promise.all([loadDashboardMetrics(), loadAssignedStudents()]);
                refreshStudentsBtn.disabled = false;
            });
        }

        if (refreshFollowUpsBtn) {
            refreshFollowUpsBtn.addEventListener("click", async () => {
                refreshFollowUpsBtn.disabled = true;
                await loadFollowUps();
                refreshFollowUpsBtn.disabled = false;
            });
        }

        if (followUpStatusFilter) {
            followUpStatusFilter.addEventListener("change", loadFollowUps);
        }

        if (saveNoteSubmitBtn) {
            saveNoteSubmitBtn.addEventListener("click", submitCounsellingNote);
        }

        if (saveFuSubmitBtn) {
            saveFuSubmitBtn.addEventListener("click", submitFollowUp);
        }

        // Set min date for follow-up datepicker to today
        if (fuDatePicker) {
            const today = new Date().toISOString().split("T")[0];
            fuDatePicker.setAttribute("min", today);
        }
    }

    /**
     * Fetches and renders official API-driven KPI dashboard metrics.
     */
    async function loadDashboardMetrics() {
        try {
            const token = authClient.getToken();
            const resp = await fetch("/api/counsellor/dashboard", {
                headers: { "Authorization": `Bearer ${token}` }
            });

            if (!resp.ok) {
                console.error("Failed to load dashboard metrics", resp.status);
                return;
            }

            const data = await resp.json();
            const m = data.metrics || {};

            if (metricAssignedStudents) metricAssignedStudents.textContent = m.assigned_students ?? 0;
            if (metricReportsReady) metricReportsReady.textContent = m.reports_ready ?? 0;
            if (metricPendingReview) metricPendingReview.textContent = m.pending_counselling ?? 0;
            if (metricActiveFollowUps) metricActiveFollowUps.textContent = m.active_follow_ups ?? 0;
        } catch (err) {
            console.error("Error loading metrics:", err);
        }
    }

    /**
     * Fetches and renders assigned students.
     */
    async function loadAssignedStudents() {
        try {
            const token = authClient.getToken();
            const resp = await fetch("/api/counsellor/students", {
                headers: { "Authorization": `Bearer ${token}` }
            });

            if (!resp.ok) {
                if (resp.status === 403) {
                    assignedStudentsTbody.innerHTML = `
                        <tr>
                            <td colspan="7" class="text-center py-4 text-danger">
                                <i class="fa-solid fa-ban me-1"></i> Access Forbidden: Counsellor assignment required.
                            </td>
                        </tr>
                    `;
                    return;
                }
                throw new Error(`Server returned ${resp.status}`);
            }

            const data = await resp.json();
            assignedStudents = data.students || [];
            renderStudentsTable(assignedStudents);
        } catch (err) {
            console.error("Error loading assigned students:", err);
            if (assignedStudentsTbody) {
                assignedStudentsTbody.innerHTML = `
                    <tr>
                        <td colspan="7" class="text-center py-4 text-danger">
                            <i class="fa-solid fa-triangle-exclamation me-1"></i> Failed to load assigned students. Please try again.
                        </td>
                    </tr>
                `;
            }
        }
    }

    /**
     * Filters students table by search query.
     */
    function filterStudentsTable() {
        const query = (studentSearchInput?.value || "").toLowerCase().trim();
        if (!query) {
            renderStudentsTable(assignedStudents);
            return;
        }

        const filtered = assignedStudents.filter(item => {
            const name = (item.student_name || "").toLowerCase();
            const sid = (item.student_id || "").toLowerCase();
            const aid = (item.assessment_id || "").toLowerCase();
            return name.includes(query) || sid.includes(query) || aid.includes(query);
        });

        renderStudentsTable(filtered);
    }

    /**
     * Renders student rows into table body.
     */
    function renderStudentsTable(students) {
        if (!assignedStudentsTbody) return;

        if (!students || students.length === 0) {
            assignedStudentsTbody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center py-5 text-secondary">
                        <i class="fa-solid fa-folder-open fs-3 d-block mb-2 text-secondary opacity-50"></i>
                        No assigned students found in your active directory.
                    </td>
                </tr>
            `;
            return;
        }

        let html = "";
        students.forEach(st => {
            const asmId = st.assessment_id || "N/A";
            const stuId = st.student_id || "N/A";
            const stuName = st.student_name || "Unknown Student";
            const asmStatus = st.assessment_status || "REGISTERED";

            // Scan Badges
            const leftStatus = st.left_scan_status || "PENDING";
            const rightStatus = st.right_scan_status || "PENDING";
            const leftBadgeClass = leftStatus === "COMPLETED" ? "badge bg-success bg-opacity-20 text-success" : "badge bg-secondary bg-opacity-20 text-light";
            const rightBadgeClass = rightStatus === "COMPLETED" ? "badge bg-success bg-opacity-20 text-success" : "badge bg-secondary bg-opacity-20 text-light";

            // Workflow status badge
            let asmBadgeClass = "badge bg-secondary bg-opacity-25 text-light";
            if (asmStatus === "ANALYSIS_COMPLETED" || asmStatus === "COMPLETED") {
                asmBadgeClass = "badge bg-primary bg-opacity-25 text-primary border border-primary border-opacity-30";
            } else if (asmStatus === "SCAN_COMPLETED") {
                asmBadgeClass = "badge bg-info bg-opacity-25 text-info border border-info border-opacity-30";
            }

            // Report & Review Badges
            const repStatus = st.report_status;
            let reportBadgeHtml = "";
            if (repStatus === "REPORT_READY") {
                if (st.reviewed_status) {
                    reportBadgeHtml = `
                        <div class="d-flex flex-column gap-1">
                            <span class="badge bg-success bg-opacity-20 text-success"><i class="fa-solid fa-check me-1"></i>Reviewed</span>
                            <span class="text-secondary xsmall">${st.report_version || "v1.0"}</span>
                        </div>
                    `;
                } else {
                    reportBadgeHtml = `
                        <div class="d-flex flex-column gap-1">
                            <span class="badge bg-warning bg-opacity-20 text-warning"><i class="fa-solid fa-clock me-1"></i>Ready for Review</span>
                            <span class="text-secondary xsmall">${st.report_version || "v1.0"}</span>
                        </div>
                    `;
                }
            } else {
                reportBadgeHtml = `<span class="badge bg-secondary bg-opacity-20 text-secondary">Report Pending</span>`;
            }

            // Follow-up status
            const activeFuCount = st.active_follow_ups_count || 0;
            const fuBadgeHtml = activeFuCount > 0
                ? `<span class="badge bg-info bg-opacity-20 text-info"><i class="fa-solid fa-calendar me-1"></i>${activeFuCount} Scheduled</span>`
                : `<span class="text-secondary xsmall">None</span>`;

            html += `
                <tr>
                    <td>
                        <div class="fw-bold text-white">${escapeHtml(stuName)}</div>
                        <div class="text-secondary xsmall mono-text">${escapeHtml(stuId)}</div>
                    </td>
                    <td>
                        <span class="mono-text text-info">${escapeHtml(asmId)}</span>
                    </td>
                    <td>
                        <div class="d-flex gap-1">
                            <span class="${leftBadgeClass} xsmall" title="Left Eye Scan">L: ${leftStatus}</span>
                            <span class="${rightBadgeClass} xsmall" title="Right Eye Scan">R: ${rightStatus}</span>
                        </div>
                    </td>
                    <td>
                        <span class="${asmBadgeClass}">${escapeHtml(asmStatus)}</span>
                    </td>
                    <td>
                        ${reportBadgeHtml}
                    </td>
                    <td>
                        ${fuBadgeHtml}
                    </td>
                    <td class="text-end">
                        <div class="dropdown">
                            <button class="btn btn-outline-secondary btn-sm rounded-pill px-2 py-1 dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                                <i class="fa-solid fa-ellipsis-vertical"></i> Actions
                            </button>
                            <ul class="dropdown-menu dropdown-menu-dark dropdown-menu-end shadow-lg border-secondary border-opacity-30">
                                ${repStatus === "REPORT_READY" ? `
                                    <li>
                                        <a class="dropdown-item small" href="official_report.html?assessment_id=${encodeURIComponent(asmId)}" target="_blank">
                                            <i class="fa-solid fa-file-invoice text-success me-2"></i>View Official Report
                                        </a>
                                    </li>
                                ` : `
                                    <li>
                                        <span class="dropdown-item small text-secondary disabled">
                                            <i class="fa-solid fa-file-invoice me-2"></i>Report Not Ready
                                        </span>
                                    </li>
                                `}
                                <li>
                                    <button class="dropdown-item small" onclick="window.irisCounsellor.openAddNoteModal('${escapeJs(asmId)}', '${escapeJs(stuName)}')">
                                        <i class="fa-solid fa-pen-to-square text-primary me-2"></i>Add Counselling Note
                                    </button>
                                </li>
                                <li>
                                    <button class="dropdown-item small" onclick="window.irisCounsellor.openScheduleFollowUpModal('${escapeJs(asmId)}', '${escapeJs(stuName)}')">
                                        <i class="fa-solid fa-calendar-plus text-info me-2"></i>Schedule Follow-up
                                    </button>
                                </li>
                                <li><hr class="dropdown-divider border-secondary border-opacity-20"></li>
                                <li>
                                    <button class="dropdown-item small" onclick="window.irisCounsellor.viewStudentDetails('${escapeJs(stuId)}', '${escapeJs(asmId)}')">
                                        <i class="fa-solid fa-id-card-clip text-light me-2"></i>View Case Details
                                    </button>
                                </li>
                            </ul>
                        </div>
                    </td>
                </tr>
            `;
        });

        assignedStudentsTbody.innerHTML = html;
    }

    /**
     * Fetches and renders follow-ups.
     */
    async function loadFollowUps() {
        if (!followUpsTbody) return;

        try {
            const token = authClient.getToken();
            const statusVal = followUpStatusFilter ? followUpStatusFilter.value : "";
            let url = "/api/counsellor/follow-ups";
            if (statusVal) url += `?status=${encodeURIComponent(statusVal)}`;

            const resp = await fetch(url, {
                headers: { "Authorization": `Bearer ${token}` }
            });

            if (!resp.ok) {
                throw new Error(`Server returned ${resp.status}`);
            }

            const data = await resp.json();
            followUpsList = data.follow_ups || [];
            renderFollowUpsTable(followUpsList);
        } catch (err) {
            console.error("Error loading follow-ups:", err);
            followUpsTbody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center py-4 text-danger">
                        <i class="fa-solid fa-triangle-exclamation me-1"></i> Failed to load follow-ups.
                    </td>
                </tr>
            `;
        }
    }

    /**
     * Renders follow-ups table.
     */
    function renderFollowUpsTable(items) {
        if (!followUpsTbody) return;

        if (!items || items.length === 0) {
            followUpsTbody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center py-5 text-secondary">
                        <i class="fa-solid fa-calendar-check fs-3 d-block mb-2 text-secondary opacity-50"></i>
                        No scheduled follow-up consultations found matching criteria.
                    </td>
                </tr>
            `;
            return;
        }

        let html = "";
        items.forEach(fu => {
            const fuId = fu.follow_up_id;
            const stuName = fu.student_name || "Student";
            const stuId = fu.student_id || "--";
            const asmId = fu.assessment_id || "--";
            const fuDate = fu.follow_up_date || "--";
            const status = fu.status || "Pending";
            const notes = fu.notes || "No notes recorded.";

            let badgeClass = "badge bg-secondary bg-opacity-25 text-light";
            if (status === "Pending") badgeClass = "badge bg-warning bg-opacity-20 text-warning";
            else if (status === "Completed") badgeClass = "badge bg-success bg-opacity-20 text-success";
            else if (status === "Cancelled") badgeClass = "badge bg-danger bg-opacity-20 text-danger";
            else if (status === "Overdue") badgeClass = "badge bg-danger text-white";

            const canUpdate = (status === "Pending" || status === "Overdue");

            html += `
                <tr>
                    <td>
                        <div class="fw-bold text-white">${escapeHtml(stuName)}</div>
                        <div class="text-secondary xsmall mono-text">${escapeHtml(stuId)}</div>
                    </td>
                    <td>
                        <span class="mono-text text-info">${escapeHtml(asmId)}</span>
                    </td>
                    <td>
                        <div class="text-white"><i class="fa-regular fa-calendar me-1 text-info"></i>${escapeHtml(fuDate)}</div>
                    </td>
                    <td>
                        <span class="${badgeClass}">${escapeHtml(status)}</span>
                    </td>
                    <td>
                        <div class="text-light small text-truncate" style="max-width: 250px;" title="${escapeHtml(notes)}">
                            ${escapeHtml(notes)}
                        </div>
                    </td>
                    <td class="text-end">
                        ${canUpdate ? `
                            <div class="btn-group btn-group-sm">
                                <button type="button" class="btn btn-outline-success btn-sm" onclick="window.irisCounsellor.updateFollowUpStatus('${escapeJs(fuId)}', 'Completed')" title="Mark Completed">
                                    <i class="fa-solid fa-check"></i>
                                </button>
                                <button type="button" class="btn btn-outline-danger btn-sm" onclick="window.irisCounsellor.updateFollowUpStatus('${escapeJs(fuId)}', 'Cancelled')" title="Cancel Follow-up">
                                    <i class="fa-solid fa-xmark"></i>
                                </button>
                            </div>
                        ` : `
                            <span class="text-secondary xsmall">--</span>
                        `}
                    </td>
                </tr>
            `;
        });

        followUpsTbody.innerHTML = html;
    }

    /**
     * Updates follow-up status (Completed or Cancelled).
     */
    async function updateFollowUpStatus(fuId, newStatus) {
        if (!confirm(`Are you sure you want to mark this follow-up consultation as ${newStatus}?`)) {
            return;
        }

        try {
            const token = authClient.getToken();
            const resp = await fetch(`/api/follow-ups/${encodeURIComponent(fuId)}`, {
                method: "PATCH",
                headers: {
                    "Authorization": `Bearer ${token}`,
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ status: newStatus })
            });

            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                alert(`Failed to update follow-up: ${err.detail || resp.statusText}`);
                return;
            }

            await Promise.all([loadFollowUps(), loadDashboardMetrics(), loadAssignedStudents()]);
        } catch (err) {
            console.error("Error updating follow-up:", err);
            alert(`Network error: ${err.message}`);
        }
    }

    /**
     * Opens modal to add counselling note.
     */
    function openAddNoteModal(asmId, studentName) {
        currentSelectedAsmId = asmId;
        currentSelectedStudentName = studentName;

        if (modalNoteAsmId) modalNoteAsmId.textContent = asmId;
        if (modalNoteStudentName) modalNoteStudentName.textContent = studentName;
        if (counsellingNoteInput) counsellingNoteInput.value = "";

        if (addNoteModalInstance) addNoteModalInstance.show();
    }

    /**
     * Submits counselling note.
     */
    async function submitCounsellingNote() {
        const note = (counsellingNoteInput?.value || "").trim();
        if (!note) {
            alert("Please enter a counselling observation or guidance note.");
            return;
        }

        if (!currentSelectedAsmId) return;

        if (saveNoteSpinner) saveNoteSpinner.classList.remove("d-none");
        if (saveNoteSubmitBtn) saveNoteSubmitBtn.disabled = true;

        try {
            const token = authClient.getToken();
            const resp = await fetch(`/api/assessments/${encodeURIComponent(currentSelectedAsmId)}/notes`, {
                method: "POST",
                headers: {
                    "Authorization": `Bearer ${token}`,
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ note: note })
            });

            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || `Server returned ${resp.status}`);
            }

            if (addNoteModalInstance) addNoteModalInstance.hide();
            await Promise.all([loadDashboardMetrics(), loadAssignedStudents()]);
            alert("Counselling note recorded successfully.");
        } catch (err) {
            console.error("Error submitting note:", err);
            alert(`Failed to save note: ${err.message}`);
        } finally {
            if (saveNoteSpinner) saveNoteSpinner.classList.add("d-none");
            if (saveNoteSubmitBtn) saveNoteSubmitBtn.disabled = false;
        }
    }

    /**
     * Opens modal to schedule follow-up.
     */
    function openScheduleFollowUpModal(asmId, studentName) {
        currentSelectedAsmId = asmId;
        currentSelectedStudentName = studentName;

        if (modalFuAsmId) modalFuAsmId.textContent = asmId;
        if (modalFuStudentName) modalFuStudentName.textContent = studentName;
        if (fuDatePicker) fuDatePicker.value = "";
        if (fuNotesInput) fuNotesInput.value = "";

        if (scheduleFollowUpModalInstance) scheduleFollowUpModalInstance.show();
    }

    /**
     * Submits scheduled follow-up.
     */
    async function submitFollowUp() {
        const dateVal = (fuDatePicker?.value || "").trim();
        const notesVal = (fuNotesInput?.value || "").trim();

        if (!dateVal) {
            alert("Please select a consultation date.");
            return;
        }

        if (!currentSelectedAsmId) return;

        if (saveFuSpinner) saveFuSpinner.classList.remove("d-none");
        if (saveFuSubmitBtn) saveFuSubmitBtn.disabled = true;

        try {
            const token = authClient.getToken();
            const resp = await fetch(`/api/assessments/${encodeURIComponent(currentSelectedAsmId)}/follow-ups`, {
                method: "POST",
                headers: {
                    "Authorization": `Bearer ${token}`,
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    follow_up_date: dateVal,
                    notes: notesVal || null
                })
            });

            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || `Server returned ${resp.status}`);
            }

            if (scheduleFollowUpModalInstance) scheduleFollowUpModalInstance.hide();
            await Promise.all([loadDashboardMetrics(), loadFollowUps(), loadAssignedStudents()]);
            alert("Follow-up consultation scheduled successfully.");
        } catch (err) {
            console.error("Error scheduling follow-up:", err);
            alert(`Failed to schedule follow-up: ${err.message}`);
        } finally {
            if (saveFuSpinner) saveFuSpinner.classList.add("d-none");
            if (saveFuSubmitBtn) saveFuSubmitBtn.disabled = false;
        }
    }

    /**
     * Views complete case details in modal.
     */
    async function viewStudentDetails(studentId, asmId) {
        if (!studentDetailModalBody) return;
        studentDetailModalBody.innerHTML = `
            <div class="text-center py-5">
                <div class="spinner-border text-primary me-2" role="status"></div>
                <div class="text-secondary small mt-2">Loading case records for ${escapeHtml(studentId)}...</div>
            </div>
        `;

        if (studentDetailModalInstance) studentDetailModalInstance.show();

        try {
            const token = authClient.getToken();

            // Fetch student info, assessment details, notes, and follow-ups in parallel
            const [stuResp, asmResp, notesResp, fuResp] = await Promise.all([
                fetch(`/api/counsellor/students/${encodeURIComponent(studentId)}`, {
                    headers: { "Authorization": `Bearer ${token}` }
                }),
                fetch(`/api/counsellor/assessments/${encodeURIComponent(asmId)}`, {
                    headers: { "Authorization": `Bearer ${token}` }
                }),
                fetch(`/api/assessments/${encodeURIComponent(asmId)}/notes`, {
                    headers: { "Authorization": `Bearer ${token}` }
                }),
                fetch(`/api/assessments/${encodeURIComponent(asmId)}/follow-ups`, {
                    headers: { "Authorization": `Bearer ${token}` }
                })
            ]);

            if (!stuResp.ok || !asmResp.ok) {
                throw new Error("Unable to retrieve complete student or assessment details.");
            }

            const stuData = await stuResp.json();
            const asmData = await asmResp.json();
            const notesData = notesResp.ok ? await notesResp.json() : { notes: [] };
            const fuData = fuResp.ok ? await fuResp.json() : { follow_ups: [] };

            const st = stuData.student || {};
            const asm = asmData || {};
            const scans = asm.scans || {};
            const leftScan = scans.LEFT || {};
            const rightScan = scans.RIGHT || {};
            const rep = asm.report || {};
            const notes = notesData.notes || [];
            const fus = fuData.follow_ups || [];

            studentDetailModalBody.innerHTML = `
                <div class="d-flex flex-column gap-4">
                    <!-- Student Header -->
                    <div class="p-3 rounded-3" style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.07);">
                        <div class="row g-3">
                            <div class="col-sm-6">
                                <div class="text-secondary xsmall text-uppercase fw-bold">Student Name</div>
                                <div class="fs-5 fw-bold text-white">${escapeHtml(st.student_name || "N/A")}</div>
                                <div class="text-secondary small mono-text">${escapeHtml(st.student_id || studentId)}</div>
                            </div>
                            <div class="col-sm-6 text-sm-end">
                                <div class="text-secondary xsmall text-uppercase fw-bold">Assessment ID</div>
                                <div class="fs-6 fw-bold text-info mono-text">${escapeHtml(asmId)}</div>
                                <div class="mt-1">
                                    <span class="badge bg-primary bg-opacity-20 text-primary border border-primary border-opacity-30">
                                        ${escapeHtml(asm.assessment_status || "ACTIVE")}
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Dual Eye Scan & Analysis Status -->
                    <div>
                        <h6 class="text-white fw-bold mb-3"><i class="fa-solid fa-eye text-primary me-2"></i>Biometric Scans & Analysis</h6>
                        <div class="row g-3">
                            <div class="col-md-6">
                                <div class="p-3 rounded-3" style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06);">
                                    <div class="d-flex justify-content-between align-items-center mb-1">
                                        <span class="fw-bold text-white small">Left Eye Scan</span>
                                        <span class="badge ${leftScan.status === 'COMPLETED' ? 'bg-success bg-opacity-20 text-success' : 'bg-secondary bg-opacity-25 text-light'}">
                                            ${escapeHtml(leftScan.status || "PENDING")}
                                        </span>
                                    </div>
                                    <div class="text-secondary xsmall">Scan ID: <span class="mono-text">${escapeHtml(leftScan.scan_id || "--")}</span></div>
                                    <div class="text-secondary xsmall">Completed: ${escapeHtml(leftScan.completed_at || "--")}</div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="p-3 rounded-3" style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06);">
                                    <div class="d-flex justify-content-between align-items-center mb-1">
                                        <span class="fw-bold text-white small">Right Eye Scan</span>
                                        <span class="badge ${rightScan.status === 'COMPLETED' ? 'bg-success bg-opacity-20 text-success' : 'bg-secondary bg-opacity-25 text-light'}">
                                            ${escapeHtml(rightScan.status || "PENDING")}
                                        </span>
                                    </div>
                                    <div class="text-secondary xsmall">Scan ID: <span class="mono-text">${escapeHtml(rightScan.scan_id || "--")}</span></div>
                                    <div class="text-secondary xsmall">Completed: ${escapeHtml(rightScan.completed_at || "--")}</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Official Report Status -->
                    <div>
                        <h6 class="text-white fw-bold mb-3"><i class="fa-solid fa-file-invoice text-success me-2"></i>Structured Report Status</h6>
                        <div class="p-3 rounded-3 d-flex justify-content-between align-items-center" style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06);">
                            <div>
                                <div class="text-white small fw-bold">Report Status: <span class="text-info">${escapeHtml(rep.status || "NOT_GENERATED")}</span></div>
                                <div class="text-secondary xsmall">Version: ${escapeHtml(rep.version || "N/A")} | Reviewed: ${rep.reviewed_status ? `Yes (by ${escapeHtml(rep.reviewed_by || "Counsellor")})` : "Pending"}</div>
                            </div>
                            ${rep.status === "REPORT_READY" ? `
                                <a href="official_report.html?assessment_id=${encodeURIComponent(asmId)}" target="_blank" class="btn btn-outline-success btn-sm rounded-pill px-3">
                                    <i class="fa-solid fa-arrow-up-right-from-square me-1"></i> Open Report
                                </a>
                            ` : `
                                <span class="badge bg-secondary bg-opacity-25 text-light">Not Available</span>
                            `}
                        </div>
                    </div>

                    <!-- Clinical Counselling Notes History -->
                    <div>
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <h6 class="text-white fw-bold mb-0"><i class="fa-solid fa-pen-fancy text-info me-2"></i>Clinical Notes (${notes.length})</h6>
                            <button class="btn btn-outline-primary btn-sm rounded-pill py-0 px-2 small" onclick="window.irisCounsellor.openAddNoteModal('${escapeJs(asmId)}', '${escapeJs(st.student_name || "")}')">
                                <i class="fa-solid fa-plus me-1"></i> Add
                            </button>
                        </div>
                        ${notes.length > 0 ? `
                            <div class="d-flex flex-column gap-2 mt-2">
                                ${notes.map(n => `
                                    <div class="p-2 rounded-2" style="background: rgba(255,255,255,0.02); border-left: 3px solid #3b82f6;">
                                        <div class="d-flex justify-content-between text-secondary xsmall mb-1">
                                            <span><i class="fa-solid fa-user-nurse me-1"></i>${escapeHtml(n.counsellor_id || "Counsellor")}</span>
                                            <span>${escapeHtml(n.created_at || "")}</span>
                                        </div>
                                        <div class="text-light small">${escapeHtml(n.note || "")}</div>
                                    </div>
                                `).join("")}
                            </div>
                        ` : `
                            <div class="text-secondary xsmall py-2">No counselling notes recorded yet.</div>
                        `}
                    </div>

                    <!-- Scheduled Follow-ups -->
                    <div>
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <h6 class="text-white fw-bold mb-0"><i class="fa-solid fa-calendar-days text-warning me-2"></i>Follow-ups (${fus.length})</h6>
                            <button class="btn btn-outline-info btn-sm rounded-pill py-0 px-2 small" onclick="window.irisCounsellor.openScheduleFollowUpModal('${escapeJs(asmId)}', '${escapeJs(st.student_name || "")}')">
                                <i class="fa-solid fa-plus me-1"></i> Schedule
                            </button>
                        </div>
                        ${fus.length > 0 ? `
                            <div class="d-flex flex-column gap-2 mt-2">
                                ${fus.map(f => `
                                    <div class="p-2 rounded-2 d-flex justify-content-between align-items-center" style="background: rgba(255,255,255,0.02); border-left: 3px solid #06b6d4;">
                                        <div>
                                            <div class="text-white small fw-bold"><i class="fa-regular fa-calendar me-1 text-info"></i>${escapeHtml(f.follow_up_date || "")}</div>
                                            <div class="text-secondary xsmall">${escapeHtml(f.notes || "No agenda specified")}</div>
                                        </div>
                                        <span class="badge ${f.status === 'Completed' ? 'bg-success bg-opacity-20 text-success' : 'bg-warning bg-opacity-20 text-warning'}">
                                            ${escapeHtml(f.status || "Pending")}
                                        </span>
                                    </div>
                                `).join("")}
                            </div>
                        ` : `
                            <div class="text-secondary xsmall py-2">No follow-up consultations scheduled.</div>
                        `}
                    </div>
                </div>
            `;
        } catch (err) {
            console.error("Error viewing student details:", err);
            studentDetailModalBody.innerHTML = `
                <div class="text-center py-4 text-danger">
                    <i class="fa-solid fa-triangle-exclamation fs-3 d-block mb-2"></i>
                    Failed to load case details: ${escapeHtml(err.message)}
                </div>
            `;
        }
    }

    // Helper functions
    function escapeHtml(text) {
        if (!text) return "";
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function escapeJs(text) {
        if (!text) return "";
        return String(text)
            .replace(/\\/g, "\\\\")
            .replace(/'/g, "\\'")
            .replace(/"/g, '\\"')
            .replace(/\n/g, "\\n");
    }

    // Expose global methods for inline HTML event handlers
    window.irisCounsellor = {
        openAddNoteModal,
        openScheduleFollowUpModal,
        viewStudentDetails,
        updateFollowUpStatus
    };

    // Auto-initialize when DOM is ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
