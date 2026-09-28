let currentStudentId = null;

document.addEventListener("DOMContentLoaded", async () => {
    const urlParams = new URLSearchParams(window.location.search);
    currentStudentId = urlParams.get("student_id");

    await loadStudentSelector();
    if (currentStudentId) {
        await loadRecommendations(currentStudentId);
    }
});

async function loadStudentSelector() {
    const select = document.getElementById("studentSelect");
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
            document.getElementById("reportBtn").href = `student_report.html?student_id=${currentStudentId}`;
            loadRecommendations(currentStudentId);
        });

        if (currentStudentId) {
            document.getElementById("reportBtn").href = `student_report.html?student_id=${currentStudentId}`;
        }
    } catch (err) {
        console.error("Failed to load students:", err);
    }
}

async function loadRecommendations(studentId) {
    try {
        const res = await fetch(`/api/profile/${studentId}/recommendations`);
        const data = await res.json();
        if (!data.status) return;

        renderStreams(data.streams);
        renderCareers(data.careers);
        renderActivities(data.activities_and_sports);
        renderGaps(data.development_gaps);
    } catch (err) {
        console.error("Error loading recommendations:", err);
    }
}

function renderStreams(streamsData) {
    const container = document.getElementById("streamsContainer");
    const conflictsContainer = document.getElementById("streamConflictsContainer");
    const rankings = streamsData?.stream_rankings || [];
    const primaryStream = streamsData?.primary_affinity_stream || streamsData?.recommended_stream;
    const secondaryStream = streamsData?.secondary_affinity_stream;
    const conflicts = streamsData?.conflicts_and_considerations || [];
    const prov = streamsData?.provenance || {};

    // 1. Render Conflicts and Considerations Alert Banner
    if (conflictsContainer) {
        if (conflicts.length > 0) {
            const hasTie = conflicts.some(c => c.includes("Close Suitability Balance") || c.includes("Marginal differentiation"));
            conflictsContainer.innerHTML = `
                <div class="alert ${hasTie ? 'alert-warning border-warning' : 'alert-info border-info'} mb-4">
                    <div class="d-flex align-items-center mb-2">
                        <i class="fa-solid ${hasTie ? 'fa-scale-balanced' : 'fa-circle-info'} fa-lg me-2 text-${hasTie ? 'warning' : 'info'}"></i>
                        <strong class="text-dark">${hasTie ? 'Balanced Affinity Notice (Close Suitability Balance)' : 'Counselor Considerations & Factor Analysis'}</strong>
                    </div>
                    <ul class="small mb-0 ps-3">
                        ${conflicts.map(c => `<li>${c}</li>`).join("")}
                    </ul>
                </div>
            `;
        } else {
            conflictsContainer.innerHTML = "";
        }
    }

    // 2. Check for Profile Data Pending / Blank Student Data
    const allZero = rankings.length > 0 && rankings.every(s => s.compatibility_score === 0.0);
    const missingStreamData = rankings.length > 0 && rankings.every(s => s.dimensional_scores && s.dimensional_scores.academic_match === null && s.dimensional_scores.assessment_match === null);
    if (!rankings.length || allZero || missingStreamData) {
        container.innerHTML = `
            <div class="col-12">
                <div class="p-4 bg-light rounded-3 border text-center my-3">
                    <i class="fa-solid fa-clipboard-question fa-3x text-secondary mb-3"></i>
                    <h5 class="fw-bold text-dark">Profile Data Pending</h5>
                    <p class="text-muted mb-0">Prerequisite subject marks or assessment records are not yet on file for this student profile.<br>Complete academic records and assessment evaluations to compute comparative stream affinity.</p>
                </div>
            </div>
        `;
        return;
    }

    // Determine if top two streams are in balanced close score (<= 3.0 pts)
    const isTied = (rankings.length >= 2 && Math.abs(rankings[0].compatibility_score - rankings[1].compatibility_score) <= 3.0 && rankings[0].compatibility_score > 0);

    container.innerHTML = rankings.map(s => {
        let badgeHtml = '';
        if (isTied && (s.stream === primaryStream || s.stream === secondaryStream)) {
            badgeHtml = '<span class="badge bg-primary-subtle text-primary border border-primary px-3 py-1"><i class="fa-solid fa-scale-balanced me-1"></i> Balanced Affinity</span>';
        } else if (s.stream === primaryStream) {
            badgeHtml = '<span class="badge bg-primary px-3 py-1"><i class="fa-solid fa-compass me-1"></i> Primary Affinity</span>';
        } else if (s.stream === secondaryStream) {
            badgeHtml = '<span class="badge bg-secondary px-3 py-1">Secondary Affinity</span>';
        } else {
            badgeHtml = `<span class="badge bg-light text-dark border px-3 py-1">${s.level}</span>`;
        }

        const isStreamPending = s.compatibility_score === 0 || (s.dimensional_scores && s.dimensional_scores.academic_match === null && s.dimensional_scores.assessment_match === null);
        const scoreClass = s.compatibility_score >= 80 ? 'score-high' : (s.compatibility_score >= 65 ? 'score-med' : 'score-fair');
        const dim = s.dimensional_scores || {};
        const missingPrereqs = s.missing_prerequisites || [];
        const matchedFactors = s.matched_factors || s.reasons || [];

        return `
            <div class="col-lg-4 col-md-6">
                <div class="rec-card h-100 ${s.stream === primaryStream ? 'border-primary' : ''}">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        ${badgeHtml}
                        <div class="text-end">
                            ${isStreamPending ? `
                                <span class="badge bg-secondary-subtle text-secondary border px-2 py-1">Profile Data Pending</span>
                                <small class="text-muted d-block mt-1" style="font-size: 10px;">Prerequisite records pending</small>
                            ` : `
                                <div class="score-circle ${scoreClass} ms-auto">
                                    ${s.compatibility_score}
                                </div>
                                <small class="text-muted d-block mt-1" style="font-size: 11px;">Affinity: ${s.compatibility_score} / 100</small>
                            `}
                        </div>
                    </div>
                    <h5 class="fw-bold text-dark">${s.stream}</h5>
                    <p class="text-muted small mb-2">${isStreamPending ? 'Profile Data Pending' : s.level + ' (Heuristic Fit Index)'}</p>

                    <!-- Missing Prerequisites Alert -->
                    ${missingPrereqs.length > 0 ? `
                        <div class="mb-3">
                            ${missingPrereqs.map(p => `<span class="badge bg-warning-subtle text-dark border border-warning me-1 mb-1"><i class="fa-solid fa-triangle-exclamation text-warning me-1"></i> Prerequisite Missing: ${p}</span>`).join("")}
                        </div>
                    ` : ''}

                    <!-- Dimensional Breakdown -->
                    <div class="p-2 bg-light rounded-2 border mb-3">
                        <small class="text-muted fw-bold d-block mb-1" style="font-size: 11px;">DIMENSIONAL FIT BREAKDOWN:</small>
                        <div class="d-flex flex-wrap gap-1" style="font-size: 11px;">
                            <span class="badge bg-white text-dark border">Acad: ${dim.academic_match != null ? dim.academic_match + '%' : 'Pending'}</span>
                            <span class="badge bg-white text-dark border">Assess: ${dim.assessment_match != null ? dim.assessment_match + '%' : 'Pending'}</span>
                            <span class="badge bg-white text-dark border">Interest: ${dim.interest_match != null ? dim.interest_match + '%' : 'Pending'}</span>
                            <span class="badge bg-white text-dark border">Skill: ${dim.skill_match != null ? dim.skill_match + '%' : 'Pending'}</span>
                            <span class="badge bg-white text-dark border">Activity: ${dim.activity_match != null ? dim.activity_match + '%' : 'Pending'}</span>
                        </div>
                    </div>

                    <h6 class="fw-bold text-primary small text-uppercase mb-2">Key Affinity Factors:</h6>
                    <ul class="small text-muted ps-3 mb-3">
                        ${matchedFactors.map(r => `<li>${r}</li>`).join("")}
                    </ul>

                    <h6 class="fw-bold text-success small text-uppercase mb-1">Strengths:</h6>
                    <div class="mb-3">
                        ${s.strengths.map(st => `<span class="tag-pill">${st}</span>`).join("")}
                    </div>

                    <h6 class="fw-bold text-danger small text-uppercase mb-1">Considerations & Challenges:</h6>
                    <p class="small text-muted mb-3">${(s.gaps_and_challenges || s.potential_challenges).join("; ")}</p>

                    <div class="p-2 bg-light rounded-2 border mb-3">
                        <small class="text-dark fw-bold d-block mb-1">Recommended Preparation:</small>
                        <small class="text-muted">${s.recommended_preparation}</small>
                    </div>

                    <!-- Provenance Footer -->
                    <div class="pt-2 border-top text-muted" style="font-size: 11px;">
                        <span><i class="fa-solid fa-shield-halved me-1"></i> Confidence: Not statistically calibrated</span><br>
                        <span>Source: rule-based heuristic matching</span>
                    </div>
                </div>
            </div>
        `;
    }).join("");
}

function renderCareers(careerData) {
    const topContainer = document.getElementById("topCareersContainer");
    const trendContainer = document.getElementById("trendingCareersContainer");
    const otherContainer = document.getElementById("otherCareersContainer");

    // Neutral preference with legacy fallback
    const higherMatch = careerData?.higher_match_careers || careerData?.top_recommendations || [];
    const trending = careerData?.trending_catalog_careers || careerData?.trending_careers || [];
    const additional = careerData?.additional_suitable_careers || careerData?.other_suitable_careers || [];
    const trendingDisclaimer = careerData?.trending_disclaimer || "Trending indicators reflect static catalog taxonomy and do not represent real-time macroeconomic labor-market statistics.";

    const careerCard = (c, badgeText, borderClass="") => {
        const dim = c.dimensional_scores || {};
        const missingSubs = c.missing_prerequisite_subjects || [];
        const skillGaps = c.skill_gaps || [];
        const conflicts = c.conflicts_and_considerations || [];
        const factors = c.matched_factors || c.why_it_matches || [];
        const isPending = c.compatibility_score === 0 || (dim.academic_match === null && dim.assessment_match === null && dim.skill_match === null);

        return `
            <div class="col-lg-4 col-md-6">
                <div class="rec-card h-100 ${borderClass}">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="badge bg-secondary-subtle text-dark border">${c.category}</span>
                        ${isPending ? `
                            <span class="badge bg-secondary-subtle text-secondary border fw-bold">Profile Data Pending</span>
                        ` : `
                            <span class="badge bg-primary fw-bold">Compatibility: ${c.compatibility_score} / 100</span>
                        `}
                    </div>
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <h5 class="fw-bold text-dark m-0">${c.career}</h5>
                        <small class="badge bg-light text-secondary border">${isPending ? 'Pending' : (c.match_level || 'Evaluated Match')}</small>
                    </div>
                    <small class="text-muted d-block mb-2">${c.work_style || 'Professional Practice'}</small>

                    ${isPending ? `
                        <div class="alert alert-secondary py-1 px-2 small mb-2">
                            <i class="fa-solid fa-info-circle me-1"></i> Prerequisite subject marks or assessment records are not yet on file.
                        </div>
                    ` : ''}

                    <!-- Dimensional Score Chips -->
                    <div class="p-2 bg-light rounded-2 border mb-2">
                        <small class="text-muted fw-bold d-block mb-1" style="font-size: 10px;">MATCH DIMENSIONS (0-100):</small>
                        <div class="d-flex flex-wrap gap-1" style="font-size: 10px;">
                            <span class="badge bg-white text-dark border">Acad: ${dim.academic_match != null ? dim.academic_match + '%' : 'Pending'}</span>
                            <span class="badge bg-white text-dark border">Skill: ${dim.skill_match != null ? dim.skill_match + '%' : 'Pending'}</span>
                            <span class="badge bg-white text-dark border">Assess: ${dim.assessment_match != null ? dim.assessment_match + '%' : 'Pending'}</span>
                            <span class="badge bg-white text-dark border">Interest: ${dim.interest_match != null ? dim.interest_match + '%' : 'Pending'}</span>
                            <span class="badge bg-white text-dark border">Stream: ${dim.stream_eligibility != null ? dim.stream_eligibility + '%' : 'Eligible'}</span>
                        </div>
                    </div>

                    <!-- Missing Prerequisite Alert -->
                    ${missingSubs.length > 0 ? `
                        <div class="mb-2">
                            <span class="badge bg-warning-subtle text-dark border border-warning" style="font-size: 11px;">
                                <i class="fa-solid fa-triangle-exclamation text-warning me-1"></i> Missing Subjects: ${missingSubs.join(", ")}
                            </span>
                        </div>
                    ` : ''}

                    <!-- Conflicts / Considerations -->
                    ${conflicts.length > 0 ? `
                        <div class="alert alert-warning py-1 px-2 mb-2" style="font-size: 11px;">
                            <i class="fa-solid fa-circle-exclamation me-1"></i> ${conflicts.join("; ")}
                        </div>
                    ` : ''}

                    <!-- Matched Factors -->
                    <div class="mb-2">
                        <small class="text-primary fw-bold d-block mb-1">Matched Factors:</small>
                        <ul class="small text-muted ps-3 mb-0">
                            ${factors.slice(0, 3).map(f => `<li>${f}</li>`).join("")}
                        </ul>
                    </div>

                    <!-- Skill Gaps -->
                    ${skillGaps.length > 0 ? `
                        <div class="mb-2">
                            <small class="text-danger fw-bold d-block mb-1">Skill Development Targets:</small>
                            <div class="d-flex flex-wrap gap-1">
                                ${skillGaps.map(g => `<span class="badge bg-danger-subtle text-danger border" style="font-size: 10px;">${g.skill} (Target: 80%)</span>`).join("")}
                            </div>
                        </div>
                    ` : ''}

                    <div class="mb-2">
                        <small class="text-dark fw-bold d-block">Required Education:</small>
                        <small class="text-muted">${c.required_education}</small>
                    </div>

                    <div class="mb-2">
                        <small class="text-dark fw-bold d-block mb-1">Recommended Skills:</small>
                        ${(c.recommended_skills || []).map(sk => `<span class="tag-pill">${sk}</span>`).join("")}
                    </div>

                    <div class="p-2 bg-light rounded-2 border mb-2">
                        <small class="text-primary fw-bold d-block">Next Steps:</small>
                        <small class="text-muted">${c.next_steps}</small>
                    </div>

                    <!-- Provenance Footer -->
                    <div class="pt-2 border-top text-muted d-flex justify-content-between" style="font-size: 10px;">
                        <span>Confidence: Not statistically calibrated</span>
                        <span>Source: rule-based</span>
                    </div>
                </div>
            </div>
        `;
    };

    // Check if student has no data
    const allZeroCareers = higherMatch.length > 0 && higherMatch.every(c => c.compatibility_score === 0.0);
    const missingCareersData = higherMatch.length > 0 && higherMatch.every(c => c.dimensional_scores && c.dimensional_scores.academic_match === null && c.dimensional_scores.assessment_match === null && c.dimensional_scores.skill_match === null);
    if (!higherMatch.length || allZeroCareers || missingCareersData) {
        const pendingHtml = `
            <div class="col-12">
                <div class="p-4 bg-light rounded-3 border text-center my-3">
                    <i class="fa-solid fa-folder-open fa-3x text-secondary mb-3"></i>
                    <h5 class="fw-bold text-dark">Profile Data Pending</h5>
                    <p class="text-muted mb-0">Academic grades, skills, or assessment records are not yet on file for this student profile.<br>Career matching indexes will compute automatically once profile modules are completed.</p>
                </div>
            </div>
        `;
        topContainer.innerHTML = pendingHtml;
        trendContainer.innerHTML = '<div class="col-12 text-muted">Awaiting student profile data.</div>';
        otherContainer.innerHTML = '<div class="col-12 text-muted">Awaiting student profile data.</div>';
        return;
    }

    topContainer.innerHTML = higherMatch.map(c => careerCard(c, "Higher Match", "border-primary")).join("");

    trendContainer.innerHTML = `
        <div class="col-12 mb-2">
            <div class="alert alert-secondary py-2 px-3 border mb-0" style="font-size: 12px;">
                <i class="fa-solid fa-circle-info me-1 text-primary"></i>
                <strong>Catalog Taxonomy Notice:</strong> ${trendingDisclaimer}
            </div>
        </div>
        ${trending.length ? trending.map(c => careerCard(c, "Catalog Emerging", "border-info")).join("") : '<div class="col-12 text-muted">No additional catalog-trending matches found.</div>'}
    `;

    otherContainer.innerHTML = additional.length ? additional.map(c => careerCard(c, "Additional Match", "")).join("") : '<div class="col-12 text-muted">No alternative careers evaluated.</div>';
}

function renderActivities(actData) {
    const cocurContainer = document.getElementById("cocurricularContainer");
    const sportsContainer = document.getElementById("sportsContainer");

    const cocur = actData?.co_curricular_recommendations || [];
    const sports = actData?.sports_recommendations || [];

    function formatTrait(t) {
        if (!t) return "";
        return t.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase());
    }

    function renderTraitChips(matched, missing) {
        const matchedList = matched || [];
        const missingList = missing || [];
        const matchedHtml = matchedList.length > 0
            ? matchedList.map(t => `<span class="badge bg-success-subtle text-success border border-success-subtle me-1 mb-1" style="font-size: 11px;"><i class="fa-solid fa-check me-1"></i>${formatTrait(t)}</span>`).join("")
            : '<span class="text-muted small">None identified</span>';
        const missingHtml = missingList.length > 0
            ? missingList.map(t => `<span class="badge bg-secondary-subtle text-secondary border me-1 mb-1" style="font-size: 11px;"><i class="fa-solid fa-minus me-1"></i>${formatTrait(t)}</span>`).join("")
            : '<span class="text-muted small">None identified</span>';

        return `
            <div class="p-2 bg-white rounded-2 border mb-2">
                <div class="mb-1">
                    <small class="text-dark fw-bold d-block" style="font-size: 11px;">Matched Evidence:</small>
                    <div>${matchedHtml}</div>
                </div>
                <div>
                    <small class="text-muted fw-bold d-block" style="font-size: 11px;">Missing Evidence:</small>
                    <div>${missingHtml}</div>
                </div>
            </div>
        `;
    }

    cocurContainer.innerHTML = cocur.map(a => `
        <div class="col-lg-4 col-md-6">
            <div class="rec-card">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h5 class="fw-bold text-dark m-0">${a.activity}</h5>
                    ${a.compatibility != null ? `<span class="badge bg-primary-subtle text-primary fw-bold">${a.compatibility}%</span>` : `<span class="badge bg-secondary-subtle text-secondary">Pending</span>`}
                </div>
                <small class="text-muted d-block mb-2">${a.reason}</small>
                ${renderTraitChips(a.matched_traits, a.missing_traits)}
                <div class="p-2 bg-light rounded-2 border mb-3">
                    <small class="text-dark fw-bold d-block">Benefits:</small>
                    <small class="text-muted">${a.benefits || '-'}</small>
                </div>
                <div>
                    <small class="text-muted fw-bold d-block mb-1">Skills Developed:</small>
                    ${(a.skills_developed || []).map(s => `<span class="tag-pill">${s}</span>`).join("")}
                </div>
            </div>
        </div>
    `).join("");

    sportsContainer.innerHTML = sports.map(s => `
        <div class="col-lg-4 col-md-6">
            <div class="rec-card">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h5 class="fw-bold text-dark m-0">${s.activity}</h5>
                    ${s.compatibility != null ? `<span class="badge bg-success-subtle text-success fw-bold">${s.compatibility}%</span>` : `<span class="badge bg-secondary-subtle text-secondary">Pending</span>`}
                </div>
                <small class="text-muted d-block mb-2">${s.reason}</small>
                ${renderTraitChips(s.matched_traits, s.missing_traits)}
                <div class="p-2 bg-light rounded-2 border mb-3">
                    <small class="text-dark fw-bold d-block">Benefits:</small>
                    <small class="text-muted">${s.benefits || '-'}</small>
                </div>
                <div>
                    <small class="text-muted fw-bold d-block mb-1">Skills Developed:</small>
                    ${(s.skills_developed || []).map(sk => `<span class="tag-pill">${sk}</span>`).join("")}
                </div>
            </div>
        </div>
    `).join("");
}

function renderGaps(gapData) {
    const container = document.getElementById("gapsContainer");
    const gaps = gapData?.gaps || [];

    if (!gaps.length) {
        container.innerHTML = '<div class="col-12 text-muted">No skill gap metrics computed yet.</div>';
        return;
    }

    container.innerHTML = gaps.map(g => `
        <div class="col-lg-6 col-12">
            <div class="rec-card">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <div>
                        <h5 class="fw-bold text-dark m-0">${g.skill}</h5>
                        <small class="text-muted">${g.category}</small>
                    </div>
                    ${g.gap != null ? `
                        <span class="badge ${g.gap <= 10 ? 'bg-info-subtle text-info' : 'bg-warning-subtle text-warning'} border">
                            Gap: -${g.gap} pts
                        </span>
                    ` : `
                        <span class="badge bg-secondary-subtle text-secondary border">Unassessed</span>
                    `}
                </div>
                <div class="d-flex justify-content-between small text-muted my-2">
                    <span>Current: <b>${g.current_score != null ? g.current_score : 'Unassessed'}</b></span>
                    <span>Required Benchmark: <b>${g.required_score}</b></span>
                </div>
                <div class="progress mb-3" style="height: 8px;">
                    <div class="progress-bar ${g.current_score != null ? 'bg-primary' : 'bg-secondary'}" style="width: ${g.current_score != null ? g.current_score : 0}%;"></div>
                </div>
                <p class="small text-muted mb-2"><b>Recommendation:</b> ${g.recommendation}</p>
                <div class="p-2 bg-light rounded-2 border">
                    <small class="text-dark fw-bold d-block mb-1">Roadmap Milestones:</small>
                    <ul class="small text-muted ps-3 mb-0">
                        ${g.learning_roadmap.map(step => `<li>${step}</li>`).join("")}
                    </ul>
                </div>
            </div>
        </div>
    `).join("");
}
