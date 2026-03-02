# Logging utilities
def log_system_event(db, module, level, message):
    new_log = SystemLog(module=module, level=level, message=message)
    db.add(new_log)
    db.commit()

# Beispielaufruf, wenn die Kamera nicht gefunden wird:
# log_system_event(db, "VISION", "ERROR", "USB-Kamera konnte nicht initialisiert werden.")