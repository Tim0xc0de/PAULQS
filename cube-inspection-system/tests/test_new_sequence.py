"""
Test-Script: Sequenz abfahren mit Safety.
Aktionen: move, open, close, home
Safety-Parameter in robot_config.json → safety
"""

import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pyniryo import NiryoRobot
from pyniryo.api.exceptions import NiryoRobotException

# ====================================================================
# CONFIG
# ====================================================================
_cfg = json.load(open(os.path.join(os.path.dirname(__file__),
    "..", "app", "infrastructure", "robot", "robot_config.json")))

IP    = _cfg["robot_ip"]
SPEED = _cfg["gripper_speed"]
S     = {
    "enabled": True, "arm_max_velocity": 80, "grip_loss_threshold": 0.005,
    "gripper_max_torque_percentage": 100, "grip_check_wait_sec": 0.2,
    "gripper_close_wait_sec": 0.5, "gripper_open_wait_sec": 0.5,
    "led_error_color": [255, 0, 0], "led_ok_color": [0, 255, 0],
    **_cfg.get("safety", {})
}

# ====================================================================
# SEQUENZ
# ====================================================================
SEQUENCE = [
    ("home",  None),
    ("open",  None),
    ("move",  [-0.2808, 0.0389, -0.5022, -0.0628, -1.0846, -0.3006]),
    ("move",  [-0.3493, -0.4959, -0.7674, -0.0904, -0.3468, -0.2929]),
    ("close", None),
    ("move",  [-0.3021, 0.1661, -0.475, -0.0873, -1.238, -0.2638]),
    ("move",  [-0.0981, -0.7504, -0.7992, -1.5922, 1.5354, -0.0367]),
    ("move",  [0.4528, -0.7959, -0.681, -1.0752, 1.5093, 0.0983]),
    ("move",  [0.4285, -0.7383, -0.7128, -1.089, 1.4326, 2.5266]),
    ("move",  [0.4422, -0.8277, -0.678, -1.0798, 1.5093, 0.0415]),
    ("open",  None),
    ("move",  [-0.0388, -0.8277, -0.7674, -1.5692, 1.5201, -0.0475]),
    ("move",  [0.1743, -0.9443, -0.7143, -1.3391, 1.5799, 1.4604]),
    ("move",  [0.2352, -0.9443, -0.7113, -1.267, 1.5968, 1.4497]),
    ("move",  [0.4178, -0.958, -0.634, -1.0921, 1.6045, 1.4758]),
    ("close", None),
    ("move",  [0.4178, -0.7913, -0.6961, -1.0814, 1.5845, 1.5555]),
    ("move",  [0.4406, -0.7928, -0.684, -1.0982, 1.5615, 0.0599]),
    ("move",  [0.4178, -0.7989, -0.6961, -1.0967, 1.5753, 2.5281]),
    ("move",  [0.4117, -0.7989, -0.6961, -1.0998, 1.56, 0.0308]),
    ("move",  [-0.0525, -0.7459, -0.7522, -1.6014, 1.5784, 0.0154]),
    ("home",  None),
]

# ====================================================================
# SAFETY
# ====================================================================

def emergency_stop(robot, reason):
    """LED rot, Greifer auf, Motoren halten. Wartet auf ENTER."""
    print(f"\n  !!! NOTFALL-STOPP: {reason} !!!")
    try: robot.clear_collision_detected()
    except Exception: pass
    try: robot.open_gripper(speed=SPEED)
    except Exception: pass
    try: robot.led_ring_solid(S["led_error_color"])
    except Exception: pass
    print("  Motoren aktiv. Roboter manuell sichern.")
    input("  >>> ENTER zum Trennen <<<")
    try: robot.led_ring_turn_off()
    except Exception: pass


def check_collision(robot):
    try: return robot.get_collision_detected()
    except Exception: return False


def check_grip(robot):
    """Nachgreifen + Joint-Vergleich. True = Wuerfel da."""
    joints_before = robot.get_joints()
    robot.close_gripper(speed=SPEED, max_torque_percentage=S["gripper_max_torque_percentage"])
    time.sleep(S["grip_check_wait_sec"])
    joints_after = robot.get_joints()
    try: robot.clear_collision_detected()
    except Exception: pass
    for j in range(6):
        if abs(float(joints_after[j]) - float(joints_before[j])) > S["grip_loss_threshold"]:
            return False
    return True


# ====================================================================
# HAUPTLOGIK
# ====================================================================

def run_sequence(sequence):
    robot = None
    gripper_closed = False

    try:
        print(f"Verbinde {IP}...")
        robot = NiryoRobot(IP)
        if robot.need_calibration():
            print("Kalibrierung noetig!"); return

        robot.set_learning_mode(False)
        robot.set_arm_max_velocity(S["arm_max_velocity"])
        robot.clear_collision_detected()
        robot.update_tool()
        robot.open_gripper(speed=SPEED)
        time.sleep(S["gripper_open_wait_sec"])
        print(f"Safety {'AN' if S['enabled'] else 'AUS'}")

        for i, (action, data) in enumerate(sequence, 1):
            if action == "home":
                print(f"  {i}: Home")
                robot.move_to_home_pose()

            elif action == "open":
                print(f"  {i}: Greifer auf")
                robot.open_gripper(speed=SPEED)
                time.sleep(S["gripper_open_wait_sec"])
                gripper_closed = False

            elif action == "close":
                print(f"  {i}: Greifer zu")
                robot.close_gripper(speed=SPEED, max_torque_percentage=S["gripper_max_torque_percentage"])
                time.sleep(S["gripper_close_wait_sec"])
                gripper_closed = True

            elif action == "move":
                print(f"  {i}: Move {data}")
                try:
                    robot.move_joints(*data)
                except NiryoRobotException as e:
                    emergency_stop(robot, f"Schritt {i}: {e}")
                    return

                if S["enabled"]:
                    if check_collision(robot):
                        emergency_stop(robot, f"Kollision nach Schritt {i}")
                        return
                    if gripper_closed and not check_grip(robot):
                        emergency_stop(robot, f"Wuerfel verloren nach Schritt {i}")
                        return

        print("\nSequenz OK!")
        try:
            robot.led_ring_solid(S["led_ok_color"])
            time.sleep(2)
            robot.led_ring_turn_off()
        except Exception: pass

    except Exception as e:
        print(f"\nFehler: {e}")
        if robot: emergency_stop(robot, str(e))

    finally:
        if robot:
            robot.close_connection()
            print("Verbindung getrennt")


if __name__ == "__main__":
    run_sequence(SEQUENCE)
