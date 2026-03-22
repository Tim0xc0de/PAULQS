from pyniryo import NiryoRobot
from app.infrastructure.robot.movements import (
    get_robot_ip, get_position, get_sequence, get_gripper_speed,
    get_gripper_close_at, get_gripper_open_at
)


class RobotController:
    """Steuert den Niryo-Roboter."""
    
    def __init__(self):
        self.robot = None
    
    def connect(self) -> bool:
        """Verbindet mit dem Roboter."""
        try:
            self.robot = NiryoRobot(get_robot_ip())
            return True
        except Exception as e:
            print(f"[ROBOT] Verbindungsfehler: {e}")
            return False
    
    def disconnect(self):
        """Trennt die Verbindung."""
        if self.robot:
            self.robot.close_connection()
            self.robot = None
    
    def prepare(self) -> bool:
        """Bereitet den Roboter vor."""
        if not self.robot:
            return False
        try:
            if self.robot.need_calibration():
                print("[ROBOT] Kalibrierung erforderlich!")
                return False
            self.robot.set_learning_mode(False)
            self.robot.clear_collision_detected()
            return True
        except Exception as e:
            print(f"[ROBOT] Fehler: {e}")
            return False
    
    def move_to(self, position_name: str) -> bool:
        """Fährt zu einer Position aus der Config."""
        if not self.robot:
            return False
        pos = get_position(position_name)
        if not pos:
            return False
        try:
            self.robot.move_joints(*pos)
            return True
        except Exception as e:
            print(f"[ROBOT] Bewegungsfehler: {e}")
            return False
    
    def grip(self):
        """Greifer schließen."""
        if self.robot:
            self.robot.close_gripper()
    
    def release(self):
        """Greifer öffnen."""
        if self.robot:
            self.robot.open_gripper(speed=get_gripper_speed())
    
    def go_home(self):
        """Zur Home-Position fahren."""
        if self.robot:
            self.robot.move_to_home_pose()
    
    def run_sequence(self) -> bool:
        """Führt die Inspektionssequenz aus der Config aus."""
        self.run_sequence_with_capture()
        return True

    def run_sequence_with_capture(self, capture_steps=None, capture_fn=None):
        """Fährt die Sequenz ab. Ruft capture_fn bei jedem capture_step auf.
        Gibt eine Liste von (step_name, image) Tupeln zurück.
        """
        gripper_close = get_gripper_close_at()
        gripper_open = get_gripper_open_at()
        capture_steps = capture_steps or []
        captures = []

        for pos_name in get_sequence():
            print(f"[ROBOT] → {pos_name}")
            self.move_to(pos_name)

            if pos_name == gripper_close:
                self.grip()
            elif pos_name == gripper_open:
                self.release()

            if capture_fn and pos_name in capture_steps:
                print(f"[ROBOT] Kamera-Aufnahme bei {pos_name}")
                img = capture_fn()
                captures.append((pos_name, img))

        self.go_home()
        print("[ROBOT] Sequenz fertig!")
        return captures
