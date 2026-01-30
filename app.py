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

# --- KONFIGURATION ---
st.set_page_config(page_title="PJ Redaktions Tool", page_icon="🚀", layout="wide")

# Pfad für die Historie
HISTORY_FILE = "news_history.csv"

def save_to_history(titel, teaser, text, snippet):
    new_data = pd.DataFrame([{
        "Datum": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "Titel": titel,
        "Teaser": teaser,
        "Text": text,
        "Snippet": snippet
    }])
    if not os.path.isfile(HISTORY_FILE):
        new_data.to_csv(HISTORY_FILE, index=False, sep=";")
    else:
        new_data.to_csv(HISTORY_FILE, mode='a', header=False, index=False, sep=";")

# --- SIDEBAR & LOGIN ---
st.sidebar.header("🔐 Login")
pw_input = st.sidebar.text_input("Passwort:", type="password")
if pw_input != st.secrets.get("TOOL_PASSWORD", "pj-redaktion-2026"):
    st.stop()

# Archiv in der Sidebar anzeigen
st.sidebar.markdown("---")
st.sidebar.header("📚 Archiv (Letzte 5)")
if os.path.isfile(HISTORY_FILE):
    df_history = pd.read_csv(HISTORY_FILE, sep=";")
    for i, row in df_history.tail(5).iterrows():
        with st.sidebar.expander(f"🕒 {row['Datum']}: {row['Titel'][:30]}..."):
            st.write(f"**Titel:** {row['Titel']}")
            st.write(f"**Teaser:** {row['Teaser']}")
            st.write(f"**Snippet:** {row['Snippet']}")
else:
    st.sidebar.info("Noch keine Beiträge im Archiv.")

st.sidebar.markdown("---")
modus = st.sidebar.radio("Erstellung:", ["Standard Online-News", "Messe-Vorbericht"])
generate_img_flag = st.sidebar.checkbox("KI-Beitragsbild generieren?", value=True)

# ... (HILFSFUNKTIONEN WIE GEHABT: get_best_google_model, generate_horizontal_image, create_docx) ...

# --- HAUPTBEREICH ---
st.title("🚀 packaging journal Redaktions Tool")

# (Input-Logik für URL, Datei, Text wie bisher...)

# --- GENERIERUNG ---
if st.button(f"✨ {modus.upper()} JETZT GENERIEREN", type="primary"):
    with st.spinner("KI generiert strukturierte Inhalte..."):
        # 1. Text Generierung mit Struktur-Zwang
        format_instr = "[TITEL]\nMax 6 Wörter\n[TEASER]\nMax 300 Zeichen\n[TEXT]\nHaupttext ohne Ort/Datum\n[SNIPPET]\nMax 160 Zeichen"
        model_name = get_best_google_model()
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(f"{format_instr}\n\nMaterial: {final_text}")
        res_text = response.text
        
        # Parsing
        try:
            titel = res_text.split('[TITEL]')[1].split('[TEASER]')[0].strip()
            teaser = res_text.split('[TEASER]')[1].split('[TEXT]')[0].strip()
            haupttext = res_text.split('[TEXT]')[1].split('[SNIPPET]')[0].strip()
            snippet = res_text.split('[SNIPPET]')[1].strip()
            
            # Speichern
            save_to_history(titel, teaser, haupttext, snippet)
            
            st.session_state['last_t'] = titel
            st.session_state['last_te'] = teaser
            st.session_state['last_h'] = haupttext
            st.session_state['last_s'] = snippet
        except:
            st.error("Formatierungsfehler der KI. Bitte nochmal versuchen.")

        if generate_img_flag:
            st.session_state['last_image'] = generate_horizontal_image(final_text[:200])

# --- ANZEIGE ---
if 'last_h' in st.session_state:
    st.divider()
    # Hier nutzen wir st.code für den einfachen Copy-Button (WordPress-Anbindung)
    st.subheader("📌 WordPress Titel")
    st.code(st.session_state['last_t'], language=None)
    
    st.subheader("📰 Teaser (max 300 Zeichen)")
    st.code(st.session_state['last_te'], language=None)
    
    col_img, col_txt = st.columns([1, 1])
    with col_img:
        if st.session_state.get('last_image'):
            st.image(st.session_state['last_image'], caption="Rechtsklick zum Speichern")
    with col_txt:
        st.subheader("✍️ Haupttext")
        st.write(st.session_state['last_h'])
    
    st.subheader("🔍 Google Snippet (max 160 Zeichen)")
    st.code(st.session_state['last_s'], language=None)
