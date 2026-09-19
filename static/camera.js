console.log("========== IRIS CAMERA START ==========");

const employeeCode =
    sessionStorage.getItem("employee_code");

console.log(
    "Employee Code:",
    employeeCode
);

if (!employeeCode) {

    alert(
        "Customer not registered."
    );

    window.location.href =
        "/static/register.html";

    throw new Error(
        "Employee code missing"
    );
}


/* =====================================================
   DOM ELEMENTS
===================================================== */

const video =
    document.getElementById("video");

const canvas =
    document.getElementById("canvas");

const btn =
    document.getElementById("captureBtn");

const loading =
    document.getElementById("loading");

const scanStatus =
    document.getElementById("scanStatus");

const confidence =
    document.getElementById("confidence");

const eyeColor =
    document.getElementById("eyeColor");

const pupilRadius =
    document.getElementById("pupilRadius");

const irisRadius =
    document.getElementById("irisRadius");

const preview =
    document.getElementById("preview");


/* =====================================================
   VALIDATE DOM
===================================================== */

if (!video) {

    alert(
        "Camera video element not found."
    );

    throw new Error(
        "video element missing"
    );
}

if (!canvas) {

    alert(
        "Camera canvas element not found."
    );

    throw new Error(
        "canvas element missing"
    );
}

if (!btn) {

    alert(
        "Scan button not found."
    );

    throw new Error(
        "capture button missing"
    );
}


/* =====================================================
   INITIAL STATE
===================================================== */

btn.disabled = true;

if (loading) {
    loading.style.display = "none";
}

if (scanStatus) {
    scanStatus.innerHTML =
        "Starting Camera...";
}


let cameraStream = null;

let isScanning = false;


/* =====================================================
   LIST CAMERAS
===================================================== */

async function listCameras() {

    try {

        if (
            !navigator.mediaDevices ||
            !navigator.mediaDevices.enumerateDevices
        ) {

            console.warn(
                "enumerateDevices not supported"
            );

            return;
        }

        const devices =
            await navigator.mediaDevices
                .enumerateDevices();

        console.log(
            "========== CAMERAS =========="
        );

        devices
            .filter(
                device =>
                    device.kind === "videoinput"
            )
            .forEach(
                (device, index) => {

                    console.log(
                        "Camera",
                        index + 1,
                        ":",
                        device.label ||
                            "Unnamed Camera",
                        device.deviceId
                    );

                }
            );

    }
    catch (err) {

        console.error(
            "Camera List Error:",
            err
        );

    }
}


/* =====================================================
   WAIT FOR VIDEO METADATA
===================================================== */

async function waitForVideoMetadata() {

    const timeout = 10000;

    const start =
        Date.now();

    while (
        Date.now() - start <
        timeout
    ) {

        if (
            video.readyState >=
                HTMLMediaElement.HAVE_METADATA &&
            video.videoWidth > 0 &&
            video.videoHeight > 0
        ) {

            return true;
        }

        await new Promise(
            resolve =>
                setTimeout(
                    resolve,
                    100
                )
        );
    }

    return false;
}


/* =====================================================
   WAIT FOR REAL VIDEO FRAME
===================================================== */

async function waitForVideoFrame() {

    const timeout = 10000;

    const start =
        Date.now();

    while (
        Date.now() - start <
        timeout
    ) {

        if (
            video.readyState >=
                HTMLMediaElement.HAVE_CURRENT_DATA &&
            video.videoWidth > 0 &&
            video.videoHeight > 0
        ) {

            /*
             * Prefer browser's real video-frame callback.
             */

            if (
                "requestVideoFrameCallback"
                in video
            ) {

                try {

                    await new Promise(
                        resolve => {

                            video.requestVideoFrameCallback(
                                () => resolve()
                            );

                        }
                    );

                }
                catch (err) {

                    console.warn(
                        "requestVideoFrameCallback failed:",
                        err
                    );

                }

            }
            else {

                await new Promise(
                    resolve =>
                        requestAnimationFrame(
                            resolve
                        )
                );

                await new Promise(
                    resolve =>
                        requestAnimationFrame(
                            resolve
                        )
                );

                await new Promise(
                    resolve =>
                        requestAnimationFrame(
                            resolve
                        )
                );
            }

            return true;
        }

        await new Promise(
            resolve =>
                setTimeout(
                    resolve,
                    100
                )
        );
    }

    return false;
}


/* =====================================================
   START CAMERA
===================================================== */

async function startCamera() {

    try {

        console.log(
            "========== STARTING CAMERA =========="
        );

        if (
            !navigator.mediaDevices ||
            !navigator.mediaDevices.getUserMedia
        ) {

            throw new Error(
                "Camera API is not supported by this browser."
            );
        }


        /*
         * Stop old stream.
         */

        if (cameraStream) {

            cameraStream
                .getTracks()
                .forEach(
                    track =>
                        track.stop()
                );

            cameraStream = null;
        }


        /*
         * Request camera.
         */

        cameraStream =
            await navigator.mediaDevices
                .getUserMedia({

                    video: {

                        width: {
                            ideal: 1280
                        },

                        height: {
                            ideal: 720
                        },

                        facingMode: {
                            ideal: "user"
                        }

                    },

                    audio: false

                });


        console.log(
            "Camera permission granted"
        );


        /*
         * Attach stream.
         */

        video.srcObject =
            cameraStream;


        /*
         * Required video settings.
         */

        video.muted = true;

        video.autoplay = true;

        video.playsInline = true;

        video.setAttribute(
            "autoplay",
            ""
        );

        video.setAttribute(
            "muted",
            ""
        );

        video.setAttribute(
            "playsinline",
            ""
        );


        /*
         * Get camera track.
         */

        const track =
            cameraStream
                .getVideoTracks()[0];

        if (!track) {

            throw new Error(
                "Camera video track not found."
            );
        }


        console.log(
            "Camera Track:",
            {
                label:
                    track.label,

                enabled:
                    track.enabled,

                readyState:
                    track.readyState,

                settings:
                    track.getSettings()
            }
        );


        /*
         * Wait for metadata.
         */

        const metadataReady =
            await waitForVideoMetadata();

        if (!metadataReady) {

            throw new Error(
                "Camera metadata was not received."
            );
        }


        /*
         * Start playback.
         */

        try {

            await video.play();

        }
        catch (playError) {

            console.warn(
                "Initial video.play() warning:",
                playError
            );

            await new Promise(
                resolve =>
                    setTimeout(
                        resolve,
                        300
                    )
            );

            await video.play();
        }


        /*
         * Wait for real frame.
         */

        const ready =
            await waitForVideoFrame();

        if (!ready) {

            throw new Error(
                "Camera started but no video frame was received."
            );
        }


        console.log(
            "========== CAMERA READY =========="
        );

        console.log(
            "Video Width:",
            video.videoWidth
        );

        console.log(
            "Video Height:",
            video.videoHeight
        );

        console.log(
            "Video ReadyState:",
            video.readyState
        );


        /*
         * Enable scan.
         */

        btn.disabled = false;

        if (scanStatus) {

            scanStatus.innerHTML =
                "Ready";
        }

    }
    catch (err) {

        console.error(
            "Camera Error:",
            err
        );

        btn.disabled = true;

        if (scanStatus) {

            scanStatus.innerHTML =
                "Camera Error";
        }

        alert(
            "Camera Error: " +
            (
                err.message ||
                err
            )
        );
    }
}


/* =====================================================
   CAPTURE FRAME
===================================================== */

async function captureFrame() {

    console.log(
        "========== CAPTURE FRAME START =========="
    );


    if (!cameraStream) {

        throw new Error(
            "Camera stream is not available."
        );
    }


    if (!cameraStream.active) {

        throw new Error(
            "Camera stream is not active."
        );
    }


    const track =
        cameraStream
            .getVideoTracks()[0];


    if (!track) {

        throw new Error(
            "Camera video track not found."
        );
    }


    if (
        track.readyState !==
        "live"
    ) {

        throw new Error(
            "Camera track is not live."
        );
    }


    console.log(
        "Camera Track:",
        {
            label:
                track.label,

            enabled:
                track.enabled,

            readyState:
                track.readyState,

            muted:
                track.muted,

            settings:
                track.getSettings()
        }
    );


    /*
     * Wait for a real camera frame.
     */

    const ready =
        await waitForVideoFrame();


    if (!ready) {

        throw new Error(
            "Camera frame is not ready."
        );
    }


    console.log(
        "Video State:",
        {
            readyState:
                video.readyState,

            videoWidth:
                video.videoWidth,

            videoHeight:
                video.videoHeight,

            paused:
                video.paused
        }
    );


    if (
        video.videoWidth <= 0 ||
        video.videoHeight <= 0
    ) {

        throw new Error(
            "Invalid camera frame size."
        );
    }


    /*
     * =================================================
     * DIRECT CAMERA FRAME CAPTURE
     * =================================================
     *
     * ImageCapture avoids the black-frame problem
     * that can happen with drawImage(video).
     */

    let capturedBitmap = null;


    if (
        typeof ImageCapture !==
        "undefined"
    ) {

        try {

            console.log(
                "Trying ImageCapture.grabFrame()..."
            );


            const imageCapture =
                new ImageCapture(
                    track
                );


            capturedBitmap =
                await imageCapture
                    .grabFrame();


            console.log(
                "ImageCapture SUCCESS:",
                capturedBitmap.width,
                "x",
                capturedBitmap.height
            );

        }
        catch (imageCaptureError) {

            console.warn(
                "ImageCapture failed:",
                imageCaptureError
            );

            capturedBitmap = null;
        }
    }


    /*
     * =================================================
     * CANVAS
     * =================================================
     */

    canvas.width =
        capturedBitmap
            ? capturedBitmap.width
            : video.videoWidth;


    canvas.height =
        capturedBitmap
            ? capturedBitmap.height
            : video.videoHeight;


    const ctx =
        canvas.getContext(
            "2d",
            {
                alpha: false,
                willReadFrequently: true
            }
        );


    if (!ctx) {

        throw new Error(
            "Unable to create canvas context."
        );
    }


    /*
     * Clear previous image.
     */

    ctx.clearRect(
        0,
        0,
        canvas.width,
        canvas.height
    );


    /*
     * =================================================
     * DRAW CAMERA FRAME
     * =================================================
     */

    if (capturedBitmap) {

        console.log(
            "Drawing ImageCapture frame..."
        );


        ctx.drawImage(
            capturedBitmap,
            0,
            0,
            canvas.width,
            canvas.height
        );

    }
    else {

        console.log(
            "ImageCapture unavailable."
        );

        console.log(
            "Using video frame fallback..."
        );


        /*
         * Wait for another real frame.
         */

        if (
            "requestVideoFrameCallback"
            in video
        ) {

            await new Promise(
                resolve => {

                    video.requestVideoFrameCallback(
                        () => resolve()
                    );

                }
            );

        }
        else {

            await new Promise(
                resolve =>
                    requestAnimationFrame(
                        resolve
                    )
            );

            await new Promise(
                resolve =>
                    requestAnimationFrame(
                        resolve
                    )
            );
        }


        /*
         * Draw actual video frame.
         */

        ctx.drawImage(
            video,
            0,
            0,
            canvas.width,
            canvas.height
        );
    }


    /*
     * =================================================
     * CHECK PIXELS
     * =================================================
     */

    const sampleWidth =
        Math.min(
            canvas.width,
            320
        );


    const sampleHeight =
        Math.min(
            canvas.height,
            240
        );


    const imageData =
        ctx.getImageData(
            0,
            0,
            sampleWidth,
            sampleHeight
        );


    let total = 0;

    let maxValue = 0;

    let minValue = 255;


    for (
        let i = 0;
        i < imageData.data.length;
        i += 4
    ) {

        const r =
            imageData.data[i];

        const g =
            imageData.data[i + 1];

        const b =
            imageData.data[i + 2];


        const value =
            (
                r +
                g +
                b
            ) / 3;


        total += value;


        if (
            value >
            maxValue
        ) {

            maxValue =
                value;
        }


        if (
            value <
            minValue
        ) {

            minValue =
                value;
        }
    }


    const pixelCount =
        imageData.data.length /
        4;


    const average =
        total /
        pixelCount;


    console.log(
        "========== CAPTURE CHECK =========="
    );


    console.log(
        "Canvas:",
        canvas.width,
        "x",
        canvas.height
    );


    console.log(
        "Average Brightness:",
        average.toFixed(2)
    );


    console.log(
        "Min:",
        minValue
    );


    console.log(
        "Max:",
        maxValue
    );


    /*
     * =================================================
     * BLACK FRAME PROTECTION
     * =================================================
     */

    if (
        average < 5 ||
        maxValue < 10
    ) {

        throw new Error(
            "Camera frame is black. Please wait for the live camera preview and try again."
        );
    }


    /*
     * =================================================
     * CONVERT TO JPEG
     * =================================================
     */

    const blob =
        await new Promise(
            resolve => {

                canvas.toBlob(
                    resolve,
                    "image/jpeg",
                    0.95
                );

            }
        );


    if (!blob) {

        throw new Error(
            "Image conversion failed."
        );
    }


    if (
        blob.size < 1000
    ) {

        throw new Error(
            "Captured image is too small."
        );
    }


    console.log(
        "Captured JPEG Size:",
        blob.size,
        "bytes"
    );


    /*
     * Close ImageBitmap.
     */

    if (
        capturedBitmap &&
        typeof capturedBitmap.close ===
            "function"
    ) {

        capturedBitmap.close();
    }


    console.log(
        "========== CAPTURE FRAME SUCCESS =========="
    );


    return blob;
}


/* =====================================================
   RESET UI
===================================================== */

function resetScanUI() {

    if (loading) {

        loading.style.display =
            "none";
    }


    if (scanStatus) {

        scanStatus.innerHTML =
            "Ready";
    }


    if (confidence) {

        confidence.innerHTML =
            "--";
    }


    if (eyeColor) {

        eyeColor.innerHTML =
            "--";
    }


    if (pupilRadius) {

        pupilRadius.innerHTML =
            "--";
    }


    if (irisRadius) {

        irisRadius.innerHTML =
            "--";
    }
}


/* =====================================================
   SCAN BUTTON
===================================================== */

btn.onclick =
    async () => {

        /*
         * Prevent double click.
         */

        if (isScanning) {

            console.log(
                "Scan already running."
            );

            return;
        }


        isScanning = true;

        btn.disabled = true;


        try {

            /*
             * Make sure camera is ready.
             */

            const ready =
                await waitForVideoFrame();


            if (!ready) {

                throw new Error(
                    "Camera frame is not ready."
                );
            }


            if (loading) {

                loading.style.display =
                    "block";
            }


            if (scanStatus) {

                scanStatus.innerHTML =
                    "Capturing...";
            }


            /*
             * Capture image.
             */

            const blob =
                await captureFrame();


            /*
             * Preview captured image.
             */

            if (preview) {

                if (
                    preview.dataset.objectUrl
                ) {

                    URL.revokeObjectURL(
                        preview.dataset.objectUrl
                    );
                }


                const objectUrl =
                    URL.createObjectURL(
                        blob
                    );


                preview.dataset.objectUrl =
                    objectUrl;


                preview.src =
                    objectUrl;


                preview.style.display =
                    "block";
            }


            if (scanStatus) {

                scanStatus.innerHTML =
                    "Scanning...";
            }


            /*
             * =================================================
             * DETECT
             * =================================================
             */

            const form =
                new FormData();


            form.append(
                "file",
                blob,
                "camera.jpg"
            );


            console.log(
                "========== CALLING /detect =========="
            );


            const response =
                await fetch(
                    "/detect",
                    {
                        method: "POST",
                        body: form,
                        cache: "no-store"
                    }
                );


            const text =
                await response.text();


            console.log(
                "DETECT HTTP STATUS:",
                response.status
            );


            console.log(
                "DETECT RESPONSE:",
                text
            );


            let data;


            try {

                data =
                    JSON.parse(text);

            }
            catch (jsonError) {

                throw new Error(
                    "Invalid response from /detect."
                );
            }


            console.log(
                "DETECT DATA:",
                data
            );


            /*
             * Detection failed.
             */

            if (
                !response.ok ||
                !data ||
                !data.status
            ) {

                if (loading) {

                    loading.style.display =
                        "none";
                }


                if (scanStatus) {

                    scanStatus.innerHTML =
                        "Not Detected";
                }


                if (confidence) {

                    confidence.innerHTML =
                        "--";
                }


                if (eyeColor) {

                    eyeColor.innerHTML =
                        "--";
                }


                if (pupilRadius) {

                    pupilRadius.innerHTML =
                        "--";
                }


                if (irisRadius) {

                    irisRadius.innerHTML =
                        "--";
                }


                throw new Error(
                    data?.message ||
                    "YOLO detection failed. Please position your eye correctly and try again."
                );
            }


            /*
             * =================================================
             * DETECTION SUCCESS
             * =================================================
             */

            if (scanStatus) {

                scanStatus.innerHTML =
                    "Detected";
            }


            /*
             * Confidence.
             */

            if (
                data.detection &&
                data.detection.confidence !==
                    undefined
            ) {

                if (confidence) {

                    confidence.innerHTML =
                        (
                            Number(
                                data
                                    .detection
                                    .confidence
                            ) * 100
                        ).toFixed(2) +
                        "%";
                }
            }


            /*
             * Eye Color.
             */

            if (
                data.color_analysis &&
                data.color_analysis.eye_color
            ) {

                if (eyeColor) {

                    eyeColor.innerHTML =
                        data
                            .color_analysis
                            .eye_color;
                }

            }
            else {

                if (eyeColor) {

                    eyeColor.innerHTML =
                        "--";
                }
            }


            /*
             * Pupil radius.
             */

            if (
                data.features &&
                data.features.pupil_radius !==
                    undefined
            ) {

                if (pupilRadius) {

                    pupilRadius.innerHTML =
                        data
                            .features
                            .pupil_radius;
                }
            }


            /*
             * Iris radius.
             */

            if (
                data.features &&
                data.features.iris_radius !==
                    undefined
            ) {

                if (irisRadius) {

                    irisRadius.innerHTML =
                        data
                            .features
                            .iris_radius;
                }
            }


            /*
             * =================================================
             * CREATE REPORT ID
             * =================================================
             */

            const reportId =
                "IR-" +
                new Date()
                    .toISOString()
                    .replace(
                        /[-:.TZ]/g,
                        ""
                    ) +
                "-" +
                Math.random()
                    .toString(36)
                    .substring(
                        2,
                        9
                    )
                    .toUpperCase();


            console.log(
                "Report ID:",
                reportId
            );


            /*
             * =================================================
             * VERIFY
             * =================================================
             */

            const verifyForm =
                new FormData();


            verifyForm.append(
                "employee_code",
                employeeCode
            );


            verifyForm.append(
                "report_id",
                reportId
            );


            verifyForm.append(
                "file",
                blob,
                "camera.jpg"
            );


            console.log(
                "========== CALLING /verify =========="
            );


            const verifyResponse =
                await fetch(
                    "/verify",
                    {
                        method: "POST",
                        body: verifyForm,
                        cache: "no-store"
                    }
                );


            const verifyText =
                await verifyResponse.text();


            console.log(
                "VERIFY HTTP STATUS:",
                verifyResponse.status
            );


            console.log(
                "VERIFY RESPONSE:",
                verifyText
            );


            let verify;


            try {

                verify =
                    JSON.parse(
                        verifyText
                    );

            }
            catch (jsonError) {

                throw new Error(
                    "Invalid response from /verify."
                );
            }


            console.log(
                "VERIFY DATA:",
                verify
            );


            if (
                !verifyResponse.ok ||
                !verify ||
                !verify.status
            ) {

                throw new Error(
                    verify?.message ||
                    "Biometric verification failed."
                );
            }


            /*
             * =================================================
             * STORE REPORT DATA
             * =================================================
             */

            sessionStorage.setItem(
                "irisReport",
                JSON.stringify({

                    report_id:
                        reportId,

                    detect:
                        data,

                    verify:
                        verify

                })
            );


            sessionStorage.setItem(
                "iris_report_id",
                reportId
            );


            /*
             * =================================================
             * OPEN REPORT
             * =================================================
             */

            console.log(
                "Opening report:",
                reportId
            );


            window.location.href =
                "/static/report.html?report_id=" +
                encodeURIComponent(
                    reportId
                );

        }
        catch (err) {

            console.error(
                "========== SCAN ERROR ==========",
                err
            );


            if (loading) {

                loading.style.display =
                    "none";
            }


            if (scanStatus) {

                scanStatus.innerHTML =
                    "Scan Failed";
            }


            alert(
                err.message ||
                "Scan failed. Please try again."
            );

        }
        finally {

            isScanning = false;


            /*
             * Enable again if camera is active.
             */

            if (
                cameraStream &&
                cameraStream.active
            ) {

                btn.disabled = false;
            }
        }
    };


/* =====================================================
   CAMERA CLEANUP
===================================================== */

window.addEventListener(
    "beforeunload",
    () => {

        if (cameraStream) {

            cameraStream
                .getTracks()
                .forEach(
                    track =>
                        track.stop()
                );
        }


        if (
            preview &&
            preview.dataset.objectUrl
        ) {

            URL.revokeObjectURL(
                preview.dataset.objectUrl
            );
        }

    }
);


/* =====================================================
   START
===================================================== */

listCameras();

startCamera();


console.log(
    "========== IRIS CAMERA JS LOADED =========="
);