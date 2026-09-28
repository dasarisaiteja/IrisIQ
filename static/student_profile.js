let currentStudentId = null;

document.addEventListener("DOMContentLoaded", async () => {
    const urlParams = new URLSearchParams(window.location.search);
    currentStudentId = urlParams.get("student_id");

    await loadStudentSelector();
    if (currentStudentId) {
        await loadProfileData(currentStudentId);
    }

    document.getElementById("academicForm").addEventListener("submit", handleAddAcademic);
    document.getElementById("skillForm").addEventListener("submit", handleAddSkill);
    document.getElementById("interestForm").addEventListener("submit", handleAddInterest);
});

async function loadStudentSelector() {
    const select = document.getElementById("studentSelector");
    try {
        const res = await fetch("/api/profile/students");
        const data = await res.json();
        const students = data.students || [];

        if (students.length === 0) {
            select.innerHTML = '<option value="">No students available</option>';
            return;
        }

        select.innerHTML = students.map(s => `
            <option value="${s.student_id}" ${currentStudentId === s.student_id ? 'selected' : ''}>
                ${s.full_name} (${s.student_id})
            </option>
        `).join("");

        if (!currentStudentId && students.length > 0) {
            currentStudentId = students[0].student_id;
        }

        select.addEventListener("change", (e) => {
            currentStudentId = e.target.value;
            updateActionLinks(currentStudentId);
            loadProfileData(currentStudentId);
        });

        updateActionLinks(currentStudentId);
    } catch (err) {
        console.error("Failed to load students selector:", err);
    }
}

function updateActionLinks(sid) {
    document.getElementById("assessBtn").href = `assessments.html?student_id=${sid}`;
    document.getElementById("aiProfileBtn").href = `ai_profile.html?student_id=${sid}`;
    document.getElementById("reportBtn").href = `student_report.html?student_id=${sid}`;
}

async function loadProfileData(studentId) {
    try {
        const res = await fetch(`/api/profile/${studentId}`);
        const data = await res.json();
        if (!data.status || !data.profile) return;

        const p = data.profile;
        const s = p.student;

        // Header info
        document.getElementById("profName").innerText = s.full_name;
        document.getElementById("profSubtitle").innerText = `${s.course || 'Course Not Specified'} • ${s.school_college || 'Institution N/A'}`;
        document.getElementById("profIdBadge").innerText = `ID: ${s.student_id}`;
        document.getElementById("profStreamBadge").innerText = `Stream: ${(s.stream && s.stream.trim()) ? s.stream : 'Not Specified'}`;

        if (p.iris_biometrics) {
            document.getElementById("profIrisBadge").innerHTML = `<i class="fa-solid fa-circle-check text-success me-1"></i> Iris Enrolled (${p.iris_biometrics.employee_code})`;
            document.getElementById("profIrisBadge").className = "badge bg-success-subtle text-success border border-success px-3 py-1";
        } else {
            document.getElementById("profIrisBadge").innerHTML = `<i class="fa-solid fa-minus text-muted me-1"></i> Standalone (Assessments Only)`;
            document.getElementById("profIrisBadge").className = "badge bg-secondary-subtle text-secondary border px-3 py-1";
        }

        if (s.photo_path) {
            document.getElementById("profPhoto").src = s.photo_path;
        }

        // Academic average calculation
        const academics = p.academics || [];
        const avg = academics.length > 0
            ? Math.round(academics.reduce((acc, a) => acc + (a.percentage !== undefined && a.percentage !== null ? a.percentage : a.marks), 0) / academics.length)
            : null;
        document.getElementById("profAcadAvg").innerText = (avg !== null && avg !== undefined) ? `${avg}%` : "Pending";

        // Render Academics Table
        const acadTable = document.getElementById("academicsTableBody");
        if (academics.length === 0) {
            acadTable.innerHTML = '<tr><td colspan="4" class="text-center py-3 text-muted">No academic records recorded yet. Click "Add Subject" above.</td></tr>';
        } else {
            acadTable.innerHTML = academics.map(a => `
                <tr>
                    <td><strong>${a.subject}</strong></td>
                    <td><span class="badge bg-primary-subtle text-primary fw-bold">${a.percentage}%</span> <small class="text-muted">(${a.marks}/${a.max_marks})</small></td>
                    <td><span class="badge bg-light text-dark border">${(a.grade !== null && a.grade !== undefined && String(a.grade).trim() !== '') ? a.grade : 'Not Provided'}</span></td>
                    <td><small class="text-muted">${a.term || 'Current'}</small></td>
                </tr>
            `).join("");
        }

        // Render Skills
        const skillsContainer = document.getElementById("skillsContainer");
        const skills = p.skills || [];
        if (skills.length === 0) {
            skillsContainer.innerHTML = '<span class="text-muted small">No skills added yet. Click "Add Skill" above.</span>';
        } else {
            skillsContainer.innerHTML = skills.map(sk => `
                <div class="item-tag">
                    <i class="fa-solid fa-code text-primary me-1"></i>
                    <span>${sk.skill}</span>
                    <span class="badge bg-primary text-white ms-2" style="font-size: 10px;">${sk.proficiency}%</span>
                </div>
            `).join("");
        }

        // Render Interests
        const interestsContainer = document.getElementById("interestsContainer");
        const interests = p.interests || [];
        if (interests.length === 0) {
            interestsContainer.innerHTML = '<span class="text-muted small">No interests logged yet. Click "Add Interest" above.</span>';
        } else {
            interestsContainer.innerHTML = interests.map(i => `
                <div class="item-tag bg-danger-subtle border-danger-subtle text-danger-emphasis">
                    <i class="fa-solid fa-heart me-1"></i>
                    <span>${i.interest}</span>
                    <small class="text-muted ms-1">(${i.category})</small>
                </div>
            `).join("");
        }

        // Render Activities
        const actContainer = document.getElementById("activitiesContainer");
        const activities = p.activities || [];
        if (activities.length === 0) {
            actContainer.innerHTML = '<span class="text-muted small">No activities logged yet.</span>';
        } else {
            actContainer.innerHTML = activities.map(act => `
                <div class="p-2 mb-2 bg-light rounded-2 border">
                    <strong class="d-block">${act.title}</strong>
                    <small class="text-muted">${act.type || 'Co-curricular'} • ${act.year || 'Current'}</small>
                </div>
            `).join("");
        }
    } catch (err) {
        console.error("Error loading profile:", err);
    }
}

async function handleAddAcademic(e) {
    e.preventDefault();
    const payload = [{
        subject_name: document.getElementById("acadSubject").value.trim(),
        marks_obtained: parseFloat(document.getElementById("acadMarks").value),
        max_marks: parseFloat(document.getElementById("acadMaxMarks").value) || 100.0,
        grade: document.getElementById("acadGrade").value.trim() || "A",
        term: document.getElementById("acadTerm").value.trim() || "Current"
    }];

    try {
        const res = await fetch(`/api/profile/${currentStudentId}/academics`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.status) {
            bootstrap.Modal.getInstance(document.getElementById("addAcademicModal")).hide();
            document.getElementById("academicForm").reset();
            await loadProfileData(currentStudentId);
        }
    } catch (err) {
        alert("Failed to add academic record: " + err.message);
    }
}

async function handleAddSkill(e) {
    e.preventDefault();
    const payload = [{
        name: document.getElementById("skillName").value.trim(),
        type: document.getElementById("skillType").value,
        proficiency: parseFloat(document.getElementById("skillProficiency").value)
    }];

    try {
        const res = await fetch(`/api/profile/${currentStudentId}/skills`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.status) {
            bootstrap.Modal.getInstance(document.getElementById("addSkillModal")).hide();
            document.getElementById("skillForm").reset();
            await loadProfileData(currentStudentId);
        }
    } catch (err) {
        alert("Failed to add skill: " + err.message);
    }
}

async function handleAddInterest(e) {
    e.preventDefault();
    const payload = [{
        name: document.getElementById("interestName").value.trim(),
        category: document.getElementById("interestCategory").value,
        level: "High"
    }];

    try {
        const res = await fetch(`/api/profile/${currentStudentId}/interests`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.status) {
            bootstrap.Modal.getInstance(document.getElementById("addInterestModal")).hide();
            document.getElementById("interestForm").reset();
            await loadProfileData(currentStudentId);
        }
    } catch (err) {
        alert("Failed to add interest: " + err.message);
    }
}
