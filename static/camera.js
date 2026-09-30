/**
 * IrisIQ Official Dual-Eye Biometric Scanner Controller (Phase 3)
 * Orchestrates camera stream, reticle guidance, and uploads frames
 * to official backend endpoints:
 * - POST /api/assessments/{assessmentId}/scan/left
 * - POST /api/assessments/{assessmentId}/scan/right
 * - POST /api/assessments/{assessmentId}/scan/{eye}/retry
 * - GET /api/assessments/{assessmentId}/scan/status
 *
 * Backend is strictly authoritative for scan completion state.
 */

// Resilient Auth Client resolver
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

document.addEventListener("DOMContentLoaded", () => {
    // URL Context & State
    const urlParams = new URLSearchParams(window.location.search);
    const assessmentId = urlParams.get("assessment_id") || sessionStorage.getItem("iris_active_assessment_id");
    const studentIdParam = urlParams.get("student_id") || sessionStorage.getItem("iris_active_student_id");

    // DOM Elements - Header & Metadata
    const displayAssessmentId = document.getElementById("displayAssessmentId");
    const displayStudentId = document.getElementById("displayStudentId");
    const displayStudentName = document.getElementById("displayStudentName");
    const displayWorkflowStatus = document.getElementById("displayWorkflowStatus");
    const displayWorkflowStatusBadge = document.getElementById("displayWorkflowStatusBadge");
    const displayGatingStatus = document.getElementById("displayGatingStatus");

    // DOM Elements - Stepper
    const stepLeft = document.getElementById("stepLeft");
    const stepLeftIcon = document.getElementById("stepLeftIcon");
    const stepLineRight = document.getElementById("stepLineRight");
    const stepRight = document.getElementById("stepRight");
    const stepRightIcon = document.getElementById("stepRightIcon");

    // DOM Elements - Camera
    const video = document.getElementById("video");
    const canvas = document.getElementById("canvas");
    const cameraErrorOverlay = document.getElementById("cameraErrorOverlay");
    const cameraErrorMessage = document.getElementById("cameraErrorMessage");
    const cameraErrorTitle = document.getElementById("cameraErrorTitle");
    const cameraErrorIcon = document.getElementById("cameraErrorIcon");
    const retryCameraBtn = document.getElementById("retryCameraBtn");
    const cameraLoadingOverlay = document.getElementById("cameraLoadingOverlay");
    const cameraLoadingTitle = document.getElementById("cameraLoadingTitle");
    const cameraLoadingDesc = document.getElementById("cameraLoadingDesc");
    const cameraStatusBadge = document.getElementById("cameraStatusBadge");
    const cameraLiveIndicator = document.getElementById("cameraLiveIndicator");
    const targetingReticle = document.getElementById("targetingReticle");
    const cameraResolution = document.getElementById("cameraResolution");
    const activeEyeIndicator = document.getElementById("activeEyeIndicator");
    const reticleLabel = document.getElementById("reticleLabel");

    // DOM Elements - Global Alert
    const globalAlert = document.getElementById("globalAlert");
    const globalAlertMsg = document.getElementById("globalAlertMsg");
    const globalAlertIcon = document.getElementById("globalAlertIcon");

    // DOM Elements - Left Eye Card
    const leftEyeCard = document.getElementById("leftEyeCard");
    const leftStatusBadge = document.getElementById("leftStatusBadge");
    const leftScanDetails = document.getElementById("leftScanDetails");
    const leftQualityScore = document.getElementById("leftQualityScore");
    const leftQualityBar = document.getElementById("leftQualityBar");
    const leftErrorBox = document.getElementById("leftErrorBox");
    const leftErrorText = document.getElementById("leftErrorText");
    const captureLeftBtn = document.getElementById("captureLeftBtn");
    const retryLeftBtn = document.getElementById("retryLeftBtn");
    const leftSpinner = document.getElementById("leftSpinner");

    // DOM Elements - Right Eye Card
    const rightEyeCard = document.getElementById("rightEyeCard");
    const rightStatusBadge = document.getElementById("rightStatusBadge");
    const rightScanDetails = document.getElementById("rightScanDetails");
    const rightQualityScore = document.getElementById("rightQualityScore");
    const rightQualityBar = document.getElementById("rightQualityBar");
    const rightErrorBox = document.getElementById("rightErrorBox");
    const rightErrorText = document.getElementById("rightErrorText");
    const captureRightBtn = document.getElementById("captureRightBtn");
    const retryRightBtn = document.getElementById("retryRightBtn");
    const rightSpinner = document.getElementById("rightSpinner");

    // DOM Elements - Gating & Advancement
    const scanGatingBanner = document.getElementById("scanGatingBanner");
    const continueAnalysisBtn = document.getElementById("continueAnalysisBtn");
    const analysisSpinner = document.getElementById("analysisSpinner");
    const continueAnalysisIcon = document.getElementById("continueAnalysisIcon");
    const continueAnalysisText = document.getElementById("continueAnalysisText");
    const analysisSubtext = document.getElementById("analysisSubtext");

    // DOM Elements - Analysis Stepper & Panels
    const stepLineAnalysis = document.getElementById("stepLineAnalysis");
    const stepAnalysis = document.getElementById("stepAnalysis");
    const stepAnalysisIcon = document.getElementById("stepAnalysisIcon");
    const processingStatusBox = document.getElementById("processingStatusBox");
    const processingProgressBar = document.getElementById("processingProgressBar");
    const processingStatusMsg = document.getElementById("processingStatusMsg");
    const analysisResultsBox = document.getElementById("analysisResultsBox");
    const resEngineVer = document.getElementById("resEngineVer");
    const resAvgQuality = document.getElementById("resAvgQuality");
    const resSimilarity = document.getElementById("resSimilarity");
    const resPupilDelta = document.getElementById("resPupilDelta");
    const resLeftDetails = document.getElementById("resLeftDetails");
    const resRightDetails = document.getElementById("resRightDetails");
    const resEyeColor = document.getElementById("resEyeColor");
    const analysisErrorBox = document.getElementById("analysisErrorBox");
    const analysisErrorMsg = document.getElementById("analysisErrorMsg");
    const retryAnalysisBtn = document.getElementById("retryAnalysisBtn");
    const proceedReportBtn = document.getElementById("proceedReportBtn");

    let mediaStream = null;
    let isProcessing = false;
    let activeEye = "LEFT"; // Default focus is Left eye

    // Helper: Show Global Alert
    function showGlobalAlert(message, type = "danger") {
        if (!globalAlert || !globalAlertMsg) return;
        globalAlert.className = `alert alert-${type} mb-4 border border-${type} border-opacity-50`;
        globalAlertMsg.textContent = message;
        if (globalAlertIcon) {
            globalAlertIcon.className = type === "success" 
                ? "fa-solid fa-circle-check fs-5 text-success" 
                : "fa-solid fa-circle-exclamation fs-5 text-danger";
        }
        globalAlert.classList.remove("d-none");
    }

    // Helper: Hide Global Alert
    function hideGlobalAlert() {
        if (globalAlert) globalAlert.classList.add("d-none");
    }

    // Helper: Set Active Eye Focus
    function setActiveEyeFocus(eye) {
        activeEye = eye;
        if (eye === "LEFT") {
            leftEyeCard.classList.add("active-card");
            rightEyeCard.classList.remove("active-card");
            activeEyeIndicator.textContent = "LEFT EYE ACTIVE";
            activeEyeIndicator.className = "badge bg-primary px-3 py-1 rounded-pill fw-bold";
            reticleLabel.textContent = "Align LEFT Eye in Target Ring";
            reticleLabel.style.color = "#60a5fa";
        } else {
            rightEyeCard.classList.add("active-card");
            leftEyeCard.classList.remove("active-card");
            activeEyeIndicator.textContent = "RIGHT EYE ACTIVE";
            activeEyeIndicator.className = "badge bg-info px-3 py-1 rounded-pill fw-bold";
            reticleLabel.textContent = "Align RIGHT Eye in Target Ring";
            reticleLabel.style.color = "#38bdf8";
        }
    }

    // Helper: Set Unified Camera Status & Overlays
    function setCameraStatus(statusText, detail = null, type = "info") {
        if (cameraStatusBadge) {
            let badgeClass = "badge px-2 py-1 small ";
            let iconHtml = "";
            if (type === "warning") {
                badgeClass += "bg-warning-subtle text-warning border border-warning border-opacity-25";
                iconHtml = '<i class="fa-solid fa-spinner fa-spin me-1"></i>';
            } else if (type === "success") {
                badgeClass += "bg-success-subtle text-success border border-success border-opacity-25";
                iconHtml = '<i class="fa-solid fa-circle-check me-1"></i>';
            } else {
                badgeClass += "bg-danger-subtle text-danger border border-danger border-opacity-25";
                iconHtml = '<i class="fa-solid fa-circle-exclamation me-1"></i>';
            }
            cameraStatusBadge.className = badgeClass;
            cameraStatusBadge.innerHTML = `${iconHtml} ${statusText}`;
        }

        if (statusText === "Camera ready") {
            if (cameraLiveIndicator) cameraLiveIndicator.classList.add("active");
            if (cameraLoadingOverlay) cameraLoadingOverlay.classList.add("d-none");
            if (cameraErrorOverlay) {
                cameraErrorOverlay.classList.add("d-none");
                cameraErrorOverlay.classList.remove("d-flex");
            }
            if (targetingReticle) targetingReticle.classList.remove("d-none");
        } else if (statusText === "Requesting camera access...") {
            if (cameraLiveIndicator) cameraLiveIndicator.classList.remove("active");
            if (cameraLoadingOverlay) {
                cameraLoadingOverlay.classList.remove("d-none");
                cameraLoadingOverlay.classList.add("d-flex");
            }
            if (cameraErrorOverlay) {
                cameraErrorOverlay.classList.add("d-none");
                cameraErrorOverlay.classList.remove("d-flex");
            }
        } else {
            // Error states
            if (cameraLiveIndicator) cameraLiveIndicator.classList.remove("active");
            if (cameraLoadingOverlay) cameraLoadingOverlay.classList.add("d-none");
            if (cameraErrorOverlay) {
                cameraErrorOverlay.classList.remove("d-none");
                cameraErrorOverlay.classList.add("d-flex");
            }
            if (cameraErrorTitle) cameraErrorTitle.textContent = statusText;
            if (cameraErrorMessage && detail) cameraErrorMessage.textContent = detail;
            if (cameraErrorIcon) {
                if (statusText === "Camera permission denied") {
                    cameraErrorIcon.className = "fa-solid fa-shield-halved text-danger display-4 mb-3";
                } else if (statusText === "No camera detected") {
                    cameraErrorIcon.className = "fa-solid fa-video-slash text-danger display-4 mb-3";
                } else if (statusText === "Camera already in use") {
                    cameraErrorIcon.className = "fa-solid fa-lock text-warning display-4 mb-3";
                } else {
                    cameraErrorIcon.className = "fa-solid fa-triangle-exclamation text-danger display-4 mb-3";
                }
            }
        }
    }

    function handleCameraError(err) {
        console.error("Camera access failure:", err);
        const errName = err ? (err.name || "") : "";
        const errMsg = err ? (err.message || "") : "";

        if (errName === "NotAllowedError" || errName === "PermissionDeniedError") {
            setCameraStatus(
                "Camera permission denied",
                "Camera access was denied. Please click the lock or camera icon in your browser address bar, set Camera to 'Allow', and click 'Request Camera Access'.",
                "danger"
            );
        } else if (errName === "NotFoundError" || errName === "DevicesNotFoundError") {
            setCameraStatus(
                "No camera detected",
                "No webcam or camera device was detected on your system. Please connect an external camera or ensure your built-in camera is enabled.",
                "danger"
            );
        } else if (errName === "NotReadableError" || errName === "TrackStartError") {
            setCameraStatus(
                "Camera already in use",
                "The camera is currently held by another application, browser tab, or background process. Please close other camera apps and click 'Request Camera Access'.",
                "danger"
            );
        } else if (errName === "OverconstrainedError") {
            setCameraStatus(
                "Unable to start camera",
                `The camera could not satisfy requested video constraints (${err.constraint || 'resolution'}).`,
                "danger"
            );
        } else if (errName === "SecurityError") {
            setCameraStatus(
                "Unable to start camera",
                "Camera access was blocked by browser security policy or insecure origin.",
                "danger"
            );
        } else {
            setCameraStatus(
                "Unable to start camera",
                errMsg || "Could not access video input device. Please verify your camera settings.",
                "danger"
            );
        }
    }

    // 1. Initialize & Start Camera
    async function startCamera() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            setCameraStatus(
                "Unable to start camera",
                "The MediaDevices Camera API is not supported by your browser or the current origin. Please access IrisIQ via http://localhost or HTTPS.",
                "danger"
            );
            return;
        }

        setCameraStatus(
            "Requesting camera access...",
            "Please allow camera access when prompted by your browser to view the live biometric stream.",
            "warning"
        );

        if (mediaStream) {
            try {
                mediaStream.getTracks().forEach(track => track.stop());
            } catch (e) {}
            mediaStream = null;
        }

        // Progressive constraint candidates: ideal 720p HD -> VGA -> unconstrained
        const constraintCandidates = [
            {
                video: {
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                    facingMode: { ideal: "user" }
                },
                audio: false
            },
            {
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: { ideal: "user" }
                },
                audio: false
            },
            {
                video: true,
                audio: false
            }
        ];

        let streamAcquired = null;
        let lastError = null;

        for (const constraints of constraintCandidates) {
            try {
                streamAcquired = await navigator.mediaDevices.getUserMedia(constraints);
                if (streamAcquired) break;
            } catch (err) {
                lastError = err;
                // If permission was denied or device missing or in use, relaxed constraints won't help
                if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError" ||
                    err.name === "NotReadableError" || err.name === "TrackStartError" ||
                    err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
                    break;
                }
                console.warn("Retrying camera with relaxed constraints due to:", err);
            }
        }

        if (!streamAcquired) {
            handleCameraError(lastError);
            return;
        }

        try {
            mediaStream = streamAcquired;

            // Strict HTML5 video element property configuration for reliable playback
            video.muted = true;
            video.defaultMuted = true;
            video.playsInline = true;
            video.setAttribute("playsinline", "");
            video.setAttribute("muted", "");
            video.srcObject = mediaStream;

            // Wait for metadata ready before calling play
            await new Promise((resolve) => {
                if (video.readyState >= HTMLMediaElement.HAVE_METADATA) {
                    resolve();
                } else {
                    const onMeta = () => {
                        video.removeEventListener("loadedmetadata", onMeta);
                        resolve();
                    };
                    video.addEventListener("loadedmetadata", onMeta);
                    setTimeout(resolve, 1500); // Safety timeout
                }
            });

            // Start live playback
            await video.play().catch(playErr => {
                console.warn("video.play() warning:", playErr);
            });

            // Read live resolution
            const track = mediaStream.getVideoTracks()[0];
            const settings = track ? track.getSettings() : {};
            const activeWidth = video.videoWidth || settings.width || 0;
            const activeHeight = video.videoHeight || settings.height || 0;

            if (activeWidth && activeHeight) {
                cameraResolution.textContent = `${activeWidth}x${activeHeight}`;
            } else {
                cameraResolution.textContent = "Live Stream Active";
            }

            setCameraStatus("Camera ready", null, "success");

        } catch (err) {
            console.error("Video element playback error:", err);
            handleCameraError(err);
        }
    }

    if (retryCameraBtn) {
        retryCameraBtn.addEventListener("click", () => {
            startCamera();
        });
    }

    // 2. Fetch and Sync Backend Assessment Scan Status
    async function refreshScanStatus() {
        if (!assessmentId) return;

        try {
            const response = await fetch(`/api/assessments/${encodeURIComponent(assessmentId)}/scan/status`);
            if (response.status === 404) {
                showGlobalAlert(`Assessment '${assessmentId}' was not found. Please register or select an active assessment.`, "danger");
                return;
            }
            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                showGlobalAlert(errData.detail || "Failed to load assessment status.", "danger");
                return;
            }

            const data = await response.json();
            await updateUIFromStatus(data);
        } catch (err) {
            console.error("Status refresh error:", err);
        }
    }

    // 3. Update UI strictly from Backend Authoritative Status
    async function updateUIFromStatus(data) {
        displayAssessmentId.textContent = data.assessment_id;
        displayStudentId.textContent = data.student_id;
        displayStudentName.textContent = data.student_name;
        displayWorkflowStatus.textContent = data.workflow_status;

        // Workflow Status Badge Colors
        if (data.workflow_status === "SCAN_COMPLETED") {
            displayWorkflowStatusBadge.className = "badge bg-success-subtle text-success border border-success border-opacity-25 px-3 py-2 fw-semibold small";
            displayWorkflowStatusBadge.innerHTML = `<i class="fa-solid fa-circle-check me-1"></i> SCAN_COMPLETED`;
            displayGatingStatus.textContent = "Completed & Verified";
            displayGatingStatus.className = "text-success fw-bold";
        } else if (data.workflow_status.includes("COMPLETED")) {
            displayWorkflowStatusBadge.className = "badge bg-warning-subtle text-warning border border-warning border-opacity-25 px-3 py-2 fw-semibold small";
            displayWorkflowStatusBadge.innerHTML = `<i class="fa-solid fa-hourglass-half me-1"></i> ${data.workflow_status}`;
            displayGatingStatus.textContent = "1 of 2 Scans Completed";
            displayGatingStatus.className = "text-warning fw-bold";
        } else {
            displayWorkflowStatusBadge.className = "badge bg-primary-subtle text-primary border border-primary border-opacity-25 px-3 py-2 fw-semibold small";
            displayWorkflowStatusBadge.innerHTML = `<i class="fa-solid fa-spinner fa-spin-pulse me-1"></i> ${data.workflow_status}`;
            displayGatingStatus.textContent = "Dual Scan Required";
            displayGatingStatus.className = "text-info fw-bold";
        }

        const left = data.scans?.left || {};
        const right = data.scans?.right || {};

        // Update LEFT EYE card
        if (left.status === "Completed") {
            leftStatusBadge.className = "badge bg-success-subtle text-success px-3 py-2 rounded-pill small fw-semibold";
            leftStatusBadge.innerHTML = `<i class="fa-solid fa-check me-1"></i> Completed`;
            leftEyeCard.classList.add("completed-card");
            leftScanDetails.classList.remove("d-none");
            leftQualityScore.textContent = `${Math.round(left.quality_score || 0)}%`;
            leftQualityBar.style.width = `${Math.round(left.quality_score || 0)}%`;
            leftErrorBox.classList.add("d-none");

            captureLeftBtn.classList.add("d-none");
            retryLeftBtn.classList.remove("d-none");

            // Stepper Left Eye
            stepLeft.className = "step completed";
            stepLeftIcon.innerHTML = `<i class="fa-solid fa-check"></i>`;
            stepLineRight.className = "step-line active";
        } else if (left.status === "Failed") {
            leftStatusBadge.className = "badge bg-danger-subtle text-danger px-3 py-2 rounded-pill small fw-semibold";
            leftStatusBadge.innerHTML = `<i class="fa-solid fa-triangle-exclamation me-1"></i> Failed`;
            leftEyeCard.classList.remove("completed-card");
            leftScanDetails.classList.remove("d-none");
            leftErrorBox.classList.remove("d-none");
            leftErrorText.textContent = left.error_message || "Scan quality insufficient. Please retry.";
            retryLeftBtn.classList.remove("d-none");
        } else {
            leftStatusBadge.className = "badge bg-secondary-subtle text-secondary px-3 py-2 rounded-pill small fw-semibold";
            leftStatusBadge.textContent = "Pending";
            leftEyeCard.classList.remove("completed-card");
            leftScanDetails.classList.add("d-none");
            captureLeftBtn.classList.remove("d-none");
            retryLeftBtn.classList.add("d-none");
        }

        // Update RIGHT EYE card
        if (right.status === "Completed") {
            rightStatusBadge.className = "badge bg-success-subtle text-success px-3 py-2 rounded-pill small fw-semibold";
            rightStatusBadge.innerHTML = `<i class="fa-solid fa-check me-1"></i> Completed`;
            rightEyeCard.classList.add("completed-card");
            rightScanDetails.classList.remove("d-none");
            rightQualityScore.textContent = `${Math.round(right.quality_score || 0)}%`;
            rightQualityBar.style.width = `${Math.round(right.quality_score || 0)}%`;
            rightErrorBox.classList.add("d-none");

            captureRightBtn.classList.add("d-none");
            retryRightBtn.classList.remove("d-none");

            // Stepper Right Eye
            stepRight.className = "step completed";
            stepRightIcon.innerHTML = `<i class="fa-solid fa-check"></i>`;
        } else if (right.status === "Failed") {
            rightStatusBadge.className = "badge bg-danger-subtle text-danger px-3 py-2 rounded-pill small fw-semibold";
            rightStatusBadge.innerHTML = `<i class="fa-solid fa-triangle-exclamation me-1"></i> Failed`;
            rightEyeCard.classList.remove("completed-card");
            rightScanDetails.classList.remove("d-none");
            rightErrorBox.classList.remove("d-none");
            rightErrorText.textContent = right.error_message || "Scan quality insufficient. Please retry.";
            retryRightBtn.classList.remove("d-none");
        } else {
            rightStatusBadge.className = "badge bg-secondary-subtle text-secondary px-3 py-2 rounded-pill small fw-semibold";
            rightStatusBadge.textContent = "Pending";
            rightEyeCard.classList.remove("completed-card");
            rightScanDetails.classList.add("d-none");
            captureRightBtn.classList.remove("d-none");
            retryRightBtn.classList.add("d-none");
        }

        // Auto-switch focus to Right eye if Left is already completed
        if (left.status === "Completed" && right.status !== "Completed") {
            setActiveEyeFocus("RIGHT");
        }

        // Gating & Advancement Logic (strictly backend authoritative)
        if (["ANALYSIS_COMPLETED", "REPORT_GENERATING", "REPORT_READY"].includes(data.workflow_status)) {
            continueAnalysisBtn.disabled = true;
            continueAnalysisBtn.classList.remove("pulse-btn");
            await loadAndRenderAnalysis();
        } else if (data.workflow_status === "PROCESSING") {
            continueAnalysisBtn.disabled = true;
            if (processingStatusBox) processingStatusBox.classList.remove("d-none");
            pollAnalysisStatus();
        } else if (data.scans?.both_completed) {
            continueAnalysisBtn.disabled = false;
            continueAnalysisBtn.classList.add("pulse-btn");
            scanGatingBanner.innerHTML = `<i class="fa-solid fa-circle-check text-success me-1"></i> Both eye scans verified by backend. Ready to proceed.`;
            scanGatingBanner.className = "small text-success fw-bold mb-3";
        } else {
            continueAnalysisBtn.disabled = true;
            continueAnalysisBtn.classList.remove("pulse-btn");
            scanGatingBanner.innerHTML = `<i class="fa-solid fa-lock me-1"></i> Both Left and Right eye scans must be backend-verified before advancing.`;
            scanGatingBanner.className = "small text-secondary mb-3";
        }
    }

    // 4. Capture Canvas Frame & Upload to Endpoint
    async function captureAndUpload(eye, isRetry = false) {
        if (!assessmentId) {
            showGlobalAlert("No assessment context found. Please register or select an assessment.", "danger");
            return;
        }

        if (isProcessing) return;
        hideGlobalAlert();

        if (!video.videoWidth || !video.videoHeight) {
            showGlobalAlert("Camera feed is not ready. Please wait for camera initialization.", "warning");
            return;
        }

        isProcessing = true;
        const spinner = (eye === "LEFT") ? leftSpinner : rightSpinner;
        const btn = isRetry 
            ? ((eye === "LEFT") ? retryLeftBtn : retryRightBtn)
            : ((eye === "LEFT") ? captureLeftBtn : captureRightBtn);

        btn.disabled = true;
        if (spinner) spinner.classList.remove("d-none");

        try {
            // Draw current video frame to hidden canvas
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const ctx = canvas.getContext("2d");
            
            // Mirror frame correctly since video has scaleX(-1) preview
            ctx.translate(canvas.width, 0);
            ctx.scale(-1, 1);
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            ctx.setTransform(1, 0, 0, 1, 0, 0); // Reset transform

            // Convert to JPEG Blob
            const blob = await new Promise((resolve) => {
                canvas.toBlob((b) => resolve(b), "image/jpeg", 0.95);
            });

            if (!blob) {
                throw new Error("Failed to encode frame from camera.");
            }

            const formData = new FormData();
            formData.append("file", blob, `${eye.toLowerCase()}_scan.jpg`);

            const endpoint = isRetry
                ? `/api/assessments/${encodeURIComponent(assessmentId)}/scan/${eye.toLowerCase()}/retry`
                : `/api/assessments/${encodeURIComponent(assessmentId)}/scan/${eye.toLowerCase()}`;

            const response = await fetch(endpoint, {
                method: "POST",
                body: formData
            });

            const result = await response.json();

            if (response.status === 200 || response.ok) {
                if (result.status) {
                    showGlobalAlert(`${eye} eye scan captured and verified successfully!`, "success");
                } else {
                    showGlobalAlert(result.message || `${eye} eye scan failed quality verification.`, "danger");
                }
            } else if (response.status === 409) {
                showGlobalAlert(result.detail || `Conflict: A completed scan already exists for ${eye} eye. Use Rescan if replacement is needed.`, "warning");
            } else if (response.status === 400 || response.status === 413) {
                showGlobalAlert(result.detail || "Invalid image upload. Please retry capture.", "danger");
            } else if (response.status === 403) {
                showGlobalAlert(result.detail || "You are not authorized to upload scans for this assessment.", "danger");
            } else {
                showGlobalAlert(result.detail || "An unexpected error occurred while processing scan.", "danger");
            }

            // Always synchronize backend authoritative status
            await refreshScanStatus();

        } catch (err) {
            console.error(`Upload error for ${eye} eye:`, err);
            showGlobalAlert(`Network or capture error during ${eye} scan: ${err.message}`, "danger");
        } finally {
            isProcessing = false;
            btn.disabled = false;
            if (spinner) spinner.classList.add("d-none");
        }
    }

    // 5. Button Listeners
    if (captureLeftBtn) {
        captureLeftBtn.addEventListener("click", () => {
            setActiveEyeFocus("LEFT");
            captureAndUpload("LEFT", false);
        });
    }

    if (retryLeftBtn) {
        retryLeftBtn.addEventListener("click", () => {
            setActiveEyeFocus("LEFT");
            captureAndUpload("LEFT", true);
        });
    }

    if (captureRightBtn) {
        captureRightBtn.addEventListener("click", () => {
            setActiveEyeFocus("RIGHT");
            captureAndUpload("RIGHT", false);
        });
    }

    if (retryRightBtn) {
        retryRightBtn.addEventListener("click", () => {
            setActiveEyeFocus("RIGHT");
            captureAndUpload("RIGHT", true);
        });
    }

    // =========================================================
    // 5. PHASE 4: OFFICIAL BILATERAL ANALYSIS PROCESSING
    // =========================================================

    async function startAnalysisProcessing() {
        if (!assessmentId) return;

        hideGlobalAlert();
        if (analysisErrorBox) analysisErrorBox.classList.add("d-none");
        if (processingStatusBox) processingStatusBox.classList.remove("d-none");

        continueAnalysisBtn.disabled = true;
        continueAnalysisBtn.classList.remove("pulse-btn");
        if (analysisSpinner) analysisSpinner.classList.remove("d-none");
        if (continueAnalysisIcon) continueAnalysisIcon.classList.add("d-none");
        if (continueAnalysisText) continueAnalysisText.textContent = "Processing Analysis...";

        try {
            const resp = await fetch(`/api/assessments/${encodeURIComponent(assessmentId)}/process`, {
                method: "POST",
                headers: authClient.getAuthHeaders()
            });

            const result = await resp.json();

            if (!resp.ok) {
                throw new Error(result.detail || "Analysis processing failed.");
            }

            if (result.workflow_status === "ANALYSIS_COMPLETED" || result.status === true) {
                await loadAndRenderAnalysis();
            } else if (result.workflow_status === "PROCESSING") {
                pollAnalysisStatus();
            }
        } catch (err) {
            console.error("Analysis process error:", err);
            if (processingStatusBox) processingStatusBox.classList.add("d-none");
            if (analysisErrorBox) {
                analysisErrorBox.classList.remove("d-none");
                if (analysisErrorMsg) analysisErrorMsg.textContent = err.message;
            }
            continueAnalysisBtn.disabled = false;
            if (analysisSpinner) analysisSpinner.classList.add("d-none");
            if (continueAnalysisIcon) continueAnalysisIcon.classList.remove("d-none");
            if (continueAnalysisText) continueAnalysisText.textContent = "Retry Analysis";
        }
    }

    async function pollAnalysisStatus() {
        let attempts = 0;
        const maxAttempts = 30; // 30 * 1.5s = 45s max
        const interval = setInterval(async () => {
            attempts++;
            try {
                const resp = await fetch(`/api/assessments/${encodeURIComponent(assessmentId)}/process/status`, {
                    headers: authClient.getAuthHeaders()
                });
                if (!resp.ok) {
                    clearInterval(interval);
                    throw new Error("Unable to check analysis status.");
                }
                const data = await resp.json();
                if (data.workflow_status === "ANALYSIS_COMPLETED") {
                    clearInterval(interval);
                    await loadAndRenderAnalysis();
                } else if (data.workflow_status === "FAILED") {
                    clearInterval(interval);
                    throw new Error(data.safe_error_message || "Analysis processing failed on backend.");
                }
            } catch (err) {
                clearInterval(interval);
                if (processingStatusBox) processingStatusBox.classList.add("d-none");
                if (analysisErrorBox) {
                    analysisErrorBox.classList.remove("d-none");
                    if (analysisErrorMsg) analysisErrorMsg.textContent = err.message;
                }
                continueAnalysisBtn.disabled = false;
                if (analysisSpinner) analysisSpinner.classList.add("d-none");
                if (continueAnalysisIcon) continueAnalysisIcon.classList.remove("d-none");
                if (continueAnalysisText) continueAnalysisText.textContent = "Retry Analysis";
            }

            if (attempts >= maxAttempts) {
                clearInterval(interval);
                if (processingStatusBox) processingStatusBox.classList.add("d-none");
                showGlobalAlert("Analysis processing is taking longer than expected. Please refresh or retry.", "warning");
                continueAnalysisBtn.disabled = false;
                if (analysisSpinner) analysisSpinner.classList.add("d-none");
            }
        }, 1500);
    }

    async function loadAndRenderAnalysis() {
        try {
            const resp = await fetch(`/api/assessments/${encodeURIComponent(assessmentId)}/analysis`, {
                headers: authClient.getAuthHeaders()
            });
            if (!resp.ok) {
                const errData = await resp.json();
                throw new Error(errData.detail || "Failed to load analysis results.");
            }
            const data = await resp.json();
            const analysis = data.analysis;

            // Hide processing and error boxes
            if (processingStatusBox) processingStatusBox.classList.add("d-none");
            if (analysisErrorBox) analysisErrorBox.classList.add("d-none");

            // Populate results card
            if (analysisResultsBox) analysisResultsBox.classList.remove("d-none");
            if (resEngineVer) resEngineVer.textContent = analysis.model_metadata?.pipeline_version || data.model_version || "iris-analysis-v1.0";
            if (resAvgQuality) resAvgQuality.textContent = `${analysis.bilateral_analysis?.average_quality_score ?? '--'}%`;
            if (resSimilarity) resSimilarity.textContent = `${analysis.bilateral_analysis?.bilateral_geometric_similarity ?? '--'}`;
            const pDelta = analysis.bilateral_analysis?.pupil_radius_delta;
            if (resPupilDelta) resPupilDelta.textContent = (pDelta !== null && pDelta !== undefined) ? `${pDelta} px` : "--";

            const leftIrisR = analysis.left_eye?.iris_circle?.[2];
            const leftPupilR = analysis.left_eye?.pupil_circle?.[2];
            if (resLeftDetails) resLeftDetails.textContent = `Iris r=${leftIrisR || '--'}, Pupil r=${leftPupilR || '--'}`;

            const rightIrisR = analysis.right_eye?.iris_circle?.[2];
            const rightPupilR = analysis.right_eye?.pupil_circle?.[2];
            if (resRightDetails) resRightDetails.textContent = `Iris r=${rightIrisR || '--'}, Pupil r=${rightPupilR || '--'}`;

            const detColor = analysis.bilateral_analysis?.detected_left_color || analysis.left_eye?.color?.eye_color || "Brown";
            if (resEyeColor) resEyeColor.textContent = detColor;

            // Update continueAnalysis button
            continueAnalysisBtn.disabled = true;
            continueAnalysisBtn.classList.remove("pulse-btn", "btn-success");
            continueAnalysisBtn.classList.add("btn-secondary");
            if (analysisSpinner) analysisSpinner.classList.add("d-none");
            if (continueAnalysisIcon) {
                continueAnalysisIcon.classList.remove("d-none", "fa-brain");
                continueAnalysisIcon.classList.add("fa-check");
            }
            if (continueAnalysisText) continueAnalysisText.textContent = "Analysis Completed";
            if (analysisSubtext) analysisSubtext.textContent = "Dual-eye biometric analysis verified and persisted.";

            // Stepper update for Step 4
            if (stepLineAnalysis) stepLineAnalysis.className = "step-line active";
            if (stepAnalysis) {
                stepAnalysis.className = "step completed";
                if (stepAnalysisIcon) stepAnalysisIcon.innerHTML = `<i class="fa-solid fa-check"></i>`;
            }

            if (scanGatingBanner) {
                scanGatingBanner.innerHTML = `<i class="fa-solid fa-circle-check text-success me-1"></i> Bilateral analysis completed and verified.`;
                scanGatingBanner.className = "small text-success fw-bold mb-3";
            }

            // Enable official report view
            if (proceedReportBtn) {
                proceedReportBtn.disabled = false;
                proceedReportBtn.onclick = () => {
                    window.location.href = `official_report.html?assessment_id=${encodeURIComponent(assessmentId)}`;
                };
            }

        } catch (err) {
            console.error("Error loading analysis:", err);
            showGlobalAlert(`Error loading analysis: ${err.message}`, "danger");
        }
    }

    if (continueAnalysisBtn) {
        continueAnalysisBtn.addEventListener("click", () => {
            startAnalysisProcessing();
        });
    }

    if (retryAnalysisBtn) {
        retryAnalysisBtn.addEventListener("click", () => {
            startAnalysisProcessing();
        });
    }

    // Card click focus helpers
    if (leftEyeCard) {
        leftEyeCard.addEventListener("click", (e) => {
            if (!e.target.closest("button")) {
                setActiveEyeFocus("LEFT");
            }
        });
    }

    if (rightEyeCard) {
        rightEyeCard.addEventListener("click", (e) => {
            if (!e.target.closest("button")) {
                setActiveEyeFocus("RIGHT");
            }
        });
    }

    // Clean up tracks when navigating away
    window.addEventListener("beforeunload", () => {
        if (mediaStream) {
            try {
                mediaStream.getTracks().forEach(track => track.stop());
            } catch (e) {}
            mediaStream = null;
        }
    });

    // Initial Execution
    if (!assessmentId) {
        showGlobalAlert("No active Assessment ID found. Please register a student or select an assessment from Dashboard.", "warning");
    } else {
        refreshScanStatus();
    }

    startCamera();
});