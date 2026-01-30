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
    /* Sidebar Optimierung */
    [data-testid="stSidebar"] { border-right: 1px solid #e0e0e0; }
    </style>
    """, unsafe_allow_html=True)

# --- SESSION STATE & RESET LOGIK ---
if 'input_key' not in st.session_state:
    st.session_state['input_key'] = 0

def reset_app():
    """Erhöht den Key-Counter, was alle Inputs neu lädt (und leert)"""
    st.session_state['input_key'] += 1
    if 'res' in st.session_state: del st.session_state['res']
    if 'img' in st.session_state: del st.session_state['img']
    if 'og_img' in st.session_state: del st.session_state['og_img']

# --- HEADER ---
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.markdown("<h1 style='color: #24A27F; margin:0;'>pj</h1>", unsafe_allow_html=True)
with col_title:
    st.markdown("<h1 style='margin:0;'>Redaktions Tool</h1>", unsafe_allow_html=True)

# ==========================================
# SIDEBAR STRUKTUR
# ==========================================

st.sidebar.header("🔐 Login")
pw_input = st.sidebar.text_input("Passwort:", type="password")
if pw_input != st.secrets.get("TOOL_PASSWORD", "pj-redaktion-2026"):
    st.sidebar.warning("Bitte Passwort eingeben.")
    st.stop()

st.sidebar.markdown("---")

# 1. ERSTELLUNGS-MODUS
modus = st.sidebar.radio("Erstellungs-Modus:", [
    "Standard Online-News", 
    "Messe-Vorbericht (Special)",
    "LinkedIn Post (English)"
])

# 2. MESSE AUSWAHL (Nur aktiv bei Messe)
selected_messe = ""
m_link = ""
if modus == "Messe-Vorbericht (Special)":
    selected_messe = st.sidebar.selectbox("Welche Messe?", ["LogiMat", "interpack", "Fachpack", "SPS"])
    m_links = {
        "LogiMat": "https://www.logimat-messe.de/de/die-messe/ausstellerliste",
        "interpack": "https://www.interpack.de/de/Aussteller_Produkte/Ausstellerverzeichnis",
        "Fachpack": "https://www.fachpack.de/de/aussteller-produkte/ausstellerliste",
        "SPS": "https://sps.mesago.com/nuernberg/de/ausstellersuche.html"
    }
    m_link = m_links.get(selected_messe, "")

st.sidebar.markdown("---")

# 3. OPTIONEN & RESET
# Bild-Option ausblenden bei LinkedIn, da wir das Web-Bild nehmen
generate_img_flag = True
if modus != "LinkedIn Post (English)":
    generate_img_flag = st.sidebar.checkbox("KI-Beitragsbild generieren?", value=True)

st.sidebar.button("🗑️ ALLES LÖSCHEN / NEU", on_click=reset_app, type="secondary")

# 4. ARCHIV (GANZ UNTEN)
HISTORY_FILE = "news_history.csv"

def save_to_history(titel, inhalt_snippet):
    datum = datetime.now().strftime("%d.%m. %H:%M")
    if not titel or str(titel).lower() == 'nan': titel = "Unbekannter Titel"
    clean_titel = str(titel).replace(';', '').replace('\n', ' ').strip()
    clean_snippet = str(inhalt_snippet).replace(';', '').replace('\n', ' ').strip()
    
    new_entry = pd.DataFrame([{"Datum": datum, "Titel": clean_titel, "Snippet": clean_snippet}])
    
    if not os.path.isfile(HISTORY_FILE):
        new_entry.to_csv(HISTORY_FILE, index=False, sep=";")
    else:
        new_entry.to_csv(HISTORY_FILE, mode='a', header=False, index=False, sep=";")

st.sidebar.markdown("---")
st.sidebar.subheader("📚 Letzte Beiträge")

if os.path.isfile(HISTORY_FILE):
    try:
        df = pd.read_csv(HISTORY_FILE, sep=";", names=["Datum", "Titel", "Snippet"], dtype=str).fillna("")
        for i, row in df.tail(5).iloc[::-1].iterrows():
            display_title = row['Titel']
            if len(display_title) < 2: display_title = "Eintrag"
            with st.sidebar.expander(f"{display_title}"):
                st.caption(f"📅 {row['Datum']}")
                st.write(row['Snippet'])
    except Exception as e:
        st.sidebar.caption("Archiv wird neu aufgebaut...")
else:
    st.sidebar.caption("Noch keine Einträge.")


# ==========================================
# MAIN APP LOGIK
# ==========================================

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
            prompt=f"Professional industrial photography for packaging industry, theme: {topic}. High-end cinematic lighting, 16:9 horizontal, photorealistic, no text.",
            size="1792x1024", quality="standard", n=1
        )
        return response.data[0].url
    except: return None

def get_website_og_image(url):
    """Holt das Open Graph Bild von einer URL"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.content, 'html.parser')
        og_image = soup.find("meta", property="og:image")
        if og_image:
            return og_image["content"]
        else:
            return None
    except:
        return None

def create_docx(text_content):
    doc = Document()
    for line in text_content.split('\n'):
        if line.strip(): doc.add_paragraph(line)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()

def clean_text(text):
    if not text: return ""
    text = str(text).replace('**', '').replace('__', '')
    text = text.replace('### ', '').replace('## ', '').replace('# ', '')
    return text.strip()

# --- PROMPT LOGIK ---
base_rules = """
ROLLE: Fachjournalist:in des packaging journal.
TON: Journalistisch, sachlich, präzise, branchennah.
STILREGELN (STRICT):
- Kein PR-Fluff.
- Firmennamen normal schreiben.
- FORMATIERUNG: Antworte als REINER TEXT. KEINE Markdown-Zeichen wie #, ##, ### oder ** verwenden!
"""

# 1. LINKEDIN POST ENGLISH
if modus == "LinkedIn Post (English)":
    system_prompt = """
    ROLE: Social Media Manager for 'packaging journal'.
    TASK: Write a LinkedIn post in ENGLISH based on the provided content/URL.
    STYLE: Short, clear, professional but engaging. Use Emojis (📦, 🌍, 💡, etc.).
    STRUCTURE:
    1. Hook: One punchy sentence to grab attention.
    2. Key Points: 2-3 bullet points summarizing the most important facts (keep it brief).
    3. Call to Action: Use an arrow ➡️ or link 🔗 emoji followed immediately by the URL. Do NOT write "Read more".
    4. Hashtags: Always use #packaging plus 3-4 specific tags.
    
    IMPORTANT: 
    - Output ONLY the post text. 
    - Do NOT use markdown bolding (**).
    - If a specific company is mentioned, mention them (but without @ tagging, just text).
    """

# 2. MESSE VORBERICHT
elif modus == "Messe-Vorbericht (Special)":
    l_opt = st.radio("PRINT-Länge (gilt nur für Print-Version):", ["KURZ (ca. 900 Zeichen)", "NORMAL (ca. 1300 Zeichen)", "LANG (ca. 2000 Zeichen)"], horizontal=True)
    
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
    - Footer: Firmen-Website (Recherchieren oder aus Text) | Halle/Stand (nur wenn bekannt, sonst 'Halle ??, Stand ??').
    
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

# 3. STANDARD ONLINE NEWS
else:
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
    STRUKTUR: Titel (max 6 Worte), Anleser (max 300 Zeichen), Haupttext, Snippet (SEO).
    FORMAT-AUSGABE (Nutze exakt diese Trenner):
    [TITEL]...[ANLESER]...[TEXT]...[SNIPPET]...[KEYWORD]
    """

# --- INPUTS ---
current_key = st.session_state['input_key']

url_in = st.text_input("Link (URL):", key=f"url_{current_key}")
file_in = st.file_uploader("Datei:", type=["pdf", "docx", "txt"], key=f"file_{current_key}")
text_in = st.text_area("Oder Text einfügen:", height=150, key=f"text_{current_key}")

custom_focus = st.text_area("🔧 Individueller Fokus / Anweisung (optional):", 
                            placeholder="z.B. 'Fokus auf Nachhaltigkeit', 'Zielgruppe Startups'...", 
                            height=80, key=f"focus_{current_key}")

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
        with st.spinner("KI arbeitet..."):
            
            # 1. Bild holen, falls URL und LinkedIn Modus
            if modus == "LinkedIn Post (English)" and url_in:
                og_link = get_website_og_image(url_in)
                if og_link: st.session_state['og_img'] = og_link
            
            # 2. Text generieren
            model_name = get_best_google_model()
            if model_name:
                model = genai.GenerativeModel(model_name)
                
                full_input = f"{system_prompt}"
                if custom_focus:
                    full_input += f"\n\nZUSATZ-ANWEISUNG: {custom_focus}"
                if modus == "LinkedIn Post (English)" and url_in:
                    full_input += f"\n\nLINK TO ARTICLE: {url_in}"
                
                full_input += f"\n\nQUELLMATERIAL:\n{final_text}"
                
                response = model.generate_content(full_input)
                st.session_state['res'] = response.text
                
                # Bild generieren (nur wenn nicht LinkedIn Modus, dort nehmen wir Web-Bild)
                if generate_img_flag and modus != "LinkedIn Post (English)":
                    st.session_state['img'] = generate_horizontal_image(final_text[:200])
                else:
                    st.session_state['img'] = None

# --- AUSGABE & PARSING ---
if 'res' in st.session_state:
    res = st.session_state['res']
    
    # 1. LINKEDIN POST
    if modus == "LinkedIn Post (English)":
        st.subheader("LinkedIn Post (English)")
        
        # Zeige das Bild der Website, falls gefunden
        if 'og_img' in st.session_state:
            st.image(st.session_state['og_img'], caption=f"Vorschau-Bild von: {url_in}", width=600)
        
        st.code(res, language=None)
        st.caption("Einfach oben rechts kopieren und bei LinkedIn einfügen.")
        
        save_to_history("LinkedIn Post", res[:50] + "...")

    # 2. MESSE VORBERICHT
    elif modus == "Messe-Vorbericht (Special)":
        try:
            # Print
            if '[P_OBERZEILE]' in res:
                p_ober = clean_text(res.split('[P_OBERZEILE]')[1].split('[P_HEADLINE]')[0])
                p_head = clean_text(res.split('[P_HEADLINE]')[1].split('[P_TEXT]')[0])
                p_text = clean_text(res.split('[P_TEXT]')[1].split('[P_WEB]')[0])
                p_web  = clean_text(res.split('[P_WEB]')[1].split('[P_STAND]')[0])
                p_stand= clean_text(res.split('[P_STAND]')[1].split('[O_HEADLINE]')[0])
                
                save_to_history(f"{p_ober}: {p_head}", p_text[:50]+"...")
            else:
                p_ober, p_head, p_text, p_web, p_stand = "???", "Fehler", res, "???", "???"

            # Online
            if '[O_HEADLINE]' in res:
                part_online = res.split('[O_HEADLINE]')[1]
                o_head = clean_text(part_online.split('[O_ANLESER]')[0])
                o_anle = clean_text(part_online.split('[O_ANLESER]')[1].split('[O_TEXT]')[0])
                o_text = clean_text(part_online.split('[O_TEXT]')[1].split('[O_STAND]')[0])
                o_stand= clean_text(part_online.split('[O_STAND]')[1].split('[O_KEYWORD]')[0])
                o_key  = clean_text(part_online.split('[O_KEYWORD]')[1].split('[O_DESC]')[0])
                o_desc = clean_text(part_online.split('[O_DESC]')[1].split('[O_TAGS]')[0])
                o_tags = clean_text(part_online.split('[O_TAGS]')[1])
            else:
                o_head, o_anle, o_text = "Fehler", "Fehler", res

            tab_p, tab_o = st.tabs(["📟 PRINT VERSION", "🌐 ONLINE VERSION"])
            
            with tab_p:
                full_print_doc = f"{p_ober}\n\n{p_head}\n\n{p_text}\n\n{p_web}\n{p_stand}"
                st.subheader("Vorschau Print")
                st.text(full_print_doc)
                st.subheader("Kopieren")
                st.code(full_print_doc, language=None)
                st.download_button("📄 Word-Export (Print)", data=create_docx(full_print_doc), file_name="PJ_Print_Beitrag.docx")

            with tab_o:
                if st.session_state.get('img'):
                    st.image(st.session_state['img'], caption="Beitragsbild (16:9)", width=800)
                
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("### 📝 Inhalt")
                    st.caption("Titel")
                    st.code(o_head, language=None)
                    st.caption("Anleser")
                    st.code(o_anle, language=None)
                    st.caption("Haupttext")
                    st.code(o_text, language=None)
                    st.caption("Standinfo")
                    st.code(o_stand, language=None)
                with c2:
                    st.markdown("### 🔍 SEO")
                    st.caption("Keyword")
                    st.code(o_key, language=None)
                    st.caption("Description")
                    st.code(o_desc, language=None)
                    st.caption("Tags")
                    st.code(o_tags, language=None)

        except Exception as e:
            st.error("Fehler beim Verarbeiten.")
            st.write(res)

    # 3. STANDARD NEWS
    else:
        try:
            if '[TITEL]' in res:
                tit = clean_text(res.split('[TITEL]')[1].split('[ANLESER]')[0])
                anl = clean_text(res.split('[ANLESER]')[1].split('[TEXT]')[0])
                txt = clean_text(res.split('[TEXT]')[1].split('[SNIPPET]')[0])
                sni = clean_text(res.split('[SNIPPET]')[1].split('[KEYWORD]')[0])
                key = clean_text(res.split('[KEYWORD]')[1])
                
                save_to_history(f"News: {tit}", anl[:50]+"...")
            else:
                tit, anl, txt, sni, key = "Fehler", "Fehler", res, "Fehler", "Fehler"
            
            if st.session_state.get('img'):
                st.image(st.session_state['img'], caption="Beitragsbild (16:9)", width=800)
            
            c1, c2 = st.columns([2, 1])
            with c1:
                st.subheader("Inhalt")
                st.caption("Titel")
                st.code(tit, language=None)
                st.caption("Anleser")
                st.code(anl, language=None)
                st.caption("Text")
                st.code(txt, language=None)
            with c2:
                st.subheader("SEO")
                st.caption("Keyword")
                st.code(key, language=None)
                st.caption("Snippet")
                st.code(sni, language=None)
                
            full_doc = f"{tit}\n\n{anl}\n\n{txt}"
            st.download_button("📄 Word-Export", data=create_docx(full_doc), file_name="PJ_Online_News.docx")

        except Exception as e:
            st.error("Fehler beim Verarbeiten.")
            st.write(res)
