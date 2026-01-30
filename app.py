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

# --- PUBLER API (DEBUG VERSION) ---
def fetch_publer_accounts(api_key):
    url = "https://api.publer.io/v1/accounts"
    try:
        resp = requests.get(url, headers={"Authorization": f"Bearer {api_key}"})
        if resp.status_code == 200:
            data = resp.json()
            # Publer gibt manchmal {data: [...]} oder direkt [...] zurück
            if isinstance(data, list): return data, None
            elif isinstance(data, dict) and 'data' in data: return data['data'], None
            else: return data, None
        else:
            return [], f"Fehler {resp.status_code}: {resp.text}"
    except Exception as e:
        return [], f"System-Fehler: {str(e)}"

def post_to_publer(api_key, text, link, media_url, account_ids):
    url = "https://api.publer.io/v1/posts"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    # Payload bauen
    payload = {
        "text": text,
        "social_accounts": [{"id": acc_id} for acc_id in account_ids],
    }
    if link: payload["link"] = link
    if media_url: payload["media"] = [{"url": media_url}]
    
    try:
        # Wir senden ohne 'schedule_date', das triggert meist den Standard (Sofort oder Queue)
        # Wenn du explizit Drafts willst, müsste man das je nach API Version anpassen.
        # V1 interpretiert POST oft als "Schedule Now".
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

# 1. MODUS
modus = st.sidebar.radio("Modus:", [
    "Standard Online-News", 
    "Messe-Vorbericht (Special)", 
    "LinkedIn Post (English)", 
    "Social Media (Deutsch)"
])

# 2. MESSE AUSWAHL
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

# 3. PUBLER SETUP & DEBUG
publer_key = st.secrets.get("PUBLER_API_KEY", "")
if not publer_key:
    publer_key = st.sidebar.text_input("Publer API Key:", type="password")

# IDs aus Secrets lesen
ids_de_raw = st.secrets.get("PUBLER_IDS_DEUTSCH", "")
ids_en_raw = st.secrets.get("PUBLER_ID_ENGLISCH", "")
fixed_ids_de = [x.strip() for x in ids_de_raw.split(',')] if ids_de_raw else []
fixed_ids_en = [x.strip() for x in ids_en_raw.split(',')] if ids_en_raw else []

# Setup-Hilfe anzeigen, wenn IDs fehlen
if publer_key and (not fixed_ids_de or not fixed_ids_en):
    with st.sidebar.expander("🛠️ Publer IDs finden", expanded=True):
        if st.button("🔄 Konten laden"):
            accs, err = fetch_publer_accounts(publer_key)
            if err: st.error(err)
            else: st.session_state['publer_accounts'] = accs
        
        if st.session_state['publer_accounts']:
            st.caption("Kopiere die IDs in deine Secrets:")
            for acc in st.session_state['publer_accounts']:
                name = acc.get('name', 'Unbekannt')
                aid = acc.get('id', '?')
                atype = acc.get('type', '?')
                st.markdown(f"**{name}** ({atype})")
                st.code(aid, language=None)

# 4. RESET & BILD-WAHL
generate_img_flag = True
if "Social" in modus or "LinkedIn" in modus:
    generate_img_flag = False
else:
    generate_img_flag = st.sidebar.checkbox("Bild generieren?", value=True)

st.sidebar.button("🗑️ ALLES NEU", on_click=reset_app, type="secondary")

# 5. ARCHIV
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

# ================= MAIN LOGIK =================

def get_best_google_model():
    try:
        genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
        return "models/gemini-1.5-flash"
    except: return None

def generate_horizontal_image(topic):
    try:
        client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        res = client.images.generate(model="dall-e-3", prompt=f"Industrial photography, packaging industry theme: {topic}. High-end cinematic lighting, 16:9 horizontal, no text.", size="1792x1024")
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

# --- PROMPTS ---
base_rules = "ROLLE: Fachjournalist packaging journal. STIL: Sachlich. FORMAT: REINER TEXT, KEIN MARKDOWN."

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
    system_prompt = f"""
    {base_rules} TASK: {selected_messe}-Special.
    PRINT: Exakt ca. {target} Zeichen. Einstieg sofort. Footer: Website | Halle/Stand.
    ONLINE: 2500-5000 Zeichen. Zwischenüberschriften.
    FORMAT: [P_OBERZEILE]...[P_HEADLINE]...[P_TEXT]...[P_WEB]...[P_STAND]
    [O_HEADLINE]...[O_ANLESER]...[O_TEXT]...[O_STAND]...[O_KEYWORD]...[O_DESC]...[O_TAGS]
    """
else:
    l_opt = st.radio("Länge:", ["KURZ (2-4k)", "NORMAL (6-9k)", "LANG (12-15k)"], horizontal=True)
    system_prompt = f"{base_rules} TASK: Fach-News Online. FORMAT: [TITEL]...[ANLESER]...[TEXT]...[SNIPPET]...[KEYWORD]"

# --- INPUTS ---
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

# --- GENERIERUNG ---
if st.button("✨ GENERIEREN", type="primary"):
    if len(final_text) < 20: st.warning("Input fehlt.")
    else:
        with st.spinner("KI arbeitet..."):
            is_social = "LinkedIn" in modus or "Social" in modus
            
            # Bild laden für Social
            if is_social and url_in:
                og = get_website_og_image(url_in)
                if og: st.session_state['og_img'] = og
            
            mod = genai.GenerativeModel("models/gemini-1.5-flash")
            pmt = f"{system_prompt}\nFOKUS: {custom_focus}\nLINK: {url_in}\nMATERIAL:\n{final_text}"
            try:
                resp = mod.generate_content(pmt)
                st.session_state['res'] = resp.text
            except: st.error("KI Fehler")
            
            if not is_social and st.sidebar.checkbox("Bild?", value=True):
                 st.session_state['img'] = generate_horizontal_image(final_text[:200])

# --- AUSGABE ---
if 'res' in st.session_state:
    res = st.session_state['res']
    
    # 1. LINKEDIN ENGLISCH
    if modus == "LinkedIn Post (English)":
        st.subheader("LinkedIn (English)")
        if 'og_img' in st.session_state: st.image(st.session_state['og_img'], width=400)
        st.code(res, language=None)
        
        if publer_key and fixed_ids_en:
            if st.button(f"🚀 Senden (Englisch)"):
                media = st.session_state.get('og_img')
                stat = post_to_publer(publer_key, res, url_in, media, fixed_ids_en)
                if hasattr(stat, 'status_code') and stat.status_code in [200,201]: st.success("Gesendet!")
                else: st.error(f"Fehler: {stat}")
        save_to_history("LinkedIn EN", res[:50])

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
                if publer_key and fixed_ids_de:
                    if st.button(f"🚀 Senden (Deutsch/2 Konten)"):
                        media = st.session_state.get('og_img')
                        stat = post_to_publer(publer_key, li, url_in, media, fixed_ids_de)
                        if hasattr(stat, 'status_code') and stat.status_code in [200,201]: st.success("Gesendet!")
                        else: st.error(f"Fehler: {stat}")
            with c2:
                st.markdown("**X / Twitter**")
                st.code(tw, language=None)
            save_to_history("Social DE", li[:50])
        except: st.write(res)

    # 3. MESSE
    elif modus == "Messe-Vorbericht (Special)":
        try:
            p_head = clean_text(res.split('[P_HEADLINE]')[1].split('[P_TEXT]')[0])
            st.write(res) # Fallback für User falls Parsing hakt
            save_to_history(f"Messe: {p_head}", "Bericht")
        except: st.write(res)

    # 4. NEWS
    else:
        try:
            tit = clean_text(res.split('[TITEL]')[1].split('[ANLESER]')[0])
            anl = clean_text(res.split('[ANLESER]')[1].split('[TEXT]')[0])
            txt = clean_text(res.split('[TEXT]')[1].split('[SNIPPET]')[0])
            if st.session_state.get('img'): st.image(st.session_state['img'], width=600)
            st.caption("Titel"); st.code(tit, language=None)
            st.caption("Anleser"); st.code(anl, language=None)
            st.caption("Text"); st.code(txt, language=None)
            st.download_button("Word", create_docx(f"{tit}\n{anl}\n{txt}"), "News.docx")
            save_to_history(f"News: {tit}", anl[:50])
        except: st.write(res)
