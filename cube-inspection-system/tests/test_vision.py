from pyniryo import NiryoRobot
import cv2
import numpy as np

# --- Parameter (gleich wie detection.py) ---
MIN_CUBE_AREA = 2000
MAX_CUBE_RATIO = 0.4
MIN_DOT_AREA = 30
MAX_DOT_AREA = 800
MIN_CIRCULARITY = 0.45

# HSV-Grenzen für Orange (gleich wie image_processing.py)
ORANGE_LOWER = np.array([5, 150, 120])
ORANGE_UPPER = np.array([25, 255, 255])

# 1. Verbindung herstellen
robot_ip = "10.10.10.10"
robot = NiryoRobot(robot_ip)

print("Starte Objekterkennung (RETR_CCOMP Hierarchie-Ansatz)...")
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

            # A) Orange-Maske mit 5x5 MORPH_CLOSE (schließt Ritzen, erhält Augen)
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(hsv, ORANGE_LOWER, ORANGE_UPPER)
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

            # B) Konturen MIT Hierarchie (RETR_CCOMP: außen + Löcher)
            contours, hierarchy = cv2.findContours(
                mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
            )

            dot_count = 0
            cube_found = False

            if contours and hierarchy is not None:
                hierarchy = hierarchy[0]

                # Würfel = größte äußere Kontur (kein Parent)
                cube_idx = -1
                cube_area = 0
                for i in range(len(contours)):
                    if hierarchy[i][3] != -1:
                        continue
                    area = cv2.contourArea(contours[i])
                    if area < MIN_CUBE_AREA or area > max_area:
                        continue
                    bx, by, bw, bh = cv2.boundingRect(contours[i])
                    aspect = bw / bh if bh > 0 else 0
                    if 0.3 < aspect < 3.0 and area > cube_area:
                        cube_idx = i
                        cube_area = area

                if cube_idx != -1:
                    cube_found = True
                    x, y, w, h = cv2.boundingRect(contours[cube_idx])

                    # Grünes Rechteck um den Würfel
                    cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)

                    # Augen = innere Konturen (Kinder) des Würfels
                    # Schritt 1: Alle Kandidaten sammeln
                    candidates = []
                    child_idx = hierarchy[cube_idx][2]
                    while child_idx != -1:
                        area = cv2.contourArea(contours[child_idx])
                        perimeter = cv2.arcLength(contours[child_idx], True)
                        circ = (4 * np.pi * area / (perimeter ** 2)) if perimeter > 0 else 0
                        if MIN_DOT_AREA < area < MAX_DOT_AREA and circ > MIN_CIRCULARITY:
                            candidates.append((area, contours[child_idx]))
                            print(f"  Kandidat: area={area:.0f}, circ={circ:.2f}")
                        child_idx = hierarchy[child_idx][0]

                    # Schritt 2: Ausreißer entfernen
                    if len(candidates) > 2:
                        median_area = float(np.median([a for a, _ in candidates]))
                        filtered = [(a, c) for a, c in candidates if a > median_area * 0.4]
                        print(f"  Median={median_area:.0f}, {len(candidates)} Kandidaten -> {len(filtered)} nach Filter")
                    else:
                        filtered = candidates

                    for area, cont in filtered:
                        dot_count += 1
                        dx, dy_, dw, dh = cv2.boundingRect(cont)
                        cv2.rectangle(img, (dx, dy_), (dx+dw, dy_+dh), (0, 0, 255), 1)

                    # Ergebnis über den Würfel schreiben
                    text = f"Augen: {dot_count}"
                    cv2.putText(img, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
                    cv2.putText(mask, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (180,), 2)
                    print(f"Augen erkannt: {dot_count}")

            # Bilder anzeigen
            cv2.imshow("Wuerfel Erkennung (RETR_CCOMP)", img)
            cv2.imshow("Orange-Maske", mask)

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