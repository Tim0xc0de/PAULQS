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

# Schritt 1-11: Gemeinsame Sequenz
POS_1 = JointsPosition(-0.3842, -0.1126, -1.0294, -0.0413, -0.3068, -0.3634)  # Über Würfel
POS_2 = JointsPosition(-0.372, -0.4837, -0.8779, 0.0292, -0.3038, -0.3619)   # Am Würfel
# Schritt 3: Greifer zu
POS_4 = JointsPosition(-0.3248, 0.4539, -0.9067, 0.1396, -0.8867, -0.3481)   # Hoch fahren
POS_5 = JointsPosition(0.7495, 0.2948, -0.7446, -0.0827, -1.0416, 0.109)     # Oben rechts
POS_6 = JointsPosition(0.1651, -0.861, -0.8688, -1.3375, 1.474, -0.0827)     # Eingang Kamera-Gehäuse
POS_7 = JointsPosition(0.5669, -0.8943, -0.7461, -0.9279, 1.4986, -0.029)    # Vor Kamera (Seite 1)
# Schritt 8: Foto machen
POS_9 = JointsPosition(0.6065, -0.8504, -0.7491, -0.9601, 1.54, 2.528)       # Greifer drehen (Seite 2)
POS_10 = JointsPosition(0.1484, -0.6792, -0.9885, -1.336, 1.3835, 2.5296)    # Raus fahren
POS_11 = JointsPosition(0.1179, 0.0146, -0.843, 0.0415, -0.7778, 0.1182)     # Über Sortierboxen

# Schritt 12-15: OK-Pfad
POS_OK_12 = JointsPosition(-0.0555, -0.4186, -0.4583, -0.1732, -0.7885, 0.1059)  # Über OK-Box
POS_OK_13 = JointsPosition(-0.0646, -0.5428, -0.64, -0.0658, -0.3835, 0.0031)   # Vor OK-Box
# Schritt 14: Greifer auf
POS_OK_15 = JointsPosition(-0.0357, -0.1747, -0.64, -0.0858, -0.3881, 0.0077)   # Letzter Schritt vor Home

# Schritt 12-15: NOK-Pfad
POS_NOK_12 = JointsPosition(0.1651, -0.3913, -0.5098, 0.1734, -0.7011, -0.0106) # Über NOK-Box
POS_NOK_13 = JointsPosition(0.1879, -0.6216, -0.5188, 0.1059, -0.5109, 0.1504)  # Vor NOK-Box
# Schritt 14: Greifer auf
POS_NOK_15 = JointsPosition(0.1879, -0.6216, -0.5188, 0.1059, -0.5109, 0.1504)  # Letzter Schritt vor Home

# ============================================================================
# HELPER-FUNKTIONEN
# ============================================================================

def safe_move(robot, position, name):
    """
    Führt eine Bewegung aus und prüft danach auf Kollision.
    
    Args:
        robot: NiryoRobot Instanz
        position: JointsPosition Zielposition
        name: Beschreibender Name für Logging
        
    Returns:
        bool: True bei erfolgreicher Bewegung, False bei Kollision
    """
    print(f"[MOVE] Fahre zu {name}...")
    
    try:
        robot.move(position)
    except Exception as e:
        print(f"[ERROR] Bewegungsfehler bei {name}: {e}")
        return False
    
    # Kollision nach Bewegung prüfen
    if robot.collision_detected:
        print(f"[KOLLISION] Kollision bei {name} erkannt!")
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
    Haupttest: Komplette Pick-Inspect-Sort Sequenz mit Würfelerkennung.
    
    Ablauf:
    1.  Über Würfel fahren
    2.  Am Würfel positionieren
    3.  Greifer zu
    4.  Hoch fahren
    5.  Oben rechts fahren
    6.  Eingangsposition ins Kamera-Gehäuse
    7.  Ins Gehäuse fahren vor Kamera (Foto Seite 1)
    8.  Foto machen
    9.  Greifer drehen (Foto Seite 2)
    10. Raus fahren
    11. Über Sortierboxen fahren
    12-16. Sortierung (OK oder NOK Pfad) + Home
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

        # Greifer aktivieren
        print("[INIT] Aktiviere Greifer (update_tool)...")
        robot.update_tool()

        # Kollisionsstatus zurücksetzen
        print("[INIT] Lösche Kollisionsstatus...")
        robot.clear_collision_detected()

        # Zur Startposition fahren
        print("[INIT] Fahre zur Home-Position...")
        robot.move_to_home_pose()

        # ====================================================================
        # SCHRITT 1-3: PICK SEQUENZ
        # ====================================================================
        
        # Greifer öffnen für Pick
        print("[GRIPPER] Öffne Greifer...")
        robot.open_gripper(speed=GRIPPER_SPEED)

        # Schritt 1: Über Würfel
        if not safe_move(robot, POS_1, "Schritt 1 (über Würfel)"):
            return

        # Schritt 2: Am Würfel
        if not safe_move(robot, POS_2, "Schritt 2 (am Würfel)"):
            return

        # Schritt 3: Greifer zu
        if not grip_object(robot):
            print("[ERROR] Greifen fehlgeschlagen!")
            return

        # ====================================================================
        # SCHRITT 4-7: TRANSPORT ZUR KAMERA
        # ====================================================================
        
        # Schritt 4: Hoch fahren
        if not safe_move(robot, POS_4, "Schritt 4 (Hoch fahren)"):
            return

        # Schritt 5: Oben rechts
        if not safe_move(robot, POS_5, "Schritt 5 (Oben rechts)"):
            return

        # Schritt 6: Eingangsposition ins Kamera-Gehäuse
        if not safe_move(robot, POS_6, "Schritt 6 (Eingang Kamera-Gehäuse)"):
            return

        # Schritt 7: Ins Gehäuse fahren vor Kamera
        if not safe_move(robot, POS_7, "Schritt 7 (vor Kamera - Seite 1)"):
            return

        # ====================================================================
        # SCHRITT 8: FOTO SEITE 1
        # ====================================================================
        
        # Stabilisierungszeit vor Foto
        print("[CAMERA] Warte 3 Sekunden für Stabilisierung...")
        time.sleep(3)
        
        # Foto aufnehmen
        print("[CAMERA] Schritt 8 - Mache Foto 1...")
        img_compressed = robot.get_img_compressed()
        img1 = cv2.imdecode(np.frombuffer(img_compressed, dtype=np.uint8), cv2.IMREAD_COLOR)
        
        detection1 = None
        if img1 is not None:
            detection1 = detect_cube(img1)
            if detection1:
                print(f"[ERGEBNIS] Foto 1 - Würfel erkannt mit {detection1['dots']} Augen")
            else:
                print("[ERGEBNIS] Foto 1 - Kein Würfel erkannt")
        else:
            print("[ERGEBNIS] Foto 1 - Kein Bild erhalten")

        # ====================================================================
        # SCHRITT 9: GREIFER DREHEN + FOTO SEITE 2
        # ====================================================================
        
        # Schritt 9: Greifer drehen für Seite 2
        if not safe_move(robot, POS_9, "Schritt 9 (Greifer drehen - Seite 2)"):
            return

        # Stabilisierungszeit vor Foto
        print("[CAMERA] Warte 3 Sekunden für Stabilisierung...")
        time.sleep(3)
        
        # Foto aufnehmen
        print("[CAMERA] Mache Foto 2...")
        img_compressed = robot.get_img_compressed()
        img2 = cv2.imdecode(np.frombuffer(img_compressed, dtype=np.uint8), cv2.IMREAD_COLOR)
        
        detection2 = None
        if img2 is not None:
            detection2 = detect_cube(img2)
            if detection2:
                print(f"[ERGEBNIS] Foto 2 - Würfel erkannt mit {detection2['dots']} Augen")
            else:
                print("[ERGEBNIS] Foto 2 - Kein Würfel erkannt")
        else:
            print("[ERGEBNIS] Foto 2 - Kein Bild erhalten")

        # ====================================================================
        # SCHRITT 10-11: RAUS FAHREN & ÜBER SORTIERBOXEN
        # ====================================================================
        
        # Schritt 10: Raus fahren
        if not safe_move(robot, POS_10, "Schritt 10 (raus fahren)"):
            return

        # Schritt 11: Über Sortierboxen fahren
        if not safe_move(robot, POS_11, "Schritt 11 (über Sortierboxen)"):
            return

        # ====================================================================
        # SCHRITT 12-16: SORTIERUNG (OK / NOK)
        # ====================================================================
        
        # Ergebnis auswerten: Würfel ist OK wenn beide Seiten erkannt wurden
        cube_ok = (detection1 is not None) and (detection2 is not None)
        
        if cube_ok:
            print("[SORT] Würfel OK – fahre zur OK-Box")
            
            # Schritt 12: Über OK-Box
            if not safe_move(robot, POS_OK_12, "Schritt 12 (über OK-Box)"):
                return
            
            # Schritt 13: Vor OK-Box
            if not safe_move(robot, POS_OK_13, "Schritt 13 (vor OK-Box)"):
                return
            
            # Schritt 14: Greifer auf
            print("[GRIPPER] Schritt 14 - Öffne Greifer...")
            robot.open_gripper(speed=GRIPPER_SPEED)
            
            # Schritt 15: Letzter Schritt vor Home
            if not safe_move(robot, POS_OK_15, "Schritt 15 (vor Home)"):
                return
        else:
            print("[SORT] Würfel NOK – fahre zur NOK-Box")
            
            # Schritt 12: Über NOK-Box
            if not safe_move(robot, POS_NOK_12, "Schritt 12 (über NOK-Box)"):
                return
            
            # Schritt 13: Vor NOK-Box
            if not safe_move(robot, POS_NOK_13, "Schritt 13 (vor NOK-Box)"):
                return
            
            # Schritt 14: Greifer auf
            print("[GRIPPER] Schritt 14 - Öffne Greifer...")
            robot.open_gripper(speed=GRIPPER_SPEED)
            
            # Schritt 15: Letzter Schritt vor Home
            if not safe_move(robot, POS_NOK_15, "Schritt 15 (vor Home)"):
                return

        # Schritt 16: Home-Position
        print("[INIT] Schritt 16 - Fahre zur Home-Position...")
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
