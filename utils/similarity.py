import numpy as np


def cosine_similarity(vec1, vec2):

    vec1 = np.array(
        vec1,
        dtype=np.float32
    )

    vec2 = np.array(
        vec2,
        dtype=np.float32
    )

    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    similarity = np.dot(
        vec1,
        vec2
    ) / (norm1 * norm2)

    similarity = np.clip(
        similarity,
        0,
        1
    )

    return float(similarity)