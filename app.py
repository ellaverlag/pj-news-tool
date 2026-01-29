import streamlit as st
import google.generativeai as genai

st.set_page_config(page_title="PJ News Generator", page_icon="📝")

# --- MASTER PROMPT ---
SYSTEM_PROMPT = """
Du bist erfahrene:r Fachredakteur:in beim "packaging journal".
Erstelle aus dem Quelltext eine Online-News.
REGELN: Trennung von Nachricht/Werbung, keine PR-Adjektive, sachlich, präzise.
FORMAT:
1. SEO-BOX (Keyword, Snippet)
2. ARTIKEL (H1, Teaser fett, Body, Fazit)
"""

st.title("📝 PJ News-Generator (V2)")

# API Key Handling
api_key = st.sidebar.text_input("Google API Key", type="password")
if not api_key and "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]

source_text = st.text_area("Quelltext:", height=200)

if st.button("Generieren ✨", type="primary"):
    if not api_key:
        st.error("Kein API Key gefunden.")
        st.stop()
    
    try:
        genai.configure(api_key=api_key)
        
        # AUTOMATISCHE MODELL-SUCHE
        # Wir fragen die API: "Was hast du da?" und nehmen das Beste.
        available_models = [m.name for m in genai.list_models()]
        
        # Bevorzugte Modelle in Reihenfolge
        target_model = "models/gemini-1.5-flash"
        if "models/gemini-1.5-flash" not in available_models:
             # Fallback, falls Flash nicht da ist
            if "models/gemini-pro" in available_models:
                target_model = "models/gemini-pro"
            else:
                # Nimm einfach das erste, das generieren kann
                target_model = available_models[0]

        # Info für dich (damit wir sehen, was passiert)
        st.caption(f"Nutze Modell: {target_model}")
        
        model = genai.GenerativeModel(
            model_name=target_model,
            system_instruction=SYSTEM_PROMPT
        )
        
        with st.spinner("Schreibe Artikel..."):
            response = model.generate_content(source_text)
            st.markdown(response.text)

    except Exception as e:
        st.error(f"Fehler: {e}")
        # DIAGNOSE-HILFE:
        st.warning("Diagnose-Daten (bitte kopieren falls es nicht geht):")
        try:
            mods = genai.list_models()
            st.write("Verfügbare Modelle für diesen Key:")
            for m in mods:
                st.write(f"- {m.name}")
        except:
            st.write("Konnte Modelle nicht auflisten.")
