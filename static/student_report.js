let currentStudentId = null;

document.addEventListener("DOMContentLoaded", async () => {
    const urlParams = new URLSearchParams(window.location.search);
    currentStudentId = urlParams.get("student_id");

    await loadStudentSelector();
    if (currentStudentId) {
        await loadReport(currentStudentId);
    }

    document.getElementById("downloadPdfBtn").addEventListener("click", generatePdf);
    document.getElementById("printBtn").addEventListener("click", () => window.print());
});

async function loadStudentSelector() {
    const select = document.getElementById("reportStudentSelect");
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
            loadReport(currentStudentId);
        });
    } catch (err) {
        console.error("Failed to load students:", err);
    }
}

async function loadReport(studentId) {
    try {
        const res = await fetch(`/api/profile/${studentId}/report`);
        const data = await res.json();
        if (!data.status || !data.sections) return;

        const sec = data.sections;

        // 1. Cover
        document.getElementById("repId").innerText = data.report_id || `IR-V2-${studentId}`;
        document.getElementById("repDate").innerText = sec.section_01_cover?.generated_date || new Date().toLocaleDateString();

        // 2. Student Details
        const s2 = sec.section_02_student_details || {};
        document.getElementById("stuName").innerText = s2.full_name || "-";
        document.getElementById("stuInstitute").innerText = `${s2.course || 'Course Not Set'} • ${s2.school_college || 'Institute Not Set'}`;
        document.getElementById("stuId").innerText = s2.student_id || studentId;
        document.getElementById("stuAgeGender").innerText = `${s2.age || '-'} yrs, ${s2.gender || '-'}`;
        document.getElementById("stuStream").innerText = (s2.stream && s2.stream.trim()) ? s2.stream : "Not Specified";
        document.getElementById("stuCourseYear").innerText = `${s2.course || '-'} (${s2.year || '-'})`;
        document.getElementById("stuContact").innerText = `${s2.email || '-'} | ${s2.mobile || '-'}`;
        document.getElementById("stuLocation").innerText = s2.location || "N/A";
        if (s2.photo_path) {
            document.getElementById("stuPhoto").src = s2.photo_path;
        }

        // 3. Executive Summary
        const s3 = sec.section_03_executive_summary || {};
        document.getElementById("execSummaryText").innerText = s3.summary_text || "-";
        document.getElementById("execStream").innerText = s3.primary_affinity_stream || s3.recommended_stream || "-";
        document.getElementById("execCareer").innerText = s3.higher_match_career || s3.top_career || "-";
        document.getElementById("execCogIndex").innerText = s3.overall_cognitive_index ? `${s3.overall_cognitive_index}%` : "-";

        // 4 & 5. Iris Analysis & Quality
        const s4 = sec.section_04_iris_analysis || {};
        document.getElementById("irisStatus").innerText = s4.status || "Record Linked";
        if (s4.details?.notes) {
            document.getElementById("irisNotes").innerText = s4.details.notes;
        }

        const s5 = sec.section_05_iris_quality || {};
        if (s5.capture_quality_score) {
            document.getElementById("iqScore").innerText = `${s5.capture_quality_score}%`;
            document.getElementById("iqRating").innerText = s5.image_quality || "Good";
            document.getElementById("iqUsable").innerText = s5.usable_iris_percentage || "90%";
            document.getElementById("iqOcclusion").innerText = s5.occlusion_percentage || "10%";
        }

        // 6. Personality Profile
        const s6 = sec.section_06_personality_profile || {};
        const persScores = s6.scores || {};
        if (s6.is_pending || !Object.keys(persScores).length) {
            document.getElementById("personalityContainer").innerHTML = `
                <div class="col-12">
                    <div class="alert alert-secondary mb-0">
                        <i class="fa-solid fa-clock me-2"></i><strong>Profile Data Pending:</strong> This section requires completed structured assessment responses.
                    </div>
                </div>
            `;
        } else {
            document.getElementById("personalityContainer").innerHTML = Object.entries(persScores).map(([k, v]) => `
                <div class="col-md col-6">
                    <div class="metric-card text-center">
                        <div class="metric-title">${k.replace(/_/g, ' ')}</div>
                        <div class="metric-val fs-4">${typeof v === 'number' ? v.toFixed(1) : v}%</div>
                    </div>
                </div>
            `).join("");
        }

        // 7 & 8. Strengths & Development Areas
        const s7 = sec.section_07_strengths?.strengths_list || [];
        document.getElementById("strengthsList").innerHTML = s7.map(st => `
            <div class="p-2 mb-2 bg-light rounded-2 border">
                <div class="d-flex justify-content-between">
                    <strong class="text-dark">${st.title}</strong>
                    <span class="badge bg-success">${st.score}</span>
                </div>
                <small class="text-muted">${st.domain}</small>
            </div>
        `).join("");

        const s8 = sec.section_08_development_areas?.development_list || [];
        document.getElementById("devAreasList").innerHTML = s8.map(d => `
            <div class="p-2 mb-2 bg-light rounded-2 border">
                <div class="d-flex justify-content-between">
                    <strong class="text-dark">${d.title}</strong>
                    <span class="badge bg-warning text-dark">${d.gap}</span>
                </div>
                <small class="text-muted d-block">${d.action}</small>
            </div>
        `).join("");

        // 9. Behavioural Indicators
        const s9 = sec.section_09_behavioural_indicators || {};
        const s9Indicators = s9.indicators || {};
        if (s9.is_pending || !Object.keys(s9Indicators).length) {
            document.getElementById("behaviourContainer").innerHTML = `
                <div class="col-12">
                    <div class="alert alert-secondary mb-0">
                        <i class="fa-solid fa-clock me-2"></i><strong>Profile Data Pending:</strong> This section requires completed structured assessment responses.
                    </div>
                </div>
            `;
        } else {
            document.getElementById("behaviourContainer").innerHTML = Object.entries(s9Indicators).map(([k, v]) => `
                <div class="col-md-6">
                    <div class="metric-card">
                        <div class="d-flex justify-content-between">
                            <strong class="text-dark">${k.replace(/_/g, ' ').toUpperCase()}</strong>
                            <span class="badge bg-primary">${v.score}%</span>
                        </div>
                    </div>
                </div>
            `).join("");
        }

        // 10 & 11. Cognitive & Critical Abilities
        const s10 = sec.section_10_cognitive_profile || {};
        const s10Domains = s10.domains || [];
        const validS10 = s10Domains.filter(c => !c.is_pending && c.score !== null);
        if (s10.is_pending || !validS10.length) {
            document.getElementById("cognitiveGrid").innerHTML = `
                <div class="col-12">
                    <div class="alert alert-secondary mb-0">
                        <i class="fa-solid fa-clock me-2"></i><strong>Profile Data Pending:</strong> This section requires completed structured assessment responses.
                    </div>
                </div>
            `;
        } else {
            document.getElementById("cognitiveGrid").innerHTML = s10Domains.map(c => {
                if (c.is_pending || c.score === null) {
                    return `
                        <div class="col-md-4 col-sm-6">
                            <div class="p-2 bg-light rounded-2 border opacity-75">
                                <div class="d-flex justify-content-between">
                                    <small class="fw-bold text-muted">${c.domain}</small>
                                    <span class="badge bg-secondary-subtle text-secondary">Pending</span>
                                </div>
                            </div>
                        </div>
                    `;
                }
                return `
                    <div class="col-md-4 col-sm-6">
                        <div class="p-2 bg-light rounded-2 border">
                            <div class="d-flex justify-content-between">
                                <small class="fw-bold">${c.domain}</small>
                                <span class="badge bg-primary-subtle text-primary">${c.score}%</span>
                            </div>
                            <div class="d-flex justify-content-between align-items-center mt-1">
                                <small class="text-muted" style="font-size: 11px;">Level: ${c.category}</small>
                                <small class="text-muted" style="font-size: 10px;">Confidence: Not statistically calibrated</small>
                            </div>
                        </div>
                    </div>
                `;
            }).join("");
        }

        const s11 = sec.section_11_critical_abilities || {};
        const s11Abilities = s11.abilities || {};
        const caGrid = document.getElementById("criticalAbilitiesGrid");
        if (caGrid) {
            if (s11.is_pending || !Object.keys(s11Abilities).length) {
                caGrid.innerHTML = `
                    <div class="col-12">
                        <div class="alert alert-secondary mb-0">
                            <i class="fa-solid fa-clock me-2"></i><strong>Profile Data Pending:</strong> This section requires completed structured assessment responses.
                        </div>
                    </div>
                `;
            } else {
                caGrid.innerHTML = Object.entries(s11Abilities).map(([k, v]) => `
                    <div class="col-md-4 col-sm-6">
                        <div class="p-2 bg-white rounded-2 border">
                            <div class="d-flex justify-content-between">
                                <small class="fw-bold text-dark">${k.replace(/_/g, ' ').toUpperCase()}</small>
                                <span class="badge bg-success-subtle text-success">${v.score}%</span>
                            </div>
                            <div class="d-flex justify-content-between align-items-center mt-1">
                                <small class="text-muted" style="font-size: 11px;">Level: ${v.level}</small>
                                <small class="text-muted" style="font-size: 10px;">Confidence: Not statistically calibrated</small>
                            </div>
                        </div>
                    </div>
                `).join("");
            }
        }

        // 12-15. Learning & Leadership
        const s12 = sec.section_12_learning_style_vak || {};
        const s12Data = s12.vak_data || {};
        if (s12.is_pending || !s12Data.visual_pct) {
            document.getElementById("repVakContent").innerHTML = `
                <div class="text-muted"><span class="badge bg-secondary mb-1">Profile Data Pending</span><br>This section requires completed structured assessment responses.</div>
            `;
        } else {
            const prefLabel = s12Data.primary_learning_preference || (s12Data.is_balanced ? "Balanced Multi-Sensory Preference" : `${s12Data.dominant_style || 'Primary'} Learning Preference`);
            document.getElementById("repVakContent").innerHTML = `
                <b>Primary Preference:</b> ${prefLabel}<br>
                <b>Breakdown:</b> Visual: ${s12Data.visual_pct}%, Auditory: ${s12Data.auditory_pct}%, Kinesthetic: ${s12Data.kinesthetic_pct}%<br>
                <span class="text-muted">${s12Data.study_recommendations || ''}</span>
            `;
        }

        const s13 = sec.section_13_leadership_style || {};
        const s13Data = s13.leadership_data || {};
        if (s13.is_pending || s13Data.task_pct === undefined) {
            document.getElementById("repLeadContent").innerHTML = `
                <div class="text-muted"><span class="badge bg-secondary mb-1">Profile Data Pending</span><br>This section requires completed structured assessment responses.</div>
            `;
        } else {
            const leadLabel = s13Data.leadership_orientation || s13Data.dominant_style || 'Exploratory Orientation';
            document.getElementById("repLeadContent").innerHTML = `
                <b>Orientation:</b> ${leadLabel}<br>
                <b>Task vs Relational:</b> ${s13Data.task_pct}% Task | ${s13Data.relationship_pct}% Relationship<br>
                <span class="text-muted">${s13Data.strengths || ''}</span>
            `;
        }

        const s14 = sec.section_14_thinking_vs_action || {};
        const s14Data = s14.thinking_action_data || {};
        if (s14.is_pending || s14Data.thinking_pct === undefined) {
            document.getElementById("repThinkContent").innerHTML = `
                <div class="text-muted"><span class="badge bg-secondary mb-1">Profile Data Pending</span><br>This section requires completed structured assessment responses.</div>
            `;
        } else {
            const thinkLabel = s14Data.thinking_action_preference || s14Data.orientation || 'Balanced Preference';
            document.getElementById("repThinkContent").innerHTML = `
                <b>Orientation:</b> ${thinkLabel}<br>
                <b>Metrics:</b> ${s14Data.thinking_pct}% Thinking | ${s14Data.action_pct}% Action
            `;
        }

        const s15 = sec.section_15_team_management_vs_player || {};
        const s15Data = s15.team_role_data || {};
        if (s15.is_pending || s15Data.team_player_pct === undefined) {
            document.getElementById("repTeamContent").innerHTML = `
                <div class="text-muted"><span class="badge bg-secondary mb-1">Profile Data Pending</span><br>This section requires completed structured assessment responses.</div>
            `;
        } else {
            const teamLabel = s15Data.preferred_collaboration_mode || s15Data.dominant_role || 'Collaborator';
            document.getElementById("repTeamContent").innerHTML = `
                <b>Collaboration Mode:</b> ${teamLabel}<br>
                <b>Metrics:</b> ${s15Data.team_management_pct}% Management | ${s15Data.team_player_pct}% Team Player
            `;
        }

        // 16 & 17. Critical Subjects
        const s17 = sec.section_17_critical_subjects?.subjects_breakdown || [];
        document.getElementById("repSubjectsBody").innerHTML = s17.map(sub => `
            <tr>
                <td><b>${sub.subject}</b></td>
                <td><span class="badge bg-primary-subtle text-primary">${sub.current_score}%</span></td>
                <td>${sub.strength_level}</td>
                <td>${sub.compatibility}</td>
                <td><small class="text-muted">${sub.recommended_improvement}</small></td>
            </tr>
        `).join("");

        // 18. KPIs
        const s18 = sec.section_18_kpi_analysis?.kpi_list || [];
        document.getElementById("repKpiBody").innerHTML = s18.map(k => {
            const isScorePresent = k.current_score !== null && k.current_score !== undefined;
            const scoreDisplay = isScorePresent ? k.current_score : '<span class="badge bg-secondary-subtle text-secondary">Pending</span>';
            const isGapPresent = k.gap !== null && k.gap !== undefined;
            const gapDisplay = isGapPresent ? (k.gap > 0 ? '-' + k.gap : (k.gap === 0 ? '0' : '+' + Math.abs(k.gap))) : '<span class="text-muted small">-</span>';
            const gapClass = isGapPresent ? (k.gap === 0 ? 'text-success' : 'text-danger') : 'text-muted';

            return `
            <tr>
                <td><b>${k.category}</b></td>
                <td>${scoreDisplay}</td>
                <td>${k.target_score !== null && k.target_score !== undefined ? k.target_score : '-'}</td>
                <td><span class="${gapClass} fw-bold">${gapDisplay}</span></td>
                <td><small class="text-muted">${k.recommendation || '-'}</small></td>
            </tr>
            `;
        }).join("");

        // 19. Streams
        const s19Data = sec.section_19_stream_selection || {};
        const s19Rankings = s19Data.rankings || [];
        const s19Conflicts = s19Data.conflicts_and_considerations || [];
        const primaryStream = s19Data.primary_affinity_stream || s19Data.recommended_stream;
        const secondaryStream = s19Data.secondary_affinity_stream;

        const repStreamConflicts = document.getElementById("repStreamConflicts");
        if (repStreamConflicts) {
            if (s19Conflicts.length > 0) {
                const hasTie = s19Conflicts.some(c => c.includes("Close Suitability Balance") || c.includes("Marginal differentiation"));
                repStreamConflicts.innerHTML = `
                    <div class="alert ${hasTie ? 'alert-warning border-warning' : 'alert-info border-info'} mb-3 py-2 px-3">
                        <div class="d-flex align-items-center mb-1">
                            <i class="fa-solid ${hasTie ? 'fa-scale-balanced' : 'fa-circle-info'} me-2 text-${hasTie ? 'warning' : 'info'}"></i>
                            <strong class="text-dark small">${hasTie ? 'Balanced Affinity Notice (Close Suitability Balance)' : 'Counselor Considerations & Context'}</strong>
                        </div>
                        <ul class="small mb-0 ps-3">
                            ${s19Conflicts.map(c => `<li>${c}</li>`).join("")}
                        </ul>
                    </div>
                `;
            } else {
                repStreamConflicts.innerHTML = "";
            }
        }

        const isTied = (s19Rankings.length >= 2 && Math.abs(s19Rankings[0].compatibility_score - s19Rankings[1].compatibility_score) <= 3.0 && s19Rankings[0].compatibility_score > 0);

        document.getElementById("repStreamsContainer").innerHTML = s19Rankings.map(st => {
            let badgeText = st.level;
            let badgeClass = 'bg-light text-dark border';
            if (isTied && (st.stream === primaryStream || st.stream === secondaryStream)) {
                badgeText = 'Balanced Affinity';
                badgeClass = 'bg-primary-subtle text-primary border border-primary';
            } else if (st.stream === primaryStream) {
                badgeText = 'Primary Affinity';
                badgeClass = 'bg-primary';
            } else if (st.stream === secondaryStream) {
                badgeText = 'Secondary Affinity';
                badgeClass = 'bg-secondary';
            }

            const dim = st.dimensional_scores || {};
            const missing = st.missing_prerequisites || [];
            const isPending = st.compatibility_score === 0 || (dim.academic_match === null && dim.assessment_match === null);

            return `
                <div class="col-md-4">
                    <div class="p-3 bg-light rounded-3 border h-100 ${st.stream === primaryStream ? 'border-primary' : ''}">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <strong class="text-dark">${st.stream}</strong>
                            <span class="badge ${badgeClass}">${badgeText}</span>
                        </div>
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <small class="text-muted">Affinity Index:</small>
                            ${isPending ? `
                                <span class="badge bg-secondary-subtle text-secondary border">Profile Data Pending</span>
                            ` : `
                                <span class="fw-bold text-primary fs-6">${st.compatibility_score} / 100</span>
                            `}
                        </div>
                        ${isPending ? `<small class="text-muted d-block mb-2">Prerequisite subject marks or assessment records are not yet on file.</small>` : ''}

                        ${missing.length > 0 ? `
                            <div class="mb-2">
                                ${missing.map(p => `<span class="badge bg-warning-subtle text-dark border border-warning me-1 mb-1" style="font-size: 10px;"><i class="fa-solid fa-triangle-exclamation text-warning me-1"></i> Missing: ${p}</span>`).join("")}
                            </div>
                        ` : ''}

                        ${st.dimensional_scores ? `
                            <div class="p-2 bg-white rounded border mb-2" style="font-size: 10px;">
                                <span class="text-muted d-block fw-bold mb-1">DIMENSIONAL FIT:</span>
                                <div class="d-flex flex-wrap gap-1">
                                    <span class="badge bg-light text-dark border">Acad: ${dim.academic_match != null ? dim.academic_match + '%' : 'Pending'}</span>
                                    <span class="badge bg-light text-dark border">Assess: ${dim.assessment_match != null ? dim.assessment_match + '%' : 'Pending'}</span>
                                    <span class="badge bg-light text-dark border">Interest: ${dim.interest_match != null ? dim.interest_match + '%' : 'Pending'}</span>
                                    <span class="badge bg-light text-dark border">Skill: ${dim.skill_match != null ? dim.skill_match + '%' : 'Pending'}</span>
                                </div>
                            </div>
                        ` : ''}

                        <small class="text-muted d-block mb-2"><b>Key Strengths:</b> ${st.strengths?.slice(0, 2).join(", ") || '-'}</small>
                        <small class="text-dark fw-bold d-block mb-1">Recommended Preparation:</small>
                        <small class="text-muted">${st.recommended_preparation || '-'}</small>
                    </div>
                </div>
            `;
        }).join("");

        // 20 & 21. Co-curricular & Sports
        const s20 = sec.section_20_cocurricular_recommendations?.recommendations || [];
        document.getElementById("repCocurrList").innerHTML = s20.slice(0, 4).map(c => `
            <div class="col-md-3 col-6">
                <div class="p-2 bg-light rounded-2 border">
                    <div class="d-flex justify-content-between">
                        <small class="fw-bold">${c.activity}</small>
                        <span class="badge bg-primary-subtle text-primary">${c.compatibility != null ? c.compatibility + '%' : 'Pending'}</span>
                    </div>
                    <small class="text-muted d-block" style="font-size: 11px;">${c.benefits}</small>
                </div>
            </div>
        `).join("");

        const s21 = sec.section_21_sports_recommendations?.recommendations || [];
        document.getElementById("repSportsList").innerHTML = s21.slice(0, 4).map(sp => `
            <div class="col-md-3 col-6">
                <div class="p-2 bg-light rounded-2 border">
                    <div class="d-flex justify-content-between">
                        <small class="fw-bold">${sp.activity}</small>
                        <span class="badge bg-success-subtle text-success">${sp.compatibility != null ? sp.compatibility + '%' : 'Pending'}</span>
                    </div>
                    <small class="text-muted d-block" style="font-size: 11px;">${sp.benefits}</small>
                </div>
            </div>
        `).join("");

        // 22-25. Careers (Neutral preference with legacy fallbacks)
        const s22 = sec.section_22_top_career_recommendations?.higher_match_careers || sec.section_22_top_career_recommendations?.careers || [];
        document.getElementById("repTopCareers").innerHTML = s22.map(c => {
            const dim = c.dimensional_scores || {};
            const missing = c.missing_prerequisite_subjects || [];
            const isPending = c.compatibility_score === 0 || (dim.academic_match === null && dim.assessment_match === null && dim.skill_match === null);

            return `
                <div class="col-md-4">
                    <div class="p-3 bg-light rounded-3 border border-primary h-100">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <strong class="text-dark">${c.career}</strong>
                            ${isPending ? `
                                <span class="badge bg-secondary-subtle text-secondary border">Profile Data Pending</span>
                            ` : `
                                <span class="badge bg-primary">${c.compatibility_score} / 100</span>
                            `}
                        </div>
                        <small class="text-muted d-block mb-1">${c.category} • <span class="badge bg-light text-secondary border">${isPending ? 'Pending' : (c.match_level || 'Evaluated')}</span></small>
                        ${isPending ? `<small class="text-muted d-block mb-2">Prerequisite subject marks or assessment records are not yet on file.</small>` : ''}
                        <div class="d-flex flex-wrap gap-1 mb-2" style="font-size: 10px;">
                            <span class="badge bg-white text-dark border">Acad: ${dim.academic_match != null ? dim.academic_match + '%' : 'Pending'}</span>
                            <span class="badge bg-white text-dark border">Skill: ${dim.skill_match != null ? dim.skill_match + '%' : 'Pending'}</span>
                            <span class="badge bg-white text-dark border">Assess: ${dim.assessment_match != null ? dim.assessment_match + '%' : 'Pending'}</span>
                            <span class="badge bg-white text-dark border">Interest: ${dim.interest_match != null ? dim.interest_match + '%' : 'Pending'}</span>
                        </div>
                        ${missing.length > 0 ? `
                            <div class="mb-1"><span class="badge bg-warning-subtle text-dark border border-warning" style="font-size: 10px;">Missing Prereq: ${missing.join(", ")}</span></div>
                        ` : ''}
                        <small class="text-dark d-block mb-2">${c.why_it_matches?.[0] || c.matched_factors?.[0] || 'Curricular alignment confirmed'}</small>
                        <small class="text-muted d-block"><b>Edu:</b> ${c.required_education}</small>
                    </div>
                </div>
            `;
        }).join("");

        const s23 = sec.section_23_trending_careers?.trending_catalog_careers || sec.section_23_trending_careers?.careers || [];
        document.getElementById("repTrendCareers").innerHTML = s23.map(c => {
            const dim = c.dimensional_scores || {};
            const isPending = c.compatibility_score === 0 || (dim.academic_match === null && dim.assessment_match === null && dim.skill_match === null);

            return `
                <div class="col-md-4">
                    <div class="p-3 bg-light rounded-3 border h-100">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <strong class="text-dark">${c.career}</strong>
                            ${isPending ? `
                                <span class="badge bg-secondary-subtle text-secondary border">Profile Data Pending</span>
                            ` : `
                                <span class="badge bg-info-subtle text-dark border">${c.compatibility_score} / 100</span>
                            `}
                        </div>
                        <small class="text-muted d-block mb-1">${c.category} • <span class="badge bg-secondary-subtle text-secondary" style="font-size: 10px;">Curated Catalog</span></small>
                        ${isPending ? `<small class="text-muted d-block mb-2">Prerequisite subject marks or assessment records are not yet on file.</small>` : ''}
                        <div class="d-flex flex-wrap gap-1 mb-2" style="font-size: 10px;">
                            <span class="badge bg-white text-dark border">Acad: ${dim.academic_match != null ? dim.academic_match + '%' : 'Pending'}</span>
                            <span class="badge bg-white text-dark border">Skill: ${dim.skill_match != null ? dim.skill_match + '%' : 'Pending'}</span>
                            <span class="badge bg-white text-dark border">Assess: ${dim.assessment_match != null ? dim.assessment_match + '%' : 'Pending'}</span>
                        </div>
                        <small class="text-muted d-block"><b>Edu:</b> ${c.required_education}</small>
                    </div>
                </div>
            `;
        }).join("");

        const s24 = sec.section_24_other_suitable_careers?.additional_suitable_careers || sec.section_24_other_suitable_careers?.careers || [];
        document.getElementById("repOtherCareers").innerHTML = s24.map(c => {
            const isPending = c.compatibility_score === 0;
            return `
                <div class="col-md-4">
                    <div class="p-2 bg-light rounded-2 border">
                        <div class="d-flex justify-content-between align-items-center">
                            <small class="fw-bold">${c.career}</small>
                            ${isPending ? `
                                <span class="badge bg-secondary-subtle text-secondary border" style="font-size: 10px;">Profile Data Pending</span>
                            ` : `
                                <span class="badge bg-secondary">${c.compatibility_score} / 100</span>
                            `}
                        </div>
                    </div>
                </div>
            `;
        }).join("");

        // 25. Career Compatibility Summary Matrix (Fix previously unrendered Section 25)
        const s25 = sec.section_25_career_compatibility?.matrix || [];
        const matrixContainer = document.getElementById("repCareerMatrix");
        if (matrixContainer) {
            if (s25.length > 0) {
                matrixContainer.innerHTML = `
                    <table class="table table-bordered table-sm align-middle mb-0" style="font-size: 12px;">
                        <thead class="table-light">
                            <tr>
                                <th>Career Pathway</th>
                                <th>Domain Category</th>
                                <th>Affinity Index (0-100)</th>
                                <th>Match Tier</th>
                                <th>Key Supportive Evidence</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${s25.map(row => {
                                const hasScore = row.score != null && row.score > 0;
                                return `
                                    <tr>
                                        <td class="fw-bold text-dark">${row.career || '-'}</td>
                                        <td><span class="badge bg-light text-secondary border">${row.category || '-'}</span></td>
                                        <td><strong class="text-primary">${hasScore ? row.score + ' / 100' : '<span class=\"badge bg-secondary-subtle text-secondary border\">Profile Data Pending</span>'}</strong></td>
                                        <td><span class="badge ${hasScore ? (row.score >= 80 ? 'bg-success-subtle text-success' : (row.score >= 65 ? 'bg-primary-subtle text-primary' : 'bg-secondary-subtle text-secondary')) : 'bg-secondary-subtle text-secondary'} border">${hasScore ? (row.match_level || 'Evaluated') : 'Data Pending'}</span></td>
                                        <td class="text-muted">${row.why || 'Prerequisite subject marks or assessment records are not yet on file.'}</td>
                                    </tr>
                                `;
                            }).join("")}
                        </tbody>
                    </table>
                `;
            } else {
                matrixContainer.innerHTML = '<div class="p-3 text-muted text-center border rounded">No career compatibility matrix data available.</div>';
            }
        }

        // 26 & 27. Gaps & Roadmap
        const s26 = sec.section_26_skill_gap_analysis?.gaps || [];
        document.getElementById("repSkillGaps").innerHTML = s26.map(g => `
            <div class="col-md-6">
                <div class="p-2 bg-light rounded-2 border">
                    <div class="d-flex justify-content-between align-items-center">
                        <b>${g.skill}</b>
                        <span class="badge ${g.gap !== null && g.gap !== undefined ? 'bg-danger' : 'bg-secondary'}">${g.gap !== null && g.gap !== undefined ? `Gap: -${g.gap}` : (g.status || 'Unassessed')}</span>
                    </div>
                    <small class="text-muted">${g.recommendation}</small>
                </div>
            </div>
        `).join("");

        const s27 = sec.section_27_development_plan?.quarterly_roadmap || [];
        document.getElementById("repRoadmap").innerHTML = s27.map(r => `
            <div class="col-md-3 col-6">
                <div class="p-2 bg-light rounded-2 border h-100">
                    <span class="badge bg-primary mb-1">${r.quarter}</span>
                    <strong class="d-block small">${r.focus}</strong>
                    <ul class="ps-3 small text-muted mb-0">
                        ${r.milestones.map(m => `<li>${m}</li>`).join("")}
                    </ul>
                </div>
            </div>
        `).join("");

        // 28 & 29. Profile & AI Summary
        const s28 = sec.section_28_overall_student_profile || {};
        const repKeySkillsInterests = document.getElementById("repKeySkillsInterests");
        if (repKeySkillsInterests) {
            const keySkills = s28.key_skills || [];
            const keyInterests = s28.key_interests || [];
            const isPending = s28.is_pending || (!keySkills.length && !keyInterests.length);

            if (isPending) {
                repKeySkillsInterests.innerHTML = `
                    <div class="p-3 bg-white rounded-3 border">
                        <div class="d-flex align-items-center mb-2">
                            <span class="badge bg-secondary-subtle text-secondary border me-2">Profile Data Pending</span>
                            <span class="fw-bold text-secondary">28. Overall Student Profile Highlights</span>
                        </div>
                        <p class="small text-muted mb-0">Key skills and interests have not been logged yet. Profile indicators will populate once entries are recorded.</p>
                    </div>
                `;
            } else {
                const skillsHtml = keySkills.length
                    ? keySkills.map(sk => `<span class="badge bg-primary-subtle text-primary border border-primary-subtle me-1 mb-1">${sk}</span>`).join("")
                    : '<span class="text-muted small">Not provided</span>';
                const interestsHtml = keyInterests.length
                    ? keyInterests.map(it => `<span class="badge bg-info-subtle text-info border border-info-subtle me-1 mb-1">${it}</span>`).join("")
                    : '<span class="text-muted small">Not provided</span>';

                const courseDisplay = (s28.course && s28.course !== '-') ? s28.course : 'Course Not Specified';
                const schoolDisplay = (s28.school_college && s28.school_college !== '-') ? s28.school_college : 'Institution Not Specified';

                repKeySkillsInterests.innerHTML = `
                    <div class="p-3 bg-white rounded-3 border">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <h6 class="fw-bold text-primary m-0">28. Overall Student Profile Highlights</h6>
                            <span class="badge bg-light text-secondary border">${courseDisplay} • ${schoolDisplay}</span>
                        </div>
                        <div class="row g-2 mt-1">
                            <div class="col-md-6">
                                <small class="text-muted fw-bold d-block mb-1">Key Verified Skills:</small>
                                <div>${skillsHtml}</div>
                            </div>
                            <div class="col-md-6">
                                <small class="text-muted fw-bold d-block mb-1">Declared Core Interests:</small>
                                <div>${interestsHtml}</div>
                            </div>
                        </div>
                    </div>
                `;
            }
        }

        document.getElementById("repAiSummary").innerText = sec.section_29_ai_generated_summary?.narrative || "-";
    } catch (err) {
        console.error("Error loading V2 Report:", err);
    }
}

function generatePdf() {
    const root = document.getElementById("reportRoot");
    if (!root) return;

    const opt = {
        margin: [0.3, 0.3, 0.4, 0.3],
        filename: `Iris_AI_Report_V2_${currentStudentId || 'Student'}.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true, logging: false },
        jsPDF: { unit: 'in', format: 'a4', orientation: 'portrait' }
    };

    html2pdf().set(opt).from(root).save();
}
