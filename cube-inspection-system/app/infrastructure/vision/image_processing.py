import cv2
import numpy as np

# HSV-Grenzen für Orange (hohe Sättigung, um Holztisch auszuschließen)
ORANGE_LOWER = np.array([5, 150, 120])
ORANGE_UPPER = np.array([25, 255, 255])


def get_orange_mask(img):
    """Gibt eine bereinigte Binärmaske für orange Bereiche zurück."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, ORANGE_LOWER, ORANGE_UPPER)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return mask


def get_dark_spots(gray_roi):
    """Gibt eine Binärmaske für dunkle Stellen zurück (z.B. Würfelaugen).
    
    Nutzt relativen Threshold basierend auf der Median-Helligkeit:
    Alles deutlich dunkler als der Median = Auge.
    Funktioniert zuverlässig mit 1-6 Augen und bei Neigung.
    """
    # Rauschen reduzieren
    blurred = cv2.GaussianBlur(gray_roi, (5, 5), 0)
    
    # Relativer Threshold: Median der Oberfläche minus Offset
    median_val = int(np.median(blurred))
    thresh_val = max(30, median_val - 50)
    _, thresh = cv2.threshold(blurred, thresh_val, 255, cv2.THRESH_BINARY_INV)
    
    # Kleine Störungen entfernen
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    
    return thresh
