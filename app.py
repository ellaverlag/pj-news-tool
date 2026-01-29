import streamlit as st
import google.generativeai as genai
import docx2txt
import PyPDF2
import requests
from bs4 import BeautifulSoup

# --- SEITEN KONFIGURATION & BRANDING ---
st.set_page_config(page_title="packaging journal Redaktions Tool", page_icon="🚀", layout="wide")

# Custom CSS für Corporate Design (#24A27F)
st.markdown(f"""
    <style>
    .stApp {{ background-color: #f8f9fa; }}
    .stButton>button {{
        width: 100%;
        border-radius: 8px;
        height: 3.5em;
        background-color: #24A27F !important;
        color: white !important;
        font-weight: bold;
        border: none;
    }}
    [data-testid="stSidebar"] {{ background-color: #ffffff; border-right: 1px solid #e0e0e0; }}
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR: KONFIGURATION & ZUGRIFF ---
st.sidebar.header("🔐 Zugriff & Setup")

# Passwort-Abfrage
passwort_eingabe = st.sidebar.text_input("Tool-Passwort eingeben:", type="password")

# HIER DEIN PASSWORT ÄNDERN:
KORREKTES_PASSWORT = "pj-redaktion-2026"

if passwort_eingabe != KORREKTES_PASSWORT:
    if passwort_eingabe != "":
        st.sidebar.error("Falsches Passwort!")
    st.warning("Bitte gib das Passwort in der Seitenleiste ein, um das Tool zu nutzen.")
    st.stop() # Stoppt die App hier, wenn das Passwort nicht stimmt

# Ab hier läuft die App nur, wenn das Passwort korrekt ist
st.sidebar.success("Zugriff gewährt")

api_key = st.sidebar.text_input("Google API Key", type="password")
if not api_key and "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]

st.sidebar.markdown("---")
modus = st.sidebar.radio(
    "Was möchtest du erstellen?",
    ["Standard Online-News", "Messe-Vorbericht (Special)"]
)

# --- TITEL BEREICH ---
st.title("🚀 packaging journal Redaktions Tool")
st.caption(f"Angemeldet im Modus: {modus}")

# --- LOGIK FÜR DYNAMISCHE LÄNGEN & PROMPTS ---
if modus == "Standard Online-News":
    length_option = st.radio(
        "Gewünschte Artikellänge:",
        ["Kurz (~1.200 Zeichen)", "Normal (~2.500 Zeichen)", "Lang (~5.000 Zeichen)"],
        horizontal=True
    )
    SYSTEM_PROMPT_BASE = f"""
    Du bist Redakteur beim "packaging journal". Erstelle eine Online-News.
    REGELN: Titel max 6 Wörter, Keyword 1 Wort, kein PR-Sprech, keine GmbH/AG.
    LÄNGE: {length_option}.
    OUTPUT: SEO-BOX (Keyword, Meta-Desc, Tags), ARTIKEL (H1, Teaser fett, Body, Fazit).
    """
else:
    selected_messe = st.sidebar.selectbox("Welche Messe?", ["LogiMat", "interpack", "Fachpack", "SPS"])
    length_option = st.radio(
        "Gewünschte Print-Länge (Online ist immer ausführlich):",
        ["KURZ (ca. 900 Zeichen)", "NORMAL (ca. 1.300 Zeichen)", "LANG (ca. 2.000 Zeichen)"],
        horizontal=True
    )
    messe_links = {
        "LogiMat": "https://www.logimat-messe.de/de/die-messe/ausstellerliste",
        "interpack": "https://www.interpack.de/de/Aussteller_Produkte/Ausstellerverzeichnis",
        "Fachpack": "https://www.fachpack.de/de/aussteller-produkte/ausstellerliste",
        "SPS": "https://sps.mesago.com/nuernberg/de/ausstellersuche.html"
    }
    messe_link = messe_links.get(selected_messe, "")
    print_len_val = length_option.split(" ")[0]
    SYSTEM_PROMPT_BASE = f"""
    Du bist Fachredakteur beim packaging journal. Erstelle zwei Versionen eines Vorberichts für das {selected_messe}-Special.
    STIL: Journalistisch, sachlich, kein PR-Fluff. Firmennamen ohne GmbH/AG.
    WICHTIG: Nicht schreiben "zeigt auf der {selected_messe}". Nutze Anwendungs-Einstiege.
    STANDNUMMER: Suche im Quelltext. Wenn fehlt, schreibe "Halle ??, Stand ??" und verweise auf {messe_link}.
    OUTPUT-FORMAT:
    A) PRINT: Oberzeile, Headline (max 6 Wörter), Text (ca. {print_len_val} Zeichen), Website | Standnummer.
    B) ONLINE: SEO-BOX (Keyword: 1 Wort), Firma, Überschrift, Anleser fett, Text (2500-5000 Zeichen, H2), Standnummer.
    """

# --- HAUPTBEREICH: EINGABEN ---
st.markdown("### 📄 Quellmaterial bereitstellen")
col_link, col_file = st.columns(2)
with col_link:
    url_input = st.text_input("Link (URL):", placeholder="https://...")
with col_file:
    uploaded_file = st.file_uploader("Datei (PDF, DOCX):", type=["pdf", "docx", "txt"])

source_text_input = st.text_area("Oder Text direkt einfügen:", height=200)

# --- TEXT-EXTRAKTION ---
final_source_text = ""
if url_input:
    try:
        res = requests.get(url_input, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        for s in soup(["script", "style"]): s.extract()
        final_source_text = soup.get_text(separator=' ', strip=True)
    except Exception as e: st.error(f"URL-Fehler: {e}")
elif uploaded_file:
    if uploaded_file.type == "application/pdf":
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        final_source_text = " ".join([p.extract_text() for p in pdf_reader.pages])
    elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        final_source_text = docx2txt.process(uploaded_file)
    else: final_source_text = uploaded_file.read().decode("utf-8")
elif source_text_input:
    final_source_text = source_text_input

# --- GENERIERUNG ---
if st.button(f"✨ {modus.upper()} JETZT GENERIEREN", type="primary"):
    if not api_key:
        st.error("Bitte API Key in den Einstellungen hinterlegen.")
    elif not final_source_text or len(final_source_text) < 20:
        st.warning("Kein Quellmaterial gefunden.")
    else:
        try:
            with st.spinner("KI arbeitet..."):
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=SYSTEM_PROMPT_BASE)
                response = model.generate_content(final_source_text)
                st.success("Fertig!")
                st.divider()
                st.markdown(response.text)
        except Exception as e:
            st.error(f"Fehler: {e}")
