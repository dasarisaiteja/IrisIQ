/**
 * IrisIQ Student Portal Client
 * Strictly adheres to Official IRIS Backend & Frontend Requirements (Phase 7).
 * Handles:
 * - Student authentication & role verification (Student only)
 * - API-driven student profile & demographic data
 * - Active assessment workflow state tracker (Registration -> Scan -> Analysis -> Report)
 * - Bilateral scan status monitoring (LEFT & RIGHT eyes)
 * - Contextual Action Hub:
 *   - "Continue Eye Scan" (links to camera.html with assessment ID)
 *   - "Continue to Analysis" (initiates Phase 4 bilateral analysis and polls status)
 *   - "View Official Report" (links to official_report.html)
 *   - "Download PDF" (downloads server-side compiled PDF)
 * - Assessment case history table and detailed inspection modal
 * - Anti-IDOR enforcement: only student's own data is ever requested or displayed
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
    let studentProfile = null;
    let activeAssessment = null;
    let assessmentHistory = [];
    let pollingTimer = null;
    let assessmentDetailModalInstance = null;

    // DOM Elements
    const portalWorkspace = document.getElementById("portalWorkspace");
    const unauthorizedBox = document.getElementById("unauthorizedBox");
    const navAuthContainer = document.getElementById("navAuthContainer");

    // Profile Elements
    const profileStudentName = document.getElementById("profileStudentName");
    const profileStudentId = document.getElementById("profileStudentId");
    const profileRegisteredAt = document.getElementById("profileRegisteredAt");
    const profileDemographicsBadge = document.getElementById("profileDemographicsBadge");
    const refreshDashboardBtn = document.getElementById("refreshDashboardBtn");

    // Active Assessment Elements
    const activeAsmId = document.getElementById("activeAsmId");
    const activeAsmBadge = document.getElementById("activeAsmBadge");
    const stepScan = document.getElementById("stepScan");
    const stepScanCircle = document.getElementById("stepScanCircle");
    const stepScanDesc = document.getElementById("stepScanDesc");
    const stepAnalysis = document.getElementById("stepAnalysis");
    const stepAnalysisCircle = document.getElementById("stepAnalysisCircle");
    const stepAnalysisDesc = document.getElementById("stepAnalysisDesc");
    const stepReport = document.getElementById("stepReport");
    const stepReportCircle = document.getElementById("stepReportCircle");
    const stepReportDesc = document.getElementById("stepReportDesc");

    // Dual Eye Scan Elements
    const leftScanBadge = document.getElementById("leftScanBadge");
    const leftScanId = document.getElementById("leftScanId");
    const leftScanStatusText = document.getElementById("leftScanStatusText");
    const rightScanBadge = document.getElementById("rightScanBadge");
    const rightScanId = document.getElementById("rightScanId");
    const rightScanStatusText = document.getElementById("rightScanStatusText");

    // Action Hub Elements
    const actionHubLoading = document.getElementById("actionHubLoading");
    const actionHubContent = document.getElementById("actionHubContent");

    // History Table Elements
    const historyCountBadge = document.getElementById("historyCountBadge");
    const assessmentHistoryTbody = document.getElementById("assessmentHistoryTbody");
    const assessmentDetailModalBody = document.getElementById("assessmentDetailModalBody");

    /**
     * Initializes the Student Portal.
     */
    async function init() {
        // 1. Verify Authentication & Role
        const token = authClient.getToken();
        currentUser = authClient.getUser();

        if (!token || !currentUser) {
            console.warn("IrisIQ: No active student session found, redirecting to login.");
            window.location.href = "login.html?redirect=student_dashboard.html";
            return;
        }

        const role = currentUser.role || "";
        const isAuthorized = (role === "Student" || role === "Admin");

        if (!isAuthorized) {
            if (unauthorizedBox) unauthorizedBox.classList.remove("d-none");
            if (portalWorkspace) portalWorkspace.classList.add("d-none");
            return;
        }

        if (unauthorizedBox) unauthorizedBox.classList.add("d-none");
        if (portalWorkspace) portalWorkspace.classList.remove("d-none");

        // 2. Render Nav User Profile & Logout
        renderNav();

        // 3. Initialize Modals
        const modalEl = document.getElementById("assessmentDetailModal");
        if (modalEl) assessmentDetailModalInstance = new bootstrap.Modal(modalEl);

        // 4. Setup Event Listeners
        if (refreshDashboardBtn) {
            refreshDashboardBtn.addEventListener("click", async () => {
                refreshDashboardBtn.disabled = true;
                await loadPortalData();
                refreshDashboardBtn.disabled = false;
            });
        }

        // 5. Load Portal Data
        await loadPortalData();
    }

    /**
     * Renders user info and logout button in header.
     */
    function renderNav() {
        if (!navAuthContainer || !currentUser) return;
        navAuthContainer.innerHTML = `
            <div class="d-flex align-items-center gap-2">
                <div class="text-end d-none d-sm-block">
                    <div class="text-white small fw-bold">${escapeHtml(currentUser.full_name || currentUser.username)}</div>
                    <div class="text-secondary xsmall">Role: Student</div>
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
     * Loads student profile, active assessment, and assessment history.
     */
    async function loadPortalData() {
        try {
            const token = authClient.getToken();

            // 1. Fetch Student Profile
            const profResp = await fetch("/api/student/profile", {
                headers: { "Authorization": `Bearer ${token}` }
            });

            if (!profResp.ok) {
                if (profResp.status === 401) {
                    authClient.logout();
                    window.location.href = "login.html?redirect=student_dashboard.html";
                    return;
                }
                throw new Error(`Profile fetch failed: ${profResp.status}`);
            }

            const profData = await profResp.json();
            studentProfile = profData.student || {};
            renderProfile(studentProfile);

            // 2. Fetch Active Assessment Details
            const asmResp = await fetch("/api/student/assessment", {
                headers: { "Authorization": `Bearer ${token}` }
            });

            if (asmResp.ok) {
                activeAssessment = await asmResp.json();
                renderActiveAssessment(activeAssessment);
            } else {
                renderNoActiveAssessment();
            }

            // 3. Fetch Assessment History
            const histResp = await fetch("/api/student/assessments", {
                headers: { "Authorization": `Bearer ${token}` }
            });

            if (histResp.ok) {
                const histData = await histResp.json();
                assessmentHistory = histData.assessments || [];
                renderHistory(assessmentHistory);
            }
        } catch (err) {
            console.error("Error loading student portal data:", err);
        }
    }

    /**
     * Renders student profile details.
     */
    function renderProfile(st) {
        if (profileStudentName) profileStudentName.textContent = st.student_name || "Student";
        if (profileStudentId) profileStudentId.textContent = st.student_id || "--";
        if (profileRegisteredAt) profileRegisteredAt.textContent = st.created_at || "--";

        if (st.demographics && profileDemographicsBadge) {
            const d = st.demographics;
            const text = [d.gender, d.age ? `${d.age} yrs` : null, d.school_college].filter(Boolean).join(" • ");
            if (text) {
                profileDemographicsBadge.textContent = text;
                profileDemographicsBadge.classList.remove("d-none");
            }
        }
    }

    /**
     * Renders active assessment state and workflow progression.
     */
    function renderActiveAssessment(asm) {
        const aid = asm.assessment_id || "--";
        const status = asm.workflow_status || "REGISTERED";
        const scans = asm.scans || {};
        const left = scans.LEFT || {};
        const right = scans.RIGHT || {};
        const report = asm.report || {};

        if (activeAsmId) activeAsmId.textContent = aid;

        // Workflow Status Badge
        let badgeClass = "badge bg-secondary bg-opacity-25 text-light";
        if (status === "ANALYSIS_COMPLETED" || status === "REPORT_READY" || status === "COMPLETED") {
            badgeClass = "badge bg-success bg-opacity-20 text-success border border-success border-opacity-30";
        } else if (status === "PROCESSING" || status === "SCAN_COMPLETED") {
            badgeClass = "badge bg-info bg-opacity-20 text-info border border-info border-opacity-30";
        } else if (status.includes("SCAN")) {
            badgeClass = "badge bg-primary bg-opacity-20 text-primary border border-primary border-opacity-30";
        }
        if (activeAsmBadge) {
            activeAsmBadge.className = `badge px-3 py-2 fs-6 ${badgeClass}`;
            activeAsmBadge.textContent = status.replace(/_/g, " ");
        }

        // Left Eye Card
        const leftStatus = left.status || "PENDING";
        if (leftScanBadge) {
            leftScanBadge.className = `badge ${leftStatus === 'Completed' || leftStatus === 'COMPLETED' ? 'bg-success bg-opacity-20 text-success' : 'bg-secondary bg-opacity-25 text-light'}`;
            leftScanBadge.textContent = leftStatus.toUpperCase();
        }
        if (leftScanId) leftScanId.textContent = left.scan_id || "--";
        if (leftScanStatusText) {
            leftScanStatusText.textContent = (leftStatus === 'Completed' || leftStatus === 'COMPLETED')
                ? `Acquisition verified (Attempt ${left.attempt_number || 1})`
                : "Awaiting image capture";
        }

        // Right Eye Card
        const rightStatus = right.status || "PENDING";
        if (rightScanBadge) {
            rightScanBadge.className = `badge ${rightStatus === 'Completed' || rightStatus === 'COMPLETED' ? 'bg-success bg-opacity-20 text-success' : 'bg-secondary bg-opacity-25 text-light'}`;
            rightScanBadge.textContent = rightStatus.toUpperCase();
        }
        if (rightScanId) rightScanId.textContent = right.scan_id || "--";
        if (rightScanStatusText) {
            rightScanStatusText.textContent = (rightStatus === 'Completed' || rightStatus === 'COMPLETED')
                ? `Acquisition verified (Attempt ${right.attempt_number || 1})`
                : "Awaiting image capture";
        }

        const leftDone = (leftStatus === "Completed" || leftStatus === "COMPLETED");
        const rightDone = (rightStatus === "Completed" || rightStatus === "COMPLETED");
        const bothDone = leftDone && rightDone;

        // Workflow Step 2: Scan
        if (stepScan) {
            if (bothDone) {
                stepScan.className = "workflow-step completed";
                if (stepScanCircle) stepScanCircle.innerHTML = '<i class="fa-solid fa-check"></i>';
                if (stepScanDesc) stepScanDesc.textContent = "Both eyes confirmed";
            } else {
                stepScan.className = "workflow-step active";
                if (stepScanCircle) stepScanCircle.textContent = "2";
                if (stepScanDesc) stepScanDesc.textContent = leftDone ? "Left done, Right pending" : (rightDone ? "Right done, Left pending" : "Scans pending");
            }
        }

        // Workflow Step 3: Analysis
        const analysisDone = (status === "ANALYSIS_COMPLETED" || status === "REPORT_READY" || status === "COMPLETED");
        const isProcessing = (status === "PROCESSING" || status === "ANALYZING");

        if (stepAnalysis) {
            if (analysisDone) {
                stepAnalysis.className = "workflow-step completed";
                if (stepAnalysisCircle) stepAnalysisCircle.innerHTML = '<i class="fa-solid fa-check"></i>';
                if (stepAnalysisDesc) stepAnalysisDesc.textContent = "Biometrics analyzed";
            } else if (isProcessing) {
                stepAnalysis.className = "workflow-step active";
                if (stepAnalysisCircle) stepAnalysisCircle.innerHTML = '<div class="spinner-border spinner-border-sm" role="status"></div>';
                if (stepAnalysisDesc) stepAnalysisDesc.textContent = "Processing features...";
            } else {
                stepAnalysis.className = "workflow-step";
                if (stepAnalysisCircle) stepAnalysisCircle.textContent = "3";
                if (stepAnalysisDesc) stepAnalysisDesc.textContent = "Awaiting scans";
            }
        }

        // Workflow Step 4: Report
        const reportReady = (report.status === "REPORT_READY" || status === "REPORT_READY" || status === "COMPLETED");
        if (stepReport) {
            if (reportReady) {
                stepReport.className = "workflow-step completed";
                if (stepReportCircle) stepReportCircle.innerHTML = '<i class="fa-solid fa-check"></i>';
                if (stepReportDesc) stepReportDesc.textContent = report.reviewed_status ? "Reviewed by Counsellor" : "Report Ready";
            } else {
                stepReport.className = "workflow-step";
                if (stepReportCircle) stepReportCircle.textContent = "4";
                if (stepReportDesc) stepReportDesc.textContent = "Report pending";
            }
        }

        // Render Action Hub CTA
        renderActionHub(aid, status, bothDone, isProcessing, analysisDone, reportReady);
    }

    /**
     * Renders state when no active assessment exists.
     */
    function renderNoActiveAssessment() {
        if (activeAsmId) activeAsmId.textContent = "None";
        if (activeAsmBadge) {
            activeAsmBadge.className = "badge bg-secondary bg-opacity-25 text-light";
            activeAsmBadge.textContent = "NO ACTIVE CASE";
        }
        if (actionHubLoading) actionHubLoading.classList.add("d-none");
        if (actionHubContent) {
            actionHubContent.classList.remove("d-none");
            actionHubContent.innerHTML = `
                <div class="py-3 text-secondary">
                    <i class="fa-solid fa-folder-open fs-3 d-block mb-2 opacity-50"></i>
                    No active assessment registered for this student account.
                </div>
            `;
        }
    }

    /**
     * Renders dynamic Action Hub contextual button based on backend state.
     */
    function renderActionHub(aid, status, bothDone, isProcessing, analysisDone, reportReady) {
        if (actionHubLoading) actionHubLoading.classList.add("d-none");
        if (!actionHubContent) return;

        actionHubContent.classList.remove("d-none");

        // Case 1: Report Ready
        if (reportReady) {
            actionHubContent.innerHTML = `
                <div class="d-flex flex-wrap justify-content-center align-items-center gap-3">
                    <a href="official_report.html?assessment_id=${encodeURIComponent(aid)}" class="btn btn-success btn-sm rounded-pill px-4 fw-bold" target="_blank">
                        <i class="fa-solid fa-file-invoice me-2"></i>View Official Report
                    </a>
                    <a href="/api/student/assessments/${encodeURIComponent(aid)}/report/pdf" class="btn btn-outline-success btn-sm rounded-pill px-4 fw-bold" download>
                        <i class="fa-solid fa-file-pdf me-2"></i>Download PDF
                    </a>
                    <a href="official_report.html?assessment_id=${encodeURIComponent(aid)}&print=true" class="btn btn-outline-light btn-sm rounded-pill px-3" target="_blank">
                        <i class="fa-solid fa-print me-1"></i>Print Report
                    </a>
                </div>
            `;
            return;
        }

        // Case 2: Analysis currently processing
        if (isProcessing) {
            actionHubContent.innerHTML = `
                <div class="d-flex align-items-center justify-content-center gap-2 text-info py-2">
                    <div class="spinner-border spinner-border-sm" role="status"></div>
                    <span class="small fw-bold">Bilateral Feature Analysis in Progress... Polling AI Engine</span>
                </div>
            `;
            startStatusPolling(aid);
            return;
        }

        // Case 3: Analysis completed, awaiting report generation
        if (analysisDone) {
            actionHubContent.innerHTML = `
                <div class="d-flex flex-column align-items-center gap-2 py-1">
                    <div class="text-white small fw-bold">Analysis Complete! Ready to Generate Official Structured Report.</div>
                    <button type="button" id="generateReportActionBtn" class="btn btn-primary btn-sm rounded-pill px-4 fw-bold" onclick="window.irisStudent.generateReport('${escapeJs(aid)}')">
                        <i class="fa-solid fa-file-lines me-2"></i>Generate Official Report
                    </button>
                </div>
            `;
            return;
        }

        // Case 4: Both scans completed, ready to continue to analysis
        if (bothDone) {
            actionHubContent.innerHTML = `
                <div class="d-flex flex-column align-items-center gap-2 py-1">
                    <div class="text-white small fw-bold">Both LEFT and RIGHT eye scans verified complete.</div>
                    <button type="button" id="startAnalysisActionBtn" class="btn btn-info btn-sm rounded-pill px-4 fw-bold text-dark" onclick="window.irisStudent.startAnalysis('${escapeJs(aid)}')">
                        <i class="fa-solid fa-brain me-2"></i>Continue to Analysis
                    </button>
                </div>
            `;
            return;
        }

        // Case 5: Scans still pending
        actionHubContent.innerHTML = `
            <div class="d-flex flex-column align-items-center gap-2 py-1">
                <div class="text-secondary small">Biometric scan required to proceed with assessment.</div>
                <a href="camera.html?assessment_id=${encodeURIComponent(aid)}" class="btn btn-primary btn-sm rounded-pill px-4 fw-bold">
                    <i class="fa-solid fa-camera me-2"></i>Continue Eye Scan
                </a>
            </div>
        `;
    }

    /**
     * Starts bilateral analysis processing.
     */
    async function startAnalysis(aid) {
        if (!confirm("Start bilateral biometric feature extraction and neural analysis?")) {
            return;
        }

        if (actionHubContent) {
            actionHubContent.innerHTML = `
                <div class="d-flex align-items-center justify-content-center gap-2 text-info py-2">
                    <div class="spinner-border spinner-border-sm" role="status"></div>
                    <span class="small fw-bold">Initializing Analysis Pipeline...</span>
                </div>
            `;
        }

        try {
            const token = authClient.getToken();
            const resp = await fetch(`/api/assessments/${encodeURIComponent(aid)}/process`, {
                method: "POST",
                headers: { "Authorization": `Bearer ${token}` }
            });

            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                alert(`Analysis failed to start: ${err.detail || resp.statusText}`);
                await loadPortalData();
                return;
            }

            // Immediately poll or generate report
            const data = await resp.json();
            if (data.workflow_status === "ANALYSIS_COMPLETED") {
                await generateReport(aid);
            } else {
                startStatusPolling(aid);
            }
        } catch (err) {
            console.error("Error starting analysis:", err);
            alert(`Network error: ${err.message}`);
            await loadPortalData();
        }
    }

    /**
     * Generates official structured report after analysis.
     */
    async function generateReport(aid) {
        if (actionHubContent) {
            actionHubContent.innerHTML = `
                <div class="d-flex align-items-center justify-content-center gap-2 text-success py-2">
                    <div class="spinner-border spinner-border-sm" role="status"></div>
                    <span class="small fw-bold">Compiling 10-Section Structured Report & Server-Side PDF...</span>
                </div>
            `;
        }

        try {
            const token = authClient.getToken();
            const resp = await fetch(`/api/assessments/${encodeURIComponent(aid)}/report/generate`, {
                method: "POST",
                headers: { "Authorization": `Bearer ${token}` }
            });

            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                alert(`Report generation failed: ${err.detail || resp.statusText}`);
            }

            await loadPortalData();
        } catch (err) {
            console.error("Error generating report:", err);
            await loadPortalData();
        }
    }

    /**
     * Status polling for active assessment during processing.
     */
    function startStatusPolling(aid) {
        if (pollingTimer) clearInterval(pollingTimer);

        pollingTimer = setInterval(async () => {
            try {
                const token = authClient.getToken();
                const resp = await fetch(`/api/student/assessments/${encodeURIComponent(aid)}/status`, {
                    headers: { "Authorization": `Bearer ${token}` }
                });

                if (!resp.ok) return;

                const data = await resp.json();
                if (data.workflow_status === "ANALYSIS_COMPLETED" || data.workflow_status === "REPORT_READY") {
                    clearInterval(pollingTimer);
                    pollingTimer = null;
                    await loadPortalData();
                }
            } catch (e) {
                console.error("Polling error:", e);
            }
        }, 2000);
    }

    /**
     * Renders assessment history table.
     */
    function renderHistory(items) {
        if (historyCountBadge) historyCountBadge.textContent = `${items.length} Case${items.length === 1 ? '' : 's'}`;
        if (!assessmentHistoryTbody) return;

        if (!items || items.length === 0) {
            assessmentHistoryTbody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center py-5 text-secondary">
                        <i class="fa-solid fa-folder-open fs-3 d-block mb-2 opacity-50"></i>
                        No prior assessment cases recorded.
                    </td>
                </tr>
            `;
            return;
        }

        let html = "";
        items.forEach(asm => {
            const aid = asm.assessment_id || "--";
            const date = asm.date || "--";
            const stage = asm.workflow_status || "REGISTERED";
            const left = asm.left_scan_status || "PENDING";
            const right = asm.right_scan_status || "PENDING";
            const analysis = asm.analysis_status || "PENDING";
            const report = asm.report_status || "NOT_GENERATED";

            const leftClass = (left === "COMPLETED" || left === "Completed") ? "badge bg-success bg-opacity-20 text-success" : "badge bg-secondary bg-opacity-25 text-light";
            const rightClass = (right === "COMPLETED" || right === "Completed") ? "badge bg-success bg-opacity-20 text-success" : "badge bg-secondary bg-opacity-25 text-light";
            const reportClass = report === "REPORT_READY" ? "badge bg-success bg-opacity-20 text-success" : "badge bg-secondary bg-opacity-25 text-secondary";

            html += `
                <tr>
                    <td>
                        <span class="mono-text text-info fw-bold">${escapeHtml(aid)}</span>
                    </td>
                    <td>
                        <div class="text-light small">${escapeHtml(date)}</div>
                    </td>
                    <td>
                        <span class="badge bg-secondary bg-opacity-25 text-light">${escapeHtml(stage)}</span>
                    </td>
                    <td>
                        <div class="d-flex gap-1">
                            <span class="${leftClass} xsmall">L: ${left}</span>
                            <span class="${rightClass} xsmall">R: ${right}</span>
                        </div>
                    </td>
                    <td>
                        <span class="badge ${analysis === 'COMPLETED' ? 'bg-info bg-opacity-20 text-info' : 'bg-secondary bg-opacity-25 text-light'} xsmall">
                            ${escapeHtml(analysis)}
                        </span>
                    </td>
                    <td>
                        <span class="${reportClass} xsmall">${escapeHtml(report)}</span>
                    </td>
                    <td class="text-end">
                        <div class="d-flex justify-content-end gap-1">
                            ${report === "REPORT_READY" ? `
                                <a href="official_report.html?assessment_id=${encodeURIComponent(aid)}" class="btn btn-outline-success btn-sm rounded-pill px-3 py-1" target="_blank" title="View Report">
                                    <i class="fa-solid fa-file-invoice me-1"></i> Report
                                </a>
                                <a href="/api/student/assessments/${encodeURIComponent(aid)}/report/pdf" class="btn btn-outline-light btn-sm rounded-pill px-2 py-1" download title="Download PDF">
                                    <i class="fa-solid fa-download"></i>
                                </a>
                            ` : `
                                <a href="camera.html?assessment_id=${encodeURIComponent(aid)}" class="btn btn-outline-primary btn-sm rounded-pill px-3 py-1">
                                    <i class="fa-solid fa-camera me-1"></i> Scan
                                </a>
                            `}
                            <button type="button" class="btn btn-outline-secondary btn-sm rounded-pill px-2 py-1" onclick="window.irisStudent.viewDetails('${escapeJs(aid)}')" title="Details">
                                <i class="fa-solid fa-circle-info"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        });

        assessmentHistoryTbody.innerHTML = html;
    }

    /**
     * Views assessment details modal.
     */
    async function viewDetails(aid) {
        if (!assessmentDetailModalBody) return;
        assessmentDetailModalBody.innerHTML = `
            <div class="text-center py-5">
                <div class="spinner-border text-primary me-2" role="status"></div>
                <div class="text-secondary small mt-2">Loading assessment records...</div>
            </div>
        `;

        if (assessmentDetailModalInstance) assessmentDetailModalInstance.show();

        try {
            const token = authClient.getToken();
            const resp = await fetch(`/api/student/assessments/${encodeURIComponent(aid)}`, {
                headers: { "Authorization": `Bearer ${token}` }
            });

            if (!resp.ok) {
                throw new Error("Unable to retrieve assessment details.");
            }

            const data = await resp.json();
            const scans = data.scans || {};
            const left = scans.LEFT || {};
            const right = scans.RIGHT || {};
            const report = data.report || {};
            const analysis = data.analysis || {};

            assessmentDetailModalBody.innerHTML = `
                <div class="d-flex flex-column gap-3">
                    <div class="p-3 rounded-3" style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.07);">
                        <div class="row g-2">
                            <div class="col-sm-6">
                                <div class="text-secondary xsmall text-uppercase fw-bold">Assessment ID</div>
                                <div class="fs-6 fw-bold text-info mono-text">${escapeHtml(data.assessment_id)}</div>
                            </div>
                            <div class="col-sm-6 text-sm-end">
                                <div class="text-secondary xsmall text-uppercase fw-bold">Workflow Status</div>
                                <span class="badge bg-primary bg-opacity-20 text-primary border border-primary border-opacity-30">
                                    ${escapeHtml(data.workflow_status || "REGISTERED")}
                                </span>
                            </div>
                        </div>
                    </div>

                    <div class="row g-3">
                        <div class="col-sm-6">
                            <div class="p-3 rounded-3 scan-box">
                                <div class="fw-bold text-white small mb-1">LEFT Eye Scan</div>
                                <div class="text-secondary xsmall">Status: <span class="text-light fw-bold">${escapeHtml(left.status || "PENDING")}</span></div>
                                <div class="text-secondary xsmall">Scan ID: <span class="mono-text">${escapeHtml(left.scan_id || "--")}</span></div>
                                <div class="text-secondary xsmall">Attempt: ${escapeHtml(left.attempt_number || "--")}</div>
                            </div>
                        </div>
                        <div class="col-sm-6">
                            <div class="p-3 rounded-3 scan-box">
                                <div class="fw-bold text-white small mb-1">RIGHT Eye Scan</div>
                                <div class="text-secondary xsmall">Status: <span class="text-light fw-bold">${escapeHtml(right.status || "PENDING")}</span></div>
                                <div class="text-secondary xsmall">Scan ID: <span class="mono-text">${escapeHtml(right.scan_id || "--")}</span></div>
                                <div class="text-secondary xsmall">Attempt: ${escapeHtml(right.attempt_number || "--")}</div>
                            </div>
                        </div>
                    </div>

                    <div class="p-3 rounded-3" style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06);">
                        <div class="fw-bold text-white small mb-2"><i class="fa-solid fa-file-invoice text-success me-2"></i>Report Summary</div>
                        <div class="text-secondary xsmall">Status: <span class="text-light">${escapeHtml(report.status || "NOT_GENERATED")}</span></div>
                        <div class="text-secondary xsmall">Version: <span class="text-light">${escapeHtml(report.version || "N/A")}</span></div>
                        <div class="text-secondary xsmall">Reviewed: <span class="text-light">${report.reviewed_status ? 'Yes (Signed off)' : 'Pending'}</span></div>
                        ${report.status === "REPORT_READY" ? `
                            <div class="mt-3">
                                <a href="official_report.html?assessment_id=${encodeURIComponent(data.assessment_id)}" class="btn btn-outline-success btn-sm rounded-pill px-3" target="_blank">
                                    <i class="fa-solid fa-arrow-up-right-from-square me-1"></i> Open Report
                                </a>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        } catch (err) {
            console.error("Error viewing assessment details:", err);
            assessmentDetailModalBody.innerHTML = `
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

    // Expose global methods for inline HTML handlers
    window.irisStudent = {
        startAnalysis,
        generateReport,
        viewDetails
    };

    // Auto-initialize when DOM is ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
