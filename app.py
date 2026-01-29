import streamlit as st
import google.generativeai as genai

# --- KONFIGURATION ---
# Hier wird die Seite eingerichtet
st.set_page_config(page_title="PJ News Generator", page_icon="📝", layout="centered")

# --- MASTER PROMPT ---
# Das ist dein Regelwerk, das wir definiert haben
SYSTEM_PROMPT = """
Du bist erfahrene:r Fachredakteur:in beim "packaging journal". Deine Zielgruppe sind Entscheider, Ingenieure und Einkäufer der Verpackungsindustrie. 
Dein Stil ist objektiv, präzise, branchennah und journalistisch hochwertig.

DEINE AUFGABE:
Verwandle das Eingabe-Material in einen journalistischen Online-Artikel.
Oberstes Gebot: Trennung von Nachricht und Werbung. Filtere reine Marketing-Aussagen heraus.

REGELN:
* Kein PR-Fluff (kein "stolz", "einzigartig", "state-of-the-art").
* Firmennamen normal schreiben (keine VERSALIEN).
* Rechtsformen entfernen (kein GmbH, AG, Co. KG).
* Keine ® oder ™ Zeichen.
* Zahlen ausschreiben oder einheitlich formatieren.

STRUKTUR DER AUSGABE:
1. SEO-BOX (Fokus-Keyword, Meta Description, Tags)
2. ARTIKEL (H1 Titel, Teaser/Lead fettgedruckt, Body mit H2, Fazit)
"""

# --- SIDEBAR & API SETUP ---
st.sidebar.header("Einstellungen")
# Wir holen den API Key sicher aus den Streamlit Secrets (oder Eingabefeld)
api_key = st.sidebar.text_input("Google API Key", type="password", help="Hier den Key von AI Studio eingeben")

# Versuche, den Key aus den System-Secrets zu laden, falls im Feld nichts steht
if not api_key:
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]

# --- HAUPTBEREICH ---
st.title("📝 Packaging Journal News-Generator")
st.markdown("Füge unten einfach die Pressemitteilung ein. Die KI erstellt daraus den fertigen Artikel inkl. SEO-Box.")

# Eingabefeld für den Text
source_text = st.text_area("Quelltext / Pressemitteilung:", height=300, placeholder="Hier Text reinkopieren...")

# Button zum Generieren
generate_btn = st.button("Artikel erstellen ✨", type="primary")

# --- LOGIK ---
if generate_btn:
    if not api_key:
        st.error("Bitte gib einen Google API Key in der Seitenleiste ein oder hinterlege ihn in den Secrets.")
        st.stop()
    
    if not source_text:
        st.warning("Bitte gib erst einen Text ein.")
        st.stop()

    try:
        # Spinner zeigt an, dass gearbeitet wird
        with st.spinner("Die Redaktions-KI schreibt..."):
            # Modell konfigurieren
            genai.configure(api_key=api_key)
            # Wir nutzen Gemini 1.5 Flash (schnell & günstig) oder Pro (besser)
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash", 
                system_instruction=SYSTEM_PROMPT
            )
            
            # Anfrage senden
            response = model.generate_content(source_text)
            
            # Ergebnis anzeigen
            st.success("Fertig!")
            st.markdown("---")
            st.markdown(response.text)
            
            # Kleiner Helfer: Button zum Kopieren des Ergebnisses (Workaround, da Streamlit keinen nativen Copy-Button hat)
            st.caption("Tipp: Einfach den Text markieren und kopieren.")

    except Exception as e:
        st.error(f"Ein Fehler ist aufgetreten: {e}")
