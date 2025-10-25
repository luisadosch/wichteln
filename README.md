# 🎁 Wichtel-Zuteiler

Eine Streamlit-App zum Auslosen von Wichtel-Partner:innen – inklusive persistenter Speicherung der Sessions in einer SQLite-Datenbank und Admin-Überblick über alle Runden.

## Highlights

- 🚀 **Streamlit-Frontend** für Teilnehmer:innen und Admin.
- 🗄️ **Persistente Sessions** dank SQLite (Datei: `data/wichteln.db`).
- 🔑 **Session-Admin-Ansicht** pro Runde mit kontrollierter Empfänger-Anzeige.
- � **Session-Codes statt globalem Admin** – jede Runde hat ihren eigenen Admin-Zugang.
- �🐳 **Container-Setup** via `Dockerfile`.
- 🤖 **CI/CD über GitHub Actions** mit automatischem Image-Build & Push nach GHCR.

## Voraussetzungen

- Python 3.11 (empfohlen)
- `pip`

## Lokale Entwicklung

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run wichtel.py
```

Beim ersten Start wird die SQLite-Datenbank automatisch angelegt (`data/wichteln.db`).

### App ausprobieren

1. **Session anlegen:** Öffne `http://localhost:8501`, wechsle auf den Tab **Session-Admin**, gib die Teilnehmer:innen (und optional Paare) ein und klicke auf „Zuteilung generieren“.
2. **Zugangsdaten sichern:** Nach dem Speichern erhältst du zwei Codes – das **User-Passwort** für alle Teilnehmer:innen und den **Session-Admin-Code** nur für dich.
3. **Teilnehmer-Flow testen:** Wechsle in den Teilnehmer-Modus, gib das User-Passwort sowie einen Namen & Code ein, um den Empfänger anzeigen zu lassen.
4. **Session verwalten:** Gib im Session-Admin-Tab den Session-Code ein, um die Runde erneut zu öffnen. Empfänger:innen werden erst nach Klick auf „Empfänger anzeigen“ sichtbar.

So stellst du sicher, dass sowohl Admin- als auch Teilnehmer-Ansicht korrekt funktionieren.

## Datenhaltung

- Die App speichert Sessions in `data/wichteln.db`.
- Im Repository ist `data/.gitignore` hinterlegt, damit die Datenbank nicht eingecheckt wird.
- Passwörter werden zur Authentifizierung gehasht, bleiben aber für den Admin sichtbar, um sie teilen zu können.
- Der Session-Admin-Code wird gehasht gespeichert – nur wer den Code kennt, kann die Runde verwalten.

## Deployment über GitHub Actions

Workflow-Datei: `.github/workflows/deploy.yml`

Was passiert?
1. Installiert Dependencies und führt `python -m compileall .` aus.
2. Baut das Docker-Image auf Basis des `Dockerfile`.
3. Push nach GitHub Container Registry (`ghcr.io/<owner>/wichteln`) bei Push auf `main`.

> **Hinweis:** Für externe Registries müssen ggf. weitere Secrets hinterlegt werden. Der mitgelieferte Workflow nutzt lediglich das automatische `GITHUB_TOKEN`.

## Container starten

```bash
docker build -t wichteln:latest .
docker run -p 8501:8501 wichteln:latest
```

Die App ist anschließend unter `https://wichteln.streamlit.app/` erreichbar.

## Qualitätssicherung

- Tests: `pytest`
- Syntax-Check: `python -m compileall .`
- Optional eigene Tests / Linting ergänzen.

Viel Spaß beim Wichteln! 🎄
