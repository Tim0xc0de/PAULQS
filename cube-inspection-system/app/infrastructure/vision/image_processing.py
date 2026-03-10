import cv2
import numpy as np

# HSV-Grenzen für Orange
ORANGE_LOWER = np.array([5, 100, 100])
ORANGE_UPPER = np.array([25, 255, 255])


def get_orange_mask(img):
    """Gibt eine Binärmaske für orange Bereiche zurück."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, ORANGE_LOWER, ORANGE_UPPER)


def get_dark_spots(gray_roi, thresh_value=100):
    """Gibt eine Binärmaske für dunkle Stellen zurück (z.B. Würfelaugen)."""
    _, thresh = cv2.threshold(gray_roi, thresh_value, 255, cv2.THRESH_BINARY_INV)
    return thresh
