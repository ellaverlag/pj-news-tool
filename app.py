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
st.set_page_config(page_title="PJ Redaktions Tool", page_icon="🚀", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #24A27F !important; color: white !important; font-weight: bold; border: none; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e0e0e0; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR: EINSTELLUNGEN ---
st.sidebar.header("🔐 Login")
pw_input = st.sidebar.text_input("Passwort:", type="password")
if pw_input != st.secrets.get("TOOL_PASSWORD", "pj-redaktion-2026"):
    st.warning("Bitte Passwort eingeben.")
    st.stop()

st.sidebar.success("Zugriff gewährt")
st.sidebar.markdown("---")

modus = st.sidebar.radio("Was möchtest du erstellen?", ["Standard Online-News", "Messe-Vorbericht (Special)"])

st.sidebar.markdown("---")
st.sidebar.header("🎨 Visuelle Optionen")
generate_img_flag = st.sidebar.checkbox("KI-Beitragsbild generieren?", value=True)

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
            prompt=f"Professional industrial photography for packaging industry, topic: {topic}. High-end, cinematic lighting, 16:9 horizontal, photorealistic, no text.",
            size="1792x1024", 
            quality="standard",
            n=1
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

# --- PROMPT-LOGIK ---
# Allgemeine Verbote: Keine Ortsmarke, kein Datum.
constraint_text = "\n\nSTRIKTE VORGABE: Setze KEINE Ortsmarke (z.B. Berlin, Hürth) und KEIN Datum an den Anfang der Meldung. Starte direkt mit der Nachricht."
seo_vorgabe = "\nZusätzlich am Ende ausgeben:\n1. 'GOOGLE SNIPPET': Maximal 160 Zeichen.\n2. 'TEASER': Maximal 300 Zeichen."

if modus == "Standard Online-News":
    l_opt = st.radio("Artikellänge:", ["Kurz (~1.200)", "Normal (~2.500)", "Lang (~5.000)"], horizontal=True)
    system_prompt = f"Du bist Redakteur beim packaging journal. Erstelle eine Online-News. Titel max 6 Wörter, Keyword 1 Wort. Sachlich, kein PR-Fluff. Ziel-Länge: {l_opt} Zeichen.{constraint_text}{seo_vorgabe}"
else:
    selected_messe = st.sidebar.selectbox("Messe wählen:", ["LogiMat", "interpack", "Fachpack", "SPS"])
    l_opt = st.radio("Print-Länge:", ["KURZ (900)", "NORMAL (1300)", "LANG (2000)"], horizontal=True)
    m_links = {"LogiMat": "https://www.logimat-messe.de/de/die-messe/ausstellerliste", "interpack": "https://www.interpack.de/de/Aussteller_Produkte/Ausstellerverzeichnis", "Fachpack": "https://www.fachpack.de/de/aussteller-produkte/ausstellerliste", "SPS": "https://sps.mesago.com/nuernberg/de/ausstellersuche.html"}
    m_link = m_links.get(selected_messe, "")
    p_len = l_opt.split(" ")[0]
    system_prompt = f"Erstelle Print (ca. {p_len} Zeichen) & Online Vorbericht (2500-5000 Zeichen) für {selected_messe}. Titel max 6 Wörter. Standinfo verlinken auf {m_link}. Sachlich bleiben.{constraint_text}{seo_vorgabe}"

# --- HAUPTBEREICH ---
st.title("🚀 packaging journal Redaktions Tool")

st.markdown("### 📄 Quellmaterial bereitstellen")
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
    except:
