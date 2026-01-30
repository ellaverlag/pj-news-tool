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

# --- KONFIGURATION ---
st.set_page_config(page_title="PJ Redaktions Tool", page_icon="🚀", layout="wide")

# Styling
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    .stButton>button { width: 100%; border-radius: 8px; background-color: #24A27F !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIN & MODUS ---
pw_input = st.sidebar.text_input("Passwort:", type="password")
if pw_input != st.secrets.get("TOOL_PASSWORD", "pj-redaktion-2026"):
    st.warning("Bitte Passwort eingeben.")
    st.stop()

modus = st.sidebar.radio("Modus:", ["Standard Online-News", "Messe-Vorbericht (Special)"])

# --- FUNKTIONEN ---
def get_best_google_model():
    """Findet das beste verfügbare Modell in deinem Account"""
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # Priorität: Flash 1.5 -> Pro -> Erstbestes
        for preferred in ["models/gemini-1.5-flash", "models/gemini-1.5-pro", "models/gemini-pro"]:
            if preferred in models: return preferred
        return models[0] if models else None
    except:
        return None

def generate_horizontal_image(topic):
    """Erstellt das 16:9 Bild via OpenAI"""
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        response = client.images.generate(
            model="dall-e-3",
            prompt=f"Professional industrial photography for packaging industry, topic: {topic}. High-end, cinematic, 16:9 horizontal, no text.",
            size="1792x1024", 
            quality="standard",
            n=1
        )
        return response.data[0].url
    except Exception as e:
        st.error(f"Bild-Fehler: {e}")
        return None

def create_docx(text):
    doc = Document()
    for line in text.split('\n'):
        if line.startswith('# '): doc.add_heading(line[2:], 0)
        elif line.startswith('## '): doc.add_heading(line[3:], 1)
        else: doc.add_paragraph(line)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- HAUPTBEREICH ---
st.title("🚀 packaging journal Redaktions Tool")

# Prompt-Logik
if modus == "Standard Online-News":
    system_prompt = "Du bist Redakteur beim packaging journal. Erstelle eine sachliche Online-News."
else:
    selected_messe = st.sidebar.selectbox("Messe:", ["LogiMat", "interpack", "Fachpack", "SPS"])
    system_prompt = f"Erstelle einen Vorbericht für die {selected_messe}."

# Input-Bereich
url_in = st.text_input("URL:")
file_in = st.file_uploader("Datei:", type=["pdf", "docx", "txt"])
text_in = st.text_area("Oder Text:")

# Text extrahieren
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
    else: final_text = file_in.read().decode("utf-8")
else: final_text = text_in

# --- GENERIERUNG ---
if st.button("✨ JETZT GENERIEREN"):
    if len(final_text) < 20:
        st.warning("Bitte Material einfügen.")
    else:
        with st.spinner("Google & OpenAI arbeiten..."):
            # 1. Google Text
            model_name = get_best_google_model()
            if not model_name:
                st.error("Kein Google-Modell gefunden. Key prüfen!")
            else:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(f"{system_prompt}\n\nBasis-Text: {final_text}")
                st.session_state['last_result'] = response.text
                
                # 2. OpenAI Bild
                st.session_state['last_image'] = generate_horizontal_image(final_text[:150])
                st.success(f"Erledigt mit Modell: {model_name}")

# --- ANZEIGE ---
if 'last_result' in st.session_state:
    st.divider()
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.session_state.get('last_image'):
            st.image(st.session_state['last_image'], caption="Format: 16:9 (Horizontal)")
    with col2:
        st.markdown(st.session_state['last_result'])
    
    st.download_button("📄 Word-Download", data=create_docx(st.session_state['last_result']), file_name="PJ_News.docx")
