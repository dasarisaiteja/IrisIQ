const video = document.getElementById("video");
const canvas = document.getElementById("canvas");

let employeeData = null;
let captureCount = 0;
const totalImages = 40;

let isCapturing = false;

// ======================================================
// START CAMERA
// ======================================================

async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: 1280,
                height: 720,
                facingMode: "user"
            }
        });
        video.srcObject = stream;
        await video.play();
    } catch (err) {
        alert("Camera Error : " + err.message);
    }
}

startCamera();

// ======================================================
// UI HELPERS
// ======================================================

function updateCaptureUI(count, total) {
    const safeCount = Math.min(count, total);
    const percent = Math.min(100, Math.floor((safeCount / total) * 100));

    const counterEl = document.getElementById("counter");
    if (counterEl) counterEl.innerHTML = safeCount + " / " + total;

    const barEl = document.getElementById("progressBar");
    if (barEl) {
        barEl.style.width = percent + "%";
        barEl.innerHTML = percent + "%";
    }

    const statusEl = document.getElementById("status");
    if (statusEl) {
        statusEl.innerHTML = "Captured " + safeCount + " / " + total;
    }
}

// ======================================================
// REGISTER BUTTON
// ======================================================

document.getElementById("registerBtn").onclick = function () {
    if (isCapturing) {
        return;
    }

    if (employee_code.value.trim() === "") {
        alert("Enter Employee Code");
        return;
    }
    if (user_name.value.trim() === "") {
        alert("Enter Employee Name");
        return;
    }
    if (department.value.trim() === "") {
        alert("Enter Department");
        return;
    }
    if (designation.value.trim() === "") {
        alert("Enter Designation");
        return;
    }
    if (gender.value === "") {
        alert("Select Gender");
        return;
    }
    if (dob.value === "") {
        alert("Select Date Of Birth");
        return;
    }
    if (blood_group.value === "") {
        alert("Select Blood Group");
        return;
    }
    if (mobile.value.trim() === "") {
        alert("Enter Mobile");
        return;
    }
    if (email.value.trim() === "") {
        alert("Enter Email");
        return;
    }

    employeeData = {
        employee_code: employee_code.value.trim(),
        user_name: user_name.value.trim(),
        department: department.value.trim(),
        designation: designation.value.trim(),
        gender: gender.value,
        age: age.value,
        dob: dob.value,
        blood_group: blood_group.value,
        mobile: mobile.value.trim(),
        email: email.value.trim(),
        address: address.value.trim()
    };

    startAutoCapture();
};

// ======================================================
// CAPTURE SINGLE FRAME (SEQUENTIAL PROMISE)
// ======================================================

function captureSingleFrame() {
    return new Promise((resolve) => {
        if (!isCapturing || captureCount >= totalImages) {
            return resolve({ done: true });
        }

        canvas.width = video.videoWidth || 1280;
        canvas.height = video.videoHeight || 720;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0);

        canvas.toBlob(async (blob) => {
            if (!blob || !isCapturing || captureCount >= totalImages) {
                return resolve({ done: true });
            }

            const form = new FormData();
            form.append("employee_code", employeeData.employee_code);
            form.append("file", blob, (captureCount + 1) + ".jpg");

            try {
                const response = await fetch("/register-frame", {
                    method: "POST",
                    body: form
                });

                const result = await response.json();

                // If backend indicates all 40 are completed
                if (result.completed) {
                    captureCount = totalImages;
                    updateCaptureUI(totalImages, totalImages);
                    return resolve({ done: true });
                }

                if (result.saved) {
                    // Update with accurate server count if provided, or increment safely
                    const newCount = typeof result.count === "number" ? result.count : (captureCount + 1);
                    captureCount = Math.min(totalImages, newCount);
                    updateCaptureUI(captureCount, totalImages);

                    if (captureCount >= totalImages) {
                        return resolve({ done: true });
                    }
                    return resolve({ done: false, success: true });
                } else {
                    console.warn("Register frame not saved:", result.message || result.detail || result);
                    return resolve({ done: false, success: false });
                }
            } catch (err) {
                console.error("Frame capture error:", err);
                return resolve({ done: false, success: false });
            }
        }, "image/jpeg", 0.95);
    });
}

// ======================================================
// AUTO CAPTURE CONTROLLER
// ======================================================

async function startAutoCapture() {
    isCapturing = true;
    captureCount = 0;
    sessionStorage.removeItem("lastScanInfo");

    const registerBtn = document.getElementById("registerBtn");
    registerBtn.disabled = true;

    document.getElementById("status").innerHTML = "Capturing Iris Images...";
    document.getElementById("counter").innerHTML = "0 / " + totalImages;
    document.getElementById("progressBar").style.width = "0%";
    document.getElementById("progressBar").innerHTML = "0%";

    // Strictly sequential frame capture loop (prevents concurrent backlog / overcounting)
    while (isCapturing && captureCount < totalImages) {
        const res = await captureSingleFrame();
        if (res.done || captureCount >= totalImages) {
            break;
        }

        // Brief delay between frames (250ms)
        await new Promise((r) => setTimeout(r, res.success ? 200 : 350));
    }

    isCapturing = false;

    // Proceed to saving employee and training
    document.getElementById("status").innerHTML = "Saving Customer & Training AI Model...";
    updateCaptureUI(totalImages, totalImages);

    await saveEmployee();
}

// ======================================================
// SAVE EMPLOYEE
// ======================================================

async function saveEmployee() {
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0);

    return new Promise((resolve) => {
        canvas.toBlob(async (blob) => {
            const form = new FormData();
            form.append("employee_code", employeeData.employee_code);
            form.append("user_name", employeeData.user_name);
            form.append("department", employeeData.department);
            form.append("designation", employeeData.designation);
            form.append("gender", employeeData.gender);
            form.append("age", employeeData.age);
            form.append("dob", employeeData.dob);
            form.append("blood_group", employeeData.blood_group);
            form.append("mobile", employeeData.mobile);
            form.append("email", employeeData.email);
            form.append("address", employeeData.address);
            form.append("file", blob, "employee.jpg");

            try {
                document.getElementById("status").innerHTML = "Creating Customer Profile...";

                const response = await fetch("/enroll", {
                    method: "POST",
                    body: form
                });

                const result = await response.json();
                console.log("Enroll Result:", result);

                if (result.status) {
                    sessionStorage.setItem("employee_code", employeeData.employee_code);

                    if (result.scan_info && typeof result.scan_info === "object") {
                        sessionStorage.setItem("lastScanInfo", JSON.stringify(result.scan_info));
                    }

                    document.getElementById("status").innerHTML = "Registration Successful";
                    document.getElementById("counter").innerHTML = totalImages + " / " + totalImages;
                    document.getElementById("progressBar").style.width = "100%";
                    document.getElementById("progressBar").innerHTML = "100%";

                    alert("Customer Registered Successfully");

                    setTimeout(() => {
                        window.location.href = "/static/camera.html";
                    }, 1000);
                } else {
                    const msg = result.message || result.detail || "Registration failed";
                    alert(msg);
                    document.getElementById("status").innerHTML = "Registration failed: " + msg;
                    document.getElementById("registerBtn").disabled = false;
                }
            } catch (err) {
                console.error("Enroll API error:", err);
                alert("API Error : " + err.message);
                document.getElementById("status").innerHTML = "API Error: " + err.message;
                document.getElementById("registerBtn").disabled = false;
            } finally {
                resolve();
            }
        }, "image/jpeg", 0.95);
    });
}