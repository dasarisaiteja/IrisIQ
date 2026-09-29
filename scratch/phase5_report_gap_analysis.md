# Official IRIS Report Layer Gap Analysis & Technical Feasibility Audit (Phase 5A)

**Phase:** Phase 5A — Official IRIS Report Contract Discovery & Field Mapping  
**Authority Documents:** `IRIS_Backend_Detailed_Requirements.docx` & `IRIS_Frontend_Detailed_Requirements.docx`  
**Discovered Reference Document:** `sample_report.pdf` ("Brain Core / Eye 2 I through AI", 61 pages, ARIDGE)  
**Execution Timestamp:** 2026-09-29  
**Status:** **DISCOVERY & AUDIT COMPLETE (READ-ONLY)**

---

## 1. Executive Summary

This gap analysis evaluates the technical, structural, and scientific alignment between the **Official Requirements**, the **Approved Reference Report Template** (`sample_report.pdf`), the **Current Backend Implementation** (Phases 1–4), and the **Current Frontend Capabilities**.

The objective is to establish an unassailable, non-fabricated, and scientifically sound blueprint before implementing Phase 5B (Report Generation, PDF Generation, and Report Viewing).

---

## 2. Report Source Analysis (`sample_report.pdf`)

During Phase 5A discovery, an exhaustive search across the project repository and workspace identified the commercial template document:
- **Location:** `/Users/dasarisaiteja/Downloads/sample_report.pdf`
- **File Size:** 4.7 MB (61 pages)
- **Document Title:** "Brain Core / Iris Analysis – Eye 2 I through AI"
- **Author / Source:** Neha Jain / American Research Institute of Dermis & Genetic Evaluation (`www.aridge.us`)
- **Format:** Microsoft PowerPoint 2010 exported to Adobe PDF (Version 1.5)
- **Content:** 28 chapters covering personality, neuron distribution across brain lobes, critical subjects, critical abilities (IQ/EQ), stream selection, learning styles (VAK), leadership dynamics, corporate abilities, and career catalogs.

### Critical Scientific & Compliance Finding
`sample_report.pdf` relies upon **commercial iridology assertions** that claim a photograph of the human iris directly reveals brain lobe neuron counts (e.g., *"12.46 Billion Left Pre-Frontal Neurons"*), numerical IQ (*"82.79"*), numerical EQ (*"117.72"*), and personality traits.

**In strict compliance with Part 4 and Part 5 of user instructions:**
> *"Do NOT invent psychological meanings from iris images."*  
> *"Do NOT implement claims such as iris determines personality, IQ, behaviour, mental health, learning style, or neuron count."*  
> *"Do not create fabricated confidence values or hard-code arbitrary scores."*

Therefore, the official IRIS report implementation must **never** convert physical iris measurements into pseudoscientific psychological claims. The official report contract must distinguish between **genuine biometric measurements** and **questionnaire/academic indicators**.

---

## 3. Section-by-Section Gap Analysis Matrix

The table below contrasts the Official Requirements against the Reference PDF, Current Backend, and Current Frontend:

| Section | 1. Official Requirement | 2. Approved Reference (`sample_report.pdf`) | 3. Current Backend Source | 4. Current Frontend Capability | 5. Gap Identified | 6. Required Phase 5B Implementation |
|---|---|---|---|---|---|---|
| **Header & Meta** | Report title, Report ID, version, assessment ID, dates, PDF reference | Cover & Index (Pages 1–8): Client Name, Date, Report Title | `reports` table (Phase 1) + `analysis_results.model_metadata` | Stepper indicates Step 5 (Report), but no dedicated report header exists | Backend table exists but no official report generation endpoint (`POST /report/generate`) | Implement `POST /api/assessments/{id}/report/generate` and `GET /api/assessments/{id}/report` returning standard header envelope |
| **Student Info** | Student ID, Name, approved demographic fields (age, gender, school, stream) | Page 8 ("Customer's Details"): Name, DOB, Contact, Email, Address | `students` table (Phase 1 & 2) + `student_profiles` | Student details rendered in registration and scan stages | Fields exist in DB; official report endpoint must serialize them cleanly | Include formatted student sub-object in `GET /report` payload |
| **Bilateral Eye Scan** | Separate LEFT & RIGHT eye scan results, status, quality scores, detected colors, pupil/iris radii | Mentions "Eye 2 I / Iris Analysis" but contains NO real bilateral scan images, radii, or quality metrics | `eye_scans` (Phase 3) + `analysis_results` (Phase 4): Complete pupil/iris circles, quality %, colors, and file refs | Camera UI captures both eyes, but report UI does not yet render bilateral scan comparison cards | Report UI currently does not render bilateral eye scan cards | Create Bilateral Eye Scan component in report UI displaying Left and Right images, quality meters, and geometric radii |
| **Overall Result** | Combined assessment result, average capture quality, bilateral symmetry, factual summary | Page 10 ("Eyes & Brain"): High-level narrative text | `analysis_results.bilateral_analysis`: average quality score, pupil delta, ratio delta, cosine similarity | Only shows completed badge in camera UI | No dedicated summary card combining bilateral metrics in report format | Render Bilateral Symmetry & Capture Quality Summary card in report |
| **Behaviour** | Behavioral categories, indicator scores, descriptions | Page 12, 13, 27, 33: Aggression, impatience, team behaviour | `student_assessments` (if Likert survey submitted); NO iris derivation | Legacy `student_report.html` renders Likert survey scores; new scan flow has no survey | New assessment workflow is scan-only; no survey answers are collected | Mark section as `status: "PENDING_ASSESSMENT_INPUT"` with safe placeholder rather than fabricating scores |
| **Personality** | Personality traits, domain scores, descriptions (Big Five) | Page 12 ("Personality - Strength & Weakness") | `student_assessments` (if Big Five survey submitted); NO iris derivation | Legacy `student_report.html` renders Big Five radar/bars; new scan flow has no survey | Cannot scientifically or legitimately compute personality from iris scan | Mark section as `status: "PENDING_ASSESSMENT_INPUT"` or display only if student has completed survey |
| **Subjects & Interests** | Subject mastery, preferences, interest categories | Page 18 ("Critical Subjects"): Science, Maths, Language | `academic_records` & `student_interests` tables (if entered in profile) | Legacy `student_report.html` renders academic marks table | Registration in Phase 2 only collects ID and Name; academic marks are not entered | Mark section as `status: "PROFILE_DATA_PENDING"` unless academic marks exist in `academic_records` |
| **Recommendations** | Approved assessment recommendations (streams, careers, activities) | Pages 22–25, 44–46: Stream selection, top 10 careers, trending careers | `services/stream_engine.py`, `services/career_engine.py` (legacy rule-based catalog matching) | Legacy `student_report.html` renders recommendations grid | Recommendations require academic + psychometric inputs; scan-only input is insufficient | Provide recommendations only when valid prerequisite inputs exist; otherwise mark Pending |
| **Counselling** | Assigned counsellor, reviewed status, counsellor notes, scheduled follow-ups | Page 8 & Page 60 ("Summary to be discussed with Counsellor") | Phase 1 tables: `counsellor_assignments`, `counselling_notes`, `follow_ups`, `reports.reviewed_status` | No counsellor notes or review UI exists in the new official flow | Backend tables exist; report JSON must serialize assigned counsellor and notes | Include `counselling` object in report payload; support `PATCH /api/assessments/{id}/reviewed` |
| **PDF Generation** | Server-side generated PDF containing identical sections to report UI | 61-page PDF exists as a static PPT export; no dynamic PDF generation exists | **None** on backend. Legacy frontend used `html2pdf.js` client-side capture | Client-side `html2pdf.js` in `student_report.html` generates flawed, slow PDFs | No server-side PDF generator exists in the backend | Implement backend PDF generator using `reportlab` producing official multi-page PDF |

---

## 4. Legacy Report Analysis (`services/report_v2_generator.py` & `api/report.py`)

### 4.1 Legacy V1 Single-Eye Verification Report (`api/report.py`)
- **Endpoint:** `GET /report?report_id={id}`
- **Source:** Reads static JSON files from `outputs/reports/{id}/report.json`.
- **Nature:** An employee/customer verification dossier comparing a captured single-eye webcam photo against an enrolled profile image (`CUS001`, `emp004`).
- **Compatibility:** **NO OFFICIAL EQUIVALENT**. The official product is a student academic/biometric assessment with bilateral LEFT + RIGHT eye scans, not single-eye physical access verification.

### 4.2 Legacy V2 32-Section Holistic Report (`services/report_v2_generator.py`)
- **Endpoint:** `POST /api/profile/{student_id}/report`
- **Source:** Compiles 32 sections stored in `report_versions` (`version_type == 'V2'`).
- **Nature:** Modeled heavily after `sample_report.pdf`, calculating cognitive indices and career recommendations from questionnaire survey answers (`student_assessments`) and school marks (`academic_records`).
- **Compatibility:**
  - `section_02_student_details` $\longrightarrow$ **MAPPABLE WITH VERIFIED TRANSFORMATION** to `student`.
  - `section_04_iris_analysis` & `section_05_iris_quality` $\longrightarrow$ **NO OFFICIAL EQUIVALENT** (legacy V2 only tracks single-eye enrollment photos, not dual-eye scans).
  - `section_06` through `section_27` $\longrightarrow$ **SOURCE MISSING FOR SCAN-ONLY FLOW**. In the official Phase 2–4 workflow, students register with ID + Name and perform dual-eye scanning. They do not complete the 100+ psychometric questions required by `report_v2_generator.py`.
- **Verdict:** Legacy 32-section report data must be **preserved 100% read-only** for historical integrity. It **must not** be migrated wholesale into the official assessment report contract.

---

## 5. Phase 4 `analysis_results` Compatibility

The Phase 4 `analysis_results` table stores authoritative, non-fabricated bilateral metrics:
- `left_eye`: `pupil_circle`, `iris_circle`, `quality` (`capture_quality_score`, `blur_score`, `brightness`, `contrast`), `features` (`pupil_iris_ratio`, `center_distance`, `iris_thickness`), `color` (`eye_color`), `texture_descriptors` (`lbp_mean`, `lbp_std`).
- `right_eye`: `pupil_circle`, `iris_circle`, `quality`, `features`, `color`, `texture_descriptors`.
- `bilateral_analysis`: `pupil_radius_delta`, `pupil_iris_ratio_delta`, `average_quality_score`, `color_match`, `bilateral_geometric_similarity`.
- `provenance`: explicitly tagged as `iris-derived`, `rule-based`, `ml-derived`.
- `timing` & `model_metadata`: engine version (`iris-analysis-v1.0`), duration, OpenCV version.

### Mapping to Official Report:
1. `analysis_results.left_eye` $\longrightarrow$ Maps 1:1 to `report.eye_scan.left`.
2. `analysis_results.right_eye` $\longrightarrow$ Maps 1:1 to `report.eye_scan.right`.
3. `analysis_results.bilateral_analysis` $\longrightarrow$ Maps 1:1 to `report.overall_result`.
4. `analysis_results.model_metadata` $\longrightarrow$ Maps 1:1 to `report.report_meta`.

**Result:** The bilateral biometric portion of the official report is **100% supported and ready for immediate consumption**.

---

## 6. Report Versioning & Regeneration Architecture

The Phase 1 `reports` table supports full versioning:
- `report_id`: Unique identifier formatted `REP-{YYYYMMDD}-{UUID}`.
- `assessment_id`: Foreign key linked to `assessments`.
- `version`: Version string (default `'v1.0'`).
- `status`: State machine: `REPORT_GENERATING` $\longrightarrow$ `REPORT_READY` (or `FAILED`).
- `pdf_reference`: Relative path to generated PDF: `reports/{report_id}.pdf`.
- `reviewed_status`, `reviewed_by`, `reviewed_at`: Counsellor sign-off metadata.
- `UNIQUE(assessment_id, version)` constraint: Ensures an assessment cannot create duplicate uncontrolled report rows for the same version.

---

## 7. BLOCKERS BEFORE PHASE 5B

Before implementing Phase 5B code, the following three blockers must be formally resolved:

### Blocker 1: Missing Questionnaire Input for Psychological & Behavioral Sections
- **The Issue:** The official report contract defines `behaviour`, `personality`, `subjects_interest`, and `recommendations` as logical sections. However, the official workflow from Phase 2 to Phase 4 captures **only student registration and dual iris scans**.
- **The Constraint:** Iris images scientifically **cannot** determine personality, behavior, IQ, or career aptitude. Fabricating these values is strictly prohibited.
- **The Solution:** For assessments without submitted questionnaires, Phase 5B must return these sections with `status: "PENDING_ASSESSMENT_INPUT"` (or `null`/omitted), and the report UI must render a clean `"Questionnaire Assessment Pending"` banner rather than fabricating false scores.

### Blocker 2: Server-Side PDF Rendering Library Prerequisite
- **The Issue:** Generating a server-side PDF requires a dedicated rendering library. Currently, `reportlab` or `weasyprint` is not installed in the project environment (`ai-env`).
- **The Solution:** Install `reportlab` into `ai-env` during Phase 5B setup to generate clean, multi-page vector PDFs mirroring the structured JSON.

### Blocker 3: Scope of Official Report Contract
- **The Issue:** The legacy system has 32 sprawling sections in `services/report_v2_generator.py`, whereas the official requirements document specifies **10 logical sections**:
  1. `student`
  2. `assessment`
  3. `eye_scan`
  4. `overall_result`
  5. `behaviour`
  6. `personality`
  7. `subjects_interest`
  8. `recommendations`
  9. `counselling`
  10. `report_meta`
- **The Solution:** Phase 5B must implement the **official 10-section contract** as the primary schema in `api/assessments/{id}/report`, keeping the legacy 32-section report isolated in `api/profile/{id}/report`.
