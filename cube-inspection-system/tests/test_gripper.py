"""
Test-Script für Niryo Roboter Greifer-Sequenz
==============================================
Testet die komplette Pick-and-Place Sequenz mit:
- Sicheren Bewegungen mit Echtzeit-Kollisionserkennung
- Greifer-Steuerung mit Status-Feedback
- Kamera-Aufnahmen und Würfelerkennung
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pyniryo import NiryoRobot, JointsPosition
import time
import threading
import cv2
import numpy as np
from app.infrastructure.vision.detection import detect_cube

# ============================================================================
# KONFIGURATION
# ============================================================================

ROBOT_IP = "10.10.10.10"           # IP-Adresse des Niryo Roboters
GRIPPER_SPEED = 500                # Greifer-Geschwindigkeit (1-1000)
MAX_VELOCITY = 100                 # Maximale Arm-Geschwindigkeit (%)
COLLISION_CHECK_INTERVAL = 0.1     # Kollisionsprüfung alle 100ms

# ============================================================================
# ROBOTER-POSITIONEN (in Radiant)
# ============================================================================

POS_1 = JointsPosition(-0.9077, 0.213, -1.2172, -0.0827, 0.0551, -0.0459)   # Annäherung
POS_2 = JointsPosition(-0.9108, -0.9928, -0.6097, -0.2453, 1.382, -0.0321)  # Greifposition
POS_4 = JointsPosition(-0.8667, 0.1085, -0.7203, -0.0413, -0.1534, -0.0474) # Anheben
POS_5 = JointsPosition(2.5515, 0.1327, -0.7446, -0.0428, -0.155, -0.0474)   # Transport
POS_6 = JointsPosition(2.6291, -0.4974, -0.5082, 1.1812, 1.3298, -0.503)    # Vorbereitung Kamera
POS_7 = JointsPosition(2.4115, -0.5549, -0.2613, 1.0048, 1.0767, -0.5628)   # Vor Kamera (Seite 1)
POS_8 = JointsPosition(2.4115, -0.5368, -0.2613, 0.9588, 1.1411, 2.528)     # Vor Kamera (Seite 2, gedreht)
POS_10 = JointsPosition(2.5774, -0.5428, -0.4128, 1.1935, 1.3206, 2.5296)   # Ablageposition

# ============================================================================
# HELPER-FUNKTIONEN
# ============================================================================

def safe_move(robot, position, name):
    """
    Führt eine sichere Bewegung mit Echtzeit-Kollisionserkennung durch.
    
    Die Bewegung läuft in einem separaten Thread, während der Hauptthread
    alle 100ms auf Kollisionen prüft. Bei Erkennung wird der Roboter
    sofort gestoppt und die Gelenke bleiben gesperrt.
    
    Args:
        robot: NiryoRobot Instanz
        position: JointsPosition Zielposition
        name: Beschreibender Name für Logging
        
    Returns:
        bool: True bei erfolgreicher Bewegung, False bei Kollision
    """
    print(f"[MOVE] Fahre zu {name}...")
    
    # Fehler aus dem Bewegungs-Thread speichern
    move_error = [None]
    
    def do_move():
        """Bewegung in separatem Thread ausführen."""
        try:
            robot.move(position)
        except Exception as e:
            move_error[0] = e
    
    # Bewegung im Hintergrund starten
    thread = threading.Thread(target=do_move)
    thread.start()
    
    # Hauptthread: Kollision während der Bewegung prüfen
    collision = False
    while thread.is_alive():
        if robot.collision_detected:
            print(f"[KOLLISION] Notfall-Stopp bei {name}!")
            # Learning Mode kurz aktivieren um Bewegung zu stoppen
            robot.set_learning_mode(True)
            time.sleep(0.1)
            # Gelenke sofort wieder sperren
            robot.set_learning_mode(False)
            robot.clear_collision_detected()
            collision = True
            break
        time.sleep(COLLISION_CHECK_INTERVAL)
    
    # Warten bis der Bewegungs-Thread beendet ist
    thread.join(timeout=5.0)
    
    # Fehler aus dem Thread weiterleiten
    if move_error[0] and not collision:
        raise move_error[0]
    
    if collision:
        return False
    
    # Final-Check nach abgeschlossener Bewegung
    if robot.collision_detected:
        print(f"[WARNUNG] Kollision bei {name} nach Bewegung erkannt!")
        robot.clear_collision_detected()
        return False
    
    print(f"[MOVE] {name} erfolgreich erreicht")
    return True


def grip_object(robot):
    """
    Greift ein Objekt mit dem Greifer und prüft den Status.
    
    Schließt den Greifer mit definierter Geschwindigkeit und wartet
    kurz, damit sich der Griff stabilisieren kann. Anschließend wird
    die aktuelle Gelenkposition ausgelesen als Feedback.
    
    Args:
        robot: NiryoRobot Instanz
        
    Returns:
        bool: True bei erfolgreichem Greifen
    """
    print("[GRIPPER] Schließe Greifer...")
    robot.close_gripper(speed=GRIPPER_SPEED)
    
    # Kurze Wartezeit für stabilen Griff
    time.sleep(0.5)
    
    # Status-Feedback: Aktuelle Gelenkpositionen ausgeben
    print("[GRIPPER] Prüfe Griff-Status...")
    current_joints = robot.get_joints()
    print(f"[INFO] Aktuelle Gelenkposition: {current_joints}")
    
    return True


# ============================================================================
# HAUPTTEST-FUNKTION
# ============================================================================

def test_gripper_open():
    """
    Haupttest: Komplette Pick-and-Place Sequenz mit Würfelerkennung.
    
    Ablauf:
    1. Roboter initialisieren und kalibrieren
    2. Würfel greifen (POS_1 → POS_2)
    3. Würfel zur Kamera transportieren (POS_4 → POS_5 → POS_6 → POS_7)
    4. Erste Seite fotografieren und erkennen
    5. Würfel drehen (POS_8)
    6. Zweite Seite fotografieren und erkennen
    7. Würfel ablegen (POS_10)
    8. Zur Home-Position zurückkehren
    """
    robot = None
    
    try:
        # ====================================================================
        # INITIALISIERUNG
        # ====================================================================
        
        print(f"[INIT] Verbinde mit PAUL ({ROBOT_IP})...")
        robot = NiryoRobot(ROBOT_IP)

        # Kalibrierungsstatus prüfen
        if robot.need_calibration():
            print("[ERROR] Roboter braucht Kalibrierung – Test abgebrochen.")
            return

        # Learning Mode deaktivieren (Motoren aktivieren)
        print("[INIT] Setze Learning Mode aus...")
        robot.set_learning_mode(False)
        
        # Maximale Geschwindigkeit setzen
        print("[INIT] Setze Geschwindigkeit...")
        robot.set_arm_max_velocity(MAX_VELOCITY)

        # Kollisionsstatus zurücksetzen
        print("[INIT] Lösche Kollisionsstatus...")
        robot.clear_collision_detected()

        # Zur Startposition fahren
        print("[INIT] Fahre zur Home-Position...")
        robot.move_to_home_pose()

        # ====================================================================
        # PICK SEQUENZ
        # ====================================================================
        
        # Greifer öffnen für Pick
        print("[GRIPPER] Öffne Greifer...")
        robot.open_gripper(speed=GRIPPER_SPEED)

        # Annäherung an Würfel
        if not safe_move(robot, POS_1, "Position 1 (Annäherung)"):
            return

        # Greifposition erreichen
        if not safe_move(robot, POS_2, "Position 2 (Greifposition)"):
            return

        # Würfel greifen
        if not grip_object(robot):
            print("[ERROR] Greifen fehlgeschlagen!")
            return

        # ====================================================================
        # TRANSPORT ZUR KAMERA
        # ====================================================================
        
        # Würfel anheben
        if not safe_move(robot, POS_4, "Position 4 (Anheben)"):
            return

        # Transport-Position
        if not safe_move(robot, POS_5, "Position 5 (Transport)"):
            return

        # Vorbereitung für Kamera
        if not safe_move(robot, POS_6, "Position 6 (Kamera-Vorbereitung)"):
            return

        # ====================================================================
        # ERSTE KAMERA-AUFNAHME
        # ====================================================================
        
        # Position vor Kamera (Seite 1)
        if not safe_move(robot, POS_7, "Position 7 (vor Kamera - Seite 1)"):
            return

        # Stabilisierungszeit vor Foto
        print("[CAMERA] Warte 3 Sekunden für Stabilisierung...")
        time.sleep(3)
        
        # Foto aufnehmen
        print("[CAMERA] Mache Foto 1...")
        img_compressed = robot.get_img_compressed()
        img1 = cv2.imdecode(np.frombuffer(img_compressed, dtype=np.uint8), cv2.IMREAD_COLOR)
        
        # Würfelerkennung durchführen
        if img1 is not None:
            detection1 = detect_cube(img1)
            if detection1:
                print(f"[ERGEBNIS] Foto 1 - Würfel erkannt mit {detection1['dots']} Augen")
            else:
                print("[ERGEBNIS] Foto 1 - Kein Würfel erkannt")
        else:
            print("[ERGEBNIS] Foto 1 - Kein Bild erhalten")

        # ====================================================================
        # ZWEITE KAMERA-AUFNAHME (GEDREHT)
        # ====================================================================
        
        # Würfel drehen für zweite Seite
        if not safe_move(robot, POS_8, "Position 8 (vor Kamera - Seite 2 gedreht)"):
            return

        # Stabilisierungszeit vor Foto
        print("[CAMERA] Warte 3 Sekunden für Stabilisierung...")
        time.sleep(3)
        
        # Foto aufnehmen
        print("[CAMERA] Mache Foto 2...")
        img_compressed = robot.get_img_compressed()
        img2 = cv2.imdecode(np.frombuffer(img_compressed, dtype=np.uint8), cv2.IMREAD_COLOR)
        
        # Würfelerkennung durchführen
        if img2 is not None:
            detection2 = detect_cube(img2)
            if detection2:
                print(f"[ERGEBNIS] Foto 2 - Würfel erkannt mit {detection2['dots']} Augen")
            else:
                print("[ERGEBNIS] Foto 2 - Kein Würfel erkannt")
        else:
            print("[ERGEBNIS] Foto 2 - Kein Bild erhalten")

        # ====================================================================
        # PLACE SEQUENZ
        # ====================================================================
        
        # Greifer öffnen zum Ablegen
        print("[GRIPPER] Öffne Greifer...")
        robot.open_gripper(speed=GRIPPER_SPEED)

        # Zur Ablageposition fahren
        if not safe_move(robot, POS_10, "Position 10 (Ablage)"):
            return

        # Zurück zur Home-Position
        print("[INIT] Fahre zur Home-Position...")
        robot.move_to_home_pose()

        print("[SUCCESS] Sequenz erfolgreich abgeschlossen!")

    except Exception as e:
        # ====================================================================
        # FEHLERBEHANDLUNG
        # ====================================================================
        
        print(f"[ERROR] Fehler aufgetreten: {e}")
        
        # Notfall-Stopp: Learning Mode kurz an/aus um Bewegung zu stoppen
        if robot:
            try:
                robot.set_learning_mode(True)
                time.sleep(0.1)
                robot.set_learning_mode(False)
                print("[SAFETY] Bewegung gestoppt – Gelenke gesperrt")
            except:
                pass
                
    finally:
        # ====================================================================
        # CLEANUP
        # ====================================================================
        
        # Roboter sicher herunterfahren (Gelenke bleiben aktiv/gesperrt)
        if robot:
            try:
                robot.close_connection()
                print("[CLEANUP] Verbindung getrennt – Gelenke bleiben gesperrt")
            except:
                pass


if __name__ == "__main__":
    test_gripper_open()
