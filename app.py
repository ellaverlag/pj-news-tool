import streamlit as st
import google.generativeai as genai
import docx2txt
import PyPDF2
import requests
from bs4 import BeautifulSoup
from docx import Document
from io import BytesIO

# --- KONFIGURATION & BRANDING ---
st.set_page_config(page_title="packaging journal Redaktions Tool", page_icon="🚀", layout="wide")

# Custom CSS für Corporate Design (#24A27F)
st.markdown(f"""
    <style>
    .stApp {{ background-color: #f8f9fa; }}
    .stButton>button {{
        width: 100%; border-radius: 8px; height: 3.5em;
        background-color: #24A27F !important; color: white !important; font-weight: bold; border: none;
    }}
    [data-testid="stSidebar"] {{ background-color: #ffffff; border-right: 1px solid #e0e0e0; }}
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR: ZUGRIFF ---
st.sidebar.header("🔐 Login")
pw_input = st.sidebar.text_input("Tool-Passwort:", type="password")

# Passwortprüfung aus den Secrets (FallBack auf dein 2026er Passwort)
if pw_input != st.secrets.get("TOOL_PASSWORD", "pj-redaktion-2026"):
    st.warning("Bitte gültiges Passwort eingeben.")
    st.stop()

st.sidebar.success("Zugriff gewährt")
st.sidebar.markdown("---")
modus = st.sidebar.radio("Was möchtest du erstellen?", ["Standard Online-News", "Messe-Vorbericht (Special)"])

# --- HILFSFUNKTIONEN ---

def create_docx(text):
    doc = Document()
    for line in text.split('\n'):
        if line.startswith('# '): doc.add_heading(line[2:], 0)
        elif line.startswith('## '): doc.add_heading(line[3:], 1)
        else: doc.add_paragraph(line)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

def export_to_wordpress(title, content):
    wp_url = st.secrets.get("WP_URL")
    wp_user = st.secrets.get("WP_USER")
    wp_pw = st.secrets.get("WP_APP_PW")
    
    if not all([wp_url, wp_user, wp_pw]):
        return "❌ WP-Daten fehlen in den Secrets!"

    endpoint = f"{wp_url.rstrip('/')}/wp-json/wp/v2/posts"
    payload = {"title": title, "content": content, "status": "draft"}
    
    try:
        res = requests.post(endpoint, json=payload, auth=(wp_user, wp_pw), timeout=15)
        if res.status_code == 201: return "✅ Erfolg: Entwurf in WordPress angelegt!"
        else: return f"❌ WP-Fehler: {res.status_code} - {res.text}"
    except Exception as e: return f"❌ Verbindung fehlgeschlagen: {e}"

# --- HAUPTBEREICH ---
st.title("🚀 packaging journal Redaktions Tool")

# Dynamische Prompt-Logik
if modus == "Standard Online-News":
    length_option = st.radio("Artikellänge:", ["Kurz (~1.200)", "Normal (~2.500)", "Lang (~5.000)"], horizontal=True)
    system_prompt = f"Du bist Redakteur beim packaging journal. Erstelle eine Online-News. Titel max 6 Wörter, Keyword 1 Wort. Länge: {length_option}."
else:
    selected_messe = st.sidebar.selectbox("Messe wählen:", ["LogiMat", "interpack", "Fachpack", "SPS"])
    length_option = st.radio("Print-Länge (Online ist immer ausführlich):", ["KURZ (900)", "NORMAL (1300)", "LANG (2000)"], horizontal=True)
    
    messe_links = {
        "LogiMat": "https://www.logimat-messe.de/de/die-messe/ausstellerliste",
        "interpack": "https://www.interpack.de/de/Aussteller_Produkte/Ausstellerverzeichnis",
        "Fachpack": "https://www.fachpack.de/de/aussteller-produkte/ausstellerliste",
        "SPS": "https://sps.mesago.com/nuernberg/de/ausstellersuche.html"
    }
    m_link = messe_links.get(selected_messe, "")
    p_len = length_option.split(" ")[0]
    
    system_prompt = f"""
    Du bist Fachredakteur beim packaging journal. Erstelle Print & Online Vorbericht für {selected_messe}. 
    STIL: Journalistisch, sachlich. Firmennamen ohne GmbH/AG. Titel max 6 Wörter.
    STANDNUMMER: Suche im Quelltext. Wenn fehlt, schreibe 'Halle ??, Stand ??' und verweise auf {m_link}.
    AUSGABE: A) PRINT (ca. {p_len} Zeichen), B) ONLINE (SEO-Box, Anleser fett, 2500-5000 Zeichen mit H2).
    """

st.markdown("### 📄 Quellmaterial bereitstellen")
col_url, col_upload = st.columns(2)
with col_url:
    url_in = st.text_input("Link (URL):", placeholder="https://...")
with col_upload:
    file_in = st.file_uploader("Datei hochladen:", type=["pdf", "docx", "txt"])

text_in = st.text_area("Oder Text direkt einfügen:", height=150)

# Extraktion
final_text = ""
if url_in:
    try:
        r = requests.get(url_in, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        for s in soup(["script", "style"]): s.extract()
        final_text = soup.get_text(separator=' ', strip=True)
    except Exception as e: st.error(f"Link-Fehler: {e}")
elif file_in:
    if file_in.type == "application/pdf":
        pdf = PyPDF2.PdfReader(file_in)
        final_text = " ".join([p.extract_text() for p in pdf.pages])
    elif file_in.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        final_text = docx2txt.process(file_in)
    else:
        final_text = file_in.read().decode("utf-8")
else:
    final_text = text_in

# --- BUTTON & GENERIERUNG ---
if st.button(f"✨ {modus.upper()} JETZT GENERIEREN", type="primary"):
    if not final_text or len(final_text) < 20:
        st.warning("Bitte ausreichend Quellmaterial bereitstellen.")
    else:
        try:
            with st.spinner("KI verarbeitet Daten..."):
                genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
                model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=system_prompt)
                response = model.generate_content(final_text)
                
                # Speichern im Session State für Export-Funktionen
                st.session_state['last_result'] = response.text
                
                st.success("Erstellung abgeschlossen!")
                st.divider()
                st.markdown(st.session_state['last_result'])
                
                # Export-Sektion
                exp1, exp2 = st.columns(2)
                with exp1:
                    st.download_button("📄 Als Word (.docx) laden", 
                                       data=create_docx(st.session_state['last_result']), 
                                       file_name=f"PJ_{modus.replace(' ', '_')}.docx")
                with exp2:
                    if st.button("🌐 In WordPress exportieren"):
                        lines = st.session_state['last_result'].split('\n')
                        # Titel-Suche: Nimm erste Zeile, die kein SEO-Kram ist
                        title_candidate = next((l for l in lines if l.strip() and "SEO" not in l and "Keyword" not in l), "Neuer Beitrag")
                        title = title_candidate.strip("# ")
                        msg = export_to_wordpress(title, st.session_state['last_result'])
                        st.info(msg)
        except Exception as e:
            st.error(f"Fehler: {e}")
