import streamlit as st
import google.generativeai as genai
import docx2txt
import PyPDF2
import requests
from bs4 import BeautifulSoup

# --- SEITEN KONFIGURATION ---
st.set_page_config(page_title="PJ Redaktions-Tool PRO", page_icon="🚀", layout="wide")

st.title("🚀 PJ Redaktions-Tool V8")
st.caption("Haupt-Tool für Online-News & Messe-Vorberichte (Print/Online).")

# --- SIDEBAR: EINSTELLUNGEN ---
st.sidebar.header("1. Konfiguration")
api_key = st.sidebar.text_input("Google API Key", type="password")
if not api_key and "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]

st.sidebar.markdown("---")

# HAUPT-AUSWAHL: News oder Messe
modus = st.sidebar.radio(
    "Was möchtest du erstellen?",
    ["Standard Online-News", "Messe-Vorbericht (Special)"]
)

# --- LOGIK FÜR DYNAMISCHE LÄNGEN & PROMPTS ---

if modus == "Standard Online-News":
    st.sidebar.info("Modus: Schnelle Online-Meldung.")
    length_option = st.radio(
        "Gewünschte Artikellänge:",
        ["Kurz (~1.200 Zeichen)", "Normal (~2.500 Zeichen)", "Lang (~5.000 Zeichen)"],
        horizontal=True
    )
    # Prompt für Standard-News
    SYSTEM_PROMPT_BASE = f"""
    Du bist Redakteur beim "packaging journal". Erstelle eine Online-News.
    REGELN:
    1. TITEL (H1): Maximal 6 Wörter!
    2. SEO: Fokus-Keyword nur EIN WORT.
    3. FILTER: Sachlich, kein PR-Sprech, keine Rechtsformen (GmbH etc.).
    4. LÄNGE: {length_option}.
    OUTPUT: SEO-BOX (Keyword, Meta-Desc, Tags), ARTIKEL (H1, Teaser fett, Body, Fazit).
    """
    selected_messe = ""
    messe_link = ""

else:  # Messe-Vorbericht
    selected_messe = st.sidebar.selectbox("Welche Messe?", ["LogiMat", "interpack", "Fachpack", "SPS"])
    st.sidebar.info(f"Modus: Vorbericht für {selected_messe} (Print & Online).")
    
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
    
    # Dein Masterprompt für Messen
    print_len_val = length_option.split(" ")[0] # Extrahiert KURZ, NORMAL oder LANG
    SYSTEM_PROMPT_BASE = f"""
    Du bist erfahrene:r Fachredakteur:in beim packaging journal. 
    Erstelle zwei Versionen eines Vorberichts für das {selected_messe}-Special.
    STIL: Journalistisch, sachlich, kein PR-Fluff, keine Marken-Symbole. Firmennamen ohne GmbH/AG.
    WICHTIG: Nicht schreiben "zeigt auf der {selected_messe}". Nutze Anwendungs-Einstiege.
    
    STANDNUMMER: Suche im Quelltext. Wenn fehlt, schreibe "Halle ??, Stand ??" und verweise auf {messe_link}.

    OUTPUT-FORMAT:
    A) PRINT
    Oberzeile: [Firma]
    Headline: [Max 6 Wörter]
    Text: [Keine H2, ca. {print_len_val} Zeichen gemäß Vorgabe]
    www.[website].com | Halle X, Stand Y

    B) ONLINE
    SEO-BOX (Keyword: 1 Wort, Meta-Desc, Tags)
    Firma: [Firma] | Überschrift | Anleser (fett) | Text (2500-5000 Zeichen, mit H2) | Standnummer
    """

# --- HAUPTBEREICH: EINGABEN ---
st.markdown("### Quellmaterial bereitstellen")
col_link, col_file = st.columns(2)
with col_link:
    url_input = st.text_input("Link (URL):", placeholder="https://...")
with col_file:
    uploaded_file = st.file_uploader("Datei (PDF, DOCX):", type=["pdf", "docx", "txt"])

source_text_input = st.text_area("Oder Text direkt einfügen:", height=150)

# --- TEXT-EXTRAKTION ---
final_source_text = ""
if url_input:
    try:
        res = requests.get(url_input, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        for s in soup(["script", "style"]): s.extract()
        final_source_text = soup.get_text(separator=' ', strip=True)
    except Exception as e:
        st.error(f"URL-Fehler: {e}")
elif uploaded_file:
    if uploaded_file.type == "application/pdf":
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        final_source_text = " ".join([p.extract_text() for p in pdf_reader.pages])
    elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        final_source_text = docx2txt.process(uploaded_file)
    else:
        final_source_text = uploaded_file.read().decode("utf-8")
elif source_text_input:
    final_source_text = source_text_input

# --- GENERIERUNG ---
if st.button(f"{modus} generieren ✨", type="primary"):
    if not api_key:
        st.error("Bitte API Key hinterlegen.")
    elif not final_source_text or len(final_source_text) < 20:
        st.warning("Kein ausreichendes Quellmaterial gefunden.")
    else:
        try:
            with st.spinner("KI generiert Entwürfe..."):
                genai.configure(api_key=api_key)
                # Wir nutzen gemini-1.5-flash für Geschwindigkeit und Kosten
                model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=SYSTEM_PROMPT_BASE)
                response = model.generate_content(final_source_text)
                st.success("Erfolgreich erstellt!")
                st.markdown("---")
                st.markdown(response.text)
        except Exception as e:
            st.error(f"Fehler: {e}")
