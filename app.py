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
    [data-testid="stSidebar"] { border-right: 1px solid #e0e0e0; }
    </style>
    """, unsafe_allow_html=True)

# --- SESSION STATE ---
if 'input_key' not in st.session_state: st.session_state['input_key'] = 0

def reset_app():
    st.session_state['input_key'] += 1
    keys_to_clear = ['res', 'img', 'og_img']
    for k in keys_to_clear:
        if k in st.session_state: del st.session_state[k]

# --- HILFSFUNKTIONEN ---

def get_google_model():
    """Sucht automatisch das beste verfügbare Modell, um 404-Fehler zu vermeiden."""
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        
        # 1. Liste aller Modelle abrufen, die Content generieren können
        all_models = [m for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        model_names = [m.name for m in all_models]
        
        # 2. Prioritätenliste (Wir suchen erst nach Flash, dann Pro)
        preferences = [
            "models/gemini-1.5-flash",
            "models/gemini-1.5-flash-latest",
            "models/gemini-1.5-flash-001",
            "models/gemini-1.5-pro",
            "models/gemini-1.5-pro-latest",
            "models/gemini-pro"
        ]
        
        selected_model = None
        
        # Prüfen, ob einer der Favoriten verfügbar ist
        for p in preferences:
            if p in model_names:
                selected_model = p
                break
        
        # Fallback: Wenn keiner der Favoriten da ist, nimm das erste verfügbare Modell
        if not selected_model and model_names:
            selected_model = model_names[0]
            
        if selected_model:
            # st.success(f"Nutze Modell: {selected_model}") # Optional: Anzeigen welches Modell läuft
            return genai.GenerativeModel(selected_model)
        else:
            st.error("Kritischer Fehler: Keine Google AI Modelle in diesem Account gefunden.")
            return None

    except Exception as e:
        st.error(f"Fehler bei der Modell-Auswahl: {e}")
        return None

def generate_horizontal_image(topic):
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        res = client.images.generate(
            model="dall-e-3", 
            prompt=f"Industrial photography, packaging industry theme: {topic}. High-end cinematic lighting, 16:9 horizontal, no text.", 
            size="1792x1024", quality="standard", n=1
        )
        return res.data[0].url
    except: return None

def get_website_og_image(url):
    """Holt das Vorschaubild robust. Bei Fehler gibt es None zurück (kein Absturz)."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            soup = BeautifulSoup(r.content, 'html.parser')
            og = soup.find("meta", property="og:image")
            if not og: og = soup.find("meta", attrs={"name": "og:image"})
            if og and "content" in og.attrs: return og["content"]
        return None
    except: return None

def create_docx(txt):
    d = Document()
    if txt:
        for line in str(txt).split('\n'):
            if line.strip(): d.add_paragraph(line)
    b = BytesIO()
    d.save(b)
    return b.getvalue()

def clean_text(t):
    if not t: return ""
    return str(t).replace('**','').replace('__','').replace('### ','').replace('## ','').strip()

# --- HEADER ---
col_logo, col_title = st.columns([1, 5])
with col_logo: st.markdown("<h1 style='color: #24A27F; margin:0;'>pj</h1>", unsafe_allow_html=True)
with col_title: st.markdown("<h1 style='margin:0;'>Redaktions Tool</h1>", unsafe_allow_html=True)

# ================= SIDEBAR =================
st.sidebar.header("🔐 Login")
pw_input = st.sidebar.text_input("Passwort:", type="password")
if pw_input != st.secrets.get("TOOL_PASSWORD", "pj-redaktion-2026"):
    st.sidebar.warning("Bitte Passwort eingeben.")
    st.stop()

st.sidebar.markdown("---")

# MODUS WAHL
modus = st.sidebar.radio("Erstellungs-Modus:", [
    "Standard Online-News", 
    "Messe-Vorbericht (Special)", 
    "LinkedIn Post (English)", 
    "Social Media (Deutsch)"
])

# MESSE OPTIONS
selected_messe = ""
m_link = ""
if modus == "Messe-Vorbericht (Special)":
    selected_messe = st.sidebar.selectbox("Messe:", ["LogiMat", "interpack", "Fachpack", "SPS"])
    m_links = {
        "LogiMat": "https://www.logimat-messe.de/de/die-messe/ausstellerliste", 
        "interpack": "https://www.interpack.de/de/Aussteller_Produkte/Ausstellerverzeichnis", 
        "Fachpack": "https://www.fachpack.de/de/aussteller-produkte/ausstellerliste", 
        "SPS": "https://sps.mesago.com/nuernberg/de/ausstellersuche.html"
    }
    m_link = m_links.get(selected_messe, "")

st.sidebar.markdown("---")

# OPTIONEN
generate_img_flag = True
if "Social" in modus or "LinkedIn" in modus:
    generate_img_flag = False
else:
    generate_img_flag = st.sidebar.checkbox("KI-Beitragsbild generieren?", value=True)

st.sidebar.button("🗑️ ALLES NEU / RESET", on_click=reset_app, type="secondary")

# ARCHIV
HISTORY_FILE = "news_history.csv"
def save_to_history(titel, snippet):
    d = datetime.now().strftime("%d.%m. %H:%M")
    t = str(titel).replace(';', '').strip() if titel else "Unbekannt"
    s = str(snippet).replace(';', '').strip()
    entry = pd.DataFrame([{"Datum": d, "Titel": t, "Snippet": s}])
    if not os.path.isfile(HISTORY_FILE): entry.to_csv(HISTORY_FILE, index=False, sep=";")
    else: entry.to_csv(HISTORY_FILE, mode='a', header=False, index=False, sep=";")

st.sidebar.markdown("---")
if os.path.isfile(HISTORY_FILE):
    with st.sidebar.expander("📚 Verlauf"):
        try:
            df = pd.read_csv(HISTORY_FILE, sep=";", names=["Datum","Titel","Snippet"], dtype=str).fillna("")
            for i, r in df.tail(5).iloc[::-1].iterrows():
                st.caption(f"{r['Datum']}: {r['Titel']}")
        except: pass

# ================= MAIN AREA =================

# --- PROMPT LOGIK ---
anti_pr_rules = """
STRIKTE REGELN FÜR NEUTRALITÄT (Verstoß = Fehler):
1. PERSPEKTIVE: Schreibe ausschließlich in der 3. Person ("Das Unternehmen", "Die Maschine"). 
2. VERBOTENE WÖRTER (Direkte Ansprache): "Sie", "Ihre", "Ihr", "Du", "Wir", "Uns". Diese Wörter dürfen im Text NICHT vorkommen.
3. VERBOTENE IMPERATIVE (Aufforderungen): "Besuchen Sie", "Kommen Sie", "Schauen Sie", "Erleben Sie", "Überzeugen Sie sich", "Entdecken Sie".
4. ERSATZ-REGEL: Wenn im Quelltext steht "Besuchen Sie uns in Halle 3", schreibe stattdessen "Das Exponat befindet sich in Halle 3" oder "Der Aussteller ist in Halle 3 zu finden".
5. KEINE WERTUNG: Entferne Wörter wie "stolz", "leidenschaftlich", "einzigartig", "wir freuen uns".
6. START-VERBOT: Beginne NIEMALS mit dem Messenamen oder "Auf der Messe XY zeigt...".
"""

base_rules = f"""
ROLLE: Fachjournalist für das 'packaging journal'. 
TON: Nüchtern, faktisch, technisch, distanziert.
FORMAT: REINER TEXT, KEIN MARKDOWN (keine **Fettung**).
{anti_pr_rules}
"""

if modus == "LinkedIn Post (English)":
    system_prompt = """
    ROLE: Social Media Manager 'packaging journal'. TASK: LinkedIn post in ENGLISH.
    STYLE: Short, engaging, Emojis. STRUCTURE: Hook, 2-3 Key Points, Call to Action (Arrow ➡️ or 🔗 + URL directly, NO 'read more'), Hashtags (#packaging + 3).
    OUTPUT ONLY POST TEXT. NO MARKDOWN.
    """
elif modus == "Social Media (Deutsch)":
    system_prompt = """
    ROLLE: Social Media Manager.
    OUTPUT 1: LinkedIn Post (Deutsch). Hook, Bulletpoints, CTA (➡️ oder 🔗 + URL direkt, KEIN 'Mehr lesen'), Hashtags.
    OUTPUT 2: X/Twitter Post (Deutsch). Max 270 Zeichen inkl. Link.
    FORMAT: [LINKEDIN]...[TWITTER] NO MARKDOWN.
    """
elif modus == "Messe-Vorbericht (Special)":
    len_map = {"KURZ": "900", "NORMAL": "1300", "LANG": "2000"}
    l_opt = st.radio("PRINT-Länge:", ["KURZ (900)", "NORMAL (1300)", "LANG (2000)"], horizontal=True)
    target = len_map.get(l_opt.split()[0], "900")
    
    einstiegs_anweisung = """
    WICHTIG - EINSTIEGS-VARIANZ (Wähle einen der Typen, vermeide "Firma zeigt..."):
    Typ A (Problem-Fokus): "Steigende Energiekosten erfordern effizientere Antriebe. Genau hier setzt die neue Lösung an..."
    Typ B (Technik-Fokus): "Mit einer Taktleistung von 200 Zyklen pro Minute erreicht die neue Anlage..."
    Typ C (Trend-Fokus): "Nachhaltigkeit dominiert die Verpackungsbranche. Rezyklate stehen dabei im Mittelpunkt..."
    Wähle passend zum Inhalt Typ A, B oder C. Starte NICHT mit dem Firmennamen.
    """
    
    system_prompt = f"""
    {base_rules}
    TASK: Schreibe zwei Versionen für ein {selected_messe}-Special.
    {einstiegs_anweisung}
    
    TEIL 1: PRINT-VERSION (Exakt ca. {target} Zeichen).
    Struktur: Oberzeile, Headline, Text (SOFORTIGER journalistischer EINSTIEG, kein Anleser).
    Footer: Nur 'www.firma.de' | Halle/Stand.
    
    TEIL 2: ONLINE-VERSION (2500-5000 Zeichen).
    Struktur: Headline, Anleser (max 300Z), Text mit Zwischenüberschriften, Footer.
    
    FORMAT-AUSGABE: 
    [P_OBERZEILE]...[P_HEADLINE]...[P_TEXT]...[P_WEB]...[P_STAND]
    [O_HEADLINE]...[O_ANLESER]...[O_TEXT]...[O_STAND]...[O_KEYWORD]...[O_DESC]...[O_TAGS]
    """
else:
    l_opt = st.radio("Länge:", ["KURZ (2-4k)", "NORMAL (6-9k)", "LANG (12-15k)"], horizontal=True)
    system_prompt = f"""
    {base_rules} 
    TASK: Fach-News Online. 
    EINSTIEG: Journalistisch (Problem/Lösung oder Technik), kein PR-Sprech.
    FORMAT: [TITEL]...[ANLESER]...[TEXT]...[SNIPPET]...[KEYWORD]
    """

# INPUTS
ck = st.session_state['input_key']
url_in = st.text_input("Link (URL):", key=f"url_{ck}")
file_in = st.file_uploader("Datei:", key=f"file_{ck}")
text_in = st.text_area("Text / Notizen:", height=150, key=f"text_{ck}")
custom_focus = st.text_area("🔧 Individueller Fokus / Anweisung (optional):", height=60, key=f"focus_{ck}")

final_text = ""
if url_in:
    try: r = requests.get(url_in, timeout=10); final_text = BeautifulSoup(r.text, 'html.parser').get_text(separator=' ', strip=True)
    except: st.error("URL konnte nicht gelesen werden.")
elif file_in:
    if file_in.type == "application/pdf": p = PyPDF2.PdfReader(file_in); final_text = " ".join([page.extract_text() for page in p.pages])
    else: final_text = docx2txt.process(file_in)
else: final_text = text_in

# GENERIEREN
if st.button("✨ INHALTE GENERIEREN", type="primary"):
    if len(final_text) < 20: st.warning("Bitte Material bereitstellen.")
    else:
        with st.spinner("KI arbeitet..."):
            is_social = "LinkedIn" in modus or "Social" in modus
            
            # Bild laden für Social (vom Link) - JETZT ROBUST
            if is_social and url_in:
                og = get_website_og_image(url_in)
                if og: st.session_state['og_img'] = og
            
            # Text Generierung mit Auto-Modell-Wahl
            model = get_google_model()
            if model:
                pmt = f"{system_prompt}\nFOKUS: {custom_focus}\nLINK: {url_in}\nMATERIAL:\n{final_text}"
                try:
                    resp = model.generate_content(pmt)
                    st.session_state['res'] = resp.text
                except Exception as e:
                    st.error(f"GENAUER FEHLER: {e}")
            
            # Bild KI Generierung (nur wenn nicht Social)
            if generate_img_flag and not is_social:
                 st.session_state['img'] = generate_horizontal_image(final_text[:200])

# AUSGABE
if 'res' in st.session_state:
    res = st.session_state['res']
    
    # 1. LINKEDIN ENGLISCH
    if modus == "LinkedIn Post (English)":
        st.subheader("LinkedIn (English)")
        if 'og_img' in st.session_state: 
            st.image(st.session_state['og_img'], caption="Vorschau-Bild der URL", width=500)
        
        clean_res = clean_text(res)
        st.code(clean_res, language=None)
        st.caption("Oben rechts klicken zum Kopieren.")
        save_to_history("LinkedIn EN", clean_res[:50])

    # 2. SOCIAL DEUTSCH
    elif modus == "Social Media (Deutsch)":
        st.subheader("Social Media (Deutsch)")
        if 'og_img' in st.session_state: 
            st.image(st.session_state['og_img'], caption="Vorschau-Bild der URL", width=500)
        try:
            li = clean_text(res.split('[LINKEDIN]')[1].split('[TWITTER]')[0])
            tw = clean_text(res.split('[TWITTER]')[1])
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**LinkedIn (Lang)**")
                st.code(li, language=None)
            with c2:
                st.markdown("**X / Twitter (Kurz)**")
                st.code(tw, language=None)
            save_to_history("Social DE", li[:50])
        except: st.write(res)

    # 3. MESSE SPECIAL
    elif modus == "Messe-Vorbericht (Special)":
        try:
            # Parsing mit Fallback
            p_head = "Unbekannt"
            if '[P_HEADLINE]' in res:
                p_head = clean_text(res.split('[P_HEADLINE]')[1].split('[P_TEXT]')[0])
            
            if '[P_OBERZEILE]' in res and '[O_HEADLINE]' in res:
                p_ober = clean_text(res.split('[P_OBERZEILE]')[1].split('[P_HEADLINE]')[0])
                p_text = clean_text(res.split('[P_TEXT]')[1].split('[P_WEB]')[0])
                p_web  = clean_text(res.split('[P_WEB]')[1].split('[P_STAND]')[0])
                p_stand= clean_text(res.split('[P_STAND]')[1].split('[O_HEADLINE]')[0])
                
                full_print = f"{p_ober}\n\n{p_head}\n\n{p_text}\n\n{p_web}\n{p_stand}"
                
                # Online
                o_part = res.split('[O_HEADLINE]')[1]
                o_head = clean_text(o_part.split('[O_ANLESER]')[0])
                o_anle = clean_text(o_part.split('[O_ANLESER]')[1].split('[O_TEXT]')[0])
                o_text = clean_text(o_part.split('[O_TEXT]')[1].split('[O_STAND]')[0])
                o_stand = clean_text(o_part.split('[O_STAND]')[1].split('[O_KEYWORD]')[0])
                
                save_to_history(f"Messe: {p_head}", "Bericht")

                t1, t2 = st.tabs(["📟 PRINT", "🌐 ONLINE"])
                with t1:
                    st.code(full_print, language=None)
                    st.download_button("📄 Word (Print)", create_docx(full_print), "Print.docx")
                with t2:
                    if st.session_state.get('img'): st.image(st.session_state['img'], width=600)
                    st.markdown("**Titel:**"); st.code(o_head, language=None)
                    st.markdown("**Anleser:**"); st.code(o_anle, language=None)
                    st.markdown("**Text:**"); st.code(o_text, language=None)
                    st.markdown("**Stand:**"); st.code(o_stand, language=None)
            else:
                st.error("Formatierungs-Fehler der KI. Hier ist der Rohtext:")
                st.write(res)
        except: st.write(res)

    # 4. STANDARD NEWS
    else:
        try:
            if '[TITEL]' in res:
                tit = clean_text(res.split('[TITEL]')[1].split('[ANLESER]')[0])
                anl = clean_text(res.split('[ANLESER]')[1].split('[TEXT]')[0])
                txt = clean_text(res.split('[TEXT]')[1].split('[SNIPPET]')[0])
                if st.session_state.get('img'): st.image(st.session_state['img'], width=600)
                
                st.markdown("**Titel:**"); st.code(tit, language=None)
                st.markdown("**Anleser:**"); st.code(anl, language=None)
                st.markdown("**Text:**"); st.code(txt, language=None)
                
                full_doc_text = tit + "\n\n" + anl + "\n\n" + txt
                st.download_button("📄 Word (News)", create_docx(full_doc_text), "News.docx")
                save_to_history(f"News: {tit}", anl[:50])
            else:
                st.write(res)
        except: st.write(res)
