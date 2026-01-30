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

# --- BRANDING & FARBEN ---
st.set_page_config(page_title="packaging journal Redaktions Tool", page_icon="🚀", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    .stButton>button { 
        width: 100%; border-radius: 8px; height: 3.5em; 
        background-color: #24A27F !important; color: white !important; 
        font-weight: bold; border: none;
    }
    .stCode { border: 1px solid #24A27F !important; border-radius: 5px; background-color: #ffffff !important; }
    h3 { color: #24A27F; margin-top: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- HEADER ---
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.markdown("<h1 style='color: #24A27F; margin:0;'>pj</h1>", unsafe_allow_html=True)
with col_title:
    st.markdown("<h1 style='margin:0;'>Redaktions Tool</h1>", unsafe_allow_html=True)

# --- SIDEBAR ---
st.sidebar.header("🔐 Login")
pw_input = st.sidebar.text_input("Passwort:", type="password")
if pw_input != st.secrets.get("TOOL_PASSWORD", "pj-redaktion-2026"):
    st.sidebar.warning("Bitte Passwort eingeben.")
    st.stop()

modus = st.sidebar.radio("Erstellungs-Modus:", ["Standard Online-News", "Messe-Vorbericht (Special)"])
generate_img_flag = st.sidebar.checkbox("KI-Beitragsbild generieren?", value=True)

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
        # Festgelegtes horizontales Format (16:9) gemäß deinem Wunsch
        response = client.images.generate(
            model="dall-e-3",
            prompt=f"Professional industrial photography for packaging industry, theme: {topic}. High-end cinematic lighting, 16:9 horizontal, photorealistic, no text.",
            size="1792x1024", quality="standard", n=1
        )
        return response.data[0].url
    except: return None

def create_docx(text):
    doc = Document()
    for line in text.split('\n'):
        if line.strip(): doc.add_paragraph(line)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- PROMPT LOGIK ---
base_constraints = """
WICHTIGE REDAKTIONELLE REGELN:
- KEIN Markdown verwenden (KEINE **, KEINE #, KEINE _). Reintext!
- KEINE Ortsmarke, KEIN Datum am Anfang.
- KEIN 'Über Firma XY' oder Hintergrund-Unternehmensprofile.
- KEIN PR-Sprech wie 'Besuchen Sie uns', 'Wir freuen uns'. Journalistisch neutral bleiben.
- Einstiege VARIATION: Nicht mit 'Firma XY präsentiert' starten. Nutze Problemstellungen, Use Cases oder Trends.
- Firmennamen normal (nicht VERSAL).
"""

if modus == "Messe-Vorbericht (Special)":
    selected_messe = st.sidebar.selectbox("Messe:", ["LogiMat", "interpack", "Fachpack", "SPS"])
    l_opt = st.radio("Print-Länge (Strikt einhalten):", ["KURZ (~900)", "NORMAL (~1300)", "LANG (~2000)"], horizontal=True)
    m_links = {"LogiMat": "https://www.logimat-messe.de/de/die-messe/ausstellerliste", "interpack": "https://www.interpack.de/de/Aussteller_Produkte/Ausstellerverzeichnis", "Fachpack": "https://www.fachpack.de/de/aussteller-produkte/ausstellerliste", "SPS": "https://sps.mesago.com/nuernberg/de/ausstellersuche.html"}
    m_link = m_links.get(selected_messe, "")
    target_len = l_opt.split("~")[1].replace(")", "")

    system_prompt = f"""
    Rolle: Fachredakteur:in beim packaging journal.
    {base_constraints}
    
    AUFGABE: Erstelle zwei Versionen für {selected_messe}. 
    
    1. PRINT: 
    - Länge: EXAKT ca. {target_len} Zeichen. 
    - Struktur: Oberzeile (Firma), Headline, Text (SOFORTIGER EINSTIEG OHNE ANLESER), Website ({m_link}), Halle/Standnummer.
    
    2. ONLINE: 
    - Länge: 2500-5000 Zeichen.
    - Struktur: Headline, Anleser (MAX 300 Zeichen), Haupttext mit H2-Zwischenüberschriften (ohne #), Halle/Standnummer, SEO-Snippet (max 160).
    
    FORMAT-VORGABE:
    [PRINT_TITEL]...[PRINT_TEXT]...[PRINT_STAND]
    [ONLINE_TITEL]...[ONLINE_ANLESER]...[ONLINE_TEXT]...[ONLINE_SNIPPET]
    """
else:
    l_opt = st.radio("Länge:", ["Kurz (~1200)", "Normal (~2500)", "Lang (~5000)"], horizontal=True)
    system_prompt = f"Erstelle eine Standard-News. {base_constraints} Headline, Anleser (MAX 300 Zeichen), Text, Snippet. Länge: {l_opt}."

# --- INPUTS ---
url_in = st.text_input("Link (URL):")
file_in = st.file_uploader("Datei:", type=["pdf", "docx", "txt"])
text_in = st.text_area("Oder Text einfügen:")

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
    else: final_text = docx2txt.process(file_in)
else: final_text = text_in

# --- GENERIERUNG ---
if st.button("✨ JETZT GENERIEREN", type="primary"):
    if len(final_text) < 20:
        st.warning("Bitte Material bereitstellen.")
    else:
        with st.spinner("KI erstellt Inhalte..."):
            model_name = get_best_google_model()
            if model_name:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(f"{system_prompt}\n\nMATERIAL: {final_text}")
                st.session_state['res'] = response.text
                if generate_img_flag:
                    st.session_state['img'] = generate_horizontal_image(final_text[:200])

# --- AUSGABE ---
if 'res' in st.session_state:
    res = st.session_state['res']
    
    tab_p, tab_o = st.tabs(["📟 PRINT VERSION", "🌐 ONLINE (WordPress)"])
    
    with tab_p:
        try:
            p_titel = res.split('[PRINT_TITEL]')[1].split('[PRINT_TEXT]')[0].replace('*', '').strip()
            p_text = res.split('[PRINT_TEXT]')[1].split('[PRINT_STAND]')[0].replace('*', '').strip()
            p_stand = res.split('[PRINT_STAND]')[1].replace('*', '').strip()
            
            full_print = f"{p_titel}\n\n{p_text}\n\n{p_stand}"
            st.subheader("Kopier-Box (Nur Text)")
            st.code(full_print, language=None)
            st.download_button("📄 Word-Export (Nur Print)", data=create_docx(full_print), file_name="PJ_Print_Beitrag.docx")
        except:
            st.code(res.replace('*', ''), language=None)

    with tab_o:
        try:
            o_titel = res.split('[ONLINE_TITEL]')[1].split('[ONLINE_ANLESER]')[0].replace('*', '').strip()
            o_anleser = res.split('[ONLINE_ANLESER]')[1].split('[ONLINE_TEXT]')[0].replace('*', '').strip()
            o_text = res.split('[ONLINE_TEXT]')[1].split('[ONLINE_SNIPPET]')[0].replace('*', '').strip()
            o_snippet = res.split('[ONLINE_SNIPPET]')[1].replace('*', '').strip()

            if st.session_state.get('img'):
                st.image(st.session_state['img'], caption="Horizontales Beitragsbild (16:9)", width=800)
            
            st.subheader("📌 WordPress Titel")
            st.code(o_titel, language=None)
            st.subheader("📰 Anleser / Teaser (max 300 Zeichen)")
            st.code(o_anleser, language=None)
            st.subheader("✍️ Haupttext")
            st.code(o_text, language=None)
            st.subheader("🔍 Google Snippet")
            st.code(o_snippet, language=None)
        except:
            st.code(res.replace('*', ''), language=None)
