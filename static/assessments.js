let currentDomain = "personality";
let currentQuestions = [];
let selectedStudentId = null;

const domainDescriptions = {
    personality: "Measures Openness, Conscientiousness, Extraversion, Agreeableness, and Emotional Stability (Big Five model)",
    critical_abilities: "Evaluates Problem Solving, Creative Ability, Pressure Handling, Emotion Management, and Logical Reasoning",
    learning_style: "Determines Visual (V), Auditory (A), and Kinesthetic (K) multi-sensory learning style preferences",
    leadership_style: "Evaluates Task-Oriented vs. Relationship-Oriented leadership styles and team direction",
    thinking_action: "Analyzes balance between deep reflective analysis and rapid pragmatic execution",
    team_player: "Assesses inclination towards Team Management & Delegation vs Collaborative Team Contributor",
    behavioral: "Evaluates key behavioral habits including environmental adaptability and task perseverance",
    emotional_social: "Evaluates empathetic attunement, social self-confidence, and interpersonal poise"
};

document.addEventListener("DOMContentLoaded", async () => {
    const urlParams = new URLSearchParams(window.location.search);
    selectedStudentId = urlParams.get("student_id");

    await loadStudentSelector();
    setupTabs();
    await loadQuestions(currentDomain);
    if (selectedStudentId) {
        await loadAssessmentHistory(selectedStudentId);
    }

    document.getElementById("assessmentForm").addEventListener("submit", handleAssessmentSubmit);
});

async function loadStudentSelector() {
    const select = document.getElementById("studentSelect");
    try {
        const res = await fetch("/api/profile/students");
        const data = await res.json();
        const students = data.students || [];

        if (students.length === 0) {
            select.innerHTML = '<option value="">No students available. Please register first.</option>';
            return;
        }

        select.innerHTML = students.map(s => `
            <option value="${s.student_id}" ${selectedStudentId === s.student_id ? 'selected' : ''}>
                ${s.full_name} (${s.student_id})
            </option>
        `).join("");

        if (!selectedStudentId && students.length > 0) {
            selectedStudentId = students[0].student_id;
        }

        select.addEventListener("change", (e) => {
            selectedStudentId = e.target.value;
            document.getElementById("profileLink").href = `student_profile.html?student_id=${selectedStudentId}`;
            loadAssessmentHistory(selectedStudentId);
        });

        if (selectedStudentId) {
            document.getElementById("profileLink").href = `student_profile.html?student_id=${selectedStudentId}`;
        }
    } catch (err) {
        console.error("Failed to load students:", err);
    }
}

function setupTabs() {
    const tabBtns = document.querySelectorAll("#domainTabs .nav-link");
    tabBtns.forEach(btn => {
        btn.addEventListener("click", async (e) => {
            tabBtns.forEach(b => b.classList.remove("active"));
            e.currentTarget.classList.add("active");

            currentDomain = e.currentTarget.getAttribute("data-domain");
            document.getElementById("currentDomainTitle").innerText = e.currentTarget.innerText.trim();
            document.getElementById("currentDomainDescription").innerText = domainDescriptions[currentDomain] || "";
            document.getElementById("resultsCard").style.display = "none";

            await loadQuestions(currentDomain);
        });
    });
}

async function loadQuestions(domain) {
    const container = document.getElementById("questionsContainer");
    container.innerHTML = '<div class="text-center py-4"><i class="fa-solid fa-spinner fa-spin me-2"></i> Loading questions...</div>';

    try {
        const res = await fetch(`/api/profile/questions/all?domain=${domain}`);
        const data = await res.json();
        currentQuestions = data.questions || [];

        if (currentQuestions.length === 0) {
            container.innerHTML = '<div class="alert alert-warning">No questions configured for this domain.</div>';
            return;
        }

        container.innerHTML = currentQuestions.map((q, idx) => {
            const optionsHtml = q.options.map(opt => `
                <div class="col-md-6 col-12">
                    <input type="radio" name="q_${q.id}" id="opt_${q.id}_${opt.val}" value="${opt.val}" class="option-input d-none" required>
                    <label for="opt_${q.id}_${opt.val}" class="option-label">
                        <i class="fa-regular fa-circle me-2 text-muted"></i> ${opt.text}
                    </label>
                </div>
            `).join("");

            return `
                <div class="question-box">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="badge bg-primary-subtle text-primary border domain-badge">Question ${idx + 1} of ${currentQuestions.length}</span>
                        <small class="text-muted text-uppercase fw-bold" style="font-size: 11px;">Subcategory: ${q.subcategory || domain}</small>
                    </div>
                    <h6 class="fw-bold mb-3 text-dark">${q.question_text}</h6>
                    <div class="row g-2">
                        ${optionsHtml}
                    </div>
                </div>
            `;
        }).join("");

        // Attach change listeners to radio inputs
        container.querySelectorAll(".option-input").forEach(input => {
            input.addEventListener("change", checkCompletion);
        });

        checkCompletion();
    } catch (err) {
        container.innerHTML = `<div class="alert alert-danger">Error loading questions: ${err.message}</div>`;
    }
}

function checkCompletion() {
    const submitBtn = document.getElementById("submitBtn");
    const feedback = document.getElementById("resultFeedback");

    let answeredCount = 0;
    currentQuestions.forEach(q => {
        const checked = document.querySelector(`input[name="q_${q.id}"]:checked`);
        if (checked) answeredCount++;
    });

    const isComplete = answeredCount === currentQuestions.length && currentQuestions.length > 0;
    submitBtn.disabled = !isComplete || !selectedStudentId;

    if (!selectedStudentId) {
        feedback.innerHTML = '<span class="text-danger fw-bold"><i class="fa-solid fa-triangle-exclamation me-1"></i> Please select a student first.</span>';
    } else if (isComplete) {
        feedback.innerHTML = `<span class="text-success fw-bold"><i class="fa-solid fa-circle-check me-1"></i> All ${currentQuestions.length} questions answered. Ready to submit.</span>`;
    } else {
        feedback.innerText = `Answered ${answeredCount} of ${currentQuestions.length} questions.`;
    }
}

async function handleAssessmentSubmit(e) {
    e.preventDefault();
    if (!selectedStudentId) {
        alert("Please select a student before submitting.");
        return;
    }

    const responses = {};
    currentQuestions.forEach(q => {
        const checked = document.querySelector(`input[name="q_${q.id}"]:checked`);
        if (checked) {
            responses[q.id] = checked.value;
        }
    });

    const submitBtn = document.getElementById("submitBtn");
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-2"></i> Scoring...';

    try {
        const res = await fetch("/api/profile/assessment", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                student_id: selectedStudentId,
                domain: currentDomain,
                responses: responses
            })
        });

        const data = await res.json();
        if (data.status) {
            renderResults(data.result);
            await loadAssessmentHistory(selectedStudentId);
        } else {
            alert("Assessment submission failed: " + data.message);
        }
    } catch (err) {
        alert("Error submitting assessment: " + err.message);
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fa-solid fa-check-circle me-1"></i> Submit Assessment & Compute Scores';
    }
}

function renderResults(result) {
    const resultsCard = document.getElementById("resultsCard");
    const container = document.getElementById("resultsContent");
    resultsCard.style.display = "block";

    const scores = result.scores || {};
    const details = result.details || {};

    let cardsHtml = "";
    for (const [key, val] of Object.entries(scores)) {
        const keyFormatted = key.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
        const info = details[key] || {};
        const scoreVal = typeof val === "number" ? val.toFixed(1) : val;

        cardsHtml += `
            <div class="col-md-4 col-sm-6">
                <div class="p-3 bg-light rounded-3 border">
                    <small class="text-muted text-uppercase fw-bold">${keyFormatted}</small>
                    <div class="d-flex align-items-baseline gap-2 mt-1">
                        <h3 class="fw-bold text-primary m-0">${scoreVal}${typeof val === 'number' ? '%' : ''}</h3>
                        ${info.level ? `<span class="badge bg-primary-subtle text-primary">${info.level}</span>` : ''}
                    </div>
                    <div class="progress mt-2" style="height: 6px;">
                        <div class="progress-bar bg-primary" style="width: ${typeof val === 'number' ? val : 100}%"></div>
                    </div>
                    <div class="d-flex justify-content-between mt-2">
                        <small class="text-muted" style="font-size: 11px;">Source: ${result.source || 'assessment-derived'}</small>
                        <small class="text-secondary fw-semibold" style="font-size: 10px;">Heuristic indicator (0–100 scale), derived from structured assessment responses.</small>
                    </div>
                    <div class="mt-1 text-end">
                        <small class="text-muted" style="font-size: 10px;">Confidence: Not statistically calibrated</small>
                    </div>
                </div>
            </div>
        `;
    }

    if (details.dominant_style || details.primary_learning_preference || details.leadership_orientation) {
        const prefLabel = details.primary_learning_preference ? 'Primary Learning Preference' : (details.leadership_orientation ? 'Leadership Orientation' : 'Preferred Orientation');
        const prefVal = details.primary_learning_preference || details.leadership_orientation || details.dominant_style;
        cardsHtml += `
            <div class="col-12">
                <div class="p-3 bg-info-subtle text-info-emphasis rounded-3 border border-info">
                    <strong><i class="fa-solid fa-lightbulb me-1"></i> ${prefLabel}:</strong> ${prefVal}
                    ${details.study_recommendations ? `<p class="mb-0 mt-1 small">${details.study_recommendations}</p>` : ''}
                    ${details.characteristics ? `<p class="mb-0 mt-1 small">Characteristics: ${details.characteristics}</p>` : ''}
                    ${details.scientific_note ? `<p class="mb-0 mt-1 small text-muted fst-italic">${details.scientific_note}</p>` : ''}
                    ${details.scientific_disclaimer ? `<p class="mb-0 mt-1 small text-muted fst-italic">${details.scientific_disclaimer}</p>` : ''}
                </div>
            </div>
        `;
    }

    container.innerHTML = cardsHtml;
    resultsCard.scrollIntoView({ behavior: "smooth" });
}

async function loadAssessmentHistory(studentId) {
    const container = document.getElementById("historyContainer");
    try {
        const res = await fetch(`/api/profile/${studentId}/assessments`);
        const data = await res.json();
        const history = data.history || {};
        const keys = Object.keys(history);

        if (keys.length === 0) {
            container.innerHTML = '<span class="text-muted">No assessments completed yet for this student. Complete the domains above.</span>';
            return;
        }

        container.innerHTML = `
            <div class="d-flex flex-wrap gap-2">
                ${keys.map(k => `
                    <span class="badge bg-success-subtle text-success border border-success px-3 py-2">
                        <i class="fa-solid fa-circle-check me-1"></i>
                        ${k.replace(/_/g, ' ').toUpperCase()}: Completed on ${history[k].completed_on}
                    </span>
                `).join("")}
            </div>
        `;
    } catch (err) {
        container.innerHTML = `<span class="text-danger">Failed to load history: ${err.message}</span>`;
    }
}
