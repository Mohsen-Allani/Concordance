from pathlib import Path

import cv2
import numpy as np

MAX_SKEW_DEG = 10.0   # ignore rotations larger than this — they're detection errors, not real skew


def preprocess(image_path: Path, out_path: Path) -> Path:
    img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    img = _deskew_safe(img)
    img = cv2.fastNlMeansDenoising(img, h=7)                 # gentler denoise
    img = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8)).apply(img)
    cv2.imwrite(str(out_path), img)
    return out_path


def _deskew_safe(img):
    coords = np.column_stack(np.where(img < 200))
    if coords.size == 0:
        return img

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle

    if abs(angle) > MAX_SKEW_DEG:      # clamp: refuse implausible rotations
        return img
    if abs(angle) < 0.5:               # already straight, don't touch
        return img

    h, w = img.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)

    cos, sin = abs(m[0, 0]), abs(m[0, 1])   # expand canvas so nothing is cropped
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    m[0, 2] += (new_w - w) / 2
    m[1, 2] += (new_h - h) / 2

    return cv2.warpAffine(
        img, m, (new_w, new_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,               # white fill, not smeared edges
    )
