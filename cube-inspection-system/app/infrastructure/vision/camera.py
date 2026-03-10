import cv2
import numpy as np
from pyniryo import NiryoRobot


def capture(robot: NiryoRobot) -> np.ndarray | None:
    """Holt ein Bild von der Roboter-Kamera und gibt es als BGR-Array zurück."""
    img_compressed = robot.get_img_compressed()
    img_array = np.frombuffer(img_compressed, dtype=np.uint8)
    return cv2.imdecode(img_array, cv2.IMREAD_COLOR)
