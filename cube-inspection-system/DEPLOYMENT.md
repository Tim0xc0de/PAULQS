# Deployment auf Niryo-Roboter

Diese Anleitung zeigt, wie du das komplette PAULQS Cube Inspection System direkt auf dem Niryo-Roboter installierst und startest.

---

## Voraussetzungen

- **Niryo-Roboter** mit SSH-Zugang
- **Netzwerkverbindung** zum Roboter (WLAN oder Ethernet)
- **SSH-Client** auf deinem Computer

---

## 1. SSH-Verbindung zum Roboter herstellen

```bash
# Standard Niryo SSH-Zugangsdaten (falls nicht geändert):
# Benutzer: niryo
# Passwort: robotics

ssh niryo@10.10.10.10
```

**Hinweis:** Ersetze `10.10.10.10` mit der tatsächlichen IP deines Roboters.

---

## 2. System vorbereiten

```bash
# System aktualisieren
sudo apt update
sudo apt upgrade -y

# Python und pip prüfen
python3 --version  # Sollte >= 3.8 sein
pip3 --version

# Git installieren (falls nicht vorhanden)
sudo apt install git -y
```

---

## 3. Projekt auf den Roboter kopieren

### Option A: Via Git (empfohlen)

```bash
cd ~
git clone <dein-repository-url> PAULQS
cd PAULQS/cube-inspection-system
```

### Option B: Via SCP (von deinem Computer aus)

```bash
# Auf deinem Computer ausführen:
cd /Users/timmehmeti/Documents/Abschlussprojekt
scp -r PAULQS niryo@10.10.10.10:~/
```

---

## 4. Dependencies installieren

```bash
cd ~/PAULQS/cube-inspection-system

# Virtual Environment erstellen (empfohlen)
python3 -m venv venv
source venv/bin/activate

# Dependencies installieren
pip install -r requirements.txt
```

**Wichtig:** Die Installation kann auf dem Roboter 10-15 Minuten dauern (OpenCV, NumPy sind groß).

---

## 5. Konfiguration anpassen

### `robot_config.json` – Roboter-IP auf localhost setzen

```bash
nano app/infrastructure/robot/robot_config.json
```

Ändere die IP auf `127.0.0.1` oder `localhost`:

```json
{
  "robot_ip": "127.0.0.1",
  ...
}
```

**Grund:** Der Code läuft jetzt direkt auf dem Roboter, daher ist die Verbindung lokal.

### `db_config.json` – Absoluten Pfad verwenden

```bash
nano app/infrastructure/database/db_config.json
```

Ändere auf absoluten Pfad:

```json
{
  "database_url": "sqlite:////home/niryo/PAULQS/cube-inspection-system/test.db",
  "check_same_thread": false
}
```

---

## 6. Server starten

### Manueller Start (zum Testen)

```bash
cd ~/PAULQS/cube-inspection-system
source venv/bin/activate
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Wichtig:** `--host 0.0.0.0` ermöglicht Zugriff von anderen Geräten im Netzwerk.

Jetzt kannst du von deinem Computer aus zugreifen:
- Dashboard: `http://10.10.10.10:8000/dashboard/`
- API Docs: `http://10.10.10.10:8000/docs`

### Automatischer Start beim Booten (systemd Service)

Erstelle einen systemd Service, damit der Server automatisch startet:

```bash
sudo nano /etc/systemd/system/paulqs.service
```

Inhalt:

```ini
[Unit]
Description=PAULQS Cube Inspection System
After=network.target

[Service]
Type=simple
User=niryo
WorkingDirectory=/home/niryo/PAULQS/cube-inspection-system
Environment="PATH=/home/niryo/PAULQS/cube-inspection-system/venv/bin"
ExecStart=/home/niryo/PAULQS/cube-inspection-system/venv/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Service aktivieren und starten:

```bash
sudo systemctl daemon-reload
sudo systemctl enable paulqs.service
sudo systemctl start paulqs.service

# Status prüfen
sudo systemctl status paulqs.service

# Logs anschauen
sudo journalctl -u paulqs.service -f
```

---

## 7. Firewall-Regeln (falls nötig)

```bash
# Port 8000 öffnen
sudo ufw allow 8000/tcp
sudo ufw reload
```

---

## 8. Zugriff von deinem Computer

Nach dem Deployment kannst du von jedem Gerät im gleichen Netzwerk zugreifen:

- **Dashboard:** `http://10.10.10.10:8000/dashboard/`
- **API:** `http://10.10.10.10:8000/api/config`
- **API Docs:** `http://10.10.10.10:8000/docs`

---

## Troubleshooting

### Problem: "ModuleNotFoundError: No module named 'pyniryo'"

**Lösung:**
```bash
source venv/bin/activate
pip install pyniryo
```

### Problem: "Permission denied" beim Kamera-Zugriff

**Lösung:**
```bash
# Benutzer zur video-Gruppe hinzufügen
sudo usermod -a -G video niryo
# Neu einloggen oder Roboter neu starten
```

### Problem: Server startet nicht automatisch

**Lösung:**
```bash
# Service-Logs prüfen
sudo journalctl -u paulqs.service -n 50

# Service neu starten
sudo systemctl restart paulqs.service
```

### Problem: Datenbank-Fehler "unable to open database file"

**Lösung:**
```bash
# Verzeichnis-Rechte prüfen
ls -la ~/PAULQS/cube-inspection-system/
chmod 755 ~/PAULQS/cube-inspection-system/

# DB-Datei manuell erstellen
cd ~/PAULQS/cube-inspection-system
python3 -c "from app.infrastructure.database.db import engine, Base; Base.metadata.create_all(bind=engine)"
```

---

## Updates deployen

Wenn du Code-Änderungen machst:

```bash
# Auf dem Roboter:
cd ~/PAULQS/cube-inspection-system
git pull  # Falls via Git

# Service neu starten
sudo systemctl restart paulqs.service
```

---

## Performance-Tipps

1. **Swap-Space erhöhen** (falls wenig RAM):
   ```bash
   sudo fallocate -l 2G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

2. **Unnötige Services deaktivieren** um Ressourcen zu sparen

3. **Bilder komprimieren** in `camera.py` (JPEG-Qualität reduzieren)

---

## Sicherheit

- **Passwort ändern:**
  ```bash
  passwd
  ```

- **SSH-Key statt Passwort verwenden**

- **Firewall aktivieren:**
  ```bash
  sudo ufw enable
  sudo ufw allow ssh
  sudo ufw allow 8000/tcp
  ```

---

## Vorteile dieser Lösung

✅ **Standalone-System** – Roboter braucht keinen externen Computer  
✅ **Immer erreichbar** – Solange Roboter an ist, läuft das Dashboard  
✅ **Keine Netzwerk-Latenz** – Roboter-Steuerung ist lokal (127.0.0.1)  
✅ **Einfache Wartung** – Updates via SSH oder Git  
✅ **Automatischer Start** – System startet nach Stromausfall automatisch  

---

## Alternative: Docker (fortgeschritten)

Falls der Roboter Docker unterstützt, kannst du auch ein Docker-Image erstellen:

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Dann:
```bash
docker build -t paulqs .
docker run -d -p 8000:8000 --restart always paulqs
```
