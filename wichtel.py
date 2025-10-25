import os
import streamlit as st
import random
import json
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

st.set_page_config(page_title="Wichtel-Zuteiler", page_icon="🎁", layout="wide")

# Datenbank-Konfiguration
DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "wichteln.db"
DB_PATH = None


def get_db_path() -> Path:
    global DB_PATH
    if DB_PATH is None:
        custom = os.getenv("WICHTEL_DB_PATH")
        DB_PATH = Path(custom).expanduser().resolve() if custom else DEFAULT_DB_PATH
    return DB_PATH


def set_db_path(path: Path):
    global DB_PATH
    DB_PATH = Path(path).expanduser().resolve()


def init_database(db_path: Path | None = None):
    """Initialisiert die SQLite-Datenbank und legt Tabellen an."""
    target_path = Path(db_path).expanduser().resolve() if db_path else get_db_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(target_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_password TEXT NOT NULL,
                user_password_hash TEXT NOT NULL UNIQUE,
                admin_code_hash TEXT,
                assignments_json TEXT NOT NULL,
                pairs_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        # Spalte für Admin-Code nachrüsten, falls sie fehlt
        columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
        if "admin_code_hash" not in columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN admin_code_hash TEXT")
        # Sicherstellen, dass ein passender Index existiert
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_admin_code_hash ON sessions(admin_code_hash)"
        )


@contextmanager
def get_db_connection():
    path = get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def hash_user_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def hash_admin_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def save_session_to_db(user_password: str, admin_code: str, assignments: list, pairs: list) -> None:
    assignments_json = json.dumps(assignments, ensure_ascii=False)
    pairs_json = json.dumps(pairs, ensure_ascii=False)
    user_hash = hash_user_password(user_password)
    admin_hash = hash_admin_code(admin_code)
    timestamp = datetime.utcnow().isoformat()

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO sessions (user_password, user_password_hash, admin_code_hash, assignments_json, pairs_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_password_hash) DO UPDATE SET
                user_password = excluded.user_password,
                admin_code_hash = excluded.admin_code_hash,
                assignments_json = excluded.assignments_json,
                pairs_json = excluded.pairs_json,
                created_at = excluded.created_at
            """,
            (user_password, user_hash, admin_hash, assignments_json, pairs_json, timestamp),
        )


def load_session_from_db(user_password: str):
    hashed = hash_user_password(user_password)
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id, user_password, assignments_json, pairs_json FROM sessions WHERE user_password_hash = ?",
            (hashed,),
        ).fetchone()

    if not row:
        return None

    assignments = json.loads(row["assignments_json"])
    pairs = json.loads(row["pairs_json"]) if row["pairs_json"] else []

    return {
        "id": row["id"],
        "user_password": row["user_password"],
        "assignments": assignments,
        "pairs": pairs,
    }


def load_session_from_admin_code(admin_code: str):
    hashed = hash_admin_code(admin_code)
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id, user_password, assignments_json, pairs_json, created_at FROM sessions WHERE admin_code_hash = ?",
            (hashed,),
        ).fetchone()

    if not row:
        return None

    assignments = json.loads(row["assignments_json"])
    pairs = json.loads(row["pairs_json"]) if row["pairs_json"] else []

    return {
        "id": row["id"],
        "user_password": row["user_password"],
        "assignments": assignments,
        "pairs": pairs,
        "created_at": row["created_at"],
    }


init_database()

# Hilfsfunktionen
def generate_code(length=6):
    """Generiert einen zufälligen Code"""
    chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    return ''.join(random.choice(chars) for _ in range(length))

def generate_user_password(length=8):
    """Generiert ein lesbares Passwort für User"""
    words = ['Stern', 'Baum', 'Schnee', 'Mond', 'Licht', 'Engel', 'Kerze', 'Glocke', 
             'Frost', 'Wind', 'Nebel', 'Sonne', 'Regen', 'Wolke', 'Blitz', 'Feuer']
    nums = ''.join([str(random.randint(0, 9)) for _ in range(3)])
    return f"{random.choice(words)}{nums}"

def generate_session_code(length=12):
    """Generiert einen einmaligen Session-Admin-Code."""
    chars = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    return ''.join(random.choice(chars) for _ in range(length))

def parse_pairs(pairs_text, names):
    """Parst Paare aus dem Textfeld"""
    pairs = []
    if not pairs_text:
        return pairs
    
    lines = [l.strip() for l in pairs_text.split('\n') if l.strip()]
    name_lower = {n.lower(): n for n in names}
    
    for line in lines:
        parts = [p.strip() for p in line.split(',') if p.strip()]
        if len(parts) >= 2:
            a_lower = parts[0].lower()
            b_lower = parts[1].lower()
            if a_lower in name_lower and b_lower in name_lower:
                pairs.append((name_lower[a_lower], name_lower[b_lower]))
    
    return pairs

def generate_assignment(names, pairs, allow_self=False, max_attempts=5000):
    """Generiert eine Wichtel-Zuteilung mit Paare-Schutz (verhindert, dass jemand seinem Partner zugewiesen wird)."""
    if len(names) == 0:
        return None
    if len(names) == 1 and allow_self:
        return [(names[0], names[0])]
    if len(names) == 1:
        return None

    # Erstelle Paare-Map (lowercase für sichere Vergleiche)
    pair_map = {}
    for a, b in pairs:
        pair_map[a.lower()] = b.lower()
        pair_map[b.lower()] = a.lower()

    n = len(names)
    indices = list(range(n))

    # Lowercase-Namen für Vergleiche
    names_lower = [n_.lower() for n_ in names]

    for attempt in range(max_attempts):
        perm = indices.copy()
        random.shuffle(perm)

        valid = True
        for i in range(n):
            giver_idx = i
            receiver_idx = perm[i]

            # Regel 1: Keine Selbstzuweisung (außer erlaubt)
            if not allow_self and giver_idx == receiver_idx:
                valid = False
                break

            giver = names_lower[giver_idx]
            receiver = names_lower[receiver_idx]

            # Regel 2: Verhindere, dass jemand seinem definierten Partner zugewiesen wird
            partner = pair_map.get(giver)
            if partner and partner == receiver:
                valid = False
                break

        if valid:
            return [(names[i], names[perm[i]]) for i in range(n)]

    # Fallback: Rotation — aber nur wenn sie nicht gegen Paare verstößt
    if not allow_self and n > 1:
        rotation = [(names[i], names[(i + 1) % n]) for i in range(n)]
        # Prüfe Rotation auf Paar-Konflikte
        conflict = False
        for giver, receiver in rotation:
            if pair_map.get(giver.lower()) == receiver.lower():
                conflict = True
                break
        if not conflict:
            return rotation

    return None


# Initialisiere Session State
if 'temp_assignments' not in st.session_state:
    st.session_state.temp_assignments = None
if 'temp_codes' not in st.session_state:
    st.session_state.temp_codes = {}
if 'temp_pairs' not in st.session_state:
    st.session_state.temp_pairs = []
if 'current_user_password' not in st.session_state:
    st.session_state.current_user_password = None
if 'loaded_data' not in st.session_state:
    st.session_state.loaded_data = None
if 'temp_session_admin_code' not in st.session_state:
    st.session_state.temp_session_admin_code = None
if 'admin_session_data' not in st.session_state:
    st.session_state.admin_session_data = None
if 'admin_session_code' not in st.session_state:
    st.session_state.admin_session_code = None
if 'revealed_assignments' not in st.session_state:
    st.session_state.revealed_assignments = set()

# Header
st.title("🎁 Wichtel-Zuteiler")

# Sidebar für Modus-Auswahl
with st.sidebar:
    st.header("Modus")
    mode = st.radio("Wähle Modus:", ["👤 Teilnehmer", "�️ Session-Admin"], key="mode_select")
    
    st.divider()
    
    st.success("✅ Datenbank verbunden")
    st.caption("💾 Sessions bleiben auch nach Neustart bestehen")

# TEILNEHMER-MODUS
if mode == "👤 Teilnehmer":
    st.header("👤 Teilnehmer-Bereich")
    
    # User-Passwort Eingabe
    if st.session_state.current_user_password is None or st.session_state.loaded_data is None:
        st.info("🔐 Gib das User-Passwort ein, das du vom Organisator erhalten hast.")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            user_pw = st.text_input("User-Passwort:", type="password", key="user_password_input", 
                                   placeholder="z.B. Stern472")
        with col2:
            unlock_btn = st.button("🔓 Laden", type="primary", use_container_width=True)
        
        if unlock_btn and user_pw:
            with st.spinner("Lade Daten..."):
                loaded_data = load_session_from_db(user_pw)

            if loaded_data:
                st.session_state.current_user_password = user_pw
                st.session_state.loaded_data = loaded_data
                st.success("✅ Wichtel-Runde geladen!")
                st.rerun()
            else:
                st.error("❌ Keine Wichtel-Runde mit diesem Passwort gefunden!")
                st.info("💡 Tipp: Der Admin muss die Runde erst erstellen und speichern.")
        
        st.divider()
        st.caption("💡 **Hinweis:** Das User-Passwort wurde vom Organisator beim Erstellen der Zuteilung generiert.")
    
    else:
        # Daten sind geladen
        st.success(f"✅ Wichtel-Runde geladen! (Passwort: `{st.session_state.current_user_password}`)")
        
        if st.button("🔒 Andere Runde laden", key="change_session"):
            st.session_state.current_user_password = None
            st.session_state.loaded_data = None
            st.rerun()
        
        st.divider()
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("🎁 Finde heraus, wen du beschenkst!")
            
            name = st.text_input("Dein Name:", placeholder="z.B. Anna", key="user_name")
            code = st.text_input("Dein persönlicher Code:", placeholder="z.B. A1B2C3", key="user_code").upper()
            
            if st.button("🎅 Empfänger anzeigen", type="primary", use_container_width=True):
                if not name or not code:
                    st.error("❌ Bitte fülle beide Felder aus!")
                else:
                    # Suche nach Übereinstimmung
                    found = False
                    receiver_name = None
                    
                    for item in st.session_state.loaded_data['assignments']:
                        if item['name'].upper() == name.upper() and item['code'] == code:
                            found = True
                            receiver_name = item['receiver']
                            break
                    
                    if found and receiver_name:
                        st.balloons()
                        st.success("🎄 **Du beschenkst:**")
                        st.markdown(f"# 🎁 **{receiver_name}**")
                        st.info("🤫 Halte das geheim und viel Spaß beim Wichteln!")
                    else:
                        st.error("❌ Name oder Code nicht gefunden. Bitte überprüfe deine Eingaben!")
                        st.caption("💡 Tipp: Achte auf Groß-/Kleinschreibung beim Code!")
        
        with col2:
            st.subheader("ℹ️ Anleitung")
            st.markdown("""
            1. **User-Passwort** eingeben
            2. **Dein Name** eingeben
            3. **Dein Code** eingeben
            4. Empfänger anzeigen
            5. **Geheim halten!** 🤫
            """)
            
            st.divider()
            
            # Info über geladene Runde
            if st.session_state.loaded_data:
                participant_count = len(st.session_state.loaded_data['assignments'])
                st.info(f"👥 {participant_count} Teilnehmer in dieser Runde")

# SESSION-ADMIN-MODUS
else:
    st.header("�️ Session-Admin")
    st.caption("Erstelle neue Runden oder verwalte bestehende Sessions mit deinem individuellen Session-Code.")

    st.divider()
    st.header("🆕 Neue Session erstellen")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("1. Namen eingeben")
        names_input = st.text_area(
            "Namen (ein Name pro Zeile):",
            height=200,
            placeholder="Anna\nBen\nCarla\nDaniel\nEva\nFrank",
            help="Gib alle Teilnehmer ein, einen Namen pro Zeile"
        )

        st.subheader("2. Paare definieren (optional)")
        pairs_input = st.text_area(
            "Paare, die sich NICHT gegenseitig beschenken dürfen:",
            height=100,
            placeholder="Anna,Ben\nCarla,Daniel",
            help="Trage hier Paare ein (z.B. Ehepaar, Geschwister). Format: Name1,Name2"
        )

        st.info("ℹ️ **Wichtig:** Paare werden niemals gegenseitig zugeordnet (A ↔ B wird verhindert).")

    with col2:
        st.subheader("Optionen")
        allow_self = st.checkbox("Selbstzuweisung erlauben", value=False)

        if st.button("🎲 Zuteilung generieren", type="primary", use_container_width=True):
            names = [n.strip() for n in names_input.split('\n') if n.strip()]
            names = list(dict.fromkeys(names))

            if len(names) < 2 and not allow_self:
                st.error("❌ Mindestens 2 Namen erforderlich!")
            else:
                pairs = parse_pairs(pairs_input, names)

                with st.spinner("Generiere Zuteilung..."):
                    result = generate_assignment(names, pairs, allow_self)

                if result is None:
                    st.error("❌ Konnte keine gültige Zuteilung finden. Versuche es erneut!")
                else:
                    codes = {giver: generate_code() for giver, _ in result}

                    st.session_state.temp_assignments = result
                    st.session_state.temp_codes = codes
                    st.session_state.temp_pairs = pairs
                    if st.session_state.temp_session_admin_code is None:
                        st.session_state.temp_session_admin_code = generate_session_code()
                    st.session_state.revealed_assignments = set()
                    st.success("✅ Zuteilung erfolgreich generiert!")

        if st.session_state.temp_assignments:
            if st.button("🔄 Neu würfeln", use_container_width=True):
                names = [giver for giver, _ in st.session_state.temp_assignments]
                result = generate_assignment(names, st.session_state.temp_pairs, allow_self)
                if result:
                    codes = {giver: generate_code() for giver, _ in result}
                    st.session_state.temp_assignments = result
                    st.session_state.temp_codes = codes
                    st.success("✅ Neue Zuteilung erstellt!")
                else:
                    st.error("❌ Konnte keine neue Zuteilung finden!")

    # Vorschau anzeigen
    if st.session_state.temp_assignments:
        st.divider()
        st.header("📋 Vorschau der Zuteilung")

        if st.session_state.temp_pairs:
            pair_names = [f"{a} & {b}" for a, b in st.session_state.temp_pairs]
            st.info(f"👫 **Definierte Paare:** {', '.join(pair_names)}")

        pair_map = {}
        for a, b in st.session_state.temp_pairs:
            pair_map[a] = b
            pair_map[b] = a

        st.subheader("Generierte Codes:")
        for giver, receiver in st.session_state.temp_assignments:
            code = st.session_state.temp_codes[giver]
            partner = pair_map.get(giver)

            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                if partner:
                    st.markdown(f"**{giver}** 👫 _(mit {partner})_")
                else:
                    st.markdown(f"**{giver}**")
            with col2:
                st.code(code, language=None)
            with col3:
                st.caption(f"→ {receiver}")

        st.divider()

        if 'temp_user_password' not in st.session_state:
            st.session_state.temp_user_password = generate_user_password()

        st.subheader("🔑 Zugangsdaten für diese Session")
        st.success(f"**User-Passwort:** `{st.session_state.temp_user_password}`")
        st.success(f"**Session-Admin-Code:** `{st.session_state.temp_session_admin_code}`")
        st.warning("⚠️ Bewahre beide Codes sicher auf. Der Session-Code öffnet die Admin-Ansicht nur für diese Runde.")

        st.divider()
        st.info("💾 Nach dem Speichern können Teilnehmer mit dem User-Passwort auf die Session zugreifen.")

        col1, col2 = st.columns([1, 1])

        with col1:
            txt_content = "WICHTEL-CODES - SESSION-ADMIN\n" + "="*50 + "\n\n"
            txt_content += f"USER-PASSWORT: {st.session_state.temp_user_password}\n"
            txt_content += f"SESSION-ADMIN-CODE: {st.session_state.temp_session_admin_code}\n"
            txt_content += "⚠️ Teile den Session-Code nur mit der verantwortlichen Person!\n\n"
            txt_content += "="*50 + "\n\n"

            if st.session_state.temp_pairs:
                txt_content += "Definierte Paare:\n"
                for a, b in st.session_state.temp_pairs:
                    txt_content += f"  {a} & {b}\n"
                txt_content += "\n"

            txt_content += "CODES FÜR TEILNEHMER:\n"
            txt_content += "-" * 30 + "\n"
            for giver, _ in st.session_state.temp_assignments:
                txt_content += f"{giver}: {st.session_state.temp_codes[giver]}\n"

            txt_content += "\n" + "="*50 + "\n"
            txt_content += "KOMPLETTE ZUTEILUNG (nur für Session-Admin):\n"
            txt_content += "-" * 30 + "\n"
            for giver, receiver in st.session_state.temp_assignments:
                txt_content += f"{giver} ({st.session_state.temp_codes[giver]}) → {receiver}\n"

            st.download_button(
                "📄 Session-Admin-Kopie herunterladen",
                txt_content,
                f"wichtel-session-{st.session_state.temp_user_password}.txt",
                "text/plain",
                use_container_width=True,
                help="Sichere diese Datei als Backup!"
            )

        with col2:
            if st.button("💾 PERMANENT SPEICHERN", type="primary", use_container_width=True):
                data_to_save = {
                    "user_password": st.session_state.temp_user_password,
                    "admin_code": st.session_state.temp_session_admin_code,
                    "assignments": [
                        {
                            "name": giver,
                            "code": st.session_state.temp_codes[giver],
                            "receiver": receiver
                        }
                        for giver, receiver in st.session_state.temp_assignments
                    ],
                    "pairs": [[a, b] for a, b in st.session_state.temp_pairs]
                }

                try:
                    save_session_to_db(
                        data_to_save["user_password"],
                        data_to_save["admin_code"],
                        data_to_save["assignments"],
                        data_to_save["pairs"],
                    )
                except Exception as e:
                    st.error(f"❌ Speichern fehlgeschlagen: {e}")
                else:
                    st.success("✅ Session permanent gespeichert!")
                    st.balloons()
                    st.info(
                        "🔑 Teile jetzt das User-Passwort mit den Teilnehmern und behalte den Session-Admin-Code für dich."
                    )
                    st.session_state.admin_session_code = data_to_save["admin_code"]
                    st.session_state.admin_session_data = load_session_from_admin_code(data_to_save["admin_code"])
                    st.session_state.revealed_assignments = set()

                    st.session_state.temp_assignments = None
                    st.session_state.temp_codes = {}
                    st.session_state.temp_pairs = []
                    if 'temp_user_password' in st.session_state:
                        del st.session_state.temp_user_password
                    if 'temp_session_admin_code' in st.session_state:
                        del st.session_state.temp_session_admin_code

    st.divider()
    st.header("🔑 Bestehende Session verwalten")

    admin_code_input = st.text_input(
        "Session-Admin-Code eingeben:",
        value=st.session_state.admin_session_code or "",
        max_chars=20,
        type="password",
        help="Nur wer den Session-Code kennt, sieht die Zuteilung."
    )
    col_open, col_reset = st.columns([1, 1])
    with col_open:
        if st.button("📂 Session öffnen", type="primary", use_container_width=True):
            if not admin_code_input:
                st.error("Bitte gib einen Session-Admin-Code ein.")
            else:
                with st.spinner("Lade Session..."):
                    admin_data = load_session_from_admin_code(admin_code_input)
                if admin_data:
                    st.session_state.admin_session_code = admin_code_input
                    st.session_state.admin_session_data = admin_data
                    st.session_state.revealed_assignments = set()
                    st.success("Session geladen!")
                    st.rerun()
                else:
                    st.error("Session-Code nicht gefunden. Bitte prüfe deine Eingabe.")
    with col_reset:
        if st.button("❌ Session schließen", use_container_width=True):
            st.session_state.admin_session_code = None
            st.session_state.admin_session_data = None
            st.session_state.revealed_assignments = set()
            st.rerun()

    if st.session_state.admin_session_data:
        data = st.session_state.admin_session_data
        participant_count = len(data["assignments"])

        st.success(
            f"Aktive Session geöffnet. User-Passwort: `{data['user_password']}`, Teilnehmer: {participant_count}"
        )
        st.caption(f"Erstellt am: {data['created_at'][:19]} UTC")

        if data["pairs"]:
            st.markdown("**Definierte Paare:** " + ", ".join(f"{a} & {b}" for a, b in data["pairs"]))

        st.subheader("🎁 Teilnehmerübersicht")
        session_id = data["id"]

        for item in data["assignments"]:
            giver = item["name"]
            code = item["code"]
            receiver = item["receiver"]
            reveal_key = f"{session_id}:{code}"
            revealed = reveal_key in st.session_state.revealed_assignments

            col1, col2, col3 = st.columns([2, 2, 2])
            with col1:
                st.markdown(f"**{giver}**")
            with col2:
                st.code(code, language=None)
            with col3:
                if revealed:
                    st.success(f"🎁 {receiver}")
                else:
                    if st.button("Empfänger anzeigen", key=f"reveal_{reveal_key}", use_container_width=True):
                        revealed_set = set(st.session_state.revealed_assignments)
                        revealed_set.add(reveal_key)
                        st.session_state.revealed_assignments = revealed_set
                        st.rerun()

        st.divider()
        if st.button("🔁 Session in Formular laden", key="load_session_into_form"):
            st.session_state.temp_assignments = [
                (item["name"], item["receiver"]) for item in data["assignments"]
            ]
            st.session_state.temp_codes = {
                item["name"]: item["code"] for item in data["assignments"]
            }
            st.session_state.temp_pairs = [tuple(pair) for pair in data.get("pairs", [])]
            st.session_state.temp_user_password = data["user_password"]
            st.session_state.temp_session_admin_code = st.session_state.admin_session_code
            st.success("Session ins Formular übernommen. Du kannst nun Änderungen vornehmen und neu speichern.")

# Footer
st.divider()
st.caption("🔒 **Sicherheit:** User-Passwörter werden gehasht geprüft und stehen dem Admin zur Verwaltung bereit.")
st.caption("🗄️ **Datenhaltung:** Sessions werden dauerhaft in einer lokalen SQLite-Datenbank gespeichert.")