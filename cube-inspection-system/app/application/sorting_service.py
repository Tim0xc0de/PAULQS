# ====================================================================
# IMPORTS
# ====================================================================
from app.utils.logger import log

# ====================================================================
# SORTING SERVICE
# ====================================================================
def sort_cube(controller, is_ok: bool):
    """
    Sortiert den Würfel in die richtige Kiste (Schritt 12-16).
    
    Ablauf wie test_gripper.py:
    12. Über Box fahren
    13. Vor Box fahren (Drop-Position)
    14. Greifer auf
    15. Exit-Position (letzter Schritt vor Home)
    16. Home-Position
    
    Args:
        controller: Verbundener RobotController (Greifer hält den Würfel)
        is_ok: True = Würfel korrekt, False = Würfel fehlerhaft
    """
    controller.run_sort_sequence(is_ok)
