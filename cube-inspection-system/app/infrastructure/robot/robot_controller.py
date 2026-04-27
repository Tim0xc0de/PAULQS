import time
from pyniryo import NiryoRobot
from pyniryo.api.exceptions import NiryoRobotException
from app.infrastructure.robot.movements import (
    get_robot_ip, get_position, get_sequence, get_gripper_speed,
    get_gripper_close_at, get_gripper_open_at,
    get_sort_ok_sequence, get_sort_ok_exit,
    get_sort_nok_sequence, get_sort_nok_exit,
    get_safety_config
)
from app.utils.logger import log


class RobotSafetyError(Exception):
    """Kollision oder Wuerfelverlust."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class RobotController:
    """Steuert den Niryo-Roboter mit Safety (robot_config.json → safety).

    Grip-Monitoring:
      Nach jedem close_gripper und nach jeder Bewegung mit geschlossenem
      Greifer wird der Griff verifiziert (Nachgreifen + Joint-Vergleich).
      Konfigurierbar ueber safety.verify_grip (default: True).
    """

    def __init__(self):
        self.robot = None
        self._gripper_closed = False
        self._safety = get_safety_config()
        self._emergency = False

    # ================================================================
    # VERBINDUNG
    # ================================================================

    def connect(self) -> bool:
        try:
            ip = get_robot_ip()
            self.robot = NiryoRobot(ip)
            log("ROBOT", "INFO", f"Verbunden ({ip})")
            return True
        except Exception as e:
            log("ROBOT", "ERROR", f"Verbindungsfehler: {e}")
            return False

    def disconnect(self):
        """Trennt Verbindung. Bei Notfall bleibt sie offen (LED + Motoren)."""
        if not self.robot:
            return
        if self._emergency:
            log("ROBOT", "WARNING", "Notfall aktiv - Verbindung bleibt offen")
            return
        try: self.robot.led_ring_turn_off()
        except Exception: pass
        self.robot.close_connection()
        self.robot = None
        log("ROBOT", "INFO", "Verbindung getrennt")

    def force_disconnect(self):
        """Erzwingt Trennung (nach manuellem Recovery)."""
        if not self.robot:
            return
        try: self.robot.led_ring_turn_off()
        except Exception: pass
        self.robot.close_connection()
        self.robot = None
        self._emergency = False
        log("ROBOT", "INFO", "Verbindung erzwungen getrennt")

    # ================================================================
    # VORBEREITUNG
    # ================================================================

    def prepare(self) -> bool:
        if not self.robot:
            return False
        try:
            if self.robot.need_calibration():
                log("ROBOT", "ERROR", "Kalibrierung erforderlich!")
                return False
            self.robot.set_learning_mode(False)
            self.robot.set_arm_max_velocity(self._safety["arm_max_velocity"])
            self.robot.update_tool()
            self.robot.clear_collision_detected()
            self.robot.open_gripper(speed=get_gripper_speed())
            time.sleep(self._safety["gripper_open_wait_sec"])
            self.robot.move_to_home_pose()
            log("ROBOT", "INFO", "Roboter bereit")
            return True
        except Exception as e:
            log("ROBOT", "ERROR", f"Vorbereitung fehlgeschlagen: {e}")
            return False

    # ================================================================
    # BEWEGUNG
    # ================================================================

    def move_to(self, position_name: str) -> bool:
        """Faehrt zu Position. Safety-Checks nach jedem Move. Raises RobotSafetyError."""
        if not self.robot:
            return False
        pos = get_position(position_name)
        if not pos:
            log("ROBOT", "ERROR", f"Position '{position_name}' nicht in Config!")
            return False
        try:
            self.robot.move_joints(*pos)
            log("ROBOT", "INFO", f"\u2192 {position_name}")
            if self._safety["enabled"]:
                self._safety_check(position_name)
            return True
        except RobotSafetyError:
            raise
        except NiryoRobotException as e:
            self.emergency_stop(f"{position_name}: {e}")
            raise RobotSafetyError(f"Fehler bei '{position_name}'")
        except Exception as e:
            log("ROBOT", "ERROR", f"Bewegungsfehler '{position_name}': {e}")
            return False

    def go_home(self):
        if self.robot:
            self.robot.move_to_home_pose()
            log("ROBOT", "INFO", "Home")

    # ================================================================
    # GREIFER
    # ================================================================

    def grip(self) -> bool:
        """Schliesst den Greifer und verifiziert den Griff.

        Nach dem Schliessen wird der Griff geprueft (Nachgreifen + Joint-
        Vergleich). Schlaegt die Pruefung fehl, wird ein Notfall-Stopp
        ausgeloest und RobotSafetyError geworfen.

        Returns True bei Erfolg.
        Raises RobotSafetyError wenn kein Wuerfel gegriffen.
        """
        if not self.robot:
            return False
        self.robot.close_gripper(
            speed=get_gripper_speed(),
            max_torque_percentage=self._safety["gripper_max_torque_percentage"],
        )
        time.sleep(self._safety["gripper_close_wait_sec"])
        self._gripper_closed = True

        if self._safety["enabled"] and self._safety.get("verify_grip", True):
            if not self._check_grip():
                self._gripper_closed = False
                self.emergency_stop("Griff-Verifikation fehlgeschlagen - kein Wuerfel gegriffen")
                raise RobotSafetyError("Greifer leer oder Wuerfel verloren nach Greifen")
        log("ROBOT", "INFO", "Greifer zu")
        return True

    def release(self):
        if not self.robot:
            return
        self.robot.open_gripper(speed=get_gripper_speed())
        time.sleep(self._safety["gripper_open_wait_sec"])
        self._gripper_closed = False
        log("ROBOT", "INFO", "Greifer auf")

    # ================================================================
    # SAFETY
    # ================================================================

    def emergency_stop(self, reason: str):
        """LED rot, Greifer auf, Motoren halten. Kein Learning Mode."""
        self._emergency = True
        log("ROBOT", "ERROR", f"NOTFALL-STOPP: {reason}")
        try: self.robot.clear_collision_detected()
        except Exception: pass
        try: self.robot.open_gripper(speed=get_gripper_speed())
        except Exception: pass
        try: self.robot.led_ring_solid(self._safety["led_error_color"])
        except Exception: pass
        log("ROBOT", "WARNING", "Motoren aktiv. Manuell sichern!")

    def _safety_check(self, pos_name: str):
        """Kollision + Grip-Monitoring nach jedem Move.

        1. Kollisionserkennung (Niryo-intern)
        2. Grip-Monitoring: Nachgreifen + Joint-Vergleich wenn Greifer
           geschlossen sein sollte (nur bei verify_grip=True).

        Raises RobotSafetyError bei Problem.
        """
        if self._check_collision():
            self.emergency_stop(f"Kollision bei '{pos_name}'")
            raise RobotSafetyError(f"Kollision bei '{pos_name}'")

        if (self._gripper_closed
                and self._safety.get("verify_grip", True)):
            if not self._check_grip():
                self.emergency_stop(f"Wuerfelverlust bei '{pos_name}'")
                raise RobotSafetyError(f"Wuerfelverlust bei '{pos_name}'")

    def _check_collision(self) -> bool:
        try: return self.robot.get_collision_detected()
        except Exception: return False

    def _check_grip(self) -> bool:
        """Nachgreifen + Joint-Vergleich. True = Griff OK.

        Schliesst den Greifer erneut und vergleicht die Arm-Joints
        vorher/nachher. Aendert sich ein Joint um mehr als
        grip_loss_threshold → Wuerfel hat sich verschoben oder ist weg.

        Hinweis: Kann 'leeren Griff' (Greifer schliesst auf Luft) nicht
        zuverlaessig von 'festem Griff' unterscheiden, da pyniryo v1
        keine Greifer-Positionsrueckmeldung bietet. Fuer 100%ige Leer-
        Griff-Erkennung waere ein physischer Sensor am Greifer noetig.
        """
        threshold = self._safety["grip_loss_threshold"]
        try:
            joints_before = self.robot.get_joints()
            self.robot.close_gripper(
                speed=get_gripper_speed(),
                max_torque_percentage=self._safety["gripper_max_torque_percentage"],
            )
            time.sleep(self._safety["grip_check_wait_sec"])
            joints_after = self.robot.get_joints()
            try: self.robot.clear_collision_detected()
            except Exception: pass

            for j in range(6):
                diff = abs(float(joints_after[j]) - float(joints_before[j]))
                if diff > threshold:
                    log("ROBOT", "WARNING",
                        f"Grip-Check: Joint {j} Abweichung {diff:.4f} > {threshold}")
                    return False
            return True
        except NiryoRobotException as e:
            log("ROBOT", "ERROR", f"Grip-Check Fehler: {e}")
            return False

    # ================================================================
    # SEQUENZEN
    # ================================================================

    def run_sequence_with_capture(self, capture_steps=None, capture_fn=None):
        """Inspektionssequenz mit Grip-Monitoring.

        Ablauf pro Schritt:
          1. move_to(pos) → _safety_check (Kollision + Grip wenn closed)
          2. Greifer oeffnen/schliessen falls konfiguriert
          3. Foto aufnehmen falls konfiguriert

        Returns [(pos_name, image), ...]
        Raises RobotSafetyError bei Kollision oder Wuerfelverlust.
        """
        gripper_close = get_gripper_close_at()
        gripper_open = get_gripper_open_at()
        capture_wait = self._safety["capture_wait_sec"]
        capture_steps = capture_steps or []
        captures = []

        for pos_name in get_sequence():
            if not self.move_to(pos_name):
                return []

            if pos_name in gripper_open:
                time.sleep(1.5)
                self.release()

            if pos_name in gripper_close:
                self.grip()

            if capture_fn and pos_name in capture_steps:
                time.sleep(capture_wait)
                captures.append((pos_name, capture_fn()))

        log("ROBOT", "INFO", f"Inspektion fertig ({len(captures)} Bilder)")
        return captures

    def run_sort_sequence(self, is_ok: bool):
        """Sortierung: OK/NOK → Box → Greifer auf → Home"""
        if is_ok:
            seq, exit_pos = get_sort_ok_sequence(), get_sort_ok_exit()
            log("SORTING", "INFO", "OK \u2192 OK-Box")
        else:
            seq, exit_pos = get_sort_nok_sequence(), get_sort_nok_exit()
            log("SORTING", "WARNING", "NOK \u2192 NOK-Box")

        for pos_name in seq:
            self.move_to(pos_name)
        self.release()
        if exit_pos:
            self.move_to(exit_pos)
        self.go_home()
        log("SORTING", "INFO", "Sortierung fertig")
