import cv2
import numpy as np

# ====================================================================
# FARB-DEFINITIONEN (HSV-Bereiche)
# ====================================================================
# Setup: Weiße PLA-3D-Druck-Fotobox, weißer LED-Ring oben, Kamera von oben.
# → Hintergrund ist weiß (S ≈ 0, V hoch) und wird durch die hohen
#   Sättigungs-Schwellwerte (≥ 80–150) automatisch ausgefiltert.
#
# Jede Farbe hat eine Liste von (lower, upper)-Tupeln.
# Rot braucht zwei Bereiche, weil Hue in HSV bei 0/180 umschlägt.
COLOR_RANGES = {
    "orange": [
        (np.array([5, 150, 120]),  np.array([25, 255, 255])),
    ],
    "rot": [
        (np.array([0, 100, 100]),  np.array([10, 255, 255])),
        (np.array([160, 100, 100]), np.array([180, 255, 255])),
    ],
    "gelb": [
        (np.array([20, 100, 100]), np.array([35, 255, 255])),
    ],
    "gruen": [
        (np.array([35, 80, 80]),   np.array([85, 255, 255])),
    ],
    "blau": [
        (np.array([100, 100, 80]), np.array([130, 255, 255])),
    ],
    "lila": [
        (np.array([125, 80, 80]),  np.array([155, 255, 255])),
    ],
    # HINWEIS: "weiss" ist NICHT nutzbar mit der weißen Fotobox,
    # da Hintergrund und Würfel denselben HSV-Bereich haben.
    # Nur verwenden, wenn ein dunkler/farbiger Hintergrund genutzt wird.
    "weiss": [
        (np.array([0, 0, 180]),    np.array([180, 50, 255])),
    ],
}


def get_color_mask(img, color: str):
    """Gibt eine bereinigte Binärmaske für die angegebene Farbe zurück.
    
    Unterstützt alle Farben aus COLOR_RANGES.
    Farben mit mehreren HSV-Bereichen (z.B. Rot) werden automatisch kombiniert.
    """
    color = color.lower().strip()
    if color not in COLOR_RANGES:
        raise ValueError(f"Unbekannte Farbe '{color}'. Verfügbar: {list(COLOR_RANGES.keys())}")
    
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
    
    for lower, upper in COLOR_RANGES[color]:
        mask |= cv2.inRange(hsv, lower, upper)
    
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return mask


def get_orange_mask(img):
    """Gibt eine bereinigte Binärmaske für orange Bereiche zurück."""
    return get_color_mask(img, "orange")


def get_dark_spots(gray_roi):
    """Gibt eine Binärmaske für dunkle Stellen zurück (z.B. Würfelaugen).
    
    Nutzt adaptives Thresholding: Erkennt Bereiche, die lokal dunkler
    sind als ihre Umgebung. Funktioniert zuverlässig bei gleichmäßiger
    LED-Beleuchtung, 1-6 Augen und bei Neigung.
    """
    # Rauschen reduzieren (groesserer Kernel filtert Oberflaechentextur besser)
    blurred = cv2.GaussianBlur(gray_roi, (7, 7), 0)
    
    # Adaptiver Threshold: erkennt lokal dunklere Stellen
    # blockSize=51 → grosse Nachbarschaft, damit der Hintergrund-Mittelwert
    #                 nicht vom Dot verfaelscht wird
    # C=8 → staerkerer Threshold, filtert subtile Schatten/Textur besser
    thresh = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 51, 8
    )
    
    # Halbmonde schließen (LED-Ring erzeugt einseitige Schatten)
    kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel_close)
    
    # Ringe/Donuts füllen → aus hohlen Ringen werden volle Kreise
    cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(thresh, cnts, -1, 255, cv2.FILLED)
    
    # Jetzt erst Noise entfernen – echte Dots sind jetzt gefüllte Kreise (~15px)
    # und überleben 5x5 problemlos, kleine Noise-Blobs nicht.
    kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_open)
    
    return thresh
