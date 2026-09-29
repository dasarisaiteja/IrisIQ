/**
 * IrisIQ Official Student Registration (Phase 2)
 * Handles student registration form submission to POST /api/students,
 * displays generated Assessment ID, and routes to the eye scanning step.
 */
document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("studentRegistrationForm");
    const studentIdInput = document.getElementById("student_id");
    const studentNameInput = document.getElementById("student_name");
    const registerBtn = document.getElementById("registerBtn");
    const registerSpinner = document.getElementById("registerSpinner");
    const registerIcon = document.getElementById("registerIcon");
    const resetBtn = document.getElementById("resetBtn");
    const cancelBtn = document.getElementById("cancelBtn");

    const alertBox = document.getElementById("alertBox");
    const alertMsg = document.getElementById("alertMsg");
    const alertIcon = document.getElementById("alertIcon");

    const formSection = document.getElementById("formSection");
    const successSection = document.getElementById("successSection");
    const successStudentId = document.getElementById("successStudentId");
    const successStudentName = document.getElementById("successStudentName");
    const successAssessmentId = document.getElementById("successAssessmentId");
    const startScanBtn = document.getElementById("startScanBtn");
    const registerAnotherBtn = document.getElementById("registerAnotherBtn");

    let isSubmitting = false;
    let latestRegistration = null;

    // Helper: Show Alert
    function showAlert(message, type = "danger") {
        if (!alertBox || !alertMsg) return;
        alertBox.className = `alert alert-${type} mb-4 border border-${type} border-opacity-50`;
        alertMsg.textContent = message;

        if (alertIcon) {
            alertIcon.className = type === "success" 
                ? "fa-solid fa-circle-check fs-5 text-success" 
                : "fa-solid fa-circle-exclamation fs-5 text-danger";
        }
        alertBox.classList.remove("d-none");
    }

    // Helper: Hide Alert
    function hideAlert() {
        if (alertBox) {
            alertBox.classList.add("d-none");
        }
    }

    // Helper: Set Submitting State
    function setSubmitting(submitting) {
        isSubmitting = submitting;
        if (registerBtn) {
            registerBtn.disabled = submitting;
        }
        if (registerSpinner) {
            if (submitting) {
                registerSpinner.classList.remove("d-none");
                if (registerIcon) registerIcon.classList.add("d-none");
            } else {
                registerSpinner.classList.add("d-none");
                if (registerIcon) registerIcon.classList.remove("d-none");
            }
        }
    }

    // Handle Form Submit
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        hideAlert();

        if (isSubmitting) return;

        const studentId = studentIdInput.value.trim();
        const studentName = studentNameInput.value.trim();

        // Client-side validations
        if (!studentId) {
            showAlert("Please enter a valid Student ID.");
            studentIdInput.focus();
            return;
        }

        const idPattern = /^[A-Za-z0-9_-]+$/;
        if (!idPattern.test(studentId)) {
            showAlert("Student ID must contain only alphanumeric characters, hyphens, or underscores.");
            studentIdInput.focus();
            return;
        }

        if (!studentName || studentName.length < 2) {
            showAlert("Please enter the student's full name (at least 2 characters).");
            studentNameInput.focus();
            return;
        }

        setSubmitting(true);

        try {
            const response = await fetch("/api/students", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    student_id: studentId,
                    student_name: studentName
                })
            });

            const data = await response.json();

            if (response.status === 201 || (response.ok && data.status)) {
                // Success
                latestRegistration = {
                    student_id: data.student ? data.student.student_id : studentId,
                    student_name: data.student ? data.student.student_name : studentName,
                    assessment_id: data.assessment ? data.assessment.assessment_id : "--"
                };

                // Populate Success View
                successStudentId.textContent = latestRegistration.student_id;
                successStudentName.textContent = latestRegistration.student_name;
                successAssessmentId.textContent = latestRegistration.assessment_id;

                // Toggle views
                formSection.classList.add("d-none");
                successSection.classList.remove("d-none");
                hideAlert();
            } else if (response.status === 409) {
                // Conflict - Duplicate student_id
                showAlert(data.detail || `Student ID '${studentId}' is already registered in the system.`, "danger");
            } else if (response.status === 403) {
                showAlert(data.detail || "You do not have permission to register this student.", "danger");
            } else if (response.status === 400) {
                showAlert(data.detail || "Invalid registration data. Please check your inputs.", "danger");
            } else {
                showAlert(data.detail || data.message || "An error occurred during registration. Please try again.", "danger");
            }
        } catch (error) {
            console.error("Student registration network error:", error);
            showAlert("Network error connecting to IrisIQ API server. Please check your connection and retry.", "danger");
        } finally {
            setSubmitting(false);
        }
    });

    // Reset Action
    if (resetBtn) {
        resetBtn.addEventListener("click", () => {
            form.reset();
            hideAlert();
            studentIdInput.focus();
        });
    }

    // Cancel Action
    if (cancelBtn) {
        cancelBtn.addEventListener("click", () => {
            if (window.history.length > 1) {
                window.location.href = "dashboard.html";
            } else {
                form.reset();
                hideAlert();
            }
        });
    }

    // "Start Eye Scan" CTA Action
    if (startScanBtn) {
        startScanBtn.addEventListener("click", () => {
            if (!latestRegistration) return;
            // Navigates to camera.html with the new assessment_id and student_id context
            const scanUrl = `camera.html?assessment_id=${encodeURIComponent(latestRegistration.assessment_id)}&student_id=${encodeURIComponent(latestRegistration.student_id)}`;
            window.location.href = scanUrl;
        });
    }

    // "Register Another Student" Action
    if (registerAnotherBtn) {
        registerAnotherBtn.addEventListener("click", () => {
            form.reset();
            latestRegistration = null;
            successSection.classList.add("d-none");
            formSection.classList.remove("d-none");
            hideAlert();
            studentIdInput.focus();
        });
    }
});