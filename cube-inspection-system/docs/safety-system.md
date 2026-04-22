# Sicherheitssystem (Safety System)

## Uebersicht

Das Sicherheitssystem schuetzt den Niryo-Roboter und die Umgebung waehrend
des Betriebs. Es erkennt zwei Hauptprobleme:

1. **Wuerfelverlust** – Der Wuerfel faellt aus dem Greifer
2. **Kollision** – Der Roboter kollidiert mit einem Hindernis

Bei einem Problem wird sofort ein **Notfall-Stopp** ausgeloest.

---

## Probleme und Loesungen

### Problem 1: `robot.move(JointsPosition(...))` bewegt den Roboter nicht

**Symptom:** Befehle geben `OK: None` zurueck, aber der Roboter bewegt sich nicht.
Nur Greifer-Aktionen (open/close) funktionieren.

**Ursache:** Die Methode `robot.move(JointsPosition(...))` fuehrt bei pyniryo
keine tatsaechliche Bewegung aus.

**Loesung:** `robot.move_joints(*pos)` verwenden – wie in `test_robot.py` und
`robot_controller.py` bereits korrekt implementiert.

### Problem 2: Gelenkpositionen ausserhalb der Limits

**Symptom:** `robot.move_joints(...)` gibt `OK: None` zurueck, aber der Roboter
bewegt sich trotzdem nicht. Bekannte Positionen funktionieren.

**Ursache:** Die angegebenen Gelenkwerte lagen ausserhalb der Software-Limits
des Niryo Ned2 (z.B. Joint 1 bei -3.17 rad, Limit ist ~±3.05 rad).

**Loesung:** Positionen mit dem Teach-Script (`test_new_sequence.py` im
Teach-Modus) oder ueber Niryo Studio direkt am Roboter aufnehmen.

### Problem 3: Greifer-Check loest immer False Positive aus

**Symptom:** Nach jedem Move meldet das System "Wuerfel gefallen", obwohl der
Wuerfel noch im Greifer ist.

**Ursache (Bug):** Der Grip-Check verglich die Gelenkpositionen nach dem
initialen `close_gripper` (an Position A) mit den Gelenkpositionen nach
dem Nachgreifen (an Position B). Da der Roboter sich bewegt hat, sind
natuerlich alle 6 Gelenke unterschiedlich.

**Loesung:** Gelenkpositionen direkt **vor** und **nach** dem Nachgreifen
an der **aktuellen** Position vergleichen. Nur die Differenz durch das
Nachgreifen selbst wird gemessen.

### Problem 4: LED-Ring geht sofort wieder aus

**Symptom:** Bei Notfall-Stopp leuchtet die LED nur kurz rot und geht dann aus.

**Ursache:** `robot.close_connection()` im `finally`-Block setzt die LED zurueck.

**Loesung:**
- **Test-Script:** `emergency_stop()` wartet auf `input()` (ENTER) bevor
  die Verbindung getrennt wird. LED bleibt rot bis der Benutzer bestaetigt.
- **Produktiv-Code:** `disconnect()` wird bei aktivem Notfall uebersprungen.
  Erst `force_disconnect()` trennt die Verbindung und schaltet die LED aus.

### Problem 5: Learning Mode bei Notfall schaltet Motoren ab

**Symptom:** Bei Notfall-Stopp faellt der Roboterarm herunter.

**Ursache:** `robot.set_learning_mode(True)` deaktiviert alle Motoren.

**Loesung:** Bei Notfall-Stopp wird **kein** Learning Mode aktiviert.
Die Motoren bleiben aktiv und halten den Arm in seiner Position.
Der Benutzer muss den Roboter manuell (z.B. ueber Niryo Studio)
in eine sichere Position bringen.

---

## Konfiguration

Alle Sicherheitsparameter sind in `robot_config.json` unter `safety` konfigurierbar:

```json
{
  "safety": {
    "enabled": true,
    "grip_loss_threshold": 0.005,
    "gripper_max_torque_percentage": 100,
    "gripper_hold_torque_percentage": 50,
    "grip_check_wait_sec": 0.2,
    "gripper_close_wait_sec": 0.5,
    "gripper_open_wait_sec": 0.5,
    "led_error_color": [255, 0, 0],
    "led_ok_color": [0, 255, 0],
    "capture_wait_sec": 3
  }
}
```

### Parameter-Beschreibung

| Parameter | Typ | Default | Beschreibung |
|---|---|---|---|
| `enabled` | bool | `true` | Safety-System ein/aus. Bei `false` werden keine Checks durchgefuehrt. |
| `grip_loss_threshold` | float | `0.005` | Schwellwert in rad fuer die Grip-Pruefung. Kleinerer Wert = empfindlicher, groesserer Wert = toleranter. |
| `gripper_max_torque_percentage` | int | `100` | Maximale Greifer-Kraft beim Schliessen und Oeffnen (0-100%). |
| `gripper_hold_torque_percentage` | int | `50` | Haltekraft des Greifers im offenen Zustand (0-100%). |
| `grip_check_wait_sec` | float | `0.2` | Wartezeit nach dem Nachgreifen bevor Joints gelesen werden. |
| `gripper_close_wait_sec` | float | `0.5` | Wartezeit nach dem Schliessen des Greifers. |
| `gripper_open_wait_sec` | float | `0.5` | Wartezeit nach dem Oeffnen des Greifers. |
| `led_error_color` | [R,G,B] | `[255,0,0]` | LED-Farbe bei Notfall-Stopp (Rot). |
| `led_ok_color` | [R,G,B] | `[0,255,0]` | LED-Farbe bei erfolgreicher Sequenz (Gruen). |
| `capture_wait_sec` | int | `3` | Wartezeit vor Fotoaufnahme fuer Stabilisierung. |

### Tuning-Tipps

- **False Positives (Fehlalarme):** `grip_loss_threshold` erhoehen (z.B. auf `0.01`)
- **Wuerfel faellt unbemerkt:** `grip_loss_threshold` verringern (z.B. auf `0.002`)
- **Safety komplett deaktivieren:** `"enabled": false` setzen
- **LED-Farbe aendern:** RGB-Werte 0-255 fuer `led_error_color` / `led_ok_color`

---

## Architektur

### Dateien

| Datei | Rolle |
|---|---|
| `robot_config.json` | Safety-Parameter (Schwellwerte, Farben, Wartezeiten) |
| `movements.py` | `get_safety_config()` – laedt Safety-Config mit Defaults |
| `robot_controller.py` | `RobotController` mit integrierten Safety-Methoden |
| `inspection_service.py` | Faengt `RobotSafetyError` und verhindert `disconnect()` |
| `test_new_sequence.py` | Test-Script mit gleicher Safety-Logik, liest Config aus JSON |

### Ablauf bei Notfall-Stopp

```
Move → Kollisions-Check → Grip-Check → FEHLER erkannt
  ↓
emergency_stop()
  ├── Greifer oeffnen (100%)
  ├── LED rot
  └── Motoren bleiben aktiv (KEIN Learning Mode)
  ↓
RobotSafetyError wird ausgeloest
  ↓
disconnect() wird uebersprungen (LED + Motoren bleiben an)
  ↓
Benutzer bringt Roboter manuell in sichere Position
  ↓
force_disconnect() → LED aus, Verbindung getrennt
```

### RobotSafetyError

Neue Exception-Klasse die bei Sicherheitsproblemen ausgeloest wird:

```python
class RobotSafetyError(Exception):
    def __init__(self, reason: str):
        self.reason = reason
```

Wird in `inspection_service.py` separat gefangen, damit `disconnect()` 
uebersprungen wird und die LED rot bleibt.
