import cv2
import numpy as np
import math


def analyze_iris_quality(image, pupil=None, iris=None, bbox=None, detection_confidence=None):
    """
    Analyzes iris capture quality without modifying any model predictions.
    
    Parameters:
        image: BGR numpy array (crop or full frame)
        pupil: tuple (px, py, pr) or None
        iris: tuple (ix, iy, ir) or None
        bbox: tuple (x1, y1, x2, y2) or None
        detection_confidence: float (0-1) or None
        
    Returns:
        dict: Quality metrics with scores, categories, and usable iris percentage.
    """
    if image is None or image.size == 0:
        return {
            "image_quality": "Unusable",
            "capture_quality_score": 0.0,
            "blur_score": 0.0,
            "is_blur": True,
            "brightness": 0.0,
            "brightness_status": "Too Dark",
            "contrast": 0.0,
            "contrast_status": "Poor",
            "eye_visibility": 0.0,
            "iris_visibility": 0.0,
            "occlusion_percentage": 100.0,
            "segmentation_confidence": 0.0,
            "usable_iris_percentage": 0.0,
            "source": "rule-based",
            "notes": "No image data provided"
        }

    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()

    # 1. Blur Analysis (Laplacian variance)
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    blur_score = min(100.0, round((laplacian_var / 120.0) * 100.0, 1))
    is_blurry = laplacian_var < 20.0

    # 2. Brightness Analysis (Mean pixel luminance)
    mean_brightness = float(np.mean(gray))
    if mean_brightness < 45.0:
        brightness_status = "Underexposed"
    elif mean_brightness > 210.0:
        brightness_status = "Overexposed"
    else:
        brightness_status = "Optimal"
    brightness_score = max(0.0, min(100.0, 100.0 - (abs(mean_brightness - 128.0) / 128.0) * 100.0))

    # 3. Contrast Analysis (RMS contrast: standard deviation of luminance)
    contrast_val = float(np.std(gray))
    contrast_score = min(100.0, round((contrast_val / 65.0) * 100.0, 1))
    if contrast_val < 25.0:
        contrast_status = "Low Contrast"
    elif contrast_val > 75.0:
        contrast_status = "High Contrast"
    else:
        contrast_status = "Well Balanced"

    # 4. Eye Visibility
    if detection_confidence is not None:
        eye_visibility = round(float(detection_confidence) * 100.0, 1)
    elif bbox is not None:
        eye_visibility = 90.0
    else:
        eye_visibility = 80.0 if (w >= 100 and h >= 100) else 50.0

    # 5. Iris Visibility & Segmentation Confidence
    has_iris = iris is not None and len(iris) >= 3 and iris[2] > 0
    has_pupil = pupil is not None and len(pupil) >= 3 and pupil[2] > 0

    if has_iris and has_pupil:
        ix, iy, ir = int(iris[0]), int(iris[1]), int(iris[2])
        px, py, pr = int(pupil[0]), int(pupil[1]), int(pupil[2])

        # Concentricity check
        concentric_distance = math.sqrt((ix - px) ** 2 + (iy - py) ** 2)
        concentric_ratio = concentric_distance / max(1.0, float(ir))

        # Size plausibility
        ratio = pr / max(1.0, float(ir))
        ratio_valid = 0.15 <= ratio <= 0.75

        # Segmentation confidence based on geometric consistency
        seg_conf = 85.0
        if concentric_ratio < 0.25:
            seg_conf += 10.0
        else:
            seg_conf -= min(40.0, concentric_ratio * 100.0)

        if ratio_valid:
            seg_conf += 5.0
        else:
            seg_conf -= 30.0

        segmentation_confidence = max(10.0, min(99.0, round(seg_conf, 1)))
        iris_visibility = max(10.0, min(99.0, round(seg_conf * 0.95, 1)))

        # 6. Occlusion & Usable Iris Percentage
        mask = np.zeros(gray.shape, dtype=np.uint8)
        cv2.circle(mask, (ix, iy), ir, 255, -1)
        cv2.circle(mask, (px, py), pr, 0, -1)

        total_iris_pixels = int(np.count_nonzero(mask))
        if total_iris_pixels > 0:
            iris_pixels = gray[mask > 0]
            occluded_reflections = np.count_nonzero(iris_pixels > 245)
            occluded_shadows = np.count_nonzero(iris_pixels < 20)
            occluded_count = occluded_reflections + occluded_shadows

            occlusion_ratio = occluded_count / float(total_iris_pixels)
            occlusion_percentage = round(min(100.0, occlusion_ratio * 100.0), 1)
            usable_iris_percentage = round(max(0.0, 100.0 - occlusion_percentage), 1)
        else:
            occlusion_percentage = 40.0
            usable_iris_percentage = 60.0
    else:
        segmentation_confidence = 40.0
        iris_visibility = 45.0
        occlusion_percentage = 35.0
        usable_iris_percentage = 65.0

    # 7. Composite Capture Quality Score (0-100)
    composite_score = (
        blur_score * 0.30 +
        usable_iris_percentage * 0.25 +
        segmentation_confidence * 0.20 +
        contrast_score * 0.15 +
        brightness_score * 0.10
    )
    capture_quality_score = round(max(0.0, min(100.0, composite_score)), 1)

    if capture_quality_score >= 80.0:
        image_quality = "Excellent"
    elif capture_quality_score >= 65.0:
        image_quality = "Good"
    elif capture_quality_score >= 50.0:
        image_quality = "Acceptable"
    else:
        image_quality = "Poor"

    return {
        "image_quality": image_quality,
        "capture_quality_score": capture_quality_score,
        "blur_score": blur_score,
        "is_blur": is_blurry,
        "brightness": round(mean_brightness, 1),
        "brightness_status": brightness_status,
        "contrast": round(contrast_val, 1),
        "contrast_status": contrast_status,
        "eye_visibility": eye_visibility,
        "iris_visibility": iris_visibility,
        "occlusion_percentage": occlusion_percentage,
        "segmentation_confidence": segmentation_confidence,
        "usable_iris_percentage": usable_iris_percentage,
        "source": "rule-based",
        "notes": "Calculated via geometric iris boundaries and pixel distribution"
    }
