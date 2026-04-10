import cv2
import numpy as np
from app.infrastructure.vision.image_processing import ORANGE_LOWER, ORANGE_UPPER

MIN_CUBE_AREA = 2000
MAX_CUBE_RATIO = 0.4
MIN_DOT_AREA = 30
MAX_DOT_AREA = 800
MIN_CIRCULARITY = 0.45


def _get_dot_mask(img):
    """Orange-Maske mit kleinem Kernel (3x3).
    
    Schließt winzige Oberflächen-Lücken (Textur),
    aber lässt die Augen-Löcher offen (die sind viel größer).
    """
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, ORANGE_LOWER, ORANGE_UPPER)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return mask


def detect_cube(img) -> dict | None:
    """Erkennt einen orangen Würfel und zählt seine Augen.
    
    Ansatz: Contour-Hierarchie (RETR_CCOMP).
    - Äußere Kontur = Würfelfläche (orange)
    - Innere Konturen = Löcher in der Fläche = Augen
    
    Kein Grauwert-Threshold, kein Convex Hull, kein Erosion.
    OpenCV findet die Löcher direkt.
    """
    h_img, w_img = img.shape[:2]
    max_area = h_img * w_img * MAX_CUBE_RATIO

    # Orange-Maske mit kleinem Kernel (erhält Augen-Löcher)
    mask = _get_dot_mask(img)

    # Konturen MIT Hierarchie finden (2-Level: außen + Löcher)
    contours, hierarchy = cv2.findContours(
        mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours or hierarchy is None:
        return None

    hierarchy = hierarchy[0]

    # Würfel = größte äußere Kontur (kein Parent)
    cube_idx = -1
    cube_area = 0
    for i in range(len(contours)):
        if hierarchy[i][3] != -1:
            continue  # hat Parent → ist ein Loch, kein äußerer Rand
        area = cv2.contourArea(contours[i])
        if area < MIN_CUBE_AREA or area > max_area:
            continue
        bx, by, bw, bh = cv2.boundingRect(contours[i])
        aspect = bw / bh if bh > 0 else 0
        if 0.3 < aspect < 3.0 and area > cube_area:
            cube_idx = i
            cube_area = area

    if cube_idx == -1:
        return None

    x, y, w, h = cv2.boundingRect(contours[cube_idx])

    # Augen = innere Konturen (Kinder) des Würfels
    # Schritt 1: Alle Kandidaten sammeln (lockerer Filter)
    candidates = []
    child_idx = hierarchy[cube_idx][2]  # erstes Kind
    while child_idx != -1:
        area = cv2.contourArea(contours[child_idx])
        if MIN_DOT_AREA < area < MAX_DOT_AREA:
            perimeter = cv2.arcLength(contours[child_idx], True)
            if perimeter > 0:
                circ = 4 * np.pi * area / (perimeter ** 2)
                if circ > MIN_CIRCULARITY:
                    candidates.append(area)
        child_idx = hierarchy[child_idx][0]  # nächstes Geschwister

    # Schritt 2: Ausreißer entfernen (Ritzen sind viel kleiner als echte Augen)
    if len(candidates) > 2:
        median_area = float(np.median(candidates))
        dots = sum(1 for a in candidates if a > median_area * 0.4)
    else:
        dots = len(candidates)

    return {"x": x, "y": y, "w": w, "h": h, "dots": dots}
