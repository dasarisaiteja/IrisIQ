import cv2
from skimage.feature import graycomatrix, graycoprops


def extract_glcm(image):

    if image is None:
        return None

    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    glcm = graycomatrix(
        gray,
        distances=[1],
        angles=[0],
        levels=256,
        symmetric=True,
        normed=True
    )

    return {
        "contrast": round(float(graycoprops(glcm, "contrast")[0, 0]), 4),
        "homogeneity": round(float(graycoprops(glcm, "homogeneity")[0, 0]), 4),
        "energy": round(float(graycoprops(glcm, "energy")[0, 0]), 4),
        "correlation": round(float(graycoprops(glcm, "correlation")[0, 0]), 4),
        "dissimilarity": round(float(graycoprops(glcm, "dissimilarity")[0, 0]), 4)
    }