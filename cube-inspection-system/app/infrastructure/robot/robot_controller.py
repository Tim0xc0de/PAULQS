import time
from pyniryo import NiryoRobot
from app.infrastructure.robot.movements import (
    get_robot_ip, get_position, get_sequence, get_gripper_speed,
    get_gripper_close_at, get_gripper_open_at, get_capture_at,
    get_sort_ok_sequence, get_sort_ok_exit,
    get_sort_nok_sequence, get_sort_nok_exit
)
from app.utils.logger import log

CAPTURE_WAIT = 3  # Sekunden warten vor Foto für Stabilisierung


class RobotController:
    """Steuert den Niryo-Roboter.
    
    Ablauf 1:1 wie test_gripper.py:
    Home → Greifer auf → step1 → step2 → Greifer zu → step4-7 → Foto1
    → step9 → Foto2 → step10-11 → Sortierung (OK/NOK) → Home
    """
    
    def __init__(self):
        self.robot = None
    
    def connect(self) -> bool:
        """Verbindet mit dem Roboter."""
        try:
            ip = get_robot_ip()
            self.robot = NiryoRobot(ip)
            log("ROBOT", "INFO", f"Verbunden mit Roboter ({ip})")
            return True
        except Exception as e:
            log("ROBOT", "ERROR", f"Verbindungsfehler: {e}")
            return False
    
    def disconnect(self):
        """Trennt die Verbindung."""
        if self.robot:
            self.robot.close_connection()
            self.robot = None
            log("ROBOT", "INFO", "Verbindung getrennt")
    
    def prepare(self) -> bool:
        """Bereitet den Roboter vor (wie test_gripper.py Initialisierung)."""
        if not self.robot:
            return False
        try:
            if self.robot.need_calibration():
                log("ROBOT", "ERROR", "Kalibrierung erforderlich!")
                return False
            self.robot.set_learning_mode(False)
            self.robot.set_arm_max_velocity(100)
            self.robot.update_tool()
            self.robot.clear_collision_detected()
            self.robot.move_to_home_pose()
            log("ROBOT", "INFO", "Roboter vorbereitet (Learning-Mode aus, Tool aktualisiert, Home)")
            return True
        except Exception as e:
            log("ROBOT", "ERROR", f"Vorbereitung fehlgeschlagen: {e}")
            return False
    
    def move_to(self, position_name: str) -> bool:
        """Fährt zu einer Position aus der Config."""
        if not self.robot:
            return False
        pos = get_position(position_name)
        if not pos:
            log("ROBOT", "ERROR", f"Position '{position_name}' nicht in Config!")
            return False
        try:
            self.robot.move_joints(*pos)
            log("ROBOT", "INFO", f"Position '{position_name}' erreicht")
            return True
        except Exception as e:
            log("ROBOT", "ERROR", f"Bewegungsfehler bei '{position_name}': {e}")
            return False
    
    def grip(self):
        """Greifer schließen (wie test_gripper.py grip_object)."""
        if not self.robot:
            return False
        self.robot.close_gripper(speed=get_gripper_speed())
        time.sleep(0.5)
        log("ROBOT", "INFO", "Greifer geschlossen")
        return True
    
    def release(self):
        """Greifer öffnen."""
        if self.robot:
            self.robot.open_gripper(speed=get_gripper_speed())
            log("ROBOT", "INFO", "Greifer geoeffnet")
    
    def go_home(self):
        """Zur Home-Position fahren."""
        if self.robot:
            self.robot.move_to_home_pose()
            log("ROBOT", "INFO", "Home-Position erreicht")

    def run_sequence_with_capture(self, capture_steps=None, capture_fn=None):
        """Fährt Schritt 1-11 ab, exakt wie test_gripper.py.
        
        Ablauf:
        1. Greifer auf
        2. step1_over_cube → step2_at_cube → Greifer zu
        3. step4_up → step5 → step6 → step7_before_cam → [Foto]
        4. step9_cam_rotated → [Foto]
        5. step10_exit_cam → step11_over_boxes
        
        Returns: Liste von (step_name, image) Tupeln
        """
        gripper_close = get_gripper_close_at()
        gripper_open = get_gripper_open_at()
        capture_steps = capture_steps or []
        captures = []

        for pos_name in get_sequence():
            # Greifer öffnen VOR dem Fahren (wie im Test: erst open, dann move)
            if pos_name == gripper_open:
                log("ROBOT", "INFO", f"Greifer oeffnen vor {pos_name}")
                self.release()

            # Zur Position fahren
            log("ROBOT", "INFO", f"Fahre zu Position: {pos_name}")
            if not self.move_to(pos_name):
                log("ROBOT", "ERROR", f"Bewegung zu {pos_name} fehlgeschlagen - Sequenz abgebrochen")
                return []

            # Greifer schließen NACH Ankunft (wie im Test: erst move, dann close)
            if pos_name == gripper_close:
                log("ROBOT", "INFO", f"Greifer schliessen nach {pos_name}")
                self.grip()

            # Foto machen NACH Ankunft (mit Wartezeit wie im Test)
            if capture_fn and pos_name in capture_steps:
                log("ROBOT", "INFO", f"Warte {CAPTURE_WAIT}s fuer Stabilisierung...")
                time.sleep(CAPTURE_WAIT)
                log("ROBOT", "INFO", f"Kamera-Aufnahme bei {pos_name}")
                img = capture_fn()
                captures.append((pos_name, img))

        log("ROBOT", "INFO", f"Inspektionssequenz abgeschlossen ({len(captures)} Bilder)")
        return captures

    def run_sort_sequence(self, is_ok: bool):
        """Fährt Schritt 12-16 ab (Sortierung), exakt wie test_gripper.py.
        
        OK-Pfad:  sort_ok_above → sort_ok_drop → Greifer auf → sort_ok_exit → Home
        NOK-Pfad: sort_nok_above → sort_nok_drop → Greifer auf → sort_nok_exit → Home
        """
        if is_ok:
            sequence = get_sort_ok_sequence()
            exit_pos = get_sort_ok_exit()
            log("SORTING", "INFO", "Wuerfel ist OK - fahre zur OK-Box")
        else:
            sequence = get_sort_nok_sequence()
            exit_pos = get_sort_nok_exit()
            log("SORTING", "WARNING", "Wuerfel ist NICHT OK - fahre zur NOK-Box")

        # Schritt 12-13: Über Box → Vor Box
        for pos_name in sequence:
            log("SORTING", "INFO", f"Fahre zu {pos_name}")
            self.move_to(pos_name)

        # Schritt 14: Greifer auf
        self.release()
        log("SORTING", "INFO", "Greifer geoeffnet - Wuerfel abgelegt")

        # Schritt 15: Exit-Position
        if exit_pos:
            log("SORTING", "INFO", f"Fahre zu {exit_pos}")
            self.move_to(exit_pos)

        # Schritt 16: Home
        self.go_home()
        log("SORTING", "INFO", "Sortierung abgeschlossen")
