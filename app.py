import streamlit as st
import google.generativeai as genai
import docx2txt
import PyPDF2
import requests
from bs4 import BeautifulSoup
from docx import Document
from io import BytesIO
from openai import OpenAI
import pandas as pd
from datetime import datetime
import os

# --- KONFIGURATION & BRANDING ---
st.set_page_config(page_title="PJ Redaktions Tool", page_icon="🚀", layout="wide")

# Hausfarbe: #24A27F
st.markdown(f"""
    <style>
    .stApp {{ background-color: #f8f9fa; }}
    .stButton>button {{ 
        width: 100%; border-radius: 8px; height: 3.5em; 
        background-color: #24A27F !important; color: white !important; 
        font-weight: bold; border: none;
    }}
    div[data-baseweb="radio"] div {{ color: #24A27F !important; }}
    [data-testid="stSidebar"] {{ background-color: #ffffff; border-right: 1px solid #e0e0e0; }}
    .stCode {{ border: 1px solid #24A27F !important; border-radius: 5px; }}
    </style>
    """, unsafe_allow_html=True)

# --- LOGO ANZEIGEN ---
# Falls du eine lokale Datei nutzt: st.image("logo.png", width=250)
# Hier beispielhaft als Platzhalter/Überschrift mit Logo-Logik
col_logo, col_title = st.columns([1, 4])
with col_logo:
    # https://packaging-journal.de/wp-content/uploads/2026/01/PJ-Homepage-2026-Logo-Footer-normal.png
    st.markdown(f"<h2 style='color: #24A27F;'>packaging journal</h2>", unsafe_allow_html=True)
with col_title:
    st.title("🚀 Redaktions Tool")

# --- DATEI-HISTORIE ---
HISTORY_FILE = "news_history.csv"

def save_to_history(titel, text):
    new_data = pd.DataFrame([{"Datum": datetime.now().strftime("%d.%m.%Y %H:%M"), "Titel": titel, "Inhalt": text[:100] + "..."}])
    if not os.path.isfile(HISTORY_FILE):
        new_data.to_csv(HISTORY_FILE, index=False, sep=";")
    else:
        new_data.to_csv(HISTORY_FILE, mode='a', header=False, index=False, sep=";")

# --- HILFSFUNKTIONEN ---
def get_best_google_model():
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for preferred in ["models/gemini-1.5-flash", "models/gemini-1.5-pro"]:
            if preferred in models: return preferred
        return models[0] if models else None
    except: return None

def generate_horizontal_image(topic):
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        response = client.images.generate(
            model="dall-e-3",
            prompt=f"Professional industrial photography for packaging industry, theme: {topic}. High-end cinematic lighting, 16:9 horizontal, no text.",
            size="1792x1024", quality="standard", n=1
        )
        return response.data[0].url
    except: return None

def create_docx(text):
    doc = Document()
    doc.add_paragraph(text)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- SIDEBAR ---
st.sidebar.header("🔐 Login")
pw_input = st.sidebar.text_input("Passwort:", type="password")
if pw_input != st.secrets.get("TOOL_PASSWORD", "pj-redaktion-2026"):
    st.warning("Bitte gültiges Passwort eingeben.")
    st.stop()

modus = st.sidebar.radio("Was möchtest du erstellen?", ["Standard Online-News", "Messe-Vorbericht (Special)"])
generate_img_flag = st.sidebar.checkbox("KI-Beitragsbild generieren?", value=True)

# --- PROMPT-LOGIK ---
# Gemeinsame Regeln [cite: 6, 13, 17, 18]
base_rules = """
Rolle: Erfahrene:r Fachredakteur:in beim packaging journal[cite: 5]. 
Stil: Journalistisch, sachlich, präzise[cite: 6]. 
Regeln: Kein PR-Fluff [cite: 14], Firmennamen normal (keine Versalien) [cite: 16], Rechtsformen (GmbH/AG) und Symbole (R/TM) entfernen[cite: 17, 18]. 
KEINE Ortsmarke oder Datum am Anfang setzen.
"""

if modus == "Standard Online-News":
    l_opt = st.radio("Artikellänge:", ["Kurz (~1.200)", "Normal (~2.500)", "Lang (~5.000)"], horizontal=True)
    system_prompt = f"{base_rules}\nErstelle eine Online-News. Format: [TITEL] (max 6 Wörter), [TEASER] (max 300 Zeichen), [TEXT] (Ziel: {l_opt} Zeichen), [SNIPPET] (max 160 Zeichen)."
else:
    selected_messe = st.sidebar.selectbox("Messe wählen:", ["LogiMat", "interpack", "Fachpack", "SPS"])
    l_opt = st.radio("Print-Länge wählen:", ["KURZ (ca. 900)", "NORMAL (ca. 1300)", "LANG (ca. 2000)"], horizontal=True)
    m_links = {"LogiMat": "https://www.logimat-messe.de/de/die-messe/ausstellerliste", "interpack": "https://www.interpack.de/de/Aussteller_Produkte/Ausstellerverzeichnis", "Fachpack": "https://www.fachpack.de/de/aussteller-produkte/ausstellerliste", "SPS": "https://sps.mesago.com/nuernberg/de/ausstellersuche.html"}
    m_link = m_links.get(selected_messe, "")
    p_len = l_opt.split(" ")[0]
    
    system_prompt = f"""
    {base_rules}
    Aufgabe: Erstelle zwei Versionen für die Messe {selected_messe}[cite: 8]:
    
    1) PRINT-Version: Oberzeile (Firma), Headline, Text (ca. {p_len} Zeichen ohne Zwischenüberschriften), Website, Halle/Standnummer[cite: 28, 29, 30, 31, 36, 37].
    2) ONLINE-Version: Firma, Überschrift, Anleser (2-3 Sätze), Haupttext (2500-5000 Zeichen mit H2-Zwischenüberschriften), Halle/Standnummer[cite: 38, 39, 40, 41, 42, 43].
    3) SEO-BOX (für Online): Fokus-Keyword, Meta Description (max 160 Zeichen), Tags[cite: 44, 45, 46, 47, 48].
    
    WICHTIG: Einstiege variieren (Use Case, Trend, Engpass etc.). Standnummer explizit aufführen[cite: 43]. Website verlinkt auf {m_link}[cite: 25].
    """

# --- INPUT & EXTRAKTION (URL/FILE/TEXT) ---
url_in = st.text_input("Link (URL):")
file_in = st.file_uploader("Datei:", type=["pdf", "docx", "txt"])
text_in = st.text_area("Oder Text einfügen:")

# (Extraktion Logik bleibt gleich wie im funktionierenden Test...)
final_text = ""
if url_in:
    try:
        r = requests.get(url_in, timeout=10)
        final_text = BeautifulSoup(r.text, 'html.parser').get_text(separator=' ', strip=True)
    except: st.error("URL-Fehler")
elif file_in:
    if file_in.type == "application/pdf":
        pdf = PyPDF2.PdfReader(file_in)
        final_text = " ".join([p.extract_text() for p in pdf.pages])
    else: final_text = docx2txt.process(file_in)
else: final_text = text_in

# --- GENERIERUNG ---
if st.button(f"✨ {modus.upper()} JETZT GENERIEREN", type="primary"):
    if len(final_text) < 20:
        st.warning("Bitte Material bereitstellen.")
    else:
        with st.spinner("KI generiert Inhalte gemäß Masterprompt..."):
            model_name = get_best_google_model()
            if model_name:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(f"{system_prompt}\n\nQuellmaterial: {final_text}")
                st.session_state['last_result'] = response.text
                if generate_img_flag:
                    st.session_state['last_image'] = generate_horizontal_image(final_text[:200])
                save_to_history("Generierung", response.text)

# --- ANZEIGE ---
if 'last_result' in st.session_state:
    st.divider()
    if st.session_state.get('last_image'):
        st.image(st.session_state['last_image'], caption="Beitragsbild (16:9)")
    
    st.subheader("📄 Dein Ergebnis")
    st.code(st.session_state['last_result'], language=None)
    st.download_button("📄 Word-Download", data=create_docx(st.session_state['last_result']), file_name="PJ_Beitrag.docx")
