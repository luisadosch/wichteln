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
                assignments_json TEXT NOT NULL,
                pairs_json TEXT,
                created_at TEXT NOT NULL
            )
            """
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


def save_session_to_db(user_password: str, assignments: list, pairs: list) -> None:
    payload = {
        "assignments": assignments,
        "pairs": pairs,
    }
    assignments_json = json.dumps(payload["assignments"], ensure_ascii=False)
    pairs_json = json.dumps(payload["pairs"], ensure_ascii=False)
    hashed = hash_user_password(user_password)
    timestamp = datetime.utcnow().isoformat()

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO sessions (user_password, user_password_hash, assignments_json, pairs_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_password_hash) DO UPDATE SET
                user_password = excluded.user_password,
                assignments_json = excluded.assignments_json,
                pairs_json = excluded.pairs_json,
                created_at = excluded.created_at
            """,
            (user_password, hashed, assignments_json, pairs_json, timestamp),
        )


def load_session_from_db(user_password: str):
    hashed = hash_user_password(user_password)
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT user_password, assignments_json, pairs_json FROM sessions WHERE user_password_hash = ?",
            (hashed,),
        ).fetchone()

    if not row:
        return None

    assignments = json.loads(row["assignments_json"])
    pairs = json.loads(row["pairs_json"]) if row["pairs_json"] else []

    return {
        "user_password": row["user_password"],
        "assignments": assignments,
        "pairs": pairs,
    }


def list_sessions_for_admin():
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT id, user_password, assignments_json, pairs_json, created_at FROM sessions ORDER BY datetime(created_at) DESC"
        ).fetchall()

    sessions = []
    for row in rows:
        assignments = json.loads(row["assignments_json"])
        pairs = json.loads(row["pairs_json"]) if row["pairs_json"] else []
        sessions.append(
            {
                "id": row["id"],
                "user_password": row["user_password"],
                "assignments": assignments,
                "pairs": pairs,
                "created_at": row["created_at"],
                "participant_count": len(assignments),
            }
        )
    return sessions


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
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
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
if 'selected_admin_session_id' not in st.session_state:
    st.session_state.selected_admin_session_id = None
if 'admin_sessions_cache' not in st.session_state:
    st.session_state.admin_sessions_cache = []

# Admin Passwort - aus Environment Variable oder Default
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "wichtel2024")  # ⚠️ Setze in Streamlit Secrets!

# Header
st.title("🎁 Wichtel-Zuteiler")

# Sidebar für Modus-Auswahl
with st.sidebar:
    st.header("Modus")
    mode = st.radio("Wähle Modus:", ["👤 Teilnehmer", "🔧 Admin"], key="mode_select")
    
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

# ADMIN-MODUS
else:
    if not st.session_state.authenticated:
        # Login-Formular
        st.subheader("🔐 Admin-Login")
        st.info("Nur der Organisator kann neue Zuteilungen erstellen.")
        
        password = st.text_input("Admin-Passwort:", type="password", key="admin_pw")
        
        if st.button("🔓 Einloggen", type="primary"):
            if password == ADMIN_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Falsches Passwort!")
        
        st.divider()
        st.caption("🔧 **Admin-Setup:** Setze `ADMIN_PASSWORD` in Streamlit Secrets für mehr Sicherheit!")
    
    else:
        # ADMIN IST EINGELOGGT
        st.success("✅ Als Admin eingeloggt")

        # Sessions aus Datenbank laden
        st.session_state.admin_sessions_cache = list_sessions_for_admin()
        
        if st.button("🚪 Logout", key="logout"):
            st.session_state.authenticated = False
            st.session_state.temp_assignments = None
            st.session_state.temp_codes = {}
            st.session_state.temp_pairs = []
            st.rerun()
        
        st.divider()
        st.header("📝 Neue Zuteilung erstellen")
        
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
            
            # Erstelle Paare-Map
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
            
            # User-Passwort generieren
            if 'temp_user_password' not in st.session_state:
                st.session_state.temp_user_password = generate_user_password()
            
            st.subheader("🔑 User-Passwort für diese Wichtel-Runde")
            st.success(f"**User-Passwort:** `{st.session_state.temp_user_password}`")
            st.warning("⚠️ **WICHTIG:** Teile dieses Passwort zusammen mit den Codes an alle Teilnehmer!")
            
            # SPEICHERN Button
            st.divider()
            st.info("💾 Nach dem Speichern können Teilnehmer mit dem User-Passwort auf die Zuteilung zugreifen.")
            
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # TXT Export
                txt_content = "WICHTEL-CODES - ADMIN KOPIE\n" + "="*50 + "\n\n"
                txt_content += f"USER-PASSWORT FÜR DIESE RUNDE: {st.session_state.temp_user_password}\n"
                txt_content += "⚠️ Teile dieses Passwort an alle Teilnehmer!\n\n"
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
                txt_content += "KOMPLETTE ZUTEILUNG (nur für Admin):\n"
                txt_content += "-" * 30 + "\n"
                for giver, receiver in st.session_state.temp_assignments:
                    txt_content += f"{giver} ({st.session_state.temp_codes[giver]}) → {receiver}\n"
                
                st.download_button(
                    "📄 Admin-Kopie herunterladen",
                    txt_content,
                    f"wichtel-admin-{st.session_state.temp_user_password}.txt",
                    "text/plain",
                    use_container_width=True,
                    help="Sichere diese Datei als Backup!"
                )
            
            with col2:
                if st.button("💾 PERMANENT SPEICHERN", type="primary", use_container_width=True):
                    # Daten vorbereiten
                    data_to_save = {
                        "user_password": st.session_state.temp_user_password,
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
                            data_to_save["assignments"],
                            data_to_save["pairs"],
                        )
                    except Exception as e:
                        st.error(f"❌ Speichern fehlgeschlagen: {e}")
                    else:
                        # Admin-Cache aktualisieren
                        st.session_state.admin_sessions_cache = list_sessions_for_admin()
                        
                        st.success("✅ Zuteilung permanent gespeichert!")
                        st.balloons()

                        st.info(f"🔑 Teilnehmer können jetzt mit dem Passwort `{st.session_state.temp_user_password}` zugreifen!")
                        
                        # Reset temp data
                        st.session_state.temp_assignments = None
                        st.session_state.temp_codes = {}
                        st.session_state.temp_pairs = []
                        if 'temp_user_password' in st.session_state:
                            del st.session_state.temp_user_password

        st.divider()
        st.header("📚 Gespeicherte Sessions")

        if st.button("🔄 Liste aktualisieren", key="refresh_sessions"):
            st.session_state.admin_sessions_cache = list_sessions_for_admin()

        sessions = st.session_state.admin_sessions_cache

        if not sessions:
            st.session_state.selected_admin_session_id = None
            st.info("Noch keine Sessions gespeichert. Erstelle eine neue Runde und speichere sie permanent.")
        else:
            option_entries = []
            for idx, session in enumerate(sessions):
                label = f"{idx+1}. {session['created_at'][:19]} UTC – {session['user_password']} ({session['participant_count']} TN)"
                option_entries.append((label, session["id"], session))

            available_labels = [entry[0] for entry in option_entries]

            default_index = 0
            if st.session_state.selected_admin_session_id is not None:
                for idx, (_, session_id, _) in enumerate(option_entries):
                    if session_id == st.session_state.selected_admin_session_id:
                        default_index = idx
                        break

            selected_label = st.selectbox(
                "Wähle eine Session zur Ansicht:",
                available_labels,
                index=default_index,
                key="admin_session_select",
            )

            selected_session = None
            for label, session_id, payload in option_entries:
                if label == selected_label:
                    selected_session = payload
                    st.session_state.selected_admin_session_id = session_id
                    break

            if selected_session:
                st.subheader("🔎 Session-Details")
                left_col, right_col = st.columns(2)
                with left_col:
                    st.metric("Teilnehmer", selected_session["participant_count"])
                    st.metric("User-Passwort", selected_session["user_password"])
                with right_col:
                    st.metric("Erstellt am", selected_session["created_at"][:19] + " UTC")
                    st.metric("Paare", len(selected_session["pairs"]))

                st.markdown("### 🎁 Gesamte Zuteilung")
                for item in selected_session["assignments"]:
                    giver = item["name"]
                    code = item["code"]
                    receiver = item["receiver"]
                    st.markdown(f"- **{giver}** (`{code}`) → {receiver}")

                if selected_session["pairs"]:
                    st.markdown("### 👫 Paare")
                    st.write(", ".join(f"{a} & {b}" for a, b in selected_session["pairs"]))

                if st.button("🔁 Session in Formular laden", key="load_session_into_form"):
                    st.session_state.temp_assignments = [
                        (item["name"], item["receiver"]) for item in selected_session["assignments"]
                    ]
                    st.session_state.temp_codes = {
                        item["name"]: item["code"] for item in selected_session["assignments"]
                    }
                    st.session_state.temp_pairs = [tuple(pair) for pair in selected_session["pairs"]]
                    st.session_state.temp_user_password = selected_session["user_password"]
                    st.success("Session in Formular übernommen. Du kannst nun Änderungen vornehmen und neu speichern.")

# Footer
st.divider()
st.caption("🔒 **Sicherheit:** User-Passwörter werden gehasht geprüft und stehen dem Admin zur Verwaltung bereit.")
st.caption("🗄️ **Datenhaltung:** Sessions werden dauerhaft in einer lokalen SQLite-Datenbank gespeichert.")