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
    div[data-baseweb="tab-list"] button[aria-selected="true"] {
        background-color: #24A27F !important;
        color: white !important;
    }
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
        # Festgelegtes horizontales Format (16:9)
        response = client.images.generate(
            model="dall-e-3",
            prompt=f"Professional industrial photography for packaging industry, theme: {topic}. High-end cinematic lighting, 16:9 horizontal, photorealistic, no text.",
            size="1792x1024", quality="standard", n=1
        )
        return response.data[0].url
    except: return None

def create_docx(text_content):
    doc = Document()
    for line in text_content.split('\n'):
        if line.strip(): doc.add_paragraph(line)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

def clean_text(text):
    """Entfernt Markdown-Sterne und Raute-Zeichen (###) für sauberes Kopieren"""
    if not text: return ""
    # Entferne Markdown Fettdruck
    text = text.replace('**', '').replace('__', '')
    # Entferne Markdown Überschriften
    text = text.replace('### ', '').replace('## ', '').replace('# ', '')
    return text.strip()

# --- PROMPT LOGIK ---

# Gemeinsame Basis-Regeln aus dem Masterprompt
base_rules = """
ROLLE: Fachjournalist:in des packaging journal.
ZIELGRUPPE: Entscheider, Ingenieure, Planer.
TON: Journalistisch, sachlich, präzise, branchennah. KEINE Werbung, KEIN PR-Sprech.
STILREGELN (STRICT):
- Kein PR-Fluff: Streiche unbelegte Superlative.
- Firmennamen normal schreiben (keine Versalien).
- Rechtsformen (GmbH/AG) entfernen.
- Keine Marken-Symbole (R/TM).
- Keine Sätze wie 'Besuchen Sie uns' oder 'Wir freuen uns'.
- KEIN 'Über Firma XY'-Block am Ende.
- KEIN Datum und KEINE Ortsmarke am Anfang.
- Einstiege VARIIEREN (Use Case, Trend, Engpass...). Nicht immer 'Firma XY präsentiert'.
- FORMATIERUNG: Antworte als REINER TEXT. KEINE Markdown-Zeichen wie #, ##, ### oder ** verwenden!
"""

if modus == "Messe-Vorbericht (Special)":
    selected_messe = st.sidebar.selectbox("Messe:", ["LogiMat", "interpack", "Fachpack", "SPS"])
    # Neue Print-Längen Definition
    l_opt = st.radio("PRINT-Länge (gilt nur für Print-Version):", ["KURZ (ca. 900 Zeichen)", "NORMAL (ca. 1300 Zeichen)", "LANG (ca. 2000 Zeichen)"], horizontal=True)
    
    # Extrahiere Ziel-Zeichenzahl für Print
    target_print_len = "900"
    if "1300" in l_opt: target_print_len = "1300"
    if "2000" in l_opt: target_print_len = "2000"

    system_prompt = f"""
    {base_rules}
    AUFGABE: Erstelle zwei Versionen für ein {selected_messe}-Special.
    
    --- TEIL 1: PRINT-VERSION ---
    VORGABE: Exakt ca. {target_print_len} Zeichen.
    STRUKTUR:
    - Oberzeile: [Firma]
    - Headline: [Max 6 Wörter, prägnant]
    - Text: SOFORTIGER EINSTIEG ins Thema. KEIN Anleser.
    - Footer: Firmen-Website (Recherchieren oder aus Text. Falls unbekannt '???') | Halle/Stand (nur wenn bekannt, sonst 'Halle ??, Stand ??').
    
    --- TEIL 2: ONLINE-VERSION ---
    VORGABE: Standardlänge 2500-5000 Zeichen.
    STRUKTUR:
    - Headline: [Max 6 Wörter]
    - Anleser: [Max 300 Zeichen, 2-3 Sätze]
    - Text: [Mit Zwischenüberschriften als normale Zeile ohne #, journalistisch tiefgehend]
    - Footer: Halle/Stand.
    - SEO: Fokus-Keyword, Meta Description (max 160), Tags.

    FORMAT-AUSGABE (Nutze exakt diese Trenner):
    [P_OBERZEILE]...[P_HEADLINE]...[P_TEXT]...[P_WEB]...[P_STAND]
    [O_HEADLINE]...[O_ANLESER]...[O_TEXT]...[O_STAND]...[O_KEYWORD]...[O_DESC]...[O_TAGS]
    """

else: # Standard Online-News
    # Neue Längen-Definitionen für Online-News
    l_opt = st.radio("Länge:", [
        "KURZ (2.000–4.000 Zeichen)", 
        "NORMAL (6.000–9.000 Zeichen)", 
        "LANG (12.000–15.000 Zeichen)"
    ], horizontal=True)
    
    len_instruction = "2000-4000 Zeichen"
    if "NORMAL" in l_opt: len_instruction = "6000-9000 Zeichen, nutze Zwischenüberschriften (ohne #)"
    if "LANG" in l_opt: len_instruction = "12000-15000 Zeichen, nutze Zwischenüberschriften (ohne #)"

    system_prompt = f"""
    {base_rules}
    AUFGABE: Erstelle eine Fach-News für Online.
    LÄNGE: {len_instruction}.
    
    STRUKTUR:
    1. Titel: Max 6 Wörter, sachlich, kein Clickbait.
    2. Anleser: Max 300 Zeichen, neutral.
    3. Haupttext: Fließtext, journalistisch, keine PR. Zwischenüberschriften als normale Textzeile schreiben.
    4. SEO: Snippet (max 160 Zeichen), Fokus-Keyword.
    
    FORMAT-AUSGABE (Nutze exakt diese Trenner):
    [TITEL]...[ANLESER]...[TEXT]...[SNIPPET]...[KEYWORD]
    """

# --- INPUTS ---
url_in = st.text_input("Link (URL):")
file_in = st.file_uploader("Datei:", type=["pdf", "docx", "txt"])
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
    else: final_text = docx2txt.process(file_in)
else: final_text = text_in

# --- GENERIERUNG ---
if st.button("✨ INHALTE GENERIEREN", type="primary"):
    if len(final_text) < 20:
        st.warning("Bitte Material bereitstellen.")
    else:
        with st.spinner("KI arbeitet nach Masterprompt..."):
            model_name = get_best_google_model()
            if model_name:
                model = genai.GenerativeModel(model_name)
                # Wir geben der KI den Prompt + das Material
                full_input = f"{system_prompt}\n\nQUELLMATERIAL:\n{final_text}"
                response = model.generate_content(full_input)
                st.session_state['res'] = response.text
                
                # Bild generieren (nur bei Online News oder wenn gewünscht auch bei Messe)
                if generate_img_flag:
                    st.session_state['img'] = generate_horizontal_image(final_text[:200])
                else:
                    st.session_state['img'] = None

# --- AUSGABE LOGIK ---
if 'res' in st.session_state:
    res = st.session_state['res']
    
    # MESSE VORBERICHT AUSGABE
    if modus == "Messe-Vorbericht (Special)":
        tab_p, tab_o = st.tabs(["📟 PRINT VERSION", "🌐 ONLINE VERSION"])
        
        with tab_p:
            try:
                # Parsing Print
                p_ober = res.split('[P_OBERZEILE]')[1].split('[P_HEADLINE]')[0]
                p_head = res.split('[P_HEADLINE]')[1].split('[P_TEXT]')[0]
                p_text = res.split('[P_TEXT]')[1].split('[P_WEB]')[0]
                p_web  = res.split('[P_WEB]')[1].split('[P_STAND]')[0]
                p_stand= res.split('[P_STAND]')[1].split('[O_HEADLINE]')[0] # Stoppt vor Online Teil

                # Bereinigen
                p_ober = clean_text(p_ober)
                p_head = clean_text(p_head)
                p_text = clean_text(p_text)
                p_web  = clean_text(p_web)
                p_stand= clean_text(p_stand)
                
                full_print_doc = f"{p_ober}\n\n{p_head}\n\n{p_text}\n\n{p_web}\n{p_stand}"
                
                st.subheader("Vorschau Print")
                st.text(full_print_doc) # Einfache Textanzeige zur Kontrolle
                
                st.subheader("Kopieren & Export")
                st.code(full_print_doc, language=None)
                st.download_button("📄 Word-Export (Nur Print)", data=create_docx(full_print_doc), file_name="PJ_Print_Beitrag.docx")
            except Exception as e:
                st.error("Formatierung nicht erkannt. Rohausgabe:")
                st.write(res)

        with tab_o:
            try:
                # Parsing Online
                # Suche ab dem Online Teil, falls Print Tags stören
                part_online = res.split('[O_HEADLINE]')[1]
                
                o_head = part_online.split('[O_ANLESER]')[0]
                o_anle = part_online.split('[O_ANLESER]')[1].split('[O_TEXT]')[0]
                o_text = part_online.split('[O_TEXT]')[1].split('[O_STAND]')[0]
                o_stand= part_online.split('[O_STAND]')[1].split('[O_KEYWORD]')[0]
                o_key  = part_online.split('[O_KEYWORD]')[1].split('[O_DESC]')[0]
                o_desc = part_online.split('[O_DESC]')[1].split('[O_TAGS]')[0]
                o_tags = part_online.split('[O_TAGS]')[1]

                # Bereinigen
                o_head = clean_text(o_head)
                o_anle = clean_text(o_anle)
                o_text = clean_text(o_text)
                o_stand= clean_text(o_stand)
                o_key  = clean_text(o_key)
                o_desc = clean_text(o_desc)
                o_tags = clean_text(o_tags)

                if st.session_state.get('img'):
                    st.image(st.session_state['img'], caption="Beitragsbild (16:9)", width=800)
                
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("### 📝 Inhalt")
                    st.caption("Titel (max 6 Wörter)")
                    st.code(o_head, language=None)
                    st.caption("Anleser (max 300 Zeichen)")
                    st.code(o_anle, language=None)
                    st.caption("Haupttext (Clean, ohne ###)")
                    st.code(o_text, language=None)
                    st.caption("Standinfo")
                    st.code(o_stand, language=None)
                
                with c2:
                    st.markdown("### 🔍 SEO Box")
                    st.caption("Fokus Keyword")
                    st.code(o_key, language=None)
                    st.caption("Meta Description (max 160)")
                    st.code(o_desc, language=None)
                    st.caption("Tags")
                    st.code(o_tags, language=None)

            except Exception as e:
                st.write(res) # Fallback

    # STANDARD ONLINE NEWS AUSGABE
    else:
        try:
            # Parsing
            tit = res.split('[TITEL]')[1].split('[ANLESER]')[0]
            anl = res.split('[ANLESER]')[1].split('[TEXT]')[0]
            txt = res.split('[TEXT]')[1].split('[SNIPPET]')[0]
            sni = res.split('[SNIPPET]')[1].split('[KEYWORD]')[0]
            key = res.split('[KEYWORD]')[1]

            # Bereinigen
            tit = clean_text(tit)
            anl = clean_text(anl)
            txt = clean_text(txt)
            sni = clean_text(sni)
            key = clean_text(key)
            
            if st.session_state.get('img'):
                st.image(st.session_state['img'], caption="Beitragsbild (16:9)", width=800)
            
            c1, c2 = st.columns([2, 1])
            with c1:
                st.subheader("Inhalt")
                st.caption("Titel")
                st.code(tit, language=None)
                st.caption("Anleser")
                st.code(anl, language=None)
                st.caption("Text (Clean, ohne ###)")
                st.code(txt, language=None)
            
            with c2:
                st.subheader("SEO")
                st.caption("Fokus Keyword")
                st.code(key, language=None)
                st.caption("Snippet")
                st.code(sni, language=None)
                
            full_doc = f"{tit}\n\n{anl}\n\n{txt}"
            st.download_button("📄 Word-Export", data=create_docx(full_doc), file_name="PJ_Online_News.docx")

        except Exception as e:
            st.error("Konnte Struktur nicht parsen. Rohdaten:")
            st.write(res)
