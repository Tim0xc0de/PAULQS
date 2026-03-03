from pyniryo import NiryoRobot, JointsPosition
import subprocess
import sys
import os

ROBOT_IP = "10.10.10.10"

# 4 Positionen (Joints in rad) als JointsPosition Objekte
POS_1 = JointsPosition(-0.707, -0.723, -0.363, 0.043, -0.124, 0.006)  # Greifer zu
POS_2 = JointsPosition(-0.704,  0.057, -0.364,  0.112, -0.138,  0.014)
POS_3 = JointsPosition( 0.772,  0.127, -0.317, -0.054, -0.147,  0.017)
POS_4 = JointsPosition( 0.634,  0.043, -1.057,  0.072,  0.492, -0.089)
POS_5 = JointsPosition( 0.431, -1.064, -0.277, -0.606,  1.147,  0.109)
POS_6 = JointsPosition( 0.372, -1.029, -0.460, -0.572,  1.307,  0.042)  # Greifer auf

# Greifer-Öffnungsweite (max)
GRIPPER_SPEED = 500
GRIPPER_MAX_OPEN = 1000  # Maximale Öffnung

def move_sequence():
    """Fährt 4 Positionen ab mit Greifer-Aktionen."""
    robot = None
    try:
        print(f"[ROBOT] Verbinde mit PAUL ({ROBOT_IP})...")
        robot = NiryoRobot(ROBOT_IP)
        
        if robot.need_calibration():
            print("[ROBOT] Roboter braucht Kalibrierung – Test wird übersprungen (Greifarm muss manuell abgenommen werden).")
            return
        
        print("[ROBOT] Setze Learning Mode aus...")
        robot.set_learning_mode(False)
        
        print("[ROBOT] Lösche Kollisionsstatus...")
        robot.clear_collision_detected()
        
        # Position 1: Erst fahren, dann greifen
        print("[ROBOT] Fahre zu Position 1...")
        robot.move_joints(*POS_1)
        print("[ROBOT] Greifer schließen...")
        robot.close_gripper()
        
        # Position 2
        print("[ROBOT] Fahre zu Position 2...")
        robot.move_joints(*POS_2)
        
        # Position 3
        print("[ROBOT] Fahre zu Position 3...")
        robot.move_joints(*POS_3)
        
        # Position 4
        print("[ROBOT] Fahre zu Position 4...")
        robot.move_joints(*POS_4)

        # Position 5
        print("[ROBOT] Fahre zu Position 5...")
        robot.move_joints(*POS_5)

        print("[ROBOT] Greifer weit öffnen...")
        robot.open_gripper(speed=GRIPPER_SPEED, max_torque_percentage=100, hold_torque_percentage=50)

        # Position 6: Greifer auf
        print("[ROBOT] Fahre zu Position 6...")
        robot.move_joints(*POS_6)

        print("[ROBOT] Fahre zur Home-Position...")
        robot.move_to_home_pose()
        
        print("[ROBOT] Sequenz abgeschlossen!")
        
    except Exception as e:
        print(f"[ROBOT] Fehler: {e}")
    finally:
        if robot:
            robot.close_connection()

if __name__ == "__main__":
    move_sequence()
    
    # Nach Roboter-Sequenz automatisch Vision starten
    print("[VISION] Starte Würfelerkennung...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    vision_script = os.path.join(script_dir, "test_vision.py")
    subprocess.run([sys.executable, vision_script])