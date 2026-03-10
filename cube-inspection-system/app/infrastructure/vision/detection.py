import cv2
from app.infrastructure.vision.image_processing import get_orange_mask, get_dark_spots

MIN_CUBE_AREA = 1000
MIN_DOT_AREA = 10
MAX_DOT_AREA = 300


def detect_cube(img) -> dict | None:
    """Erkennt einen orangen Würfel und zählt seine Augen.
    Gibt {"x", "y", "w", "h", "dots"} zurück oder None.
    """
    # Würfel finden
    mask = get_orange_mask(img)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    largest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(largest) < MIN_CUBE_AREA:
        return None

    x, y, w, h = cv2.boundingRect(largest)

    # Augen zählen im Würfelbereich
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    roi = gray[y:y+h, x:x+w]
    thresh = get_dark_spots(roi)
    dot_contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    dots = sum(1 for d in dot_contours if MIN_DOT_AREA < cv2.contourArea(d) < MAX_DOT_AREA)

    return {"x": x, "y": y, "w": w, "h": h, "dots": dots}
