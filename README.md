# 🎁 Wichtel-Zuteiler
Eine Streamlit-App zum Auslosen von Wichtelpartnern mit persistenter Speicherung von Sessions in Supabase (Postgres). 
Die App bietet zwei Modi: 
* Teilnehmende (finden ihren Empfänger anhand eines persönlichen Codes) und
* * Session-Admin (Erstellen/Verwalten von Runden).

App: https://wichteln.streamlit.app/

## Kurzanleitung zur App

1. Session erstellen (Admin-Modus): Teilnehmende (ein Name pro Zeile) eingeben, optional Paare (die sich nicht gegenseitig beschenken sollen). Zuteilung generieren.
2. Codes: Die App erzeugt ein gemeinsames User-Passwort (für alle Teilnehmenden) und pro Person einen persönlichen Code. Notiere User-Passwort und Session-Admin-Code.
3. Session speichern: Nach dem Speichern werden die Daten in Supabase abgelegt. Teilnehmende können mit dem User-Passwort in den Teilnehmer-Modus und ihren Empfänger mit Namen + persönlichem Code anzeigen.
4. Session verwalten: Mit dem Session-Admin-Code kannst du die gesamte Zuteilung sehen und Empfänger einzeln freigeben.

Viel Spaß beim Wichteln! 🎄

## Highlights

- 🚀 Streamlit-Frontend für Teilnehmende und Admin
- ☁️ Persistente Sessions in Supabase
- 🔐 Pro-Session User-Passwort + Session-Admin-Code für sichere Verwaltung
- 🛡️ Admin-Code und Prüfungen via Hashing; Teilnehmer-Passwörter werden gehasht geprüft
- 🐳 Container-Setup über das mitgelieferte `Dockerfile`

## Voraussetzungen

- Python 3.11 (empfohlen)
- pip
- Ein Supabase-Projekt (oder PostgreSQL-kompatible REST-API), Zugangsdaten siehe unten

## Supabase / Secrets

Die App speichert Sessions in einer Supabase-Instanz. Es gibt zwei Möglichkeiten, die Verbindungsdaten bereitzustellen:

1. Umgebungvariablen

	- SUPABASE_URL (z. B. https://xyz.supabase.co)
	- SUPABASE_SERVICE_ROLE_KEY (oder SUPABASE_KEY)
	- optional: SUPABASE_SCHEMA (Default: public)

	Du kannst diese Variablen lokal z. B. in einer `.env`-Datei ablegen und mit `python-dotenv` oder deinem Shell-Setup laden.

2. `st.secrets` (Streamlit)

	Wenn du die App auf Streamlit Cloud/deployed betreibst, kannst du die Secrets unter `connections.supabase.url`, `connections.supabase.key` und `connections.supabase.schema` hinterlegen. Die App versucht zuerst `st.secrets` zu lesen und fällt dann auf die Umgebungsvariablen zurück.

Wichtig: Die App wirft einen Fehler, wenn weder `SUPABASE_URL` noch `SUPABASE_SERVICE_ROLE_KEY` (oder `st.secrets`) gesetzt sind.

### Datenbank-Schema anlegen

Da Supabase standardmäßig keinen `rpc/sql`-Endpunkt bereitstellt, kann die App das Tabellen-Schema nicht automatisch erzeugen. Lege die Tabelle daher einmalig manuell an:

1. Öffne im Supabase Dashboard den SQL Editor deines Projekts.
2. Kopiere den Inhalt aus `supabase/schema.sql` (in diesem Repository).
3. Führe das Skript mit einem Service-Role-Key aus.

Nach dem erfolgreichen Ausführen steht die Tabelle `public.sessions` bereit und die App kann Sessions speichern.

## Lokale Entwicklung

1. Virtuelle Umgebung anlegen und Abhängigkeiten installieren

```bash
python -m venv .venv
source .venv/bin/activate  # macOS / Linux
pip install -r requirements.txt
```

2. Supabase-Zugang lokal setzen (Beispiel `.env`)

```env
SUPABASE_URL=https://...
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

3. App starten

```bash
streamlit run wichtel.py
```

Öffne anschließend http://localhost:8501


## Docker

Das Projekt enthält ein einfaches `Dockerfile` (Base: python:3.11-slim) und startet die Streamlit-App.

Build & Run:

```bash
docker build -t wichteln:latest .
docker run -p 8501:8501 --env SUPABASE_URL="https://..." --env SUPABASE_SERVICE_ROLE_KEY="..." wichteln:latest
```

Die App ist dann unter `http://localhost:8501` erreichbar. Achte darauf, die Supabase-URL und den Key als Umgebungsvariablen an den Container zu übergeben.

## Tests

Unit-Tests existieren unter `tests/` und nutzen `pytest`. Die Tests mocken HTTP-Aufrufe zu Supabase, daher benötigst du keine echte Supabase-Instanz zum Ausführen der Tests.

```bash
pip install -r requirements.txt
pytest -q
```

## Sicherheitshinweise

- SUPABASE_SERVICE_ROLE_KEY (Service Role) sollte sicher verwahrt werden. In Produktionssetups empfehle ich, nur minimal nötige Keys zu verwenden und Zugriffsrechte richtig zu setzen.
- Teile den Session-Admin-Code nur mit Personen, die die komplette Zuteilung sehen dürfen.
- Die App hasht Passwörter (SHA-256) für Vergleiche; wenn du stärkere Sicherheitsanforderungen hast, erwäge salting oder ein bewährtes Auth-System.

## Entwicklung & Beiträge

- Code unter `wichtel.py` ist die Haupt-App (Streamlit).
- Tests unter `tests/`.

```
