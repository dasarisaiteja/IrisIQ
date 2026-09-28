document.addEventListener("DOMContentLoaded", () => {
    loadStudents();
    loadEnrolledUsers();

    document.getElementById("studentForm").addEventListener("submit", handleStudentSubmit);
    document.getElementById("searchInput").addEventListener("input", filterStudents);
});

let allStudents = [];

async function loadStudents() {
    const tableBody = document.getElementById("studentTableBody");
    try {
        const res = await fetch("/api/profile/students");
        const data = await res.json();
        allStudents = data.students || [];

        document.getElementById("studentCount").innerText = allStudents.length;
        renderStudentTable(allStudents);
    } catch (err) {
        tableBody.innerHTML = `<tr><td colspan="7" class="text-center py-4 text-danger"><i class="fa-solid fa-triangle-exclamation me-2"></i> Failed to load students: ${err.message}</td></tr>`;
    }
}

function renderStudentTable(students) {
    const tableBody = document.getElementById("studentTableBody");
    if (!students || students.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="7" class="text-center py-5 text-muted">No students registered yet. Click "Register New Student" to begin.</td></tr>`;
        return;
    }

    tableBody.innerHTML = students.map(s => {
        const photo = s.photo_path || "images/admin.png";
        const irisBadge = s.employee_code
            ? `<span class="badge bg-success-subtle text-success border border-success"><i class="fa-solid fa-circle-check me-1"></i> ${s.employee_code}</span>`
            : `<span class="badge bg-secondary-subtle text-secondary border"><i class="fa-solid fa-minus me-1"></i> Standalone</span>`;

        return `
            <tr>
                <td>
                    <div class="d-flex align-items-center gap-3">
                        <img src="${photo}" class="student-avatar" alt="${s.full_name}" onerror="this.src='images/admin.png'">
                        <div>
                            <strong class="d-block text-dark">${s.full_name}</strong>
                            <small class="text-muted">${s.gender}, ${s.age} yrs • ${s.location || 'Location N/A'}</small>
                        </div>
                    </div>
                </td>
                <td><code class="fw-bold text-primary">${s.student_id}</code></td>
                <td>${irisBadge}</td>
                <td>${s.course || '-'} <small class="text-muted d-block">${s.year || ''}</small></td>
                <td><span class="badge-stream">${(s.stream && s.stream.trim()) ? s.stream : 'Not Specified'}</span></td>
                <td>
                    <small class="d-block">${s.email || '-'}</small>
                    <small class="text-muted">${s.mobile || ''}</small>
                </td>
                <td class="text-end">
                    <a href="assessments.html?student_id=${s.student_id}" class="action-btn btn btn-sm btn-outline-primary" title="Take Assessments">
                        <i class="fa-solid fa-list-check"></i> Assess
                    </a>
                    <a href="student_profile.html?student_id=${s.student_id}" class="action-btn btn btn-sm btn-outline-secondary" title="View Profile">
                        <i class="fa-solid fa-user"></i> Profile
                    </a>
                    <a href="ai_profile.html?student_id=${s.student_id}" class="action-btn btn btn-sm btn-outline-info" title="AI Cognitive Profile">
                        <i class="fa-solid fa-brain"></i> AI Profile
                    </a>
                    <a href="student_report.html?student_id=${s.student_id}" class="action-btn btn btn-sm btn-primary" title="Generate V2 Report">
                        <i class="fa-solid fa-file-pdf"></i> Report V2
                    </a>
                </td>
            </tr>
        `;
    }).join("");
}

function filterStudents(e) {
    const query = e.target.value.toLowerCase().trim();
    if (!query) {
        renderStudentTable(allStudents);
        return;
    }
    const filtered = allStudents.filter(s =>
        s.full_name.toLowerCase().includes(query) ||
        s.student_id.toLowerCase().includes(query) ||
        (s.course && s.course.toLowerCase().includes(query)) ||
        (s.stream && s.stream.toLowerCase().includes(query)) ||
        (s.employee_code && s.employee_code.toLowerCase().includes(query))
    );
    renderStudentTable(filtered);
}

async function loadEnrolledUsers() {
    const select = document.getElementById("formEmployeeCode");
    try {
        const res = await fetch("/dashboard");
        const data = await res.json();
        const recent = data.recent_scans || [];
        const seen = new Set();

        recent.forEach(r => {
            if (r.user_name && !seen.has(r.user_name)) {
                seen.add(r.user_name);
                const opt = document.createElement("option");
                opt.value = r.user_name;
                opt.innerText = `${r.user_name} (Scan Ref: ${r.report_id})`;
                select.appendChild(opt);
            }
        });
    } catch (_) {}
}

async function handleStudentSubmit(e) {
    e.preventDefault();
    const payload = {
        full_name: document.getElementById("formFullName").value.trim(),
        age: parseInt(document.getElementById("formAge").value) || 18,
        gender: document.getElementById("formGender").value,
        email: document.getElementById("formEmail").value.trim(),
        mobile: document.getElementById("formMobile").value.trim(),
        school_college: document.getElementById("formSchool").value.trim(),
        course: document.getElementById("formCourse").value.trim(),
        year: document.getElementById("formYear").value.trim(),
        stream: document.getElementById("formStream").value,
        location: document.getElementById("formLocation").value.trim(),
        employee_code: document.getElementById("formEmployeeCode").value || null
    };

    try {
        const res = await fetch("/api/profile/students", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const result = await res.json();
        if (result.status) {
            bootstrap.Modal.getInstance(document.getElementById("newStudentModal")).hide();
            document.getElementById("studentForm").reset();
            await loadStudents();
        } else {
            alert("Error: " + result.message);
        }
    } catch (err) {
        alert("Failed to save student: " + err.message);
    }
}
