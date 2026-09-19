const video = document.getElementById("video");
const canvas = document.getElementById("canvas");

let employeeData = null;

let captureCount = 0;
const totalImages = 40;

let captureTimer = null;

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

    }

    catch (err) {

        alert("Camera Error : " + err.message);

    }

}

startCamera();

// ======================================================
// REGISTER BUTTON
// ======================================================

document.getElementById("registerBtn").onclick = function () {

    if (employee_code.value == "") {
        alert("Enter Employee Code");
        return;
    }

    if (user_name.value == "") {
        alert("Enter Employee Name");
        return;
    }

    if (department.value == "") {
        alert("Enter Department");
        return;
    }

    if (designation.value == "") {
        alert("Enter Designation");
        return;
    }

    if (gender.value == "") {
        alert("Select Gender");
        return;
    }

    if (dob.value == "") {
        alert("Select Date Of Birth");
        return;
    }

    if (blood_group.value == "") {
        alert("Select Blood Group");
        return;
    }

    if (mobile.value == "") {
        alert("Enter Mobile");
        return;
    }

    if (email.value == "") {
        alert("Enter Email");
        return;
    }

    employeeData = {

        employee_code: employee_code.value,
        user_name: user_name.value,
        department: department.value,
        designation: designation.value,
        gender: gender.value,
        age: age.value,
        dob: dob.value,
        blood_group: blood_group.value,
        mobile: mobile.value,
        email: email.value,
        address: address.value

    };

    captureCount = 0;

    startAutoCapture();

};

// ======================================================
// AUTO CAPTURE
// ======================================================

async function startAutoCapture() {

    document.getElementById("registerBtn").disabled = true;

    document.getElementById("status").innerHTML =
        "Capturing Iris Images...";

    document.getElementById("counter").innerHTML =
        "0 / " + totalImages;

    document.getElementById("progressBar").style.width = "0%";

    captureTimer = setInterval(async () => {

        if (captureCount >= totalImages) {

            clearInterval(captureTimer);

            document.getElementById("status").innerHTML =
                "Saving Employee...";

            await saveEmployee();

            return;

        }

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        canvas
            .getContext("2d")
            .drawImage(video, 0, 0);

        canvas.toBlob(async (blob) => {

            const form = new FormData();

            form.append(
                "employee_code",
                employeeData.employee_code
            );

            form.append(
                "file",
                blob,
                (captureCount + 1) + ".jpg"
            );

            try {

                const response = await fetch(
                    "/register-frame",
                    {
                        method: "POST",
                        body: form
                    }
                );

                const result = await response.json();

                console.log(result);

                if (result.saved) {

                    captureCount++;

                    const percent = Math.floor(
                        (captureCount / totalImages) * 100
                    );

                    document.getElementById("counter").innerHTML =
                        captureCount + " / " + totalImages;

                    document.getElementById("progressBar").style.width =
                        percent + "%";

                    document.getElementById("progressBar").innerHTML =
                        percent + "%";

                    document.getElementById("status").innerHTML =
                        "Captured " + captureCount + " / " + totalImages;

                }
                else {

                    console.log(result.message);

                }

            }

            catch (err) {

                console.log(err);

            }

        }, "image/jpeg", 0.95);

    }, 500);

}
// ======================================================
// SAVE EMPLOYEE
// ======================================================

async function saveEmployee() {

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    canvas
        .getContext("2d")
        .drawImage(video, 0, 0);

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

        form.append(
            "file",
            blob,
            "employee.jpg"
        );

        try {

            document.getElementById("status").innerHTML =
                "Creating Customer...";

            const response = await fetch(
                "/enroll",
                {
                    method: "POST",
                    body: form
                }
            );

            const result = await response.json();

            console.log(result);

            if (result.status) {

                sessionStorage.setItem(
                    "employee_code",
                    employeeData.employee_code
                );

                document.getElementById("status").innerHTML =
                    "Registration Successful";

                document.getElementById("counter").innerHTML =
                    totalImages + " / " + totalImages;

                document.getElementById("progressBar").style.width =
                    "100%";

                document.getElementById("progressBar").innerHTML =
                    "100%";

                alert("Customer Registered Successfully");

                setTimeout(() => {

                    window.location.href =
                        "/static/camera.html";

                }, 1000);

            }
            else {

                alert(result.message);

                document.getElementById("registerBtn").disabled = false;

            }

        }
        catch (err) {

            console.log(err);

            alert("API Error : " + err.message);

            document.getElementById("registerBtn").disabled = false;

        }

    }, "image/jpeg", 0.95);

}