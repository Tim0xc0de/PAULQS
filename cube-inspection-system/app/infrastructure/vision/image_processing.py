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


def get_dark_spots(gray_roi, thresh_value=80):
    """Gibt eine Binärmaske für dunkle Stellen zurück (z.B. Würfelaugen)."""
    _, thresh = cv2.threshold(gray_roi, thresh_value, 255, cv2.THRESH_BINARY_INV)
    return thresh
