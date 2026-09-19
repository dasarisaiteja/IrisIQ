// ======================================================
// IRIS AI DASHBOARD
// ======================================================

// IMPORTANT:
// Do NOT use http://45.195.229.136:8000 here.
// Website is running on HTTPS.
//
// Relative URL automatically uses:
// https://iris.syneitsystems.com/dashboard
//
// This also avoids Mixed Content errors.

const API = "/dashboard";

let verificationChart = null;
let scanChart = null;
let reportChart = null;


// ======================================================
// PAGE LOAD
// ======================================================

window.addEventListener("DOMContentLoaded", () => {

    loadDate();

    initializeCharts();

    loadDashboard();

    setupSidebar();

    setupSearch();

});


// ======================================================
// LOAD DASHBOARD
// ======================================================

async function loadDashboard() {

    try {

        console.log("Loading Dashboard...");

        const response = await fetch(API, {
            method: "GET",
            headers: {
                "Accept": "application/json"
            },
            cache: "no-store"
        });

        if (!response.ok) {

            throw new Error(
                "Dashboard API HTTP " + response.status
            );

        }

        const data = await response.json();

        console.log("Dashboard API Response:", data);


        // ==================================================
        // SUMMARY
        // ==================================================

        const totalUsers =
            Number(
                data.total_users ??
                data.total_employees ??
                0
            );

        const totalScans =
            Number(
                data.total_scans ??
                0
            );

        const accuracy =
            Number(
                data.accuracy ??
                0
            );

        const matched =
            Number(
                data.matched ??
                0
            );

        const notMatched =
            Number(
                data.not_matched ??
                data.notMatched ??
                (totalScans - matched)
            );


        // ==================================================
        // TOP CARDS
        // ==================================================

        animate(
            "totalUsers",
            totalUsers
        );

        animate(
            "totalScans",
            totalScans
        );

        animate(
            "verifiedUsers",
            accuracy,
            "%"
        );

        animate(
            "notMatched",
            notMatched
        );


        // ==================================================
        // RECENT SCANS
        // ==================================================

        loadRecentScans(
            Array.isArray(data.recent_scans)
                ? data.recent_scans
                : []
        );


        // ==================================================
        // ACTIVITY
        // ==================================================

        loadActivity(
            Array.isArray(data.activity)
                ? data.activity
                : []
        );


        // ==================================================
        // DOUGHNUT CHART
        // ==================================================

        updateVerificationChart(
            matched,
            notMatched
        );


        // ==================================================
        // MONTHLY REPORT CHART
        // ==================================================

        updateMonthlyChart(
            Array.isArray(data.monthly_reports)
                ? data.monthly_reports
                : []
        );


        console.log(
            "Dashboard loaded successfully."
        );

    }

    catch (error) {

        console.error(
            "Dashboard API Error:",
            error
        );

        showDashboardError();

    }

}


// ======================================================
// DASHBOARD ERROR
// ======================================================

function showDashboardError() {

    const scanTable =
        document.getElementById("scanTable");

    if (scanTable) {

        scanTable.innerHTML = `
            <tr>
                <td colspan="5" class="text-center text-danger">
                    Unable to load dashboard data
                </td>
            </tr>
        `;

    }


    const activityList =
        document.getElementById("activityList");

    if (activityList) {

        activityList.innerHTML = `
            <p class="text-danger">
                Unable to load recent activity
            </p>
        `;

    }

}


// ======================================================
// NUMBER ANIMATION
// ======================================================

function animate(
    id,
    target,
    suffix = ""
) {

    const element =
        document.getElementById(id);

    if (!element) {
        return;
    }


    target = Number(target);

    if (!Number.isFinite(target)) {
        target = 0;
    }


    let current = 0;

    const duration = 700;

    const steps = 40;

    const increment =
        target / steps;

    const interval =
        duration / steps;


    if (target === 0) {

        element.innerHTML =
            suffix === "%"
                ? "0.0%"
                : "0";

        return;

    }


    const timer =
        setInterval(() => {

            current += increment;


            if (current >= target) {

                current = target;

                clearInterval(timer);

            }


            if (suffix === "%") {

                element.innerHTML =
                    current.toFixed(1) + suffix;

            }

            else {

                element.innerHTML =
                    Math.floor(current);

            }

        }, interval);

}


// ======================================================
// DATE
// ======================================================

function loadDate() {

    const today =
        new Date();

    const element =
        document.getElementById(
            "todayDate"
        );

    if (!element) {
        return;
    }


    element.innerHTML =
        today.toLocaleDateString(
            "en-GB",
            {
                day: "2-digit",
                month: "short",
                year: "numeric"
            }
        );

}


// ======================================================
// RECENT SCANS
// ======================================================

function loadRecentScans(scans) {

    const tbody =
        document.getElementById(
            "scanTable"
        );

    if (!tbody) {
        return;
    }


    tbody.innerHTML = "";


    if (!Array.isArray(scans) ||
        scans.length === 0) {

        tbody.innerHTML = `
            <tr>
                <td
                    colspan="5"
                    class="text-center text-muted"
                >
                    No Scan History Found
                </td>
            </tr>
        `;

        return;

    }


    scans.forEach(scan => {

        const reportId =
            scan.report_id ??
            scan.reportId ??
            "-";


        const userName =
            scan.user_name ??
            scan.userName ??
            "Unknown";


        const scanDate =
            scan.scan_date ??
            scan.scanDate ??
            "-";


        const similarity =
            Number(
                scan.similarity ?? 0
            );


        const status =
            scan.status ??
            "Unknown";


        const isMatched =
            String(status)
                .trim()
                .toLowerCase() ===
            "matched";


        const badgeClass =
            isMatched
                ? "badge-success"
                : "badge-danger";


        const row =
            document.createElement("tr");


        row.innerHTML = `

            <td>
                ${escapeHtml(reportId)}
            </td>

            <td>
                ${escapeHtml(userName)}
            </td>

            <td>
                ${escapeHtml(scanDate)}
            </td>

            <td>
                ${Number.isFinite(similarity)
                    ? similarity.toFixed(2)
                    : "0.00"
                }%
            </td>

            <td>

                <span class="${badgeClass}">
                    ${escapeHtml(status)}
                </span>

            </td>

        `;


        tbody.appendChild(row);

    });

}


// ======================================================
// RECENT ACTIVITY
// ======================================================

function loadActivity(activity) {

    const list =
        document.getElementById(
            "activityList"
        );

    if (!list) {
        return;
    }


    list.innerHTML = "";


    if (!Array.isArray(activity) ||
        activity.length === 0) {

        list.innerHTML = `
            <p class="text-muted">
                No Recent Activity
            </p>
        `;

        return;

    }


    activity.forEach(item => {

        const title =
            item.title ??
            "Activity";


        const description =
            item.description ??
            "";


        const createdOn =
            item.created_on ??
            item.createdOn ??
            "";


        const div =
            document.createElement("div");


        div.className =
            "activity-item";


        div.innerHTML = `

            <div class="activity-icon">

                <i class="fa-solid fa-clock"></i>

            </div>

            <div>

                <strong>
                    ${escapeHtml(title)}
                </strong>

                <br>

                <small>
                    ${escapeHtml(description)}
                </small>

                <br>

                <small>
                    ${escapeHtml(createdOn)}
                </small>

            </div>

        `;


        list.appendChild(div);

    });

}


// ======================================================
// INITIALIZE CHARTS
// ======================================================

function initializeCharts() {

    // --------------------------------------------------
    // DOUGHNUT
    // --------------------------------------------------

    const verificationCanvas =
        document.getElementById(
            "verificationChart"
        );


    if (verificationCanvas &&
        typeof Chart !== "undefined") {

        verificationChart =
            new Chart(
                verificationCanvas,
                {
                    type: "doughnut",

                    data: {

                        labels: [
                            "Matched",
                            "Not Matched"
                        ],

                        datasets: [{

                            data: [
                                0,
                                0
                            ],

                            backgroundColor: [
                                "#10b981",
                                "#ef4444"
                            ],

                            borderWidth: 0

                        }]

                    },

                    options: {

                        responsive: true,

                        maintainAspectRatio: false,

                        plugins: {

                            legend: {

                                position: "bottom"

                            }

                        }

                    }

                }
            );

    }


    // --------------------------------------------------
    // DAILY SCANS
    // --------------------------------------------------

    const scanCanvas =
        document.getElementById(
            "scanChart"
        );


    if (scanCanvas &&
        typeof Chart !== "undefined") {

        scanChart =
            new Chart(
                scanCanvas,
                {
                    type: "line",

                    data: {

                        labels: [
                            "Mon",
                            "Tue",
                            "Wed",
                            "Thu",
                            "Fri",
                            "Sat",
                            "Sun"
                        ],

                        datasets: [{

                            label:
                                "Daily Scans",

                            data: [
                                0,
                                0,
                                0,
                                0,
                                0,
                                0,
                                0
                            ],

                            borderColor:
                                "#2563eb",

                            backgroundColor:
                                "rgba(37,99,235,.15)",

                            fill: true,

                            tension: 0.4

                        }]

                    },

                    options: {

                        responsive: true,

                        maintainAspectRatio: false,

                        plugins: {

                            legend: {

                                display: false

                            }

                        }

                    }

                }
            );

    }


    // --------------------------------------------------
    // MONTHLY REPORTS
    // --------------------------------------------------

    const reportCanvas =
        document.getElementById(
            "reportChart"
        );


    if (reportCanvas &&
        typeof Chart !== "undefined") {

        reportChart =
            new Chart(
                reportCanvas,
                {
                    type: "bar",

                    data: {

                        labels: [
                            "Jan",
                            "Feb",
                            "Mar",
                            "Apr",
                            "May",
                            "Jun",
                            "Jul",
                            "Aug",
                            "Sep",
                            "Oct",
                            "Nov",
                            "Dec"
                        ],

                        datasets: [{

                            label:
                                "Reports",

                            data: [
                                0,
                                0,
                                0,
                                0,
                                0,
                                0,
                                0,
                                0,
                                0,
                                0,
                                0,
                                0
                            ],

                            borderRadius: 8,

                            backgroundColor:
                                "#2563eb"

                        }]

                    },

                    options: {

                        responsive: true,

                        maintainAspectRatio: false,

                        plugins: {

                            legend: {

                                display: false

                            }

                        }

                    }

                }
            );

    }

}


// ======================================================
// UPDATE DOUGHNUT
// ======================================================

function updateVerificationChart(
    matched,
    failed
) {

    if (!verificationChart) {
        return;
    }


    matched =
        Number(matched) || 0;


    failed =
        Number(failed) || 0;


    verificationChart.data.datasets[0].data = [
        matched,
        failed
    ];


    verificationChart.update();

}


// ======================================================
// UPDATE MONTHLY REPORTS
// ======================================================

function updateMonthlyChart(
    monthlyData
) {

    if (!reportChart) {
        return;
    }


    const months = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec"
    ];


    let values = [];


    if (Array.isArray(monthlyData)) {

        values =
            monthlyData
                .slice(0, 12)
                .map(value =>
                    Number(value) || 0
                );

    }


    while (values.length < 12) {

        values.push(0);

    }


    reportChart.data.labels =
        months;


    reportChart.data.datasets[0].data =
        values;


    reportChart.update();

}


// ======================================================
// SIDEBAR TOGGLE
// ======================================================

function setupSidebar() {

    const toggleBtn =
        document.getElementById(
            "toggleSidebar"
        );


    const sidebar =
        document.querySelector(
            ".sidebar"
        );


    if (!toggleBtn ||
        !sidebar) {

        return;

    }


    toggleBtn.addEventListener(
        "click",
        () => {

            sidebar.classList.toggle(
                "active"
            );

        }
    );

}


// ======================================================
// SEARCH
// ======================================================

function setupSearch() {

    const search =
        document.getElementById(
            "searchEmployee"
        );


    if (!search) {
        return;
    }


    search.addEventListener(
        "keyup",
        function () {

            const value =
                this.value
                    .toLowerCase()
                    .trim();


            document
                .querySelectorAll(
                    "#scanTable tr"
                )
                .forEach(row => {

                    const text =
                        row.innerText
                            .toLowerCase();


                    row.style.display =
                        text.includes(value)
                            ? ""
                            : "none";

                });

        }
    );

}


// ======================================================
// HTML ESCAPE
// ======================================================

function escapeHtml(value) {

    return String(value ?? "")
        .replace(
            /&/g,
            "&amp;"
        )
        .replace(
            /</g,
            "&lt;"
        )
        .replace(
            />/g,
            "&gt;"
        )
        .replace(
            /"/g,
            "&quot;"
        )
        .replace(
            /'/g,
            "&#039;"
        );

}


// ======================================================
// AUTO REFRESH
// ======================================================

// Refresh dashboard every 30 seconds.

setInterval(
    () => {

        loadDashboard();

    },
    30000
);