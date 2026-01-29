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

# Custom CSS für Corporate Design
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

def generate_visual(topic):
    """Generiert ein horizontales Bild via OpenAI DALL-E 3"""
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        response = client.images.generate(
            model="dall-e-3",
            prompt=f"Professional high-end photography for the packaging industry, theme: {topic}. Cinematic lighting, 8k, horizontal wide angle, photorealistic, no text.",
            size="1792x1024", 
            quality="standard",
            n=1
        )
        return response.data[0].url
    except Exception as e:
        st.error(f"Bildfehler: {e}")
        return None

# --- HAUPTBEREICH ---
st.title("🚀 packaging journal Redaktions Tool")

if modus == "Standard Online-News":
    l_opt = st.radio("Artikellänge:", ["Kurz (~1.200)", "Normal (~2.500)", "Lang (~5.000)"], horizontal=True)
    system_prompt = f"Du bist Redakteur beim packaging journal. Erstelle eine Online-News. Titel max 6 Wörter, Keyword 1 Wort. Sachlich, kein PR-Fluff. Länge: {l_opt}."
else:
    selected_messe = st.sidebar.selectbox("Messe wählen:", ["LogiMat", "interpack", "Fachpack", "SPS"])
    l_opt = st.radio("Print-Länge:", ["KURZ (900)", "NORMAL (1300)", "LANG (2000)"], horizontal=True)
    m_links = {
        "LogiMat": "https://www.logimat-messe.de/de/die-messe/ausstellerliste",
        "interpack": "https://www.interpack.de/de/Aussteller_Produkte/Ausstellerverzeichnis",
        "Fachpack": "https://www.fachpack.de/de/aussteller-produkte/ausstellerliste",
        "SPS": "https://sps.mesago.com/nuernberg/de/ausstellersuche.html"
    }
    m_link = m_links.get(selected_messe, "")
    p_len = l_opt.split(" ")[0]
    system_prompt = f"Erstelle Print (ca. {p_len} Zeichen) & Online Vorbericht (2500-5000 Zeichen) für {selected_messe}. Titel max 6 Wörter. Standinfo verlinken auf {m_link}. Sachlich bleiben."

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
    except: st.error("Fehler beim Laden der URL")
elif file_in:
    if file_in.type == "application/pdf":
        pdf = PyPDF2.PdfReader(file_in)
        final_text = " ".join([p.extract_text() for p in pdf.pages])
    elif file_in.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        final_text = docx2txt.process(file_in)
    else: final_text = file_in.read().decode("utf-8")
else: final_text = text_in

# --- GENERIERUNG ---
if st.button(f"✨ {modus.upper()} JETZT GENERIEREN", type="primary"):
    if len(final_text) < 20:
        st.warning("Bitte Material bereitstellen.")
    else:
        try:
            with st.spinner("KI generiert Text und Bild..."):
                # 1. Text Generierung (Google Gemini) mit Fallback-Logik gegen 404
                genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
                
                success = False
                # Teste verschiedene Modell-Namen
                for model_name in ["gemini-1.5-flash", "gemini-pro", "models/gemini-1.5-flash"]:
                    try:
                        model = genai.GenerativeModel(model_name, system_instruction=system_prompt)
                        response = model.generate_content(final_text)
                        st.session_state['last_result'] = response.text
                        success = True
                        break
                    except:
                        continue
                
                if not success:
                    st.error("Google API Modell-Fehler. Bitte API-Key oder Modell-Verfügbarkeit prüfen.")
                else:
                    # 2. Bild Generierung (OpenAI DALL-E 3)
                    img_url = generate_visual(final_text[:200]) 
                    st.session_state['last_image'] = img_url
                    st.success("Text und horizontales Bild wurden erstellt!")

        except Exception as e:
            st.error(f"Kritischer Fehler: {e}")

# --- ANZEIGE & EXPORT ---
if 'last_result' in st.session_state:
    st.divider()
    
    col_img, col_txt = st.columns([1, 1])
    
    with col_img:
        st.markdown("### 🖼️ Beitragsbild (Horizontal 16:9)")
        if st.session_state.get('last_image'):
            st.image(st.session_state['last_image'], use_container_width=True)
        else:
            st.info("Bild wird generiert oder konnte nicht geladen werden.")
            
    with col_txt:
        st.markdown("### 📝 Generierter Text")
        st.markdown(st.session_state['last_result'])
    
    st.divider()
    st.markdown("### 📥 Export")
    st.download_button(
        label="📄 Word-Download (.docx)", 
        data=create_docx(st.session_state['last_result']), 
        file_name="PJ_Beitrag.docx"
    )
