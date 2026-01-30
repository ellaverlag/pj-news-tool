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
    /* Buttons in Hausfarbe */
    .stButton>button {{ 
        width: 100%; border-radius: 8px; height: 3.5em; 
        background-color: #24A27F !important; color: white !important; 
        font-weight: bold; border: none;
    }}
    /* Akzentfarbe für Radio-Buttons und Checkboxen */
    div[data-baseweb="radio"] div {{ color: #24A27F !important; }}
    /* Sidebar Design */
    [data-testid="stSidebar"] {{ background-color: #ffffff; border-right: 1px solid #e0e0e0; }}
    /* Copy-Box Design */
    .stCode {{ border: 1px solid #24A27F !important; border-radius: 5px; }}
    </style>
    """, unsafe_allow_html=True)

# --- DATEI-HISTORIE SETUP ---
HISTORY_FILE = "news_history.csv"

def save_to_history(titel, teaser, text, snippet):
    new_data = pd.DataFrame([{
        "Datum": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "Titel": titel,
        "Teaser": teaser,
        "Text": text,
        "Snippet": snippet
    }])
    if not os.path.isfile(HISTORY_FILE):
        new_data.to_csv(HISTORY_FILE, index=False, sep=";")
    else:
        new_data.to_csv(HISTORY_FILE, mode='a', header=False, index=False, sep=";")

# --- HILFSFUNKTIONEN ---
def get_best_google_model():
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for preferred in ["models/gemini-1.5-flash", "models/gemini-1.5-pro", "models/gemini-pro"]:
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
    for line in text.split('\n'):
        if line.startswith('# '): doc.add_heading(line[2:], 0)
        elif line.startswith('## '): doc.add_heading(line[3:], 1)
        else: doc.add_paragraph(line)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- SIDEBAR ---
st.sidebar.header("🔐 Login")
pw_input = st.sidebar.text_input("Passwort:", type="password")
if pw_input != st.secrets.get("TOOL_PASSWORD", "pj-redaktion-2026"):
    st.warning("Bitte gültiges Passwort eingeben.")
    st.stop()

# Archiv-Anzeige
st.sidebar.markdown("---")
st.sidebar.header("📚 Archiv (Letzte 5)")
if os.path.isfile(HISTORY_FILE):
    try:
        df_history = pd.read_csv(HISTORY_FILE, sep=";")
        for i, row in df_history.tail(5).iterrows():
            with st.sidebar.expander(f"🕒 {row['Datum']}"):
                st.caption(f"**{row['Titel']}**")
                st.write(f"Snippet: {row['Snippet']}")
    except: st.sidebar.info("Archiv wird geladen...")
else:
    st.sidebar.info("Noch kein Archiv vorhanden.")

st.sidebar.markdown("---")
modus = st.sidebar.radio("Was möchtest du erstellen?", ["Standard Online-News", "Messe-Vorbericht (Special)"])
generate_img_flag = st.sidebar.checkbox("KI-Beitragsbild generieren?", value=True)

# --- PROMPT-LOGIK ---
format_instruction = """
ANTWORTE STRENG IN DIESEM FORMAT (verwende die Trenner [TITEL], [TEASER], [TEXT], [SNIPPET]):
[TITEL]
(Max 6 Wörter)
[TEASER]
(Max 300 Zeichen)
[TEXT]
(Hier der Haupttext ohne Ortsmarke/Datum)
[SNIPPET]
(Max 160 Zeichen Google Snippet)
"""

if modus == "Standard Online-News":
    l_opt = st.radio("Artikellänge:", ["Kurz (~1.200)", "Normal (~2.500)", "Lang (~5.000)"], horizontal=True)
    system_prompt = f"Du bist Redakteur beim packaging journal. Erstelle Online-News. {format_instruction} Länge: {l_opt}."
else:
    selected_messe = st.sidebar.selectbox("Messe:", ["LogiMat", "interpack", "Fachpack", "SPS"])
    l_opt = st.radio("Länge:", ["KURZ (900)", "NORMAL (1300)", "LANG (2000)"], horizontal=True)
    system_prompt = f"Erstelle Messe-Bericht für {selected_messe}. {format_instruction} Länge: {l_opt}."

# --- HAUPTBEREICH ---
st.title("🚀 packaging journal Redaktions Tool")

col_u, col_f = st.columns(2)
with col_u: url_in = st.text_input("Link (URL):")
with col_f: file_in = st.file_uploader("Datei:", type=["pdf", "docx", "txt"])
text_in = st.text_area("Oder Text einfügen:", height=150)

# Extraktion
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
        with st.spinner("KI verarbeitet Daten..."):
            model_name = get_best_google_model()
            if model_name:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(f"{system_prompt}\n\nMaterial: {final_text}")
                res_text = response.text
                
                # Parsing
                try:
                    titel = res_text.split('[TITEL]')[1].split('[TEASER]')[0].strip()
                    teaser = res_text.split('[TEASER]')[1].split('[TEXT]')[0].strip()
                    haupttext = res_text.split('[TEXT]')[1].split('[SNIPPET]')[0].strip()
                    snippet = res_text.split('[SNIPPET]')[1].strip()
                    
                    save_to_history(titel, teaser, haupttext, snippet)
                    
                    st.session_state['last_t'] = titel
                    st.session_state['last_te'] = teaser
                    st.session_state['last_h'] = haupttext
                    st.session_state['last_s'] = snippet
                except:
                    st.error("KI-Formatfehler. Bitte erneut versuchen.")

                if generate_img_flag:
                    st.session_state['last_image'] = generate_horizontal_image(final_text[:200])
                else:
                    st.session_state['last_image'] = None

# --- ANZEIGE ---
if 'last_h' in st.session_state:
    st.divider()
    
    st.subheader("📌 WordPress Titel")
    st.code(st.session_state['last_t'], language=None)
    
    st.subheader("📰 Teaser (max 300 Zeichen)")
    st.code(st.session_state['last_te'], language=None)
    
    col_img, col_txt = st.columns([1, 1])
    with col_img:
        if st.session_state.get('last_image'):
            st.image(st.session_state['last_image'], caption="Rechtsklick zum Speichern")
        else:
            st.info("Kein Bild generiert.")
    with col_txt:
        st.subheader("✍️ Haupttext")
        st.write(st.session_state['last_h'])
    
    st.subheader("🔍 Google Snippet (max 160 Zeichen)")
    st.code(st.session_state['last_s'], language=None)
    
    st.divider()
    st.download_button("📄 Word-Download (.docx)", data=create_docx(st.session_state['last_h']), file_name="PJ_Beitrag.docx")
