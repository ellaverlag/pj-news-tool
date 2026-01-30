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
if 'publer_accounts' not in st.session_state: st.session_state['publer_accounts'] = []

def reset_app():
    st.session_state['input_key'] += 1
    keys_to_clear = ['res', 'img', 'og_img']
    for k in keys_to_clear:
        if k in st.session_state: del st.session_state[k]

# --- PUBLER API ---
def fetch_publer_accounts(api_key):
    try:
        url = "https://api.publer.io/v1/accounts"
        resp = requests.get(url, headers={"Authorization": f"Bearer {api_key}"})
        return resp.json() if resp.status_code == 200 else []
    except: return []

def post_to_publer(api_key, text, link, media_url, account_ids):
    url = "https://api.publer.io/v1/posts"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "text": text,
        "social_accounts": [{"id": acc_id} for acc_id in account_ids],
    }
    if link: payload["link"] = link
    if media_url: payload["media"] = [{"url": media_url}]
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        return response
    except Exception as e: return str(e)

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
modus = st.sidebar.radio("Modus:", ["Standard Online-News", "Messe-Vorbericht (Special)", "LinkedIn Post (English)", "Social Media (Deutsch)"])

# MESSE OPTIONEN
selected_messe = ""
m_link = ""
if modus == "Messe-Vorbericht (Special)":
    selected_messe = st.sidebar.selectbox("Messe:", ["LogiMat", "interpack", "Fachpack", "SPS"])
    m_links = {"LogiMat": "https://www.logimat-messe.de/de/die-messe/ausstellerliste", "interpack": "https://www.interpack.de/de/Aussteller_Produkte/Ausstellerverzeichnis", "Fachpack": "https://www.fachpack.de/de/aussteller-produkte/ausstellerliste", "SPS": "https://sps.mesago.com/nuernberg/de/ausstellersuche.html"}
    m_link = m_links.get(selected_messe, "")

st.sidebar.markdown("---")

# --- PUBLER CONFIG & SETUP ---
# Versuche API Key aus Secrets zu lesen, sonst Eingabefeld
publer_key = st.secrets.get("PUBLER_API_KEY", "")
if not publer_key:
    publer_key = st.sidebar.text_input("Publer API Key:", type="password")

# Versuche Ziel-IDs aus Secrets zu lesen
# Erwartetes Format in Secrets: "12345,67890" (Komma-getrennt) oder einzelne ID
ids_de_raw = st.secrets.get("PUBLER_IDS_DEUTSCH", "")
ids_en_raw = st.secrets.get("PUBLER_ID_ENGLISCH", "")

# Umwandeln in Listen
fixed_ids_de = [x.strip() for x in ids_de_raw.split(',')] if ids_de_raw else []
fixed_ids_en = [x.strip() for x in ids_en_raw.split(',')] if ids_en_raw else []

# Setup-Hilfe in der Sidebar anzeigen, wenn keine IDs in Secrets gefunden wurden
if publer_key and (not fixed_ids_de or not fixed_ids_en):
    with st.sidebar.expander("🛠️ Publer Setup (IDs finden)", expanded=True):
        st.caption("Lade Konten, um die IDs für die Secrets zu kopieren:")
        if st.button("🔄 Konten laden"):
            accs = fetch_publer_accounts(publer_key)
            st.session_state['publer_accounts'] = accs
        
        if st.session_state['publer_accounts']:
            for acc in st.session_state['publer_accounts']:
                st.markdown(f"**{acc['name']}** ({acc['type']})")
                st.code(acc['id'], language=None)
            st.caption("👉 Kopiere diese IDs in deine Secrets-Datei bei Streamlit.")

st.sidebar.button("🗑️ ALLES NEU", on_click=reset_app, type="secondary")

# ARCHIV
HISTORY_FILE = "news_history.csv"
def save_to_history(titel, snippet):
    d = datetime.now().strftime("%d.%m. %H:%M")
    t = str(titel).replace(';', '').strip() if titel else "Unbekannt"
    s = str(snippet).replace(';', '').strip()
    entry = pd.DataFrame([{"Datum": d, "Titel": t, "Snippet": s}])
    if not os.path.isfile(HISTORY_FILE): entry.to_csv(HISTORY_FILE, index=False, sep=";")
    else: entry.to_csv(HISTORY_FILE, mode='a', header=False, index=False, sep=";")

if os.path.isfile(HISTORY_FILE):
    with st.sidebar.expander("📚 Verlauf"):
        try:
            df = pd.read_csv(HISTORY_FILE, sep=";", names=["Datum","Titel","Snippet"], dtype=str).fillna("")
            for i, r in df.tail(5).iloc[::-1].iterrows():
                st.caption(f"{r['Datum']}: {r['Titel']}")
        except: pass

# ================= MAIN =================

def get_best_google_model():
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        return "models/gemini-1.5-flash"
    except: return None

def generate_horizontal_image(topic):
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        res = client.images.generate(model="dall-e-3", prompt=f"Packaging industry, theme: {topic}. Cinematic lighting, 16:9, no text.", size="1792x1024")
        return res.data[0].url
    except: return None

def get_website_og_image(url):
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        soup = BeautifulSoup(r.content, 'html.parser')
        og = soup.find("meta", property="og:image")
        return og["content"] if og else None
    except: return None

def create_docx(txt):
    d = Document(); [d.add_paragraph(l) for l in txt.split('\n') if l.strip()]
    b = BytesIO(); d.save(b); return b.getvalue()

def clean_text(t): return str(t).replace('**','').replace('__','').replace('### ','').replace('## ','').strip() if t else ""

# PROMPTS
base_rules = "ROLLE: Fachjournalist packaging journal. STIL: Sachlich. FORMAT: REINER TEXT, KEIN MARKDOWN."

if modus == "LinkedIn Post (English)":
    system_prompt = """
    ROLE: Social Media Manager 'packaging journal'. TASK: LinkedIn post in ENGLISH.
    STYLE: Short, engaging, Emojis. STRUCTURE: Hook, 2-3 Key Points, Call to Action (Arrow ➡️ + URL), Hashtags (#packaging + 3).
    OUTPUT ONLY POST TEXT. NO MARKDOWN.
    """
elif modus == "Social Media (Deutsch)":
    system_prompt = """
    ROLLE: Social Media Manager.
    OUTPUT 1: LinkedIn Post (Deutsch). Hook, Bulletpoints, CTA (➡️ + URL), Hashtags.
    OUTPUT 2: X/Twitter Post (Deutsch). Max 270 Zeichen inkl. Link.
    FORMAT: [LINKEDIN]...[TWITTER] NO MARKDOWN.
    """
elif modus == "Messe-Vorbericht (Special)":
    len_map = {"KURZ": "900", "NORMAL": "1300", "LANG": "2000"}
    l_opt = st.radio("PRINT-Länge:", ["KURZ (900)", "NORMAL (1300)", "LANG (2000)"], horizontal=True)
    target = len_map.get(l_opt.split()[0], "900")
    system_prompt = f"""
    {base_rules} TASK: {selected_messe}-Special.
    PRINT: Exakt {target} Zeichen. Footer: Website | Halle/Stand.
    ONLINE: 2500-5000 Zeichen. Zwischenüberschriften.
    FORMAT: [P_OBERZEILE]...[P_HEADLINE]...[P_TEXT]...[P_WEB]...[P_STAND]
    [O_HEADLINE]...[O_ANLESER]...[O_TEXT]...[O_STAND]...[O_KEYWORD]...[O_DESC]...[O_TAGS]
    """
else:
    l_opt = st.radio("Länge:", ["KURZ (2-4k)", "NORMAL (6-9k)", "LANG (12-15k)"], horizontal=True)
    system_prompt = f"{base_rules} TASK: Fach-News Online. FORMAT: [TITEL]...[ANLESER]...[TEXT]...[SNIPPET]...[KEYWORD]"

# INPUTS
ck = st.session_state['input_key']
url_in = st.text_input("Link (URL):", key=f"url_{ck}")
file_in = st.file_uploader("Datei:", key=f"file_{ck}")
text_in = st.text_area("Text / Notizen:", height=150, key=f"text_{ck}")
custom_focus = st.text_area("🔧 Zusatz-Infos / Fokus:", height=60, key=f"focus_{ck}")

final_text = ""
if url_in:
    try: r = requests.get(url_in, timeout=10); final_text = BeautifulSoup(r.text, 'html.parser').get_text(separator=' ', strip=True)
    except: st.error("URL Fehler")
elif file_in:
    if file_in.type == "application/pdf": p = PyPDF2.PdfReader(file_in); final_text = " ".join([page.extract_text() for page in p.pages])
    else: final_text = docx2txt.process(file_in)
else: final_text = text_in

# GENERIEREN
if st.button("✨ GENERIEREN", type="primary"):
    if len(final_text) < 20: st.warning("Input fehlt.")
    else:
        with st.spinner("KI arbeitet..."):
            is_social = "LinkedIn" in modus or "Social" in modus
            if is_social and url_in:
                og = get_website_og_image(url_in)
                if og: st.session_state['og_img'] = og
            
            mod = genai.GenerativeModel("models/gemini-1.5-flash") # Fallback falls function fail
            pmt = f"{system_prompt}\nFOKUS: {custom_focus}\nLINK: {url_in}\nMATERIAL:\n{final_text}"
            try:
                resp = mod.generate_content(pmt)
                st.session_state['res'] = resp.text
            except: st.error("KI Fehler")
            
            if not is_social and st.sidebar.checkbox("Bild?", value=True):
                 st.session_state['img'] = generate_horizontal_image(final_text[:200])

# ANZEIGE
if 'res' in st.session_state:
    res = st.session_state['res']
    
    # 1. LINKEDIN ENGLISCH
    if modus == "LinkedIn Post (English)":
        st.subheader("LinkedIn (English)")
        if 'og_img' in st.session_state: st.image(st.session_state['og_img'], width=400)
        st.code(res, language=None)
        
        # Sende-Button
        if publer_key:
            if fixed_ids_en:
                if st.button(f"🚀 An Englischen Account senden"):
                    media = st.session_state.get('og_img')
                    stat = post_to_publer(publer_key, res, url_in, media, fixed_ids_en)
                    if hasattr(stat, 'status_code') and stat.status_code in [200,201]: st.success("Gesendet!")
                    else: st.error(f"Fehler: {stat}")
            else:
                st.warning("⚠️ Keine 'PUBLER_ID_ENGLISCH' in Secrets gefunden. Bitte Setup in Sidebar nutzen.")

    # 2. SOCIAL DEUTSCH
    elif modus == "Social Media (Deutsch)":
        st.subheader("Social Media (Deutsch)")
        if 'og_img' in st.session_state: st.image(st.session_state['og_img'], width=400)
        try:
            li = res.split('[LINKEDIN]')[1].split('[TWITTER]')[0].strip()
            tw = res.split('[TWITTER]')[1].strip()
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**LinkedIn (Lang)**")
                st.code(li, language=None)
                if publer_key:
                    if fixed_ids_de:
                        if st.button(f"🚀 LinkedIn an 2 DE-Accounts"):
                            media = st.session_state.get('og_img')
                            stat = post_to_publer(publer_key, li, url_in, media, fixed_ids_de)
                            if hasattr(stat, 'status_code') and stat.status_code in [200,201]: st.success("Gesendet!")
                            else: st.error(f"Fehler: {stat}")
                    else: st.warning("⚠️ Keine 'PUBLER_IDS_DEUTSCH' in Secrets.")
            with c2:
                st.markdown("**X / Twitter**")
                st.code(tw, language=None)
        except: st.write(res)

    # 3. MESSE / NEWS (Kurzform der Anzeige)
    elif modus == "Messe-Vorbericht (Special)":
        # (Hier der Standard-Parsing Code von vorhin, gekürzt für Übersicht)
        try:
            p_head = clean_text(res.split('[P_HEADLINE]')[1].split('[P_TEXT]')[0])
            st.write(res) # Fallback Anzeige
            save_to_history(f"Messe: {p_head}", "Bericht")
        except: st.write(res)
    else:
        st.write(res)
        save_to_history("News", "Beitrag")
