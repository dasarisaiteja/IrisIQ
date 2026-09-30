/**
 * Official IRIS Admin Portal Controller (Phase 8)
 * Conforms strictly to IRIS_Backend_Detailed_Requirements.docx & IRIS_Frontend_Detailed_Requirements.docx.
 * 
 * Features:
 * - 100% API-driven data integration across all modules
 * - Strict Admin RBAC checking and session expiration handling
 * - Zero hardcoded statistics, student names, or assessment states
 * - Modular tab routing with instant updates
 */

(function () {
    "use strict";

    // -------------------------------------------------------------
    // 1. STATE & AUTH INITIALIZATION
    // -------------------------------------------------------------
    const userObj = (window.IrisAuth && window.IrisAuth.getUser()) || null;
    const token = localStorage.getItem("token") || (window.IrisAuth && window.IrisAuth.getToken()) || localStorage.getItem("iris_access_token");
    const role = localStorage.getItem("role") || (userObj && userObj.role) || (window.IrisAuth && window.IrisAuth.getRole()) || "";
    const username = localStorage.getItem("username") || (userObj && (userObj.full_name || userObj.username)) || "admin";

    const authGuardOverlay = document.getElementById("authGuardOverlay");
    const currentSectionTitle = document.getElementById("currentSectionTitle");
    const adminUserDisplay = document.getElementById("adminUserDisplay");

    if (adminUserDisplay) {
        adminUserDisplay.textContent = username;
    }

    function checkAuth() {
        const curToken = token || (window.IrisAuth && window.IrisAuth.getToken()) || localStorage.getItem("iris_access_token");
        const curRole = role || (window.IrisAuth && window.IrisAuth.getRole()) || localStorage.getItem("role") || "";
        if (!curToken || (curRole.toLowerCase() !== "admin")) {
            if (authGuardOverlay) authGuardOverlay.style.display = "flex";
            setTimeout(() => {
                window.location.href = "login.html";
            }, 1800);
            return false;
        }
        return true;
    }

    if (!checkAuth()) return;

    function getAuthHeaders() {
        const curToken = token || (window.IrisAuth && window.IrisAuth.getToken()) || localStorage.getItem("iris_access_token");
        return {
            "Authorization": `Bearer ${curToken}`,
            "Content-Type": "application/json"
        };
    }

    async function apiFetch(url, options = {}) {
        const headers = { ...getAuthHeaders(), ...(options.headers || {}) };
        try {
            const resp = await fetch(url, { ...options, headers });
            if (resp.status === 401) {
                localStorage.removeItem("token");
                localStorage.removeItem("role");
                if (authGuardOverlay) {
                    document.getElementById("authGuardMessage").textContent = "Your administrative session has expired. Redirecting to login...";
                    authGuardOverlay.style.display = "flex";
                }
                setTimeout(() => { window.location.href = "login.html"; }, 1500);
                throw new Error("Session expired");
            }
            return resp;
        } catch (err) {
            console.error("API Fetch Error:", err);
            throw err;
        }
    }

    // -------------------------------------------------------------
    // 2. TAB & NAVIGATION ROUTING
    // -------------------------------------------------------------
    const sectionTitles = {
        "dashboard": "Admin Dashboard",
        "students": "Student Directory",
        "assessments": "Assessments Management",
        "scans": "Bilateral Eye Scans Overview",
        "reports": "Official Reports Directory",
        "counsellors": "Counsellors & Assignments",
        "counselling": "Counselling & Follow-up",
        "users": "Users & Roles Administration",
        "audit": "Institutional Security Audit Trail",
        "notifications": "System Notifications",
        "settings": "Institutional Settings",
        "profile": "Administrator Profile"
    };

    function switchSection(sectionId) {
        if (!sectionTitles[sectionId]) sectionId = "dashboard";

        document.querySelectorAll(".portal-section").forEach(sec => sec.classList.remove("active"));
        document.querySelectorAll(".nav-link-custom").forEach(link => link.classList.remove("active"));

        const targetSec = document.getElementById(`sec-${sectionId}`);
        if (targetSec) targetSec.classList.add("active");

        const targetLink = document.querySelector(`.nav-link-custom[data-section="${sectionId}"]`);
        if (targetLink) targetLink.classList.add("active");

        if (currentSectionTitle) {
            currentSectionTitle.textContent = sectionTitles[sectionId];
        }

        // Trigger on-demand module loader
        if (sectionId === "dashboard") loadDashboardSummary();
        else if (sectionId === "students") loadStudents();
        else if (sectionId === "assessments") loadAssessments();
        else if (sectionId === "scans") loadScans();
        else if (sectionId === "reports") loadReports();
        else if (sectionId === "counsellors") loadCounsellors();
        else if (sectionId === "users") loadUsers();
        else if (sectionId === "audit") loadAuditLogs();

        window.location.hash = sectionId;
    }

    document.querySelectorAll(".nav-link-custom[data-section]").forEach(link => {
        link.addEventListener("click", function (e) {
            e.preventDefault();
            const sec = this.getAttribute("data-section");
            switchSection(sec);
            // Close mobile menu if open
            document.getElementById("adminSidebar").classList.remove("show");
        });
    });

    document.querySelectorAll(".switch-tab").forEach(btn => {
        btn.addEventListener("click", function (e) {
            e.preventDefault();
            const target = this.getAttribute("data-target");
            switchSection(target);
        });
    });

    // -------------------------------------------------------------
    // 3. DASHBOARD SUMMARY
    // -------------------------------------------------------------
    async function loadDashboardSummary() {
        try {
            const resp = await apiFetch("/api/admin/dashboard/summary");
            if (!resp.ok) return;
            const data = await resp.json();

            const c = data.counts || {};
            document.getElementById("statTotalStudents").textContent = c.total_students ?? 0;
            document.getElementById("statTotalAssessments").textContent = c.total_assessments ?? 0;
            document.getElementById("statPendingScans").textContent = c.pending_scans ?? 0;
            document.getElementById("statProcessing").textContent = c.processing ?? 0;
            document.getElementById("statReportsReady").textContent = c.reports_ready ?? 0;
            document.getElementById("statCounsellors").textContent = c.counsellors ?? 0;

            // Render Recent Students
            const stuBody = document.getElementById("recentStudentsBody");
            if (stuBody) {
                if (!data.recent_students || data.recent_students.length === 0) {
                    stuBody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-3">No recent students found</td></tr>`;
                } else {
                    stuBody.innerHTML = data.recent_students.map(s => `
                        <tr>
                            <td class="mono fw-semibold text-white">${escapeHtml(s.student_id)}</td>
                            <td>${escapeHtml(s.student_name)}</td>
                            <td class="text-secondary small">${escapeHtml(s.created_at || "")}</td>
                            <td><span class="badge-status ${getStatusBadgeClass(s.latest_status)}">${escapeHtml(s.latest_status)}</span></td>
                        </tr>
                    `).join("");
                }
            }

            // Render Recent Assessments
            const asmBody = document.getElementById("recentAssessmentsBody");
            if (asmBody) {
                if (!data.recent_assessments || data.recent_assessments.length === 0) {
                    asmBody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-3">No recent assessments found</td></tr>`;
                } else {
                    asmBody.innerHTML = data.recent_assessments.map(a => `
                        <tr>
                            <td class="mono fw-semibold text-primary">${escapeHtml(a.assessment_id)}</td>
                            <td>${escapeHtml(a.student_name)}</td>
                            <td><span class="badge-status ${getStatusBadgeClass(a.workflow_status)}">${escapeHtml(a.workflow_status)}</span></td>
                            <td><span class="badge-status ${a.report_status === 'REPORT_READY' ? 'status-ready' : 'status-pending'}">${escapeHtml(a.report_status)}</span></td>
                        </tr>
                    `).join("");
                }
            }
        } catch (e) {
            console.error("Error loading dashboard summary:", e);
        }
    }

    // -------------------------------------------------------------
    // 4. STUDENTS MANAGEMENT
    // -------------------------------------------------------------
    async function loadStudents() {
        const tbody = document.getElementById("studentsTableBody");
        const search = document.getElementById("studentSearchInput")?.value || "";
        tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-4"><i class="fa-solid fa-spinner fa-spin me-2"></i>Loading students...</td></tr>`;

        try {
            const url = `/api/admin/students?limit=50${search ? `&search=${encodeURIComponent(search)}` : ""}`;
            const resp = await apiFetch(url);
            if (!resp.ok) throw new Error("Failed to load students");
            const data = await resp.json();

            if (!data.students || data.students.length === 0) {
                tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-4">No students registered yet</td></tr>`;
                return;
            }

            tbody.innerHTML = data.students.map(s => `
                <tr>
                    <td class="mono fw-semibold text-white">${escapeHtml(s.student_id)}</td>
                    <td class="fw-semibold">${escapeHtml(s.student_name)}</td>
                    <td><span class="badge-status ${getStatusBadgeClass(s.assessment_status)}">${escapeHtml(s.assessment_status)}</span></td>
                    <td><span class="badge-status ${s.left_eye === 'Completed' ? 'status-ready' : 'status-pending'}">${escapeHtml(s.left_eye)}</span></td>
                    <td><span class="badge-status ${s.right_eye === 'Completed' ? 'status-ready' : 'status-pending'}">${escapeHtml(s.right_eye)}</span></td>
                    <td><span class="badge-status ${s.report === 'Ready' ? 'status-ready' : 'status-pending'}">${escapeHtml(s.report)}</span></td>
                    <td class="small text-secondary">${escapeHtml(s.counsellor || "Unassigned")}</td>
                    <td class="small text-secondary">${escapeHtml(s.date || "")}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-info view-student-btn py-0 px-2" data-id="${escapeHtml(s.student_id)}">
                            <i class="fa-solid fa-eye me-1"></i>View
                        </button>
                    </td>
                </tr>
            `).join("");

            document.querySelectorAll(".view-student-btn").forEach(btn => {
                btn.addEventListener("click", function () {
                    const sid = this.getAttribute("data-id");
                    inspectStudentDetail(sid);
                });
            });
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="9" class="text-center text-danger py-4">Error loading students</td></tr>`;
        }
    }

    async function inspectStudentDetail(studentId) {
        const body = document.getElementById("studentDetailBody");
        const modal = new bootstrap.Modal(document.getElementById("studentDetailModal"));
        body.innerHTML = `<div class="text-center py-4 text-muted"><i class="fa-solid fa-spinner fa-spin me-2"></i>Loading details...</div>`;
        modal.show();

        try {
            const resp = await apiFetch(`/api/admin/students/${encodeURIComponent(studentId)}`);
            if (!resp.ok) throw new Error("Failed to load student detail");
            const data = await resp.json();
            const s = data.student || {};
            const d = data.demographics || {};
            const asm = data.assessments || [];

            body.innerHTML = `
                <div class="row g-3 mb-4">
                    <div class="col-md-6">
                        <div class="glass-card p-3 mb-0">
                            <h6 class="fw-bold text-white mb-2">Student Information</h6>
                            <div class="small mb-1"><span class="text-secondary">Student ID:</span> <strong class="mono text-white">${escapeHtml(s.student_id)}</strong></div>
                            <div class="small mb-1"><span class="text-secondary">Full Name:</span> <strong class="text-white">${escapeHtml(s.student_name)}</strong></div>
                            <div class="small mb-1"><span class="text-secondary">Registered By:</span> ${escapeHtml(s.created_by)}</div>
                            <div class="small"><span class="text-secondary">Registration Date:</span> ${escapeHtml(s.created_at)}</div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="glass-card p-3 mb-0">
                            <h6 class="fw-bold text-white mb-2">Approved Demographics</h6>
                            <div class="small mb-1"><span class="text-secondary">Age / Gender:</span> ${escapeHtml(d.age || "N/A")} / ${escapeHtml(d.gender || "N/A")}</div>
                            <div class="small mb-1"><span class="text-secondary">Institution:</span> ${escapeHtml(d.school_college || "N/A")}</div>
                            <div class="small mb-1"><span class="text-secondary">Stream / Course:</span> ${escapeHtml(d.stream || "N/A")} / ${escapeHtml(d.course || "N/A")}</div>
                            <div class="small"><span class="text-secondary">Location:</span> ${escapeHtml(d.location || "N/A")}</div>
                        </div>
                    </div>
                </div>

                <h6 class="fw-bold text-white mb-2">Assessment History (${asm.length} cases)</h6>
                <div class="table-responsive">
                    <table class="custom-table">
                        <thead>
                            <tr>
                                <th>Assessment ID</th>
                                <th>Status</th>
                                <th>Created</th>
                                <th>Completed</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${asm.length === 0 ? `<tr><td colspan="4" class="text-center text-muted">No assessments on file</td></tr>` : asm.map(a => `
                                <tr>
                                    <td class="mono text-primary">${escapeHtml(a.assessment_id)}</td>
                                    <td><span class="badge-status ${getStatusBadgeClass(a.workflow_status)}">${escapeHtml(a.workflow_status)}</span></td>
                                    <td class="small text-secondary">${escapeHtml(a.created_at)}</td>
                                    <td class="small text-secondary">${escapeHtml(a.completed_at || "In Progress")}</td>
                                </tr>
                            `).join("")}
                        </tbody>
                    </table>
                </div>
            `;
        } catch (e) {
            body.innerHTML = `<div class="text-center text-danger py-4">Error loading student profile</div>`;
        }
    }

    // -------------------------------------------------------------
    // 5. ASSESSMENTS MANAGEMENT
    // -------------------------------------------------------------
    async function loadAssessments() {
        const tbody = document.getElementById("assessmentsTableBody");
        const statusFilter = document.getElementById("assessmentStatusFilter")?.value || "";
        const search = document.getElementById("assessmentSearchInput")?.value || "";
        tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-4"><i class="fa-solid fa-spinner fa-spin me-2"></i>Loading assessments...</td></tr>`;

        try {
            let url = `/api/admin/assessments?limit=50`;
            if (statusFilter) url += `&status=${encodeURIComponent(statusFilter)}`;
            if (search) url += `&search=${encodeURIComponent(search)}`;

            const resp = await apiFetch(url);
            if (!resp.ok) throw new Error("Failed to load assessments");
            const data = await resp.json();

            if (!data.assessments || data.assessments.length === 0) {
                tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-4">No assessments found</td></tr>`;
                return;
            }

            tbody.innerHTML = data.assessments.map(a => `
                <tr>
                    <td class="mono fw-semibold text-primary">${escapeHtml(a.assessment_id)}</td>
                    <td>
                        <div class="fw-semibold text-white">${escapeHtml(a.student_name)}</div>
                        <small class="mono text-secondary">${escapeHtml(a.student_id)}</small>
                    </td>
                    <td><span class="badge-status ${getStatusBadgeClass(a.workflow_status)}">${escapeHtml(a.workflow_status)}</span></td>
                    <td><span class="badge-status ${a.left_scan_status === 'Completed' ? 'status-ready' : 'status-pending'}">${escapeHtml(a.left_scan_status)}</span></td>
                    <td><span class="badge-status ${a.right_scan_status === 'Completed' ? 'status-ready' : 'status-pending'}">${escapeHtml(a.right_scan_status)}</span></td>
                    <td><span class="badge-status ${a.report_status === 'REPORT_READY' ? 'status-ready' : 'status-pending'}">${escapeHtml(a.report_status)}</span></td>
                    <td class="small text-secondary">${escapeHtml(a.counsellor_id || "Unassigned")}</td>
                    <td class="small text-secondary">${escapeHtml(a.created_at || "")}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-info inspect-asm-btn py-0 px-2" data-id="${escapeHtml(a.assessment_id)}">
                            <i class="fa-solid fa-magnifying-glass me-1"></i>Inspect
                        </button>
                    </td>
                </tr>
            `).join("");

            document.querySelectorAll(".inspect-asm-btn").forEach(btn => {
                btn.addEventListener("click", function () {
                    const aid = this.getAttribute("data-id");
                    inspectAssessmentDetail(aid);
                });
            });
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="9" class="text-center text-danger py-4">Error loading assessments</td></tr>`;
        }
    }

    async function inspectAssessmentDetail(assessmentId) {
        const body = document.getElementById("assessmentDetailBody");
        const modal = new bootstrap.Modal(document.getElementById("assessmentDetailModal"));
        body.innerHTML = `<div class="text-center py-4 text-muted"><i class="fa-solid fa-spinner fa-spin me-2"></i>Loading case details...</div>`;
        modal.show();

        try {
            const resp = await apiFetch(`/api/admin/assessments/${encodeURIComponent(assessmentId)}`);
            if (!resp.ok) throw new Error("Failed to load assessment details");
            const data = await resp.json();
            const a = data.assessment || {};
            const scans = data.scans || {};
            const an = data.analysis || {};
            const rep = data.report || null;
            const asg = data.assignment || null;
            const notes = data.counselling_notes || [];

            body.innerHTML = `
                <div class="row g-3 mb-4">
                    <div class="col-md-4">
                        <div class="glass-card p-3 mb-0">
                            <h6 class="fw-bold text-white mb-2">Case Metadata</h6>
                            <div class="small mb-1"><span class="text-secondary">Assessment ID:</span> <strong class="mono text-primary">${escapeHtml(a.assessment_id)}</strong></div>
                            <div class="small mb-1"><span class="text-secondary">Student:</span> <strong class="text-white">${escapeHtml(a.student_name)} (${escapeHtml(a.student_id)})</strong></div>
                            <div class="small mb-1"><span class="text-secondary">Workflow:</span> <span class="badge-status ${getStatusBadgeClass(a.workflow_status)}">${escapeHtml(a.workflow_status)}</span></div>
                            <div class="small"><span class="text-secondary">Created:</span> ${escapeHtml(a.created_at)}</div>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="glass-card p-3 mb-0">
                            <h6 class="fw-bold text-white mb-2">Bilateral Scan Verification</h6>
                            <div class="small mb-1"><span class="text-secondary">LEFT Eye:</span> <span class="badge-status ${scans.LEFT?.status === 'Completed' ? 'status-ready' : 'status-pending'}">${escapeHtml(scans.LEFT?.status || 'Pending')}</span> (Q: ${(scans.LEFT?.quality_score || 0).toFixed(2)})</div>
                            <div class="small mb-1"><span class="text-secondary">RIGHT Eye:</span> <span class="badge-status ${scans.RIGHT?.status === 'Completed' ? 'status-ready' : 'status-pending'}">${escapeHtml(scans.RIGHT?.status || 'Pending')}</span> (Q: ${(scans.RIGHT?.quality_score || 0).toFixed(2)})</div>
                            <div class="small"><span class="text-secondary">AI Model Version:</span> ${escapeHtml(an.model_version || "Not Analyzed")}</div>
                            <a href="camera.html?assessment_id=${encodeURIComponent(a.assessment_id)}" target="_blank" class="btn btn-sm btn-outline-primary mt-2 py-0 px-2"><i class="fa-solid fa-camera me-1"></i>Open Scanner</a>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="glass-card p-3 mb-0">
                            <h6 class="fw-bold text-white mb-2">Clinical Oversight</h6>
                            <div class="small mb-1"><span class="text-secondary">Counsellor:</span> <strong class="text-white">${escapeHtml(asg?.counsellor_id || "Unassigned")}</strong></div>
                            <div class="small mb-1"><span class="text-secondary">Report Review:</span> <span class="badge-status ${rep?.reviewed_status ? 'status-ready' : 'status-pending'}">${rep?.reviewed_status ? 'Reviewed' : 'Pending Review'}</span></div>
                            ${rep?.has_pdf ? `<a href="/api/assessments/${encodeURIComponent(a.assessment_id)}/report/pdf" target="_blank" class="btn btn-sm btn-outline-success mt-2 py-0 px-2"><i class="fa-solid fa-file-pdf me-1"></i>Download PDF</a>` : ''}
                        </div>
                    </div>
                </div>

                <h6 class="fw-bold text-white mb-2">Counselling Notes (${notes.length})</h6>
                ${notes.length === 0 ? `<div class="text-muted small">No counselling notes recorded for this assessment.</div>` : notes.map(n => `
                    <div class="glass-card p-3 mb-2">
                        <div class="d-flex justify-content-between small text-secondary mb-1">
                            <span><i class="fa-solid fa-user-doctor me-1 text-primary"></i>${escapeHtml(n.counsellor_id)}</span>
                            <span>${escapeHtml(n.created_at)}</span>
                        </div>
                        <div class="text-white small">${escapeHtml(n.note)}</div>
                    </div>
                `).join("")}
            `;
        } catch (e) {
            body.innerHTML = `<div class="text-center text-danger py-4">Error loading case details</div>`;
        }
    }

    // -------------------------------------------------------------
    // 6. EYE SCANS OVERVIEW
    // -------------------------------------------------------------
    async function loadScans() {
        const tbody = document.getElementById("scansTableBody");
        const eye = document.getElementById("scanEyeFilter")?.value || "";
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4"><i class="fa-solid fa-spinner fa-spin me-2"></i>Loading scans...</td></tr>`;

        try {
            let url = `/api/admin/scans?limit=50`;
            if (eye) url += `&eye=${encodeURIComponent(eye)}`;
            const resp = await apiFetch(url);
            if (!resp.ok) throw new Error("Failed to load scans");
            const data = await resp.json();

            if (!data.scans || data.scans.length === 0) {
                tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">No scan records on file</td></tr>`;
                return;
            }

            tbody.innerHTML = data.scans.map(s => `
                <tr>
                    <td class="mono small text-secondary">${escapeHtml(s.scan_id)}</td>
                    <td class="mono fw-semibold text-primary">
                        <a href="camera.html?assessment_id=${encodeURIComponent(s.assessment_id)}" target="_blank" class="text-primary text-decoration-none" title="Open Scanner for ${escapeHtml(s.assessment_id)}">
                            ${escapeHtml(s.assessment_id)} <i class="fa-solid fa-arrow-up-right-from-square xsmall ms-1"></i>
                        </a>
                    </td>
                    <td>${escapeHtml(s.student_name)}</td>
                    <td><span class="badge ${s.eye_side === 'LEFT' ? 'bg-primary' : 'bg-info'} text-white">${escapeHtml(s.eye_side)}</span></td>
                    <td><span class="badge-status ${s.status === 'Completed' ? 'status-ready' : 'status-failed'}">${escapeHtml(s.status)}</span></td>
                    <td class="mono fw-semibold text-white">${Number(s.quality_score || 0).toFixed(2)}</td>
                    <td class="mono small text-secondary">${s.attempt_number}</td>
                    <td class="small text-secondary">${escapeHtml(s.completed_at || s.created_at || "")}</td>
                </tr>
            `).join("");
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger py-4">Error loading scans</td></tr>`;
        }
    }

    // -------------------------------------------------------------
    // 7. REPORTS MANAGEMENT
    // -------------------------------------------------------------
    async function loadReports() {
        const tbody = document.getElementById("reportsTableBody");
        const search = document.getElementById("reportSearchInput")?.value || "";
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4"><i class="fa-solid fa-spinner fa-spin me-2"></i>Loading reports...</td></tr>`;

        try {
            let url = `/api/admin/reports?limit=50`;
            if (search) url += `&search=${encodeURIComponent(search)}`;
            const resp = await apiFetch(url);
            if (!resp.ok) throw new Error("Failed to load reports");
            const data = await resp.json();

            if (!data.reports || data.reports.length === 0) {
                tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">No reports generated yet</td></tr>`;
                return;
            }

            tbody.innerHTML = data.reports.map(r => `
                <tr>
                    <td class="mono fw-semibold text-white">${escapeHtml(r.report_id)}</td>
                    <td class="mono text-primary">${escapeHtml(r.assessment_id)}</td>
                    <td>${escapeHtml(r.student_name)}</td>
                    <td class="mono small text-secondary">${escapeHtml(r.version)}</td>
                    <td><span class="badge-status ${r.report_status === 'REPORT_READY' ? 'status-ready' : 'status-pending'}">${escapeHtml(r.report_status)}</span></td>
                    <td><span class="badge-status ${r.reviewed_status ? 'status-ready' : 'status-pending'}">${r.reviewed_status ? 'Reviewed' : 'Pending'}</span></td>
                    <td class="small text-secondary">${escapeHtml(r.generated_at)}</td>
                    <td>
                        <a href="official_report.html?assessment_id=${encodeURIComponent(r.assessment_id)}" target="_blank" class="btn btn-sm btn-outline-info py-0 px-2 me-1">
                            <i class="fa-solid fa-eye me-1"></i>View
                        </a>
                        ${r.has_pdf ? `
                            <a href="/api/assessments/${encodeURIComponent(r.assessment_id)}/report/pdf" target="_blank" class="btn btn-sm btn-outline-success py-0 px-2">
                                <i class="fa-solid fa-file-pdf me-1"></i>PDF
                            </a>
                        ` : ''}
                    </td>
                </tr>
            `).join("");
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger py-4">Error loading reports</td></tr>`;
        }
    }

    // -------------------------------------------------------------
    // 8. COUNSELLORS & ASSIGNMENTS
    // -------------------------------------------------------------
    async function loadCounsellors() {
        const rosterList = document.getElementById("counsellorsRosterList");
        const asgBody = document.getElementById("assignmentsTableBody");
        const selectBox = document.getElementById("assignCounsellorSelect");

        rosterList.innerHTML = `<div class="text-muted small py-2">Loading roster...</div>`;
        asgBody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-3">Loading assignments...</td></tr>`;

        try {
            // Load Counsellors
            const cResp = await apiFetch("/api/counsellors");
            if (cResp.ok) {
                const cData = await cResp.json();
                const counsellors = cData.counsellors || [];
                if (counsellors.length === 0) {
                    rosterList.innerHTML = `<div class="text-muted small py-2">No counsellors registered</div>`;
                } else {
                    rosterList.innerHTML = counsellors.map(c => `
                        <div class="list-group-item bg-transparent text-white border-secondary px-0 py-2 d-flex justify-content-between align-items-center">
                            <div>
                                <strong class="text-white">${escapeHtml(c.full_name || c.username)}</strong>
                                <div class="small mono text-secondary">@${escapeHtml(c.username)}</div>
                            </div>
                            <span class="badge bg-primary text-uppercase" style="font-size: 0.65rem;">Active</span>
                        </div>
                    `).join("");

                    if (selectBox) {
                        selectBox.innerHTML = `<option value="">Select a registered counsellor...</option>` + counsellors.map(c => `
                            <option value="${escapeHtml(c.username)}">${escapeHtml(c.full_name || c.username)} (@${escapeHtml(c.username)})</option>
                        `).join("");
                    }
                }
            }

            // Load Assignments
            const aResp = await apiFetch("/api/admin/assignments");
            if (aResp.ok) {
                const aData = await aResp.json();
                const asgs = aData.assignments || [];
                if (asgs.length === 0) {
                    asgBody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-3">No active assignments</td></tr>`;
                } else {
                    asgBody.innerHTML = asgs.map(a => `
                        <tr>
                            <td class="mono small text-secondary">${escapeHtml(a.assignment_id)}</td>
                            <td class="mono fw-semibold text-primary">${escapeHtml(a.assessment_id)}</td>
                            <td>${escapeHtml(a.student_name)}</td>
                            <td><strong class="text-white">${escapeHtml(a.counsellor_id)}</strong></td>
                            <td><span class="badge-status ${a.status === 'ACTIVE' ? 'status-ready' : 'status-failed'}">${escapeHtml(a.status)}</span></td>
                            <td class="small text-secondary">${escapeHtml(a.assigned_at)}</td>
                            <td>
                                ${a.status === 'ACTIVE' ? `
                                    <button class="btn btn-sm btn-outline-danger revoke-asg-btn py-0 px-2" data-id="${escapeHtml(a.assignment_id)}">
                                        Revoke
                                    </button>
                                ` : '<span class="text-muted small">Closed</span>'}
                            </td>
                        </tr>
                    `).join("");

                    document.querySelectorAll(".revoke-asg-btn").forEach(btn => {
                        btn.addEventListener("click", async function () {
                            const asgId = this.getAttribute("data-id");
                            if (!confirm(`Are you sure you want to revoke assignment ${asgId}?`)) return;
                            const revResp = await apiFetch(`/api/admin/assignments/${encodeURIComponent(asgId)}/revoke`, { method: "PATCH" });
                            if (revResp.ok) {
                                loadCounsellors();
                            } else {
                                alert("Failed to revoke assignment");
                            }
                        });
                    });
                }
            }
        } catch (e) {
            console.error("Error loading counsellors module:", e);
        }
    }

    // Modal: Open Assign Counsellor
    document.getElementById("openAssignModalBtn")?.addEventListener("click", () => {
        const modal = new bootstrap.Modal(document.getElementById("assignCounsellorModal"));
        modal.show();
    });

    document.getElementById("assignCounsellorForm")?.addEventListener("submit", async function (e) {
        e.preventDefault();
        const asmId = document.getElementById("assignAssessmentId").value.trim();
        const cId = document.getElementById("assignCounsellorSelect").value.trim();

        if (!asmId || !cId) return;

        try {
            const resp = await apiFetch(`/api/assessments/${encodeURIComponent(asmId)}/assign-counsellor`, {
                method: "POST",
                body: JSON.stringify({ counsellor_id: cId })
            });
            if (resp.ok) {
                bootstrap.Modal.getInstance(document.getElementById("assignCounsellorModal")).hide();
                loadCounsellors();
            } else {
                const err = await resp.json();
                alert(err.detail || "Failed to assign counsellor");
            }
        } catch (e) {
            alert("Error submitting assignment request");
        }
    });

    // -------------------------------------------------------------
    // 9. USERS & ROLES ADMINISTRATION
    // -------------------------------------------------------------
    async function loadUsers() {
        const tbody = document.getElementById("usersTableBody");
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4"><i class="fa-solid fa-spinner fa-spin me-2"></i>Loading users...</td></tr>`;

        try {
            const resp = await apiFetch("/api/admin/users");
            if (!resp.ok) throw new Error("Failed to load users");
            const data = await resp.json();

            const users = data.users || [];
            if (users.length === 0) {
                tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">No users found</td></tr>`;
                return;
            }

            tbody.innerHTML = users.map(u => `
                <tr>
                    <td class="mono small text-secondary">${u.id}</td>
                    <td class="mono fw-semibold text-white">${escapeHtml(u.username)}</td>
                    <td><span class="badge ${u.role === 'Admin' ? 'bg-danger' : (u.role === 'Counselor' ? 'bg-primary' : 'bg-success')} text-white">${escapeHtml(u.role)}</span></td>
                    <td>${escapeHtml(u.full_name || "-")}</td>
                    <td class="small text-secondary">${escapeHtml(u.email || "-")}</td>
                    <td><span class="badge-status ${u.is_active ? 'status-ready' : 'status-failed'}">${u.is_active ? 'Active' : 'Disabled'}</span></td>
                    <td class="small text-secondary">${escapeHtml(u.created_at || "")}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-warning toggle-user-btn py-0 px-2" data-id="${u.id}" data-username="${escapeHtml(u.username)}" data-active="${u.is_active}">
                            ${u.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                    </td>
                </tr>
            `).join("");

            document.querySelectorAll(".toggle-user-btn").forEach(btn => {
                btn.addEventListener("click", async function () {
                    const uid = this.getAttribute("data-id");
                    const uname = this.getAttribute("data-username");
                    const isActive = this.getAttribute("data-active") === "true";

                    if (isActive && uname.toLowerCase() === username.toLowerCase()) {
                        alert("Safety Check: You cannot deactivate your own active admin account.");
                        return;
                    }

                    if (!confirm(`Toggle status for user '${uname}'?`)) return;

                    const patchResp = await apiFetch(`/api/admin/users/${uid}`, {
                        method: "PATCH",
                        body: JSON.stringify({ is_active: !isActive })
                    });
                    if (patchResp.ok) {
                        loadUsers();
                    } else {
                        const err = await patchResp.json();
                        alert(err.detail || "Failed to update user");
                    }
                });
            });
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger py-4">Error loading users</td></tr>`;
        }
    }

    document.getElementById("openCreateUserModalBtn")?.addEventListener("click", () => {
        const modal = new bootstrap.Modal(document.getElementById("createUserModal"));
        modal.show();
    });

    document.getElementById("createUserForm")?.addEventListener("submit", async function (e) {
        e.preventDefault();
        const un = document.getElementById("newUsername").value.trim();
        const pw = document.getElementById("newPassword").value;
        const ro = document.getElementById("newRole").value;
        const fn = document.getElementById("newFullName").value.trim();
        const em = document.getElementById("newEmail").value.trim();

        try {
            const resp = await apiFetch("/api/admin/users", {
                method: "POST",
                body: JSON.stringify({
                    username: un,
                    password: pw,
                    role: ro,
                    full_name: fn,
                    email: em
                })
            });

            if (resp.ok) {
                bootstrap.Modal.getInstance(document.getElementById("createUserModal")).hide();
                document.getElementById("createUserForm").reset();
                loadUsers();
            } else {
                const err = await resp.json();
                alert(err.detail || "Failed to provision user");
            }
        } catch (e) {
            alert("Error creating user");
        }
    });

    // -------------------------------------------------------------
    // 10. AUDIT LOGS
    // -------------------------------------------------------------
    async function loadAuditLogs() {
        const tbody = document.getElementById("auditTableBody");
        const actionFilter = document.getElementById("auditActionFilter")?.value || "";
        tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4"><i class="fa-solid fa-spinner fa-spin me-2"></i>Loading audit trail...</td></tr>`;

        try {
            let url = `/api/admin/audit-logs?limit=50`;
            if (actionFilter) url += `&action=${encodeURIComponent(actionFilter)}`;

            const resp = await apiFetch(url);
            if (!resp.ok) throw new Error("Failed to load audit logs");
            const data = await resp.json();

            const logs = data.audit_logs || [];
            if (logs.length === 0) {
                tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted py-4">No audit events logged</td></tr>`;
                return;
            }

            tbody.innerHTML = logs.map(l => `
                <tr>
                    <td class="mono small text-secondary">${escapeHtml(l.audit_id)}</td>
                    <td class="fw-semibold text-white">${escapeHtml(l.user_id || "system")}</td>
                    <td><span class="badge bg-secondary text-white">${escapeHtml(l.role || "-")}</span></td>
                    <td class="mono text-info fw-semibold">${escapeHtml(l.action)}</td>
                    <td class="mono small text-primary">${escapeHtml(l.assessment_id || "-")}</td>
                    <td class="small text-secondary">${escapeHtml(l.entity_type || "-")}</td>
                    <td><span class="badge-status ${l.status === 'SUCCESS' ? 'status-ready' : 'status-failed'}">${escapeHtml(l.status)}</span></td>
                    <td class="small text-secondary">${escapeHtml(l.timestamp)}</td>
                </tr>
            `).join("");
        } catch (e) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center text-danger py-4">Error loading audit logs</td></tr>`;
        }
    }

    // -------------------------------------------------------------
    // 11. SEARCH & FILTERS EVENT LISTENERS
    // -------------------------------------------------------------
    document.getElementById("studentSearchInput")?.addEventListener("input", debounce(() => loadStudents(), 350));
    document.getElementById("assessmentStatusFilter")?.addEventListener("change", () => loadAssessments());
    document.getElementById("assessmentSearchInput")?.addEventListener("input", debounce(() => loadAssessments(), 350));
    document.getElementById("scanEyeFilter")?.addEventListener("change", () => loadScans());
    document.getElementById("reportSearchInput")?.addEventListener("input", debounce(() => loadReports(), 350));
    document.getElementById("auditActionFilter")?.addEventListener("input", debounce(() => loadAuditLogs(), 350));

    // Global Refresh
    document.getElementById("refreshBtn")?.addEventListener("click", () => {
        const curSec = window.location.hash.replace("#", "") || "dashboard";
        switchSection(curSec);
    });

    // Global Logout
    document.getElementById("logoutBtn")?.addEventListener("click", () => {
        if (window.IrisAuth) {
            window.IrisAuth.clearAuth();
        } else {
            localStorage.clear();
        }
        window.location.href = "login.html";
    });

    // Mobile Sidebar Toggle
    document.getElementById("mobileSidebarToggle")?.addEventListener("click", () => {
        document.getElementById("adminSidebar").classList.toggle("show");
    });

    // -------------------------------------------------------------
    // 12. UTILITY HELPERS
    // -------------------------------------------------------------
    function escapeHtml(str) {
        if (str === null || str === undefined) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function getStatusBadgeClass(st) {
        if (!st) return "status-pending";
        const upper = String(st).toUpperCase();
        if (upper.includes("READY") || upper.includes("COMPLETE") || upper.includes("MATCHED")) return "status-ready";
        if (upper.includes("PROCESS") || upper.includes("ANALYZ")) return "status-processing";
        if (upper.includes("FAIL") || upper.includes("REVOKE")) return "status-failed";
        return "status-pending";
    }

    function debounce(func, wait) {
        let timeout;
        return function (...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    // -------------------------------------------------------------
    // INITIAL LOAD
    // -------------------------------------------------------------
    const initialHash = window.location.hash.replace("#", "") || "dashboard";
    switchSection(initialHash);

})();