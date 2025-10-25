# 🎁 Wichtel-Zuteiler

Eine Streamlit-App zum Auslosen von Wichtel-Partner:innen – inklusive persistenter Speicherung der Sessions in einer SQLite-Datenbank und Admin-Überblick über alle Runden.

## Highlights

- 🚀 **Streamlit-Frontend** für Teilnehmer:innen und Admin.
- 🗄️ **Persistente Sessions** dank SQLite (Datei: `data/wichteln.db`).
- 🔑 **Admin-Überblick** über sämtliche gespeicherten Runden direkt im UI.
- 🐳 **Container-Setup** via `Dockerfile`.
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

### Konfiguration

- Setze das Admin-Passwort über Environment-Variablen oder `streamlit secrets`:
  - Lokal: `export ADMIN_PASSWORD="deinPasswort"`
  - Streamlit Cloud: `secrets.toml` anlegen.

## Datenhaltung

- Die App speichert Sessions in `data/wichteln.db`.
- Im Repository ist `data/.gitignore` hinterlegt, damit die Datenbank nicht eingecheckt wird.
- Passwörter werden zur Authentifizierung gehasht, bleiben aber für den Admin sichtbar, um sie teilen zu können.

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

Die App ist anschließend unter `http://localhost:8501` erreichbar.

## Qualitätssicherung

- Syntax-Check: `python -m compileall .`
- Optional eigene Tests / Linting ergänzen.

Viel Spaß beim Wichteln! 🎄
