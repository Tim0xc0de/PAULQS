import cv2
import numpy as np
from app.infrastructure.vision.image_processing import get_orange_mask, get_dark_spots

MIN_CUBE_AREA = 2000
MAX_CUBE_RATIO = 0.4
MIN_DOT_AREA = 15
MAX_DOT_AREA = 500
MIN_CIRCULARITY = 0.35


def detect_cube(img) -> dict | None:
    """Erkennt einen orangen Würfel und zählt seine Augen.
    Gibt {"x", "y", "w", "h", "dots"} zurück oder None.
    """
    h_img, w_img = img.shape[:2]
    max_area = h_img * w_img * MAX_CUBE_RATIO

    # Würfel finden
    mask = get_orange_mask(img)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    # Besten Kandidaten wählen: passende Größe, grob quadratisch
    best = None
    best_area = 0
    for c in contours:
        area = cv2.contourArea(c)
        if area < MIN_CUBE_AREA or area > max_area:
            continue
        bx, by, bw, bh = cv2.boundingRect(c)
        aspect = bw / bh if bh > 0 else 0
        if 0.3 < aspect < 3.0 and area > best_area:
            best = c
            best_area = area

    if best is None:
        return None

    x, y, w, h = cv2.boundingRect(best)

    # Augen zählen: nur auf der Würfeloberfläche
    roi_mask = mask[y:y+h, x:x+w]
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    roi_mask_filled = cv2.dilate(roi_mask, kernel, iterations=2)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    roi_gray = gray[y:y+h, x:x+w]
    dark = get_dark_spots(roi_gray)
    dark_on_cube = cv2.bitwise_and(dark, roi_mask_filled)

    dot_contours, _ = cv2.findContours(dark_on_cube, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    dots = 0
    for d in dot_contours:
        area = cv2.contourArea(d)
        if MIN_DOT_AREA < area < MAX_DOT_AREA:
            perimeter = cv2.arcLength(d, True)
            if perimeter > 0:
                circ = 4 * np.pi * area / (perimeter * perimeter)
                if circ > MIN_CIRCULARITY:
                    dots += 1

    return {"x": x, "y": y, "w": w, "h": h, "dots": dots}
