"""
test_vision_usb.py – Visueller Test der Würfelerkennung mit USB-Kamera.

Identisch zu test_vision.py, aber nutzt eine direkt per USB angeschlossene
Kamera statt der Roboter-Kamera (kein Niryo noetig).

Bedienung:
  Klick auf gruenen Button = Analysieren
  Klick auf roten Button   = Beenden
"""
import os
import sys
import cv2
import numpy as np
import importlib.util
from datetime import datetime

# detection.py DIREKT laden (ohne app-Paket, damit pyniryo nicht importiert wird)
_app_root = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _app_root)

# image_processing zuerst laden (wird von detection benoetigt)
_ip_path = os.path.join(_app_root, "app", "infrastructure", "vision", "image_processing.py")
_ip_spec = importlib.util.spec_from_file_location("app.infrastructure.vision.image_processing", _ip_path)
_ip_mod = importlib.util.module_from_spec(_ip_spec)
sys.modules[_ip_spec.name] = _ip_mod
_ip_spec.loader.exec_module(_ip_mod)

# detection laden
_det_path = os.path.join(_app_root, "app", "infrastructure", "vision", "detection.py")
_det_spec = importlib.util.spec_from_file_location("app.infrastructure.vision.detection", _det_path)
_det_mod = importlib.util.module_from_spec(_det_spec)
sys.modules[_det_spec.name] = _det_mod
_det_spec.loader.exec_module(_det_mod)

detect_cube = _det_mod.detect_cube
draw_detection = _det_mod.draw_detection

# ====================================================================
# KONFIGURATION
# ====================================================================
CAMERA_INDEX = 1  # 0 = Elgato, 1 = Logitech (hinten am Tower)
COLOR = "auto"
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


def _resize_to_height(img, target_h):
    """Skaliert ein Bild proportional auf die Zielhoehe."""
    h, w = img.shape[:2]
    if h == 0:
        return img
    scale = target_h / h
    return cv2.resize(img, (int(w * scale), target_h))


def build_result_composite(img, detection):
    """Baut ein einzelnes Composite-Bild mit allen Analyse-Ergebnissen.
    
    Layout:
    ┌──────────────────────────────────┐
    │  ERGEBNIS: 5 Augen erkannt       │  <- Info-Leiste
    ├──────────┬───────────┬──────────┤
    │  Result  │   Maske   │   ROI    │  <- Bilder nebeneinander
    └──────────┴───────────┴──────────┘
    """
    dots = detection["dots"]
    x, y, w, h = detection["x"], detection["y"], detection["w"], detection["h"]
    mask = detection.get("mask")
    dark_mask = detection.get("dark_mask")
    color_name = detection.get("color", "unbekannt")
    color_bgr = detection.get("color_bgr", (128, 128, 128))

    # Ergebnisbild
    result = img.copy()
    draw_detection(result, detection)

    # ROI
    roi = img[y:y+h, x:x+w]
    roi_bgr_img = cv2.cvtColor(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR) if roi.size == 0 else roi

    # Maske (Farbmaske oder Dark-Spots, je nachdem was vorhanden)
    if dark_mask is not None:
        mask_bgr = cv2.cvtColor(dark_mask, cv2.COLOR_GRAY2BGR)
    elif mask is not None:
        mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
    else:
        mask_bgr = np.zeros_like(result)

    # Alle auf gleiche Hoehe skalieren (halbe Originalhoehe)
    target_h = max(result.shape[0] // 2, 120)
    r_thumb = _resize_to_height(result, target_h)
    m_thumb = _resize_to_height(mask_bgr, target_h)
    roi_thumb = _resize_to_height(roi_bgr_img, target_h) if roi.size > 0 else np.zeros((target_h, target_h, 3), dtype=np.uint8)

    # Nebeneinander zusammenbauen
    row = np.hstack([r_thumb, m_thumb, roi_thumb])
    row_w = row.shape[1]

    # Info-Leiste oben – Zeile 1: Augenzahl
    bar_h = 50
    bar = np.zeros((bar_h, row_w, 3), dtype=np.uint8)
    bar[:] = (0, 140, 0) if 1 <= dots <= 6 else (0, 0, 180)
    text = f"ERGEBNIS: {dots} Augen erkannt"
    cv2.putText(bar, text, (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

    # Info-Leiste – Zeile 2: Erkannte Farbe mit Farbquadrat
    color_bar_h = 40
    color_bar = np.zeros((color_bar_h, row_w, 3), dtype=np.uint8)
    color_bar[:] = (40, 40, 40)
    # Farbquadrat
    sq_size = 26
    sq_y = (color_bar_h - sq_size) // 2
    cv2.rectangle(color_bar, (15, sq_y), (15 + sq_size, sq_y + sq_size), color_bgr, -1)
    cv2.rectangle(color_bar, (15, sq_y), (15 + sq_size, sq_y + sq_size), (255, 255, 255), 1)
    # Farbname
    cv2.putText(color_bar, f"Farbe: {color_name}", (50, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # Labels unter den Bildern
    label_h = 25
    labels = np.zeros((label_h, row_w, 3), dtype=np.uint8)
    sections = [r_thumb.shape[1], m_thumb.shape[1], roi_thumb.shape[1]]
    names = ["Ergebnis", "Maske", "ROI"]
    offset = 0
    for sec_w, name in zip(sections, names):
        tx = offset + sec_w // 2 - len(name) * 5
        cv2.putText(labels, name, (tx, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        offset += sec_w

    composite = np.vstack([bar, color_bar, row, labels])
    return composite, result, roi


def analyze(img, run_folder, window_name):
    """Analyse und Anzeige im Hauptfenster."""

    # Schritt 1: Rohbild speichern
    print("\n[1/4] Rohbild speichern")
    save_img("01_raw.jpg", img, run_folder)

    # Schritt 2: detect_cube(debug=True) – Erkennung + Masken
    print("[2/4] detect_cube(debug=True) aufrufen")
    detection = detect_cube(img, COLOR, debug=True)

    if detection is None:
        print("  !! Kein Wuerfel erkannt.")
        # Fehlermeldung ins Hauptfenster
        h_img, w_img = img.shape[:2]
        bar = np.zeros((50, w_img, 3), dtype=np.uint8)
        bar[:] = (0, 0, 180)
        cv2.putText(bar, "KEIN WUERFEL ERKANNT", (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        cv2.imshow(window_name, np.vstack([bar, img]))
        return

    dots = detection["dots"]
    x, y, w, h = detection["x"], detection["y"], detection["w"], detection["h"]
    color_name = detection.get("color", "unbekannt")
    print(f"  Wuerfel bei ({x},{y} {w}x{h}), Augen: {dots}, Farbe: {color_name}")

    # Schritt 3: Composite bauen und anzeigen
    print("[3/4] Ergebnis zusammenbauen")
    composite, result, roi = build_result_composite(img, detection)
    save_img("02_result.jpg", result, run_folder)

    # Schritt 4: Debug-Masken speichern
    print("[4/4] Debug-Masken speichern")
    mask = detection.get("mask")
    dark_mask = detection.get("dark_mask")
    if mask is not None:
        save_img("03_mask.jpg", mask, run_folder)
    if dark_mask is not None:
        save_img("04_dark_spots.jpg", dark_mask, run_folder)
    save_img("05_roi.jpg", roi, run_folder)

    # Composite speichern
    save_img("06_composite.jpg", composite, run_folder)

    # Alles in EINEM Fenster anzeigen
    cv2.imshow(window_name, composite)
    print(f"\nErgebnis: {dots} Augen erkannt. Bilder in {run_folder}")


# ====================================================================
# HAUPTPROGRAMM
# ====================================================================
WINDOW = "USB-Kamera Livebild (Klick: Analysieren / Beenden)"

print(f"Oeffne USB-Kamera (Index {CAMERA_INDEX}) ...")
cap = cv2.VideoCapture(CAMERA_INDEX)

if not cap.isOpened():
    print(f"FEHLER: Kamera mit Index {CAMERA_INDEX} konnte nicht geoeffnet werden.")
    print("Tipp: Probiere CAMERA_INDEX = 1 oder 2 falls mehrere Kameras angeschlossen sind.")
    sys.exit(1)

run_count = 0

# Fenster vorbereiten + Maus-Callback registrieren
cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
mouse_param = {"img_h": 480, "img_w": 640}
cv2.setMouseCallback(WINDOW, on_mouse, mouse_param)

print("Livebild aktiv. Gruener Button = Analysieren, Roter Button = Beenden")

try:
    while True:
        # Livebild holen
        ret, img = cap.read()
        if not ret or img is None:
            print("Fehler: Kein Bild erhalten.")
            break

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
            analyze(img, run_folder, WINDOW)

            # Warten bis Taste oder Button-Klick → zurueck zum Livebild
            print("\nTaste oder Klick fuer naechstes Livebild (Roter Button = Beenden) ...")
            while True:
                key = cv2.waitKey(100)
                if key != -1:
                    break
                if clicked_action == "quit":
                    break
                if clicked_action == "analyze":
                    clicked_action = None
                    break

            if clicked_action == "quit":
                print("Beende ...")
                break

except Exception as e:
    print(f"Fehler: {e}")

finally:
    cv2.destroyAllWindows()
    cap.release()
    print("Kamera freigegeben.")
