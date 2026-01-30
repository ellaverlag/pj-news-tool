import streamlit as st
import google.generativeai as genai
import docx2txt
import PyPDF2
import requests
from bs4 import BeautifulSoup
from docx import Document
from io import BytesIO
from openai import OpenAI
import os

# --- KONFIGURATION & BRANDING ---
st.set_page_config(page_title="packaging journal Redaktions Tool", page_icon="🚀", layout="wide")

# Hausfarbe: #24A27F
st.markdown(f"""
    <style>
    .stApp {{ background-color: #f8f9fa; }}
    .stButton>button {{ 
        width: 100%; border-radius: 8px; height: 3.5em; 
        background-color: #24A27F !important; color: white !important; 
        font-weight: bold; border: none;
    }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 24px; }}
    .stTabs [data-baseweb="tab"] {{ 
        height: 50px; white-space: pre-wrap; background-color: #ffffff; 
        border-radius: 5px; padding: 10px 20px; color: #24A27F;
    }}
    .stTabs [aria-selected="true"] {{ border-bottom: 3px solid #24A27F !important; font-weight: bold; }}
    .stCode {{ border: 1px solid #24A27F !important; border-radius: 5px; }}
    </style>
    """, unsafe_allow_html=True)

# --- HEADER MIT LOGO ---
col_logo, col_title = st.columns([1, 4])
with col_logo:
    # Falls du ein Logo hast, ersetze das durch st.image("logo.png")
    st.markdown(f"<h1 style='color: #24A27F; margin:0;'>pj</h1>", unsafe_allow_html=True)
with col_title:
    st.markdown("<h1 style='margin:0;'>Redaktions Tool</h1>", unsafe_allow_html=True)

# --- LOGIN & SIDEBAR ---
pw_input = st.sidebar.text_input("Passwort:", type="password")
if pw_input != st.secrets.get("TOOL_PASSWORD", "pj-redaktion-2026"):
    st.stop()

modus = st.sidebar.radio("Was erstellen wir?", ["Standard Online-News", "Messe-Vorbericht (Special)"])
generate_img_flag = st.sidebar.checkbox("KI-Beitragsbild generieren?", value=True)

# --- FUNKTIONEN ---
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

# --- PROMPT DEFINITION (Strikt nach deinem Dokument) ---
if modus == "Messe-Vorbericht (Special)":
    selected_messe = st.sidebar.selectbox("Messe:", ["LogiMat", "interpack", "Fachpack", "SPS"])
    l_opt = st.radio("Print-Länge:", ["KURZ (~900)", "NORMAL (~1300)", "LANG (~2000)"], horizontal=True)
    m_links = {"LogiMat": "https://www.logimat-messe.de/de/die-messe/ausstellerliste", "interpack": "https://www.interpack.de/de/Aussteller_Produkte/Ausstellerverzeichnis", "Fachpack": "https://www.fachpack.de/de/aussteller-produkte/ausstellerliste", "SPS": "https://sps.mesago.com/nuernberg/de/ausstellersuche.html"}
    m_link = m_links.get(selected_messe, "")
    
    system_prompt = f"""
    Du bist Redakteur beim packaging journal. Erstelle zwei Versionen eines Messe-Vorberichts für {selected_messe}. 
    KEINE Einleitungstexte, KEINE Ortsmarken, KEIN Datum. Starte direkt mit dem Format.
    
    STILREGELN: Kein PR-Fluff, Firmennamen normal (nicht VERSAL), Standnummern immer explizit nennen. Einstiege variieren (Trend, Use Case etc.).

    FORMAT FÜR DIE ANTWORT (STRENG EINHALTEN):
    [PRINT_START]
    Oberzeile: [Firma]
    Headline: [Max 6 Wörter]
    Text: [Ca. {l_opt.split('~')[1].replace(')', '')} Zeichen, ohne ZÜ]
    Website: [URL]
    Stand: [Halle/Stand]
    [PRINT_END]

    [ONLINE_START]
    Firma: [Firma]
    Überschrift: [Prägnant]
    Anleser: [2-3 Sätze]
    Text: [2500-5000 Zeichen, mit H2-Zwischenüberschriften]
    Stand: [Halle/Stand]
    Snippet: [Max 160 Zeichen]
    [ONLINE_END]
    """
else:
    # Standard News Logik
    system_prompt = "Erstelle eine Online-News gemäß packaging journal Standards."

# --- HAUPTBEREICH INPUTS ---
url_in = st.text_input("Quell-URL:")
file_in = st.file_uploader("Datei hochladen:", type=["pdf", "docx"])
text_in = st.text_area("Oder Text hier rein:")

# (Extraktions-Logik hier einfügen)
final_text = text_in # Vereinfacht für das Beispiel

# --- GENERIERUNG ---
if st.button("✨ INHALTE GENERIEREN"):
    with st.spinner("KI arbeitet..."):
        model_name = get_best_google_model()
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(f"{system_prompt}\n\nMATERIAL: {final_text}")
        st.session_state['raw_output'] = response.text
        if generate_img_flag:
            st.session_state['last_image'] = generate_horizontal_image(final_text[:200])

# --- AUSGABE IN TABS ---
if 'raw_output' in st.session_state:
    raw = st.session_state['raw_output']
    
    tab1, tab2 = st.tabs(["📟 PRINT VERSION", "🌐 ONLINE VERSION"])
    
    with tab1:
        if "[PRINT_START]" in raw:
            print_content = raw.split("[PRINT_START]")[1].split("[PRINT_END]")[0].strip()
            st.code(print_content, language=None)
    
    with tab2:
        if "[ONLINE_START]" in raw:
            online_content = raw.split("[ONLINE_START]")[1].split("[ONLINE_END]")[0].strip()
            
            # Bild anzeigen falls generiert
            if st.session_state.get('last_image'):
                st.image(st.session_state['last_image'], width=600)
            
            st.code(online_content, language=None)
