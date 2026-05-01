# Roomtis Online Deployment

## Option 1: Render.com (empfohlen, kostenlos)

### Schritt 1: GitHub Repository erstellen
1. Gehe zu github.com und erstelle ein neues Repository (z.B. "roomtis")
2. Lade diese Dateien hoch:
   - `main.py`
   - `Roomtis.html`
   - `requirements.txt`
   - `Procfile`
   - `render.yaml`
   - `.gitignore`
   - `teacher_map.json` (falls vorhanden)

### Schritt 2: Bei Render.com anmelden
1. Gehe zu https://render.com
2. Registriere dich mit deinem GitHub-Account
3. Klicke auf "New" → "Web Service"
4. Verbinde dein GitHub Repository
5. Render erkennt automatisch die `render.yaml` Konfiguration
6. Klicke auf "Create Web Service"

### Schritt 3: Fertig!
- Render gibt dir eine URL wie: `https://roomtis.onrender.com`
- Diese URL kannst du auf jedem Handy im Browser öffnen
- Die App startet automatisch neu bei Änderungen im GitHub Repo

### Hinweis zum Free Tier:
- Der Server schläft nach 15 Min. Inaktivität ein
- Erster Aufruf danach dauert ~30 Sekunden
- Für immer-an: Render "Starter" Plan ($7/Monat)


## Option 2: Railway.app (Alternative)

1. Gehe zu https://railway.app
2. "New Project" → "Deploy from GitHub"
3. Repository auswählen
4. Railway erkennt Python automatisch
5. Fertig – du bekommst eine URL


## Option 3: Eigener Server (z.B. Schulserver)

Falls die Schule einen Linux-Server hat:

```bash
# Repository klonen
git clone https://github.com/DEIN-USER/roomtis.git
cd roomtis

# Python-Umgebung einrichten
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Server starten (im Hintergrund)
gunicorn main:app --bind 0.0.0.0:5000 --daemon

# Oder mit systemd (dauerhaft):
# sudo nano /etc/systemd/system/roomtis.service
```

systemd Service-Datei (`/etc/systemd/system/roomtis.service`):
```ini
[Unit]
Description=Roomtis
After=network.target

[Service]
User=www-data
WorkingDirectory=/pfad/zu/roomtis
ExecStart=/pfad/zu/roomtis/venv/bin/gunicorn main:app --bind 0.0.0.0:5000
Restart=always

[Install]
WantedBy=multi-user.target
```

Dann:
```bash
sudo systemctl enable roomtis
sudo systemctl start roomtis
```


## Wichtig: Daten-Persistenz

Auf Render (Free Tier) werden Dateien bei jedem Neustart gelöscht.
Das betrifft:
- `teacher_map.json` (Lehrer-Kürzel)
- Kalender-Dateien (`kalender_global.json`, `user_*.json`)
- L-Nummern (`l_nummern.json`)
- Fächer-Auswahl (`faecher_*.json`)

Für dauerhaften Betrieb gibt es zwei Optionen:
1. **Render Persistent Disk** (kostenpflichtig) – Dateien bleiben erhalten
2. **Datenbank nutzen** – z.B. Render PostgreSQL (kostenlos) oder SQLite auf Persistent Disk
