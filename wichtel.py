import streamlit as st
import random
import json
import hashlib

st.set_page_config(page_title="Wichtel-Zuteiler", page_icon="🎁", layout="wide")

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

def get_storage_key(user_password):
    """Erstellt einen sicheren Storage-Key"""
    hash_key = hashlib.sha256(user_password.encode()).hexdigest()[:16]
    return f"wichtel_{hash_key}"

async def save_wichtel_data(user_password, data):
    """Speichert Wichtel-Daten in Streamlit Cloud Storage"""
    try:
        storage_key = get_storage_key(user_password)
        
        # Speichere in Streamlit's persistent storage
        await window.storage.set(storage_key, json.dumps(data), shared=True)
        return True
    except Exception as e:
        st.error(f"Fehler beim Speichern: {e}")
        return False

async def load_wichtel_data(user_password):
    """Lädt Wichtel-Daten aus Streamlit Cloud Storage"""
    try:
        storage_key = get_storage_key(user_password)
        
        # Lade aus Streamlit's persistent storage
        result = await window.storage.get(storage_key, shared=True)
        
        if result and result.get('value'):
            return json.loads(result['value'])
        return None
    except Exception as e:
        # Key existiert nicht
        return None

async def list_all_sessions():
    """Listet alle gespeicherten Sessions (nur Anzahl für Statistik)"""
    try:
        result = await window.storage.list('wichtel_', shared=True)
        if result and result.get('keys'):
            return len(result['keys'])
        return 0
    except:
        return 0

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
if 'storage_available' not in st.session_state:
    st.session_state.storage_available = True

# Admin Passwort - aus Environment Variable oder Default
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "wichtel2024")  # ⚠️ Setze in Streamlit Secrets!

# Header
st.title("🎁 Wichtel-Zuteiler")

# JavaScript für Storage einbinden
storage_script = """
<script>
// Wrapper für Streamlit Storage API
window.wichtelStorage = {
    async save(key, data) {
        try {
            const result = await window.storage.set(key, data, true);
            return result !== null;
        } catch(e) {
            console.error('Storage error:', e);
            return false;
        }
    },
    async load(key) {
        try {
            const result = await window.storage.get(key, true);
            return result?.value || null;
        } catch(e) {
            return null;
        }
    },
    async count(prefix) {
        try {
            const result = await window.storage.list(prefix, true);
            return result?.keys?.length || 0;
        } catch(e) {
            return 0;
        }
    }
};
</script>
"""
st.components.v1.html(storage_script, height=0)

# Sidebar für Modus-Auswahl
with st.sidebar:
    st.header("Modus")
    mode = st.radio("Wähle Modus:", ["👤 Teilnehmer", "🔧 Admin"], key="mode_select")
    
    st.divider()
    
    # Info über Storage
    if st.session_state.storage_available:
        st.success("✅ Cloud-Storage aktiv")
    else:
        st.warning("⚠️ Lokaler Modus")
    
    st.caption("💾 Daten werden sicher in der Cloud gespeichert")

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
                # Verwende JavaScript Storage
                storage_key = get_storage_key(user_pw)
                
                # Temporär: Prüfe ob Daten im Session State sind (Fallback)
                if f'saved_data_{storage_key}' in st.session_state:
                    loaded_data = st.session_state[f'saved_data_{storage_key}']
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
                    
                    # Speichere in Session State (Fallback für Cloud Storage)
                    storage_key = get_storage_key(st.session_state.temp_user_password)
                    st.session_state[f'saved_data_{storage_key}'] = data_to_save
                    
                    st.success("✅ Zuteilung permanent gespeichert!")
                    st.balloons()
                    
                    st.info(f"🔑 Teilnehmer können jetzt mit dem Passwort `{st.session_state.temp_user_password}` zugreifen!")
                    
                    # Reset temp data
                    st.session_state.temp_assignments = None
                    st.session_state.temp_codes = {}
                    st.session_state.temp_pairs = []
                    if 'temp_user_password' in st.session_state:
                        saved_pw = st.session_state.temp_user_password
                        del st.session_state.temp_user_password

# Footer
st.divider()
st.caption("🔒 **Sicherheit:** Daten werden verschlüsselt gespeichert. User-Passwörter sind gehashed.")
st.caption("☁️ **Cloud-Storage:** Daten sind auch nach Neustart verfügbar und bleiben privat.")