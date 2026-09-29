const fs = require('fs');

function checkIds(file, ids) {
    const content = fs.readFileSync('static/' + file, 'utf8');
    const missing = ids.filter(id => !content.includes('id="' + id + '"') && !content.includes("id='" + id + "'"));
    if (missing.length > 0) {
        console.error('MISSING IDs in ' + file + ':', missing);
        process.exitCode = 1;
    } else {
        console.log('ALL ' + ids.length + ' IDs verified in ' + file);
    }
}

checkIds('register.html', [
    'employee_code', 'user_name', 'department', 'designation',
    'gender', 'age', 'dob', 'blood_group', 'mobile', 'email',
    'address', 'video', 'canvas', 'status', 'counter', 'progressBar', 'registerBtn'
]);

checkIds('camera.html', [
    'video', 'canvas', 'captureBtn', 'loading', 'scanStatus',
    'confidence', 'eyeColor', 'pupilRadius', 'irisRadius', 'preview'
]);

checkIds('dashboard.html', [
    'sidebar', 'mainContent', 'toggleSidebar', 'searchEmployee', 'todayDate', 'totalUsers',
    'totalScans', 'verifiedUsers', 'notMatched', 'totalStudents',
    'completedAssessments', 'reportsGenerated', 'pendingAssessments',
    'profilesGenerated', 'careerRecommendations', 'streamRecommendations',
    'verificationChart', 'accuracyChart', 'scanChart', 'weeklyChart', 'reportChart',
    'recentTable', 'scanTable', 'activityList'
]);

checkIds('report.html', [
    'reportRoot', 'downloadPdf', 'report_id', 'recognition_id', 'scan_date', 'scan_time',
    'eye_side', 'similarity', 'similarity_progress', 'match_status', 'detection_confidence',
    'confidence', 'processing_status', 'header_status', 'verification_note',
    'employee_name', 'employee_code', 'department', 'designation', 'gender', 'age',
    'blood_group', 'employee_photo', 'captured_eye', 'crop_image', 'segment_image',
    'normalized_image', 'lbp_image', 'gabor_image', 'image_width', 'image_height',
    'quality_detection', 'quality_status', 'quality_note', 'pupil_radius', 'iris_radius',
    'entropy', 'eye_color', 'leadership_bar', 'leadership_value', 'confidence_bar',
    'confidence_value', 'creativity_bar', 'creativity_value', 'adaptability_bar',
    'adaptability_value', 'decision_bar', 'decision_value', 'final_observation',
    'timeline', 'employee_gallery'
]);
