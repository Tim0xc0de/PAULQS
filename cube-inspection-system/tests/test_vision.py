"""
test_vision.py – Visueller Test der Würfelerkennung.

Nutzt die echte Erkennungslogik aus der App (detect_cube, _get_dot_mask).
Zeigt das Livebild der Roboter-Kamera mit klickbarem "Analysieren"-Button.

Bedienung:
  Klick auf gruenen Button = Analysieren
  Klick auf roten Button   = Beenden
"""
import os
import sys
import cv2
import numpy as np
from datetime import datetime
from pyniryo import NiryoRobot

# App-Module verfügbar machen
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.infrastructure.vision.camera import capture
from app.infrastructure.vision.detection import detect_cube, draw_detection

# ====================================================================
# KONFIGURATION
# ====================================================================
ROBOT_IP = "10.10.10.10"
COLOR = "orange"
SAVE_DIR = os.path.join(os.path.dirname(__file__), "vision_captures")
os.makedirs(SAVE_DIR, exist_ok=True)

# Button-Bereiche (werden unten ins Bild gezeichnet)
BTN_H = 40
BTN_ANALYZE = {"label": "Analysieren", "color": (0, 180, 0)}
BTN_QUIT    = {"label": "Beenden",     "color": (0, 0, 200)}

# Globaler State fuer Maus-Callback
clicked_action = None


def on_mouse(event, x, y, flags, param):
    """Maus-Callback: prueft ob ein Button geklickt wurde."""
    global clicked_action
    if event != cv2.EVENT_LBUTTONDOWN:
        return
    img_h = param["img_h"]
    img_w = param["img_w"]
    btn_y = img_h - BTN_H
    if y < btn_y:
        return
    if x < img_w // 2:
        clicked_action = "analyze"
    else:
        clicked_action = "quit"


def draw_buttons(frame):
    """Zeichnet die zwei Buttons unten ins Bild."""
    h, w = frame.shape[:2]
    mid = w // 2
    btn_y = h - BTN_H

    # Analysieren (links)
    cv2.rectangle(frame, (0, btn_y), (mid - 1, h), BTN_ANALYZE["color"], -1)
    cv2.putText(frame, BTN_ANALYZE["label"], (mid // 2 - 60, btn_y + 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # Beenden (rechts)
    cv2.rectangle(frame, (mid, btn_y), (w, h), BTN_QUIT["color"], -1)
    cv2.putText(frame, BTN_QUIT["label"], (mid + mid // 2 - 45, btn_y + 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)


def save_img(name, img, folder):
    """Speichert ein Bild unter folder/name."""
    path = os.path.join(folder, name)
    cv2.imwrite(path, img)
    print(f"  -> Gespeichert: {path}")


def analyze(img, run_folder):
    """Analyse nur mit App-Funktionen: detect_cube() und draw_detection()."""

    # Schritt 1: Rohbild speichern
    print("\n[1/4] Rohbild speichern")
    save_img("01_raw.jpg", img, run_folder)

    # Schritt 2: detect_cube(debug=True) – Erkennung + Masken
    print("[2/4] detect_cube(debug=True) aufrufen")
    detection = detect_cube(img, COLOR, debug=True)

    if detection is None:
        print("  !! Kein Wuerfel erkannt.")
        return

    dots = detection["dots"]
    x, y, w, h = detection["x"], detection["y"], detection["w"], detection["h"]
    print(f"  Wuerfel bei ({x},{y} {w}x{h}), Augen: {dots}")

    # Schritt 3: Ergebnisbild mit draw_detection() zeichnen
    print("[3/4] draw_detection() aufrufen")
    result = img.copy()
    draw_detection(result, detection)
    save_img("02_result.jpg", result, run_folder)

    # Schritt 4: Debug-Masken speichern (kommen direkt aus detect_cube)
    print("[4/4] Debug-Masken speichern")
    mask = detection.get("mask")
    dark_mask = detection.get("dark_mask")

    if mask is not None:
        save_img("03_mask.jpg", mask, run_folder)
        cv2.imshow("Farbmaske", cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR))

    if dark_mask is not None:
        save_img("04_dark_spots.jpg", dark_mask, run_folder)
        cv2.imshow("Dark Spots", cv2.cvtColor(dark_mask, cv2.COLOR_GRAY2BGR))

    # ROI speichern (einfacher Bildausschnitt, keine Logik)
    roi = img[y:y+h, x:x+w]
    save_img("05_roi.jpg", roi, run_folder)

    # Ergebnis anzeigen
    cv2.imshow("Ergebnis", result)
    cv2.imshow("ROI", roi)

    print(f"\nErgebnis: {dots} Augen erkannt. Bilder in {run_folder}")


# ====================================================================
# HAUPTPROGRAMM
# ====================================================================
WINDOW = "Livebild (Klick: Analysieren / Beenden)"

print("Verbinde mit Roboter ...")
robot = NiryoRobot(ROBOT_IP)
run_count = 0

# Fenster vorbereiten + Maus-Callback registrieren
cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
mouse_param = {"img_h": 480, "img_w": 640}
cv2.setMouseCallback(WINDOW, on_mouse, mouse_param)

print("Livebild aktiv. Gruener Button = Analysieren, Roter Button = Beenden")

try:
    while True:
        # Livebild holen
        img = capture(robot)
        if img is None:
            print("Fehler: Kein Bild erhalten.")
            break

        # Kamera ist auf dem Kopf → 180° drehen
        img = cv2.rotate(img, cv2.ROTATE_180)

        # Maus-Param aktualisieren (fuer korrekte Button-Erkennung)
        h_img, w_img = img.shape[:2]
        mouse_param["img_h"] = h_img + BTN_H
        mouse_param["img_w"] = w_img

        # Frame mit Buttons zusammenbauen
        btn_bar = np.zeros((BTN_H, w_img, 3), dtype=np.uint8)
        frame = np.vstack([img, btn_bar])
        draw_buttons(frame)
        cv2.imshow(WINDOW, frame)

        cv2.waitKey(30)

        # Button-Klick auswerten
        if clicked_action == "quit":
            print("Beende ...")
            break

        if clicked_action == "analyze":
            clicked_action = None

            run_count += 1
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            run_folder = os.path.join(SAVE_DIR, f"run_{run_count}_{ts}")
            os.makedirs(run_folder, exist_ok=True)

            print(f"\n{'='*50}")
            print(f"ANALYSE #{run_count}")
            print(f"{'='*50}")
            analyze(img, run_folder)

            # Warten bis Klick irgendwo → zurueck zum Livebild
            print("\nKlick oder Taste druecken fuer naechstes Livebild ...")
            cv2.waitKey(0)
            cv2.destroyWindow("Farbmaske")
            cv2.destroyWindow("Dark Spots")
            cv2.destroyWindow("Ergebnis")
            cv2.destroyWindow("ROI")

except Exception as e:
    print(f"Fehler: {e}")

finally:
    cv2.destroyAllWindows()
    robot.close_connection()
    print("Verbindung getrennt.")