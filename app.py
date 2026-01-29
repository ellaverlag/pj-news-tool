import streamlit as st
import google.generativeai as genai
import docx2txt
import PyPDF2
import requests
from bs4 import BeautifulSoup

# --- SEITEN KONFIGURATION ---
st.set_page_config(page_title="PJ News Generator", page_icon="📝", layout="centered")

st.title("📝 PJ News-Generator V5")
st.caption("Meldungen aus Text, Datei oder Web-Link erstellen.")

# --- SIDEBAR (API KEY) ---
st.sidebar.header("Einstellungen")
api_key = st.sidebar.text_input("Google API Key", type="password")
if not api_key and "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]

# --- HAUPTBEREICH: EINGABEN ---
length_option = st.radio(
    "Gewünschte Artikellänge:",
    ["Kurz (~1.200 Zeichen)", "Normal (~2.500 Zeichen)", "Lang (~5.000 Zeichen)"],
    horizontal=True
)

# Drei Wege zum Text
st.markdown("### Quellmaterial bereitstellen")
url_input = st.text_input("Link zur Pressemeldung (URL):", placeholder="https://...")
uploaded_file = st.file_uploader("Oder Datei hochladen (PDF, DOCX, TXT):", type=["pdf", "docx", "txt"])
source_text_input = st.text_area("Oder Text direkt einfügen:", height=150)

final_source_text = ""

# LOGIK: TEXT AUS URL EXTRAHIEREN
if url_input:
    try:
        response = requests.get(url_input, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        # Entferne Skripte und Styles
        for script in soup(["script", "style"]):
            script.extract()
        final_source_text = soup.get_text(separator=' ', strip=True)
    except Exception as e:
        st.error(f"Fehler beim Laden der URL: {e}")

# LOGIK: TEXT AUS DATEI EXTRAHIEREN (falls keine URL angegeben wurde)
elif uploaded_file:
    if uploaded_file.type == "application/pdf":
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        final_source_text = " ".join([page.extract_text() for page in pdf_reader.pages])
    elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        final_source_text = docx2txt.process(uploaded_file)
    else:
        final_source_text = uploaded_file.read().decode("utf-8")

# LOGIK: DIREKTE EINGABE (Fallback)
elif source_text_input:
    final_source_text = source_text_input

# --- PROMPT BAUEN ---
if "Kurz" in length_option:
    length_instr = "ZIEL-LÄNGE: ca. 1.200 Zeichen. Kompakter Fließtext ohne H2."
elif "Normal" in length_option:
    length_instr = "ZIEL-LÄNGE: ca. 2.500 Zeichen. Mit H2-Zwischenüberschriften."
else:
    length_instr = "ZIEL-LÄNGE: ca. 5.000 Zeichen. Ausführlich mit vielen H2."

SYSTEM_PROMPT = f"""
Du bist erfahrene:r Fachredakteur:in beim "packaging journal".
REGELN:
1. TITEL (H1): Maximal 6 Wörter!
2. SEO: Fokus-Keyword nur EIN WORT. Muss in Titel und Text vorkommen.
3. FILTER: Sachlich, keine PR-Floskeln, keine GmbH/AG/Co.KG.
4. {length_instr}
OUTPUT: 1. SEO-BOX, 2. ARTIKEL (H1, Teaser fett, Body, Fazit).
"""

# --- GENERIERUNG ---
if st.button("Artikel erstellen ✨", type="primary"):
    if not api_key:
        st.error("Bitte API Key in der Sidebar hinterlegen.")
    elif not final_source_text or len(final_source_text) < 20:
        st.warning("Bitte gültiges Quellmaterial angeben.")
    else:
        try:
            with st.spinner("Extrahiere Daten und schreibe Artikel..."):
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=SYSTEM_PROMPT)
                response = model.generate_content(final_source_text)
                st.success("Fertig!")
                st.markdown("---")
                st.markdown(response.text)
        except Exception as e:
            st.error(f"Fehler bei der Generierung: {e}")
