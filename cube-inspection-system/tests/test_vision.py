from pyniryo import NiryoRobot
import cv2
import numpy as np

# --- Parameter ---
MIN_CUBE_AREA = 2000
MAX_CUBE_RATIO = 0.4
MIN_DOT_AREA = 15
MAX_DOT_AREA = 500
MIN_CIRCULARITY = 0.35
MIN_SATURATION = 60      # Sättigung: farbige Würfel > Hintergrund/Greifer
MIN_VALUE = 50            # Minimale Helligkeit (Schwarz ausschließen)

# 1. Verbindung herstellen (IP anpassen, falls nötig)
robot_ip = "10.10.10.10"
robot = NiryoRobot(robot_ip)

print("Starte Objekterkennung (Würfel + Augenzahlen, farbunabhängig)...")
print("Drücke 'q' im Bildfenster, um das Programm zu beenden.")

try:
    while True:
        # Bild vom Roboter holen
        img_compressed = robot.get_img_compressed()
        img_array = np.frombuffer(img_compressed, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        # Kamera ist auf dem Kopf → 180° drehen
        if img is not None:
            img = cv2.rotate(img, cv2.ROTATE_180)

        if img is not None:
            h_img, w_img = img.shape[:2]
            max_area = h_img * w_img * MAX_CUBE_RATIO

            # A) Farbunabhängige Maske: alles mit Sättigung = farbiger Würfel
            #    Hintergrund (weiß/grau) und Greifer (Metall) haben niedrige Sättigung
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            color_mask = cv2.inRange(hsv,
                                     np.array([0, MIN_SATURATION, MIN_VALUE]),
                                     np.array([180, 255, 255]))
            morph_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            color_mask = cv2.morphologyEx(color_mask, cv2.MORPH_CLOSE, morph_kernel)
            color_mask = cv2.morphologyEx(color_mask, cv2.MORPH_OPEN, morph_kernel)

            # B) Würfel-Kontur finden (größte passende farbige Fläche)
            contours, _ = cv2.findContours(color_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            best = None
            best_area = 0
            for c in contours:
                area = cv2.contourArea(c)
                if area < MIN_CUBE_AREA or area > max_area:
                    continue
                bx, by, bw, bh = cv2.boundingRect(c)
                aspect = bw / bh if bh > 0 else 0
                if 0.3 < aspect < 3.0 and area > best_area:
                    best = c
                    best_area = area

            if best is not None:
                x, y, w, h = cv2.boundingRect(best)

                # Grünes Rechteck um den Würfel zeichnen
                cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)

                # C) Augen zählen — NUR innerhalb der farbigen Fläche (Greifer ausschließen!)
                roi_mask = color_mask[y:y+h, x:x+w]
                fill_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
                roi_mask_filled = cv2.dilate(roi_mask, fill_kernel, iterations=2)

                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                roi_gray = gray[y:y+h, x:x+w]

                # Adaptive Schwellwertbildung: funktioniert bei jeder Würfelfarbe,
                # da sie lokal dunkle Stellen relativ zur Umgebung erkennt
                thresh = cv2.adaptiveThreshold(
                    roi_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV, 31, 10)
                dark_on_cube = cv2.bitwise_and(thresh, roi_mask_filled)

                # Konturen der Punkte finden
                dot_contours, _ = cv2.findContours(dark_on_cube, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                dot_count = 0
                for dot in dot_contours:
                    area = cv2.contourArea(dot)
                    if MIN_DOT_AREA < area < MAX_DOT_AREA:
                        perimeter = cv2.arcLength(dot, True)
                        if perimeter > 0:
                            circ = 4 * np.pi * area / (perimeter * perimeter)
                            if circ > MIN_CIRCULARITY:
                                dot_count += 1
                                # Roten Rahmen um erkannten Punkt zeichnen
                                dx, dy_, dw, dh = cv2.boundingRect(dot)
                                cv2.rectangle(img, (x+dx, y+dy_), (x+dx+dw, y+dy_+dh), (0, 0, 255), 1)

                # Ergebnis über den Würfel schreiben
                text = f"Wuerfel! Augen: {dot_count}"
                cv2.putText(img, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Bilder anzeigen
            cv2.imshow("Logitech Wuerfel Erkennung", img)

            # Hilfreich zum Debuggen:
            # cv2.imshow("Farb-Maske", color_mask)
            # cv2.imshow("Dark on Cube", dark_on_cube)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("Beende Stream...")
                break
        else:
            print("Fehler: Bild konnte nicht dekodiert werden.")
            break

except Exception as e:
    print(f"Fehler: {e}")

finally:
    cv2.destroyAllWindows()
    robot.close_connection()