import streamlit as st
import google.generativeai as genai

# --- SEITEN KONFIGURATION ---
st.set_page_config(page_title="PJ News Generator", page_icon="📝", layout="centered")

st.title("📝 PJ News-Generator V3")
st.caption("Erstellt journalistische Meldungen für das packaging journal online.")

# --- SIDEBAR (API KEY) ---
st.sidebar.header("Einstellungen")
api_key = st.sidebar.text_input("Google API Key", type="password")

# Fallback auf Secrets, falls im Feld nichts steht
if not api_key and "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]

# --- HAUPTBEREICH: EINGABEN ---

# 1. Auswahl der Länge (Neu!)
length_option = st.radio(
    "Gewünschte Artikellänge:",
    ["Kurz (~1.200 Zeichen)", "Normal (~2.500 Zeichen)", "Lang (~5.000 Zeichen)"],
    horizontal=True
)

# 2. Textfeld
source_text = st.text_area("Quelltext / Pressemitteilung einfügen:", height=250)

# --- LOGIK: PROMPT BAUEN ---
# Wir definieren die Längen-Instruktionen basierend auf der Auswahl
if "Kurz" in length_option:
    length_instruction = (
        "ZIEL-LÄNGE: ca. 1.200 Zeichen.\n"
        "STRUKTUR: Kompakter Fließtext ohne Zwischenüberschriften. Fokus auf die reine Nachricht."
    )
elif "Normal" in length_option:
    length_instruction = (
        "ZIEL-LÄNGE: ca. 2.500 Zeichen.\n"
        "STRUKTUR: Gut lesbarer Artikel mit sinnvollen H2-Zwischenüberschriften zur Gliederung."
    )
else: # Lang
    length_instruction = (
        "ZIEL-LÄNGE: ca. 5.000 Zeichen.\n"
        "STRUKTUR: Ausführlicher Deep-Dive-Artikel. Nutze viele H2-Zwischenüberschriften für gute Lesbarkeit."
    )

# Der Basis-Prompt mit deinen neuen Regeln
SYSTEM_PROMPT = f"""
Du bist erfahrene:r Fachredakteur:in beim "packaging journal". 
Deine Zielgruppe sind Entscheider und Ingenieure der Verpackungsindustrie.
Stil: Objektiv, präzise, branchennah.

DEINE AUFGABE:
Verwandle den Quelltext in einen Online-Artikel.

REGELN (STRENG EINHALTEN):
1. TITEL (H1): Maximal 6 Wörter! Muss griffig und knackig sein.
2. SEO: Das Fokus-Keyword darf nur aus EINEM EINZIGEN WORT bestehen. Es muss im Titel und Text vorkommen.
3. MARKETING-FILTER: Entferne PR-Floskeln ("stolz", "einzigartig", "state-of-the-art"). Firmennamen normal schreiben (keine Versalien). Rechtsformen (GmbH etc.) entfernen.
4. {length_instruction}

OUTPUT-FORMAT:
1. SEO-BOX
   - Fokus-Keyword (1 Wort)
   - Meta Description (max 160 Zeichen, Klickreiz)
   - Tags

2. ARTIKEL
   - H1 Titel (max 6 Wörter)
   - Teaser (Fettgedruckt, der "Hook")
   - Artikel-Body (gemäß Längenvorgabe)
   - Fazit/Einordnung
"""

# --- GENERIERUNG ---
if st.button("Artikel erstellen ✨", type="primary"):
    if not api_key:
        st.
