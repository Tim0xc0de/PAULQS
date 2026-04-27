import cv2
import numpy as np
from app.infrastructure.vision.image_processing import COLOR_RANGES

# ====================================================================
# PARAMETER
# ====================================================================
MIN_CUBE_AREA = 2000   # px² Mindestflaeche fuer Wuerfel-Kontur
MAX_CUBE_RATIO = 0.5   # Wuerfel max 50% der Bildflaeche
MIN_DOT_CIRC = 0.30    # Mindestrundheit fuer Augen-Konturen
DOT_MARGIN = 0.08      # Augen muessen 8% vom ROI-Rand entfernt sein
DOT_MAX_REL = 0.35     # Auge max 35% der Wuerfelseite
DOT_MIN_REL = 0.04     # Auge mind. 4% der Wuerfelseite
BLACK_BAR_THRESH = 20
BLOCK_SIZE = 51         # Adaptiver Threshold: Nachbarschaftsgroesse
THRESH_C = 10           # Adaptiver Threshold: Empfindlichkeit


# ====================================================================
# HILFSFUNKTIONEN
# ====================================================================

def _crop_black_bars(img):
    """Entfernt schwarze Letterbox-Balken oben/unten (Niryo-Kamera)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    h = gray.shape[0]
    means = np.mean(gray, axis=1)
    top = 0
    for i in range(h):
        if means[i] > BLACK_BAR_THRESH:
            top = i; break
    bottom = h
    for i in range(h - 1, -1, -1):
        if means[i] > BLACK_BAR_THRESH:
            bottom = i + 1; break
    if (bottom - top) < h * 0.5:
        return img
    return img[top:bottom]


def _find_cube_bbox(img, color):
    """Findet Wuerfel-BBox per Farbmaske + solider Morphologie.

    Returns (x, y, w, h) oder None.
    """
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    for lo, hi in COLOR_RANGES[color]:
        mask |= cv2.inRange(hsv, lo, hi)
    # Solide Morphologie: schliesst ALLE Loecher (auch Augen)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    h_img, w_img = img.shape[:2]
    max_a = h_img * w_img * MAX_CUBE_RATIO
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best, best_a = None, 0
    for c in cnts:
        a = cv2.contourArea(c)
        if a < MIN_CUBE_AREA or a > max_a:
            continue
        bx, by, bw, bh = cv2.boundingRect(c)
        asp = bw / bh if bh > 0 else 0
        if 0.4 < asp < 2.5 and a > best_a:
            best, best_a = (bx, by, bw, bh), a
    return best


def _count_dots(gray_roi, cube_w, cube_h):
    """Zaehlt Augen im Graustuf-ROI per adaptivem Threshold + Konturfilter.

    Die Augen sind dunkler als die Wuerfeloberflaeche (Vertiefungen/Schatten).
    Adaptives Thresholding erkennt lokal dunklere Bereiche unabhaengig von
    der absoluten Farbe → funktioniert bei gleichfarbigen Praegungen.

    Returns (dot_count, debug_mask).
    """
    if gray_roi.size == 0:
        return 0, None
    # Rauschen reduzieren, Oberflaechentextur glaetten
    blurred = cv2.GaussianBlur(gray_roi, (7, 7), 0)
    # Lokal dunklere Stellen finden
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, BLOCK_SIZE, THRESH_C
    )
    # Halbmonde schliessen (LED-Schatten)
    k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, k_close)
    # Hohle Ringe fuellen
    cnts_fill, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(thresh, cnts_fill, -1, 255, cv2.FILLED)
    # Noise entfernen
    k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, k_open)

    # Konturen filtern
    cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_dim = max(int(min(cube_w, cube_h) * DOT_MIN_REL), 3)
    max_dim = int(max(cube_w, cube_h) * DOT_MAX_REL)
    roi_h, roi_w = gray_roi.shape[:2]
    margin_x = int(roi_w * DOT_MARGIN)
    margin_y = int(roi_h * DOT_MARGIN)

    candidates = []
    for c in cnts:
        cx, cy, cw, ch = cv2.boundingRect(c)
        # Groesse
        if cw < min_dim or ch < min_dim or cw > max_dim or ch > max_dim:
            continue
        # Position (Rand ausschliessen)
        ccx, ccy = cx + cw // 2, cy + ch // 2
        if ccx < margin_x or ccx > roi_w - margin_x:
            continue
        if ccy < margin_y or ccy > roi_h - margin_y:
            continue
        # Seitenverhaeltnis
        asp = cw / ch if ch > 0 else 0
        if not (0.35 < asp < 2.8):
            continue
        # Rundheit
        area = cv2.contourArea(c)
        peri = cv2.arcLength(c, True)
        if peri > 0:
            circ = 4 * np.pi * area / (peri ** 2)
            if circ >= MIN_DOT_CIRC:
                candidates.append(area)

    # Ausreisser entfernen
    if len(candidates) > 2:
        med = float(np.median(candidates))
        candidates = [a for a in candidates if med * 0.15 < a < med * 6.0]

    return min(len(candidates), 6), thresh


def detect_color(img, x, y, w, h):
    """Erkennt die dominante Farbe im Wuerfel-ROI."""
    roi = img[y:y+h, x:x+w]
    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    sat, val = hsv_roi[:, :, 1], hsv_roi[:, :, 2]
    cmask = (sat > 80) & (val > 80)
    if not np.any(cmask):
        return "unbekannt", (128, 128, 128)
    median_hue = float(np.median(hsv_roi[:, :, 0][cmask]))
    for name, ranges in COLOR_RANGES.items():
        if name == "weiss":
            continue
        for lo, hi in ranges:
            if float(lo[0]) <= median_hue <= float(hi[0]):
                mid = np.uint8([[[int((float(lo[0])+float(hi[0]))/2),
                                  int((float(lo[1])+float(hi[1]))/2),
                                  int((float(lo[2])+float(hi[2]))/2)]]])
                bgr = cv2.cvtColor(mid, cv2.COLOR_HSV2BGR)[0][0]
                return name, (int(bgr[0]), int(bgr[1]), int(bgr[2]))
    return "unbekannt", (128, 128, 128)


def draw_detection(img, detection):
    """Zeichnet Box und Augenzahl ins Bild (in-place)."""
    x, y, w, h = detection["x"], detection["y"], detection["w"], detection["h"]
    cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
    cv2.putText(img, f"Augen: {detection['dots']}", (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)


# ====================================================================
# HAUPTERKENNUNG
# ====================================================================

def detect_cube(img, color: str = "auto", debug: bool = False) -> dict | None:
    """Erkennt einen farbigen Wuerfel und zaehlt seine Augen.

    Ansatz:
      1. Farbmaske (HSV) + solide Morphologie → Wuerfel-BBox
      2. Graustuf-ROI + adaptives Thresholding → Augen zaehlen
         (funktioniert auch bei gleichfarbigen Praegungen)
      3. Konturfilter: Groesse, Position, Form, Rundheit
    """
    img_work = _crop_black_bars(img)

    # Auto-Modus: alle Farben probieren, groessten Wuerfel nehmen
    if color == "auto":
        best, best_a = None, 0
        for c in COLOR_RANGES:
            if c == "weiss":
                continue
            r = detect_cube(img, color=c, debug=debug)
            if r and r["w"] * r["h"] > best_a:
                best_a = r["w"] * r["h"]
                best = r
        return best

    # Schritt 1: Wuerfel finden per Farbmaske
    bbox = _find_cube_bbox(img_work, color)
    if bbox is None:
        return None
    x, y, w, h = bbox

    # Schritt 2: Augen zaehlen per adaptivem Threshold auf Graustufen-ROI
    gray = cv2.cvtColor(img_work, cv2.COLOR_BGR2GRAY)
    m = int(min(w, h) * 0.05)  # Kleiner Rand, um Wuerfelkante auszuschliessen
    roi = gray[y + m:y + h - m, x + m:x + w - m]
    dots, dot_mask = _count_dots(roi, w, h)

    # Farbe erkennen
    color_name, color_bgr = detect_color(img_work, x, y, w, h)

    result = {"x": x, "y": y, "w": w, "h": h, "dots": dots,
              "color": color_name, "color_bgr": color_bgr}
    if debug:
        result["mask"] = dot_mask
        result["dark_mask"] = dot_mask
    return result
