let currentStudentId = null;
let radarChartInstance = null;
let vakChartInstance = null;

document.addEventListener("DOMContentLoaded", async () => {
    const urlParams = new URLSearchParams(window.location.search);
    currentStudentId = urlParams.get("student_id");

    await loadStudentSelector();
    if (currentStudentId) {
        await loadAiProfileData(currentStudentId);
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
            updateLinks(currentStudentId);
            loadAiProfileData(currentStudentId);
        });

        updateLinks(currentStudentId);
    } catch (err) {
        console.error("Failed to load students:", err);
    }
}

function updateLinks(sid) {
    document.getElementById("recLink").href = `recommendations.html?student_id=${sid}`;
    document.getElementById("reportLink").href = `student_report.html?student_id=${sid}`;
}

async function loadAiProfileData(studentId) {
    try {
        const res = await fetch(`/api/profile/${studentId}/analyze`, { method: "POST" });
        const data = await res.json();
        if (!data.status) return;

        const cog = data.cognitive || {};
        const kpis = data.kpis || {};

        // 1. Overall Cognitive Index
        if (cog.overall_cognitive_index !== null && cog.overall_cognitive_index !== undefined) {
            document.getElementById("overallIndexBadge").innerText = `Cognitive Index: ${cog.overall_cognitive_index}%`;
        } else {
            document.getElementById("overallIndexBadge").innerText = `Cognitive Index: Pending`;
        }

        // 2. Render Cognitive Radar & List
        renderCognitiveDomains(cog.domains || []);

        // 3. Render VAK Learning Style
        const profRes = await fetch(`/api/profile/${studentId}`);
        const profData = await profRes.json();
        const fused = profData.profile || {};
        const vakData = fused.assessments?.learning_style?.data?.details || {};
        renderVakChart(vakData);

        // 4. Render Leadership Orientation
        const leadData = fused.assessments?.leadership_style?.data?.details || {};
        renderLeadership(leadData);

        // 5. Render Thinking vs Action & Team Player
        const thinkData = fused.assessments?.thinking_action?.data?.details || {};
        const teamData = fused.assessments?.team_player?.data?.details || {};
        renderRoleDynamics(thinkData, teamData);

        // 6. Render KPIs
        renderKpis(kpis.kpis || []);

        // 7. Render Legacy Demonstration Reference
        const leg = cog.legacy_neuron_reference || {};
        const compRef = leg.metrics?.demonstration_composite_strength ?? leg.metrics?.demonstration_neuro_strength;
        if (leg.metrics && compRef !== null && compRef !== undefined) {
            document.getElementById("legacyMetrics").innerHTML = `
                <span><b>Composite Reference:</b> ${compRef}%</span> •
                <span><b>Consistency Reference:</b> ${leg.metrics.demonstration_consistency ?? '-'}%</span> •
                <span><b>Stability Reference:</b> ${leg.metrics.demonstration_stability ?? '-'}%</span>
            `;
        } else {
            document.getElementById("legacyMetrics").innerHTML = `
                <span class="text-muted">Historical demonstration metrics pending completed assessment responses.</span>
            `;
        }
    } catch (err) {
        console.error("Error loading AI Profile:", err);
    }
}

function renderCognitiveDomains(domains) {
    const listContainer = document.getElementById("cognitiveList");
    const validDomains = domains.filter(d => !d.is_pending && d.score !== null);

    if (!validDomains.length) {
        listContainer.innerHTML = '<div class="alert alert-secondary m-3"><i class="fa-solid fa-clock me-2"></i><strong>Profile Data Pending:</strong> This section requires completed structured assessment responses.</div>';
        const ctx = document.getElementById("cognitiveRadarChart").getContext("2d");
        if (radarChartInstance) radarChartInstance.destroy();
        return;
    }

    listContainer.innerHTML = domains.map(d => {
        if (d.is_pending || d.score === null) {
            return `
                <div class="score-box opacity-75">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <strong class="text-muted">${d.domain}</strong>
                        <span class="badge bg-secondary-subtle text-secondary">Pending</span>
                    </div>
                    <div class="d-flex justify-content-between mt-1">
                        <small class="text-muted" style="font-size: 11px;">Status: Profile Data Pending</small>
                        <small class="text-muted" style="font-size: 11px;">Source: ${d.source}</small>
                    </div>
                </div>
            `;
        }

        return `
            <div class="score-box">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <strong class="text-dark">${d.domain}</strong>
                    <span class="badge bg-primary-subtle text-primary fw-bold">${d.score}%</span>
                </div>
                <div class="progress" style="height: 6px;">
                    <div class="progress-bar bg-primary" style="width: ${d.score}%;"></div>
                </div>
                <div class="d-flex justify-content-between mt-1">
                    <small class="text-muted" style="font-size: 11px;">Level: ${d.category}</small>
                    <small class="text-muted" style="font-size: 11px;">Source: ${d.source}</small>
                </div>
                <div class="d-flex justify-content-between mt-1">
                    <small class="text-secondary fw-semibold" style="font-size: 10px;">Heuristic indicator (0–100 scale), derived from structured assessment responses.</small>
                    <small class="text-muted" style="font-size: 10px;">Confidence: Not statistically calibrated</small>
                </div>
            </div>
        `;
    }).join("");

    // Radar Chart
    const ctx = document.getElementById("cognitiveRadarChart").getContext("2d");
    if (radarChartInstance) radarChartInstance.destroy();

    const labels = validDomains.map(d => d.domain);
    const scores = validDomains.map(d => d.score);

    radarChartInstance = new Chart(ctx, {
        type: "radar",
        data: {
            labels: labels,
            datasets: [{
                label: "Assessment-Derived Cognitive Indicators",
                data: scores,
                backgroundColor: "rgba(37, 99, 235, 0.2)",
                borderColor: "#2563eb",
                pointBackgroundColor: "#2563eb",
                pointBorderColor: "#fff",
                pointHoverBackgroundColor: "#fff",
                pointHoverBorderColor: "#2563eb"
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    angleLines: { color: "#e2e8f0" },
                    grid: { color: "#e2e8f0" },
                    suggestedMin: 30,
                    suggestedMax: 100,
                    ticks: { display: false }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

function renderVakChart(vak) {
    const note = document.getElementById("vakNotes");
    if (!vak || vak.is_pending || (vak.visual_pct == null && !vak.dominant_style) || vak.dominant_style === "Profile Data Pending") {
        note.innerHTML = `<span class="badge bg-secondary mb-1">Profile Data Pending</span><br><small class="text-muted">Requires completed structured assessment responses.</small>`;
        const ctx = document.getElementById("vakDoughnutChart").getContext("2d");
        if (vakChartInstance) vakChartInstance.destroy();
        return;
    }

    const v = vak.visual_pct || 0;
    const a = vak.auditory_pct || 0;
    const k = vak.kinesthetic_pct || 0;

    const ctx = document.getElementById("vakDoughnutChart").getContext("2d");
    if (vakChartInstance) vakChartInstance.destroy();

    vakChartInstance = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: ["Visual", "Auditory", "Kinesthetic"],
            datasets: [{
                data: [v, a, k],
                backgroundColor: ["#2563eb", "#06b6d4", "#f59e0b"]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: "bottom" }
            }
        }
    });

    const prefLabel = vak.primary_learning_preference || (vak.is_balanced ? "Balanced Multi-Sensory Preference" : `${vak.dominant_style || 'Primary'} Learning Preference`);
    const partialNotice = vak.is_partial ? ` <span class="badge bg-warning-subtle text-dark">Partial (${vak.answered_questions}/${vak.total_questions})</span>` : "";
    note.innerHTML = `
        <strong>Preference:</strong> ${prefLabel}${partialNotice} (${v}% V, ${a}% A, ${k}% K)<br>
        <small>${vak.study_recommendations || 'Incorporate multi-sensory study practices.'}</small>
    `;
}

function renderLeadership(lead) {
    const note = document.getElementById("leadershipNotes");
    const isLeadPending = !lead || lead.is_pending || (lead.task_pct == null && lead.task_oriented_pct == null && !lead.dominant_style) || lead.dominant_style === "Profile Data Pending";
    if (isLeadPending) {
        document.getElementById("taskBar").style.width = `0%`;
        document.getElementById("taskBar").innerText = `-`;
        document.getElementById("relBar").style.width = `0%`;
        document.getElementById("relBar").innerText = `-`;
        note.innerHTML = `<span class="badge bg-secondary mb-1">Profile Data Pending</span><br><small class="text-muted">Requires completed structured assessment responses.</small>`;
        return;
    }

    const t = lead.task_pct ?? lead.task_oriented_pct ?? 0;
    const r = lead.relationship_pct ?? lead.relationship_oriented_pct ?? 0;

    document.getElementById("taskBar").style.width = `${t}%`;
    document.getElementById("taskBar").innerText = `${t}%`;
    document.getElementById("relBar").style.width = `${r}%`;
    document.getElementById("relBar").innerText = `${r}%`;

    const leadTitle = lead.leadership_orientation || lead.dominant_style || 'Orientation Indicator';
    note.innerHTML = `
        <strong>Orientation:</strong> ${leadTitle}<br>
        <small>${lead.characteristics || 'Balanced leadership focus'}</small>
    `;
}

function renderRoleDynamics(think, team) {
    const thinkPending = !think || think.is_pending || think.thinking_pct == null;
    const teamPending = !team || team.is_pending || team.team_player_pct == null;

    if (thinkPending) {
        document.getElementById("thinkBar").style.width = `0%`;
        document.getElementById("actionBar").style.width = `0%`;
    } else {
        const th = think.thinking_pct ?? 50;
        const ac = think.action_pct ?? 50;
        document.getElementById("thinkBar").style.width = `${th}%`;
        document.getElementById("actionBar").style.width = `${ac}%`;
    }

    if (teamPending) {
        document.getElementById("mgrBar").style.width = `0%`;
        document.getElementById("playerBar").style.width = `0%`;
    } else {
        const mg = team.team_management_pct ?? 50;
        const pl = team.team_player_pct ?? 50;
        document.getElementById("mgrBar").style.width = `${mg}%`;
        document.getElementById("playerBar").style.width = `${pl}%`;
    }

    document.getElementById("roleNotes").innerHTML = `
        <strong>Thinking/Action:</strong> ${thinkPending ? 'Pending' : (think.thinking_action_preference || think.orientation || 'Balanced')}<br>
        <strong>Collaboration:</strong> ${teamPending ? 'Pending' : (team.preferred_collaboration_mode || team.dominant_role || 'Contributor')}
    `;
}

function renderKpis(kpis) {
    const tbody = document.getElementById("kpiTableBody");
    if (!kpis || !kpis.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center py-3 text-muted">No KPI metrics computed yet.</td></tr>';
        return;
    }

    tbody.innerHTML = kpis.map(k => {
        if (k.is_pending || k.current_score === null) {
            return `
                <tr>
                    <td><strong>${k.category}</strong></td>
                    <td><span class="badge bg-secondary-subtle text-secondary">Pending</span></td>
                    <td><span class="badge bg-secondary-subtle text-dark">${k.target_score}</span></td>
                    <td><span class="text-muted small">-</span></td>
                    <td><span class="badge bg-secondary">Profile Data Pending</span></td>
                    <td><small class="text-muted">${k.recommendation}</small></td>
                </tr>
            `;
        }

        const statusBadge = k.gap === 0
            ? '<span class="badge bg-success-subtle text-success">Target Met</span>'
            : (k.gap <= 10
                ? '<span class="badge bg-info-subtle text-info">Minor Gap</span>'
                : '<span class="badge bg-warning-subtle text-warning">Focus Area</span>');

        return `
            <tr>
                <td><strong>${k.category}</strong></td>
                <td><span class="badge bg-primary-subtle text-primary fw-bold">${k.current_score}</span></td>
                <td><span class="badge bg-secondary-subtle text-dark">${k.target_score}</span></td>
                <td><span class="text-${k.gap === 0 ? 'success' : 'danger'} fw-bold">${k.gap > 0 ? '-' + k.gap : '0'} pts</span></td>
                <td>${statusBadge}</td>
                <td><small class="text-muted">${k.recommendation}</small></td>
            </tr>
        `;
    }).join("");
}
