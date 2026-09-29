# Official IRIS Report Contract Discovery & Field-by-Field Mapping (Phase 5A)

**Phase:** Phase 5A — Official IRIS Report Contract Discovery & Field Mapping  
**Authority Documents:** `IRIS_Backend_Detailed_Requirements.docx` & `IRIS_Frontend_Detailed_Requirements.docx`  
**Discovered Source PDF:** `/Users/dasarisaiteja/Downloads/sample_report.pdf` ("Brain Core / Eye 2 I through AI", 61 pages)  
**Status:** **DISCOVERY & AUDIT COMPLETE (READ-ONLY)**

---

## 1. Executive Summary & Ground Rules

This document establishes the official field-by-field mapping between:
1. **Official Approved IRIS Report Contract** (defined in Backend Requirements Section 13 & Frontend Requirements Section 16).
2. **Discovered Report Source Template** (`sample_report.pdf` / ARIDGE Eye 2 I 61-page report).
3. **Current Phase 4 Persisted `analysis_results` Data** (bilateral iris geometry, quality, color, texture, and symmetry).
4. **Existing Legacy System Data** (`student_profiles`, `student_assessments`, `academic_records`, `report_versions`).

### Anti-Fabrication Rule (Part 4)
In strict compliance with user instructions:
- **Zero invented scores, IQ values, personality traits, or behaviour predictions.**
- **No conversion of biometric iris measurements into psychological claims.**
- Every field without a scientifically defensible or implemented data source is explicitly marked **MISSING SOURCE** or **UNSUPPORTED BY CURRENT PIPELINE**.

---

## 2. Source Type Classification Taxonomy

Every field in the mapping is strictly categorized by its authoritative source type:
- **`iris-derived`**: Derived directly from the physical iris image (pupil/iris radii, ratios, geometry, eye color, concentricity).
- **`ML-derived`**: Computed by machine learning / computer vision models (segmentation, LBP texture histograms, cosine similarity).
- **`rule-based`**: Computed by deterministic algorithms (quality thresholds, blur variance checks, lighting scoring).
- **`assessment-derived`**: Originating from assessment workflow events or psychometric questionnaires.
- **`profile-derived`**: Sourced from registered student demographic profile fields.
- **`academic-derived`**: Sourced from formal academic grade submissions.
- **`counselling-derived`**: Sourced from counsellor assignments, reviews, notes, and follow-up records.
- **`report metadata`**: System-generated report identifiers, timestamps, version numbers, and PDF paths.

---

## 3. Comprehensive Field-by-Field Mapping Table

| Official Section | Official Field | Approved Report Label / Source Label | Source Data Location | Source Type | Transformation / Derivation | Nullable? | Status |
|---|---|---|---|---|---|---|---|
| **student** | `student_id` | Student ID / Customer Code | `students.student_id` | `profile-derived` | Direct mapping from registered student | No | **AVAILABLE** |
| **student** | `student_name` | Student Name / Customer Name | `students.student_name` | `profile-derived` | Direct mapping from registered student | No | **AVAILABLE** |
| **student** | `age` | Age / Date of Birth | `student_profiles.age` | `profile-derived` | Direct or computed from DOB | Yes | **AVAILABLE (OPTIONAL)** |
| **student** | `gender` | Gender | `student_profiles.gender` | `profile-derived` | Direct mapping | Yes | **AVAILABLE (OPTIONAL)** |
| **student** | `school_college` | Institution / School | `student_profiles.school_college` | `profile-derived` | Direct mapping | Yes | **AVAILABLE (OPTIONAL)** |
| **student** | `stream` | Academic Stream | `student_profiles.stream` | `profile-derived` | Direct mapping | Yes | **AVAILABLE (OPTIONAL)** |
| **student** | `course` | Course / Grade | `student_profiles.course` | `profile-derived` | Direct mapping | Yes | **AVAILABLE (OPTIONAL)** |
| **student** | `location` | Location / City | `student_profiles.location` | `profile-derived` | Direct mapping | Yes | **AVAILABLE (OPTIONAL)** |
| **student** | `photo_url` | Candidate Photo | `student_profiles.photo_path` | `profile-derived` | Mapped to authenticated `/api/media` | Yes | **AVAILABLE (OPTIONAL)** |
| **assessment** | `assessment_id` | Assessment ID | `assessments.assessment_id` | `assessment-derived` | Formatted `ASM-YYYYMMDD-XXXXXX` | No | **AVAILABLE** |
| **assessment** | `assessment_date` | Assessment Date | `assessments.created_at` | `assessment-derived` | Extracted date component | No | **AVAILABLE** |
| **assessment** | `workflow_status` | Assessment Status | `assessments.status` | `assessment-derived` | Authoritative state machine value | No | **AVAILABLE** |
| **assessment** | `completed_at` | Completion Timestamp | `assessments.completed_at` | `assessment-derived` | Timestamp of dual-eye completion | Yes | **AVAILABLE** |
| **eye_scan** | `left_scan.scan_id` | Left Eye Scan ID | `eye_scans.scan_id` (LEFT) | `iris-derived` | Formatted `SCN-YYYYMMDD-LEFT-XXXX` | No | **AVAILABLE** |
| **eye_scan** | `left_scan.status` | Left Eye Scan Status | `eye_scans.status` (LEFT) | `rule-based` | Must be `Completed` | No | **AVAILABLE** |
| **eye_scan** | `left_scan.quality_score` | Left Eye Quality (%) | `analysis_results.left_eye.quality.capture_quality_score` | `rule-based` | Derived from clarity, blur, contrast | No | **AVAILABLE** |
| **eye_scan** | `left_scan.blur_score` | Left Eye Focus/Sharpness | `analysis_results.left_eye.quality.blur_score` | `rule-based` | Laplacian variance normalized score | No | **AVAILABLE** |
| **eye_scan** | `left_scan.detected_color` | Left Eye Color | `analysis_results.left_eye.color.eye_color` | `iris-derived` | RGB/HSV dominant color category | No | **AVAILABLE** |
| **eye_scan** | `left_scan.pupil_radius` | Left Pupil Radius (px) | `analysis_results.left_eye.features.pupil_radius` | `iris-derived` | Hough circle radius | No | **AVAILABLE** |
| **eye_scan** | `left_scan.iris_radius` | Left Iris Radius (px) | `analysis_results.left_eye.features.iris_radius` | `iris-derived` | Hough circle radius | No | **AVAILABLE** |
| **eye_scan** | `left_scan.pupil_iris_ratio` | Left Pupil-to-Iris Ratio | `analysis_results.left_eye.features.pupil_iris_ratio` | `iris-derived` | Ratio calculation: `pr / ir` | No | **AVAILABLE** |
| **eye_scan** | `left_scan.image_ref` | Left Eye Processed Image | `eye_scans.file_reference` | `iris-derived` | Secure relative file reference | No | **AVAILABLE** |
| **eye_scan** | `right_scan.scan_id` | Right Eye Scan ID | `eye_scans.scan_id` (RIGHT) | `iris-derived` | Formatted `SCN-YYYYMMDD-RIGHT-XXXX` | No | **AVAILABLE** |
| **eye_scan** | `right_scan.status` | Right Eye Scan Status | `eye_scans.status` (RIGHT) | `rule-based` | Must be `Completed` | No | **AVAILABLE** |
| **eye_scan** | `right_scan.quality_score` | Right Eye Quality (%) | `analysis_results.right_eye.quality.capture_quality_score` | `rule-based` | Derived from clarity, blur, contrast | No | **AVAILABLE** |
| **eye_scan** | `right_scan.blur_score` | Right Eye Focus/Sharpness | `analysis_results.right_eye.quality.blur_score` | `rule-based` | Laplacian variance normalized score | No | **AVAILABLE** |
| **eye_scan** | `right_scan.detected_color` | Right Eye Color | `analysis_results.right_eye.color.eye_color` | `iris-derived` | RGB/HSV dominant color category | No | **AVAILABLE** |
| **eye_scan** | `right_scan.pupil_radius` | Right Pupil Radius (px) | `analysis_results.right_eye.features.pupil_radius` | `iris-derived` | Hough circle radius | No | **AVAILABLE** |
| **eye_scan** | `right_scan.iris_radius` | Right Iris Radius (px) | `analysis_results.right_eye.features.iris_radius` | `iris-derived` | Hough circle radius | No | **AVAILABLE** |
| **eye_scan** | `right_scan.pupil_iris_ratio` | Right Pupil-to-Iris Ratio | `analysis_results.right_eye.features.pupil_iris_ratio` | `iris-derived` | Ratio calculation: `pr / ir` | No | **AVAILABLE** |
| **eye_scan** | `right_scan.image_ref` | Right Eye Processed Image | `eye_scans.file_reference` | `iris-derived` | Secure relative file reference | No | **AVAILABLE** |
| **overall_result** | `combined_capture_quality` | Average Biometric Quality | `analysis_results.bilateral_analysis.average_quality_score` | `rule-based` | Mean of Left & Right quality | No | **AVAILABLE** |
| **overall_result** | `bilateral_symmetry_delta` | Pupil Diameter Delta | `analysis_results.bilateral_analysis.pupil_radius_delta` | `iris-derived` | Absolute difference `abs(pr_L - pr_R)` | No | **AVAILABLE** |
| **overall_result** | `pupil_iris_ratio_delta` | Dilatation Delta | `analysis_results.bilateral_analysis.pupil_iris_ratio_delta` | `iris-derived` | Absolute difference of ratios | No | **AVAILABLE** |
| **overall_result** | `bilateral_similarity` | Bilateral Geometric Match | `analysis_results.bilateral_analysis.bilateral_geometric_similarity` | `ML-derived` | Cosine similarity of feature vectors | No | **AVAILABLE** |
| **overall_result** | `color_consistency` | Bilateral Color Agreement | `analysis_results.bilateral_analysis.color_match` | `iris-derived` | Boolean match of detected eye colors | No | **AVAILABLE** |
| **overall_result** | `biometric_summary` | Biometric Assessment Summary | `analysis_results` summary | `rule-based` | Generated factual synthesis of scan | No | **AVAILABLE** |
| **overall_result** | `cognitive_index` | Overall Cognitive Score | *None in current pipeline* | `N/A` | *Cannot be derived from iris* | Yes | **UNSUPPORTED BY CURRENT PIPELINE** |
| **overall_result** | `neuron_count` | Brain Neuron Distribution | *None in current pipeline* | `N/A` | *Iridology claim; scientifically invalid* | Yes | **UNSUPPORTED BY CURRENT PIPELINE** |
| **behaviour** | `categories` | Behavioral Traits | `student_assessments` (if completed) | `assessment-derived` | Requires psychometric questionnaire | Yes | **MISSING SOURCE (CURRENT FLOW)** |
| **behaviour** | `scores` | Behavioral Indicator Scores | `student_assessments` (if completed) | `assessment-derived` | Requires psychometric questionnaire | Yes | **MISSING SOURCE (CURRENT FLOW)** |
| **behaviour** | `descriptions` | Behavioral Descriptions | `student_assessments` (if completed) | `assessment-derived` | Requires psychometric questionnaire | Yes | **MISSING SOURCE (CURRENT FLOW)** |
| **personality** | `traits` | Big Five Traits (OCEAN) | `student_assessments` (if completed) | `assessment-derived` | Requires psychometric questionnaire | Yes | **MISSING SOURCE (CURRENT FLOW)** |
| **personality** | `scores` | Personality Domain Scores | `student_assessments` (if completed) | `assessment-derived` | Requires psychometric questionnaire | Yes | **MISSING SOURCE (CURRENT FLOW)** |
| **personality** | `levels` | Trait Band (High/Mod/Low) | `student_assessments` (if completed) | `assessment-derived` | Requires psychometric questionnaire | Yes | **MISSING SOURCE (CURRENT FLOW)** |
| **subjects_interest** | `subject_scores` | Academic Subject Mastery | `academic_records` (if submitted) | `academic-derived` | Requires school marks submission | Yes | **MISSING SOURCE (CURRENT FLOW)** |
| **subjects_interest** | `interests` | Student Interest Categories | `student_interests` (if submitted) | `profile-derived` | Requires profile questionnaire | Yes | **MISSING SOURCE (CURRENT FLOW)** |
| **recommendations** | `stream_recommendations` | Educational Streams (STEM/Comm) | `career_catalog` matching | `rule-based` | Requires marks/questionnaires | Yes | **MISSING SOURCE (CURRENT FLOW)** |
| **recommendations** | `career_recommendations` | Top Career Affinities | `career_catalog` matching | `rule-based` | Requires marks/questionnaires | Yes | **MISSING SOURCE (CURRENT FLOW)** |
| **recommendations** | `activity_recommendations`| Co-Curricular & Sports | `activity_catalog` matching | `rule-based` | Requires profile questionnaire | Yes | **MISSING SOURCE (CURRENT FLOW)** |
| **counselling** | `assigned_counsellor_id` | Assigned Counsellor | `counsellor_assignments.counsellor_id` | `counselling-derived`| Active assignment record | Yes | **AVAILABLE** |
| **counselling** | `assigned_at` | Assignment Date | `counsellor_assignments.assigned_at` | `counselling-derived`| Timestamp of counsellor assignment | Yes | **AVAILABLE** |
| **counselling** | `reviewed_status` | Report Review Status | `reports.reviewed_status` | `counselling-derived`| Boolean (0 = Pending, 1 = Reviewed)| No | **AVAILABLE** |
| **counselling** | `reviewed_by` | Reviewing Counsellor | `reports.reviewed_by` | `counselling-derived`| Counsellor username who reviewed | Yes | **AVAILABLE** |
| **counselling** | `reviewed_at` | Review Timestamp | `reports.reviewed_at` | `counselling-derived`| Timestamp when marked reviewed | Yes | **AVAILABLE** |
| **counselling** | `counselling_notes` | Counsellor Notes | `counselling_notes.note` | `counselling-derived`| Text notes entered by counsellor | Yes | **AVAILABLE** |
| **counselling** | `follow_ups` | Scheduled Follow-ups | `follow_ups` records | `counselling-derived`| List of scheduled follow-up actions | Yes | **AVAILABLE** |
| **report_meta** | `report_id` | Report ID | `reports.report_id` | `report metadata` | Formatted `REP-YYYYMMDD-XXXXXX` | No | **AVAILABLE** |
| **report_meta** | `version` | Report Version | `reports.version` | `report metadata` | Semantic version `'v1.0'` | No | **AVAILABLE** |
| **report_meta** | `status` | Report Generation Status | `reports.status` | `report metadata` | `REPORT_READY` / `REPORT_GENERATING` | No | **AVAILABLE** |
| **report_meta** | `generated_date` | Generation Timestamp | `reports.generated_at` | `report metadata` | ISO UTC timestamp | No | **AVAILABLE** |
| **report_meta** | `pdf_reference` | PDF File Reference | `reports.pdf_reference` | `report metadata` | Secure relative path `reports/{id}.pdf` | Yes | **AVAILABLE** |
| **report_meta** | `pipeline_version` | AI Engine Version | `analysis_results.model_metadata.pipeline_version` | `report metadata` | `'iris-analysis-v1.0'` | No | **AVAILABLE** |

---

## 4. Key Takeaways & Field Availability Summary

| Section | Total Defined Fields | Immediately Available from Current System | Missing / Pending Questionnaire Input | Scientifically Unsupported |
|---|---|---|---|---|
| **student** | 9 | 9 (2 required, 7 optional) | 0 | 0 |
| **assessment** | 4 | 4 | 0 | 0 |
| **eye_scan** | 18 | 18 | 0 | 0 |
| **overall_result** | 8 | 6 | 0 | 2 (Cognitive Index, Neurons) |
| **behaviour** | 3 | 0 | 3 | 0 |
| **personality** | 3 | 0 | 3 | 0 |
| **subjects_interest** | 2 | 0 | 2 | 0 |
| **recommendations** | 3 | 0 | 3 | 0 |
| **counselling** | 7 | 7 | 0 | 0 |
| **report_meta** | 6 | 6 | 0 | 0 |
| **TOTAL** | **55** | **45** | **8** | **2** |

---

## 5. Architectural Recommendations for Phase 5B

1. **Official Report Payload Structure:**
   The report JSON must cleanly separate:
   - **`biometric_intelligence`**: 100% populated with verified bilateral dual-eye metrics from `analysis_results` (quality, geometry, colors, symmetry).
   - **`student` & `assessment`**: 100% populated from `students` and `assessments`.
   - **`counselling`**: 100% populated from `counsellor_assignments`, `counselling_notes`, and `follow_ups`.
   - **`behaviour`, `personality`, `subjects_interest`, `recommendations`**: Marked as `status: "PENDING_ASSESSMENT_INPUT"` or populated only if legacy assessment questionnaires are linked, ensuring zero data fabrication.
2. **Server-Side PDF Generation:**
   Generate official PDF documents using ReportLab on the backend rather than unreliable client-side canvas capture, ensuring strict parity between API JSON and the printed document.
