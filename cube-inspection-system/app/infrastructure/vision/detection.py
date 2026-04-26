import cv2
import numpy as np
from app.infrastructure.vision.image_processing import COLOR_RANGES, get_dark_spots

MIN_CUBE_AREA = 2000
MAX_CUBE_RATIO = 0.4
MIN_DOT_AREA = 30
MAX_DOT_AREA = 800
MIN_CIRCULARITY = 0.45


def _get_dot_mask(img, color: str = "orange"):
    """Farbmaske mit kleinem Kernel (3x3).
    
    Schließt winzige Oberflächen-Lücken (Textur),
    aber lässt die Augen-Löcher offen (die sind viel größer).
    Unterstützt alle Farben aus COLOR_RANGES.
    """
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    
    for lower, upper in COLOR_RANGES[color]:
        mask |= cv2.inRange(hsv, lower, upper)
    
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return mask


def detect_color(img, x, y, w, h):
    """Erkennt die dominante Farbe im Wuerfel-ROI.
    
    Berechnet den Median-Hue aller farbigen Pixel (S>80, V>80) im ROI
    und matcht gegen COLOR_RANGES.
    
    Returns:
        (farb_name, bgr_tuple) z.B. ("orange", (0, 165, 255))
    """
    roi = img[y:y+h, x:x+w]
    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    
    # Nur farbige Pixel betrachten (nicht weiss/schwarz/grau)
    sat = hsv_roi[:, :, 1]
    val = hsv_roi[:, :, 2]
    color_mask = (sat > 80) & (val > 80)
    
    if not np.any(color_mask):
        return "unbekannt", (128, 128, 128)
    
    hue_values = hsv_roi[:, :, 0][color_mask]
    median_hue = float(np.median(hue_values))
    
    # Gegen COLOR_RANGES matchen: pruefe ob median_hue in einen Bereich faellt
    for name, ranges in COLOR_RANGES.items():
        if name == "weiss":
            continue  # Weiss hat keine Hue-basierte Erkennung
        for lower, upper in ranges:
            h_low = float(lower[0])
            h_high = float(upper[0])
            if h_low <= median_hue <= h_high:
                # BGR-Referenzfarbe aus dem mittleren HSV-Wert berechnen
                mid_h = int((h_low + h_high) / 2)
                mid_s = int((float(lower[1]) + float(upper[1])) / 2)
                mid_v = int((float(lower[2]) + float(upper[2])) / 2)
                ref_color = np.uint8([[[mid_h, mid_s, mid_v]]])
                bgr = cv2.cvtColor(ref_color, cv2.COLOR_HSV2BGR)[0][0]
                return name, (int(bgr[0]), int(bgr[1]), int(bgr[2]))
    
    return "unbekannt", (128, 128, 128)


def draw_detection(img, detection):
    """Zeichnet Box und Augenzahl ins Bild (in-place)."""
    x, y, w, h = detection["x"], detection["y"], detection["w"], detection["h"]
    cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
    cv2.putText(img, f"Augen: {detection['dots']}", (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)


def detect_cube(img, color: str = "auto", debug: bool = False) -> dict | None:
    """Erkennt einen farbigen Würfel und zählt seine Augen.
    
    Ansatz: Contour-Hierarchie (RETR_CCOMP).
    - Äußere Kontur = Würfelfläche (konfigurierbare Farbe)
    - Innere Konturen = Löcher in der Fläche = Augen
    
    Bei color="auto" werden alle Farben aus COLOR_RANGES durchprobiert
    und die Farbe mit der groessten erkannten Wuerfelfläche gewinnt.
    
    Bei debug=True enthält das Ergebnis zusätzlich:
      - 'mask': Farbmaske (Binärbild)
      - 'dark_mask': Dark-Spots-Maske des ROI (nur wenn Fallback aktiv)
    """
    # Auto-Modus: alle Farben probieren, beste nehmen
    if color == "auto":
        best_result = None
        best_area = 0
        for try_color in COLOR_RANGES:
            if try_color == "weiss":
                continue  # Weiss kollidiert mit weisser Fotobox
            result = detect_cube(img, color=try_color, debug=debug)
            if result is not None:
                area = result["w"] * result["h"]
                if area > best_area:
                    best_area = area
                    best_result = result
        return best_result

    h_img, w_img = img.shape[:2]
    max_area = h_img * w_img * MAX_CUBE_RATIO

    # Farbmaske mit kleinem Kernel (erhält Augen-Löcher)
    mask = _get_dot_mask(img, color)

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

    # Ausreißer entfernen (Ritzen sind viel kleiner als echte Augen)
    if len(candidates) > 2:
        median_area = float(np.median(candidates))
        dots = sum(1 for a in candidates if a > median_area * 0.4)
    else:
        dots = len(candidates)

    # Fallback: Wenn Hierarchie 0 Augen findet (z.B. gleichfarbige Prägung),
    # dunkle Stellen im Würfel-ROI per Helligkeits-Threshold suchen.
    dots_from_fallback = False
    dark_mask = None
    if dots == 0:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Rand abschneiden (10%) → Kantenartefakte am Würfelrand vermeiden
        m = int(min(w, h) * 0.10)
        roi_gray = gray[y+m:y+h-m, x+m:x+w-m]
        dark_mask = get_dark_spots(roi_gray)
        dot_cnts, _ = cv2.findContours(dark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        fb_areas = []
        for c in dot_cnts:
            a = cv2.contourArea(c)
            if MIN_DOT_AREA < a < MAX_DOT_AREA:
                p = cv2.arcLength(c, True)
                if p > 0 and (4 * np.pi * a / (p ** 2)) > 0.3:
                    fb_areas.append(a)
        # Ausreißer entfernen: Flächen die stark vom Median abweichen
        if len(fb_areas) > 2:
            med = float(np.median(fb_areas))
            fb_areas = [a for a in fb_areas if med * 0.3 < a < med * 3.0]
        dots = len(fb_areas)
        dots_from_fallback = True

    # Farbe des Wuerfels erkennen
    color_name, color_bgr = detect_color(img, x, y, w, h)

    result = {"x": x, "y": y, "w": w, "h": h, "dots": dots,
              "color": color_name, "color_bgr": color_bgr}
    if debug:
        result["mask"] = mask
        result["dark_mask"] = dark_mask if dots_from_fallback else None
    return result
