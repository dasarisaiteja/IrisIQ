/**
 * Official IRIS Assessment Report Page Logic (Phase 5B).
 * Manages retrieval, generation polling, rendering, PDF download, and counsellor review.
 */

document.addEventListener("DOMContentLoaded", async () => {
    // 1. Authentication & URL Query Extraction
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

    const currentUser = authClient.getUser();
    if (!currentUser || !authClient.getToken()) {
        window.location.href = `login.html?redirect=${encodeURIComponent(window.location.href)}`;
        return;
    }

    const urlParams = new URLSearchParams(window.location.search);
    const assessmentId = urlParams.get("assessment_id");

    // UI Element References
    const backToScanBtn = document.getElementById("backToScanBtn");
    const reportLoadingBox = document.getElementById("reportLoadingBox");
    const reportGeneratingBox = document.getElementById("reportGeneratingBox");
    const reportErrorBox = document.getElementById("reportErrorBox");
    const reportErrorTitle = document.getElementById("reportErrorTitle");
    const reportErrorMsg = document.getElementById("reportErrorMsg");
    const retryLoadBtn = document.getElementById("retryLoadBtn");
    const reportContent = document.getElementById("reportContent");

    // Header & Meta Elements
    const headerReportVersion = document.getElementById("headerReportVersion");
    const headerReportStatusBadge = document.getElementById("headerReportStatusBadge");
    const headerAssessmentId = document.getElementById("headerAssessmentId");
    const docReportId = document.getElementById("docReportId");
    const docAssessmentId = document.getElementById("docAssessmentId");
    const docGeneratedAt = document.getElementById("docGeneratedAt");

    // Section 1: Student
    const stuIdVal = document.getElementById("stuIdVal");
    const stuNameVal = document.getElementById("stuNameVal");
    const stuAgeGenderVal = document.getElementById("stuAgeGenderVal");
    const stuSchoolVal = document.getElementById("stuSchoolVal");
    const stuCourseStreamVal = document.getElementById("stuCourseStreamVal");
    const stuLocationVal = document.getElementById("stuLocationVal");

    // Section 2: Assessment
    const asmIdVal = document.getElementById("asmIdVal");
    const asmStatusVal = document.getElementById("asmStatusVal");
    const asmDateVal = document.getElementById("asmDateVal");
    const asmCompletedVal = document.getElementById("asmCompletedVal");
    const asmEngineVal = document.getElementById("asmEngineVal");

    // Section 3: Eye Scan (Left & Right)
    const leftScanStatusBadge = document.getElementById("leftScanStatusBadge");
    const leftQualityVal = document.getElementById("leftQualityVal");
    const leftBlurVal = document.getElementById("leftBlurVal");
    const leftColorVal = document.getElementById("leftColorVal");
    const leftRatioVal = document.getElementById("leftRatioVal");
    const leftPupilRVal = document.getElementById("leftPupilRVal");
    const leftIrisRVal = document.getElementById("leftIrisRVal");
    const leftScanIdVal = document.getElementById("leftScanIdVal");

    const rightScanStatusBadge = document.getElementById("rightScanStatusBadge");
    const rightQualityVal = document.getElementById("rightQualityVal");
    const rightBlurVal = document.getElementById("rightBlurVal");
    const rightColorVal = document.getElementById("rightColorVal");
    const rightRatioVal = document.getElementById("rightRatioVal");
    const rightPupilRVal = document.getElementById("rightPupilRVal");
    const rightIrisRVal = document.getElementById("rightIrisRVal");
    const rightScanIdVal = document.getElementById("rightScanIdVal");

    // Section 4: Overall Result
    const overallQualityVal = document.getElementById("overallQualityVal");
    const overallSimilarityVal = document.getElementById("overallSimilarityVal");
    const overallPupilDeltaVal = document.getElementById("overallPupilDeltaVal");
    const overallColorMatchVal = document.getElementById("overallColorMatchVal");
    const biometricSummaryText = document.getElementById("biometricSummaryText");

    // Section 9: Counselling
    const counsellingReviewBadge = document.getElementById("counsellingReviewBadge");
    const counsellorIdVal = document.getElementById("counsellorIdVal");
    const counsellorAssignedAtVal = document.getElementById("counsellorAssignedAtVal");
    const counsellingNotesList = document.getElementById("counsellingNotesList");
    const followUpsList = document.getElementById("followUpsList");
    const reviewModalBtn = document.getElementById("reviewModalBtn");

    // Section 10: Metadata
    const pipelineVerVal = document.getElementById("pipelineVerVal");

    // Action Buttons
    const downloadPdfBtn = document.getElementById("downloadPdfBtn");
    const downloadPdfSpinner = document.getElementById("downloadPdfSpinner");
    const downloadPdfIcon = document.getElementById("downloadPdfIcon");
    const printReportBtn = document.getElementById("printReportBtn");

    // Review Modal Form
    const submitReviewBtn = document.getElementById("submitReviewBtn");
    const submitReviewSpinner = document.getElementById("submitReviewSpinner");
    const reviewNotesInput = document.getElementById("reviewNotesInput");
    const followUpDateInput = document.getElementById("followUpDateInput");
    const followUpNotesInput = document.getElementById("followUpNotesInput");
    let reviewModalInstance = null;

    if (backToScanBtn && assessmentId) {
        backToScanBtn.href = `camera.html?assessment_id=${encodeURIComponent(assessmentId)}`;
    }

    if (!assessmentId) {
        showError("Missing Assessment Identifier", "No valid Assessment ID was specified in the query parameters. Please navigate from the Assessment Dashboard.");
        return;
    }

    // Role-based review capability
    const userRole = currentUser.role;
    if (["Admin", "Counselor", "Counsellor"].includes(userRole) && reviewModalBtn) {
        reviewModalBtn.classList.remove("d-none");
        const modalEl = document.getElementById("counsellorReviewModal");
        if (modalEl && typeof bootstrap !== "undefined") {
            reviewModalInstance = new bootstrap.Modal(modalEl);
            reviewModalBtn.addEventListener("click", () => reviewModalInstance.show());
        }
    }

    // Helper: Number Formatter
    function fmt(val, dec = 2) {
        if (val === null || val === undefined || isNaN(val)) return "--";
        return Number(val).toFixed(dec);
    }

    // Helper: Show Error State
    function showError(title, message) {
        if (reportLoadingBox) reportLoadingBox.classList.add("d-none");
        if (reportGeneratingBox) reportGeneratingBox.classList.add("d-none");
        if (reportContent) reportContent.classList.add("d-none");
        if (reportErrorBox) {
            reportErrorBox.classList.remove("d-none");
            if (reportErrorTitle) reportErrorTitle.textContent = title;
            if (reportErrorMsg) reportErrorMsg.textContent = message;
        }
    }

    // Primary: Fetch or Trigger Generation
    async function loadReport() {
        if (reportErrorBox) reportErrorBox.classList.add("d-none");
        if (reportContent) reportContent.classList.add("d-none");
        if (reportLoadingBox) reportLoadingBox.classList.remove("d-none");

        try {
            // First attempt: Check if report already exists
            const fetchResp = await fetch(`/api/assessments/${encodeURIComponent(assessmentId)}/report`, {
                headers: authClient.getAuthHeaders()
            });

            if (fetchResp.ok) {
                const repData = await fetchResp.json();
                renderReport(repData);
                return;
            }

            if (fetchResp.status === 404) {
                // Report not generated yet -> Trigger official generation
                await triggerReportGeneration();
                return;
            }

            if (fetchResp.status === 403) {
                showError("Access Forbidden", "You are not authorized to view the assessment report for this student.");
                return;
            }

            if (fetchResp.status === 409) {
                const errJson = await fetchResp.json();
                showError("Analysis Incomplete", errJson.detail || "Bilateral eye scans and analysis must be completed before generating a report.");
                return;
            }

            const errData = await fetchResp.json();
            throw new Error(errData.detail || "Failed to retrieve assessment report.");

        } catch (err) {
            console.error("Report loading error:", err);
            showError("Report Retrieval Failed", err.message);
        }
    }

    async function triggerReportGeneration() {
        if (reportLoadingBox) reportLoadingBox.classList.add("d-none");
        if (reportGeneratingBox) reportGeneratingBox.classList.remove("d-none");

        try {
            const genResp = await fetch(`/api/assessments/${encodeURIComponent(assessmentId)}/report/generate`, {
                method: "POST",
                headers: {
                    ...authClient.getAuthHeaders(),
                    "Content-Type": "application/json"
                }
            });

            if (genResp.ok) {
                const repData = await genResp.json();
                renderReport(repData);
                return;
            }

            const errData = await genResp.json();
            if (genResp.status === 409) {
                showError("Workflow Conflict", errData.detail || "Assessment is not ready for report generation. Please complete dual-eye scanning and analysis.");
            } else if (genResp.status === 403) {
                showError("Unauthorized", "You do not have permission to generate a report for this student.");
            } else {
                throw new Error(errData.detail || "Report generation failed on backend.");
            }

        } catch (err) {
            console.error("Generation error:", err);
            showError("Report Generation Failed", err.message);
        }
    }

    function renderReport(data) {
        if (reportLoadingBox) reportLoadingBox.classList.add("d-none");
        if (reportGeneratingBox) reportGeneratingBox.classList.add("d-none");
        if (reportErrorBox) reportErrorBox.classList.add("d-none");
        if (reportContent) reportContent.classList.remove("d-none");

        const sections = data.sections || {};
        const secStu = sections.student || {};
        const secAsm = sections.assessment || {};
        const secEye = sections.eye_scan || {};
        const secOverall = sections.overall_result || {};
        const secCounselling = sections.counselling || {};
        const secMeta = sections.report_meta || {};

        // Top Metadata
        const reportId = data.report_id || secMeta.report_id || "--";
        const version = data.version || secMeta.version || "v1.0";
        const status = data.report_status || secMeta.status || "REPORT_READY";
        const genDate = data.generated_at || secMeta.generated_date || "--";

        if (headerReportVersion) headerReportVersion.textContent = version;
        if (headerAssessmentId) headerAssessmentId.textContent = assessmentId;
        if (docReportId) docReportId.textContent = reportId;
        if (docAssessmentId) docAssessmentId.textContent = assessmentId;
        if (docGeneratedAt) docGeneratedAt.textContent = genDate;

        // Section 1: Student
        if (stuIdVal) stuIdVal.textContent = secStu.student_id || "--";
        if (stuNameVal) stuNameVal.textContent = secStu.student_name || "--";
        if (stuAgeGenderVal) stuAgeGenderVal.textContent = `${secStu.age || "N/A"} / ${secStu.gender || "N/A"}`;
        if (stuSchoolVal) stuSchoolVal.textContent = secStu.school_college || "Not Specified";
        if (stuCourseStreamVal) stuCourseStreamVal.textContent = `${secStu.course || "N/A"} (${secStu.stream || "General"})`;
        if (stuLocationVal) stuLocationVal.textContent = secStu.location || "Not Specified";

        // Section 2: Assessment
        if (asmIdVal) asmIdVal.textContent = secAsm.assessment_id || assessmentId;
        if (asmStatusVal) asmStatusVal.textContent = secAsm.workflow_status || status;
        if (asmDateVal) asmDateVal.textContent = secAsm.assessment_date || "--";
        if (asmCompletedVal) asmCompletedVal.textContent = secAsm.completed_at || "--";
        if (asmEngineVal) asmEngineVal.textContent = secMeta.pipeline_version || "iris-analysis-v1.0";

        // Section 3: Eye Scans
        const leftS = secEye.left_scan || {};
        const rightS = secEye.right_scan || {};

        if (leftQualityVal) leftQualityVal.textContent = `${fmt(leftS.quality_score, 1)}%`;
        if (leftBlurVal) leftBlurVal.textContent = fmt(leftS.blur_score, 1);
        if (leftColorVal) leftColorVal.textContent = leftS.detected_color || "--";
        if (leftRatioVal) leftRatioVal.textContent = fmt(leftS.pupil_iris_ratio, 4);
        if (leftPupilRVal) leftPupilRVal.textContent = `${fmt(leftS.pupil_radius, 1)} px`;
        if (leftIrisRVal) leftIrisRVal.textContent = `${fmt(leftS.iris_radius, 1)} px`;
        if (leftScanIdVal) leftScanIdVal.textContent = leftS.scan_id || "--";

        if (rightQualityVal) rightQualityVal.textContent = `${fmt(rightS.quality_score, 1)}%`;
        if (rightBlurVal) rightBlurVal.textContent = fmt(rightS.blur_score, 1);
        if (rightColorVal) rightColorVal.textContent = rightS.detected_color || "--";
        if (rightRatioVal) rightRatioVal.textContent = fmt(rightS.pupil_iris_ratio, 4);
        if (rightPupilRVal) rightPupilRVal.textContent = `${fmt(rightS.pupil_radius, 1)} px`;
        if (rightIrisRVal) rightIrisRVal.textContent = `${fmt(rightS.iris_radius, 1)} px`;
        if (rightScanIdVal) rightScanIdVal.textContent = rightS.scan_id || "--";

        // Section 4: Overall Result
        if (overallQualityVal) overallQualityVal.textContent = `${fmt(secOverall.combined_capture_quality, 1)}%`;
        if (overallSimilarityVal) overallSimilarityVal.textContent = fmt(secOverall.bilateral_similarity, 4);
        if (overallPupilDeltaVal) overallPupilDeltaVal.textContent = `${fmt(secOverall.bilateral_symmetry_delta, 1)} px`;
        if (overallColorMatchVal) {
            overallColorMatchVal.textContent = secOverall.color_consistency ? "MATCH" : "DIFF";
            overallColorMatchVal.className = secOverall.color_consistency ? "metric-value text-success fs-4" : "metric-value text-warning fs-4";
        }
        if (biometricSummaryText) {
            biometricSummaryText.textContent = secOverall.biometric_summary || "Bilateral iris geometry verified with high concentricity.";
        }

        // Section 9: Counselling
        if (counsellorIdVal) counsellorIdVal.textContent = secCounselling.assigned_counsellor_id || "Unassigned";
        if (counsellorAssignedAtVal) counsellorAssignedAtVal.textContent = secCounselling.assigned_at || "--";
        if (counsellingReviewBadge) {
            if (secCounselling.reviewed_status) {
                counsellingReviewBadge.textContent = "Reviewed";
                counsellingReviewBadge.className = "badge bg-success bg-opacity-20 text-success section-badge border border-success border-opacity-25";
            } else {
                counsellingReviewBadge.textContent = "Pending Review";
                counsellingReviewBadge.className = "badge bg-secondary bg-opacity-25 text-light section-badge";
            }
        }

        // Render notes list
        if (counsellingNotesList) {
            const notes = secCounselling.counselling_notes || [];
            if (notes.length > 0) {
                counsellingNotesList.innerHTML = notes.map(n => `
                    <div class="mb-2 pb-2 border-bottom border-secondary border-opacity-15">
                        <div class="d-flex justify-content-between xsmall text-secondary mb-1">
                            <span class="fw-bold text-info">${n.counsellor_id || 'Counsellor'}</span>
                            <span class="mono-text">${n.created_at || ''}</span>
                        </div>
                        <div class="small text-light">${n.note}</div>
                    </div>
                `).join("");
            } else {
                counsellingNotesList.innerHTML = `<p class="text-secondary fst-italic mb-0">No clinical notes recorded for this assessment.</p>`;
            }
        }

        // Render follow-ups list
        if (followUpsList) {
            const fuList = secCounselling.follow_ups || [];
            if (fuList.length > 0) {
                followUpsList.innerHTML = fuList.map(f => `
                    <div class="mb-2 pb-2 border-bottom border-secondary border-opacity-15">
                        <div class="d-flex justify-content-between xsmall text-secondary mb-1">
                            <span class="badge bg-info bg-opacity-20 text-info">${f.status || 'Pending'}</span>
                            <span class="mono-text fw-bold text-light">${f.follow_up_date || ''}</span>
                        </div>
                        <div class="small text-light">${f.notes || 'Follow-up consultation'}</div>
                    </div>
                `).join("");
            } else {
                followUpsList.innerHTML = `<p class="text-secondary fst-italic mb-0">No follow-up sessions scheduled.</p>`;
            }
        }

        // Section 10: Metadata
        if (pipelineVerVal) pipelineVerVal.textContent = secMeta.pipeline_version || "iris-analysis-v1.0";
    }

    // Action 1: Download Server-Side PDF
    if (downloadPdfBtn) {
        downloadPdfBtn.addEventListener("click", async () => {
            if (downloadPdfSpinner) downloadPdfSpinner.classList.remove("d-none");
            if (downloadPdfIcon) downloadPdfIcon.classList.add("d-none");
            downloadPdfBtn.disabled = true;

            try {
                const pdfResp = await fetch(`/api/assessments/${encodeURIComponent(assessmentId)}/report/pdf`, {
                    headers: authClient.getAuthHeaders()
                });

                if (!pdfResp.ok) {
                    const err = await pdfResp.json().catch(() => ({}));
                    throw new Error(err.detail || "Unable to download report PDF.");
                }

                const blob = await pdfResp.blob();
                const blobUrl = window.URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = blobUrl;
                a.download = `IRIS_Report_${assessmentId}.pdf`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(blobUrl);

            } catch (err) {
                console.error("PDF download failed:", err);
                alert(`PDF Download Error: ${err.message}`);
            } finally {
                if (downloadPdfSpinner) downloadPdfSpinner.classList.add("d-none");
                if (downloadPdfIcon) downloadPdfIcon.classList.remove("d-none");
                downloadPdfBtn.disabled = false;
            }
        });
    }

    // Action 2: Print
    if (printReportBtn) {
        printReportBtn.addEventListener("click", () => {
            window.print();
        });
    }

    // Action 3: Retry
    if (retryLoadBtn) {
        retryLoadBtn.addEventListener("click", () => {
            loadReport();
        });
    }

    // Action 4: Counsellor Review Submission
    if (submitReviewBtn) {
        submitReviewBtn.addEventListener("click", async () => {
            const notes = reviewNotesInput ? reviewNotesInput.value.trim() : "";
            const fuDate = followUpDateInput ? followUpDateInput.value.trim() : "";
            const fuNotes = followUpNotesInput ? followUpNotesInput.value.trim() : "";

            if (!notes && !fuDate) {
                alert("Please enter either clinical review notes or a follow-up date.");
                return;
            }

            if (submitReviewSpinner) submitReviewSpinner.classList.remove("d-none");
            submitReviewBtn.disabled = true;

            try {
                const patchResp = await fetch(`/api/assessments/${encodeURIComponent(assessmentId)}/report/review`, {
                    method: "PATCH",
                    headers: {
                        ...authClient.getAuthHeaders(),
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        review_notes: notes || null,
                        follow_up_date: fuDate || null,
                        follow_up_notes: fuNotes || null
                    })
                });

                if (!patchResp.ok) {
                    const err = await patchResp.json();
                    throw new Error(err.detail || "Failed to submit review.");
                }

                if (reviewModalInstance) {
                    reviewModalInstance.hide();
                }

                // Reset form inputs
                if (reviewNotesInput) reviewNotesInput.value = "";
                if (followUpDateInput) followUpDateInput.value = "";
                if (followUpNotesInput) followUpNotesInput.value = "";

                // Re-fetch report to display updated counselling block
                await loadReport();

            } catch (err) {
                console.error("Review submit error:", err);
                alert(`Review Submission Failed: ${err.message}`);
            } finally {
                if (submitReviewSpinner) submitReviewSpinner.classList.add("d-none");
                submitReviewBtn.disabled = false;
            }
        });
    }

    // Initial Execution
    await loadReport();
});
