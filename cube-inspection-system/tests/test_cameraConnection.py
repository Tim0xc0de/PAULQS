from pyniryo import NiryoRobot
import cv2
import numpy as np

# 1. Verbindung herstellen
robot_ip = "10.10.10.10" 
robot = NiryoRobot(robot_ip)

print("Versuche, ein Bild von der Kamera abzurufen...")

try:
    # 2. Komprimiertes Bild vom Roboter holen
    img_compressed = robot.get_img_compressed()
    
    # 3. Bild manuell dekodieren (numpy 2.x kompatibel)
    img_array = np.frombuffer(img_compressed, dtype=np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    
    if img is not None:
        # 4. Bild anzeigen
        print("Bild empfangen! Drücke eine Taste im Bildfenster, um es zu schließen.")
        cv2.imshow("Kamera-Test Logitech", img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    else:
        print("Fehler: Bild konnte nicht dekodiert werden.")

except Exception as e:
    print(f"Fehler beim Abrufen des Bildes: {e}")

finally:
    robot.close_connection()