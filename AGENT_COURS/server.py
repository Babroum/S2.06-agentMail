import os
import io
import json
import time
import pickle
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from pypdf import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from groq import Groq
from dotenv import load_dotenv

# Chargement automatique des variables du fichier .env
load_dotenv()

# =========================================================================
# ⚙️ CONFIGURATION DE L'API FLASK & DE LA TEMPORISATION
# =========================================================================
app = Flask(__name__)

# CORRECTION CRITIQUE DU CORS : Autorise explicitement toutes les méthodes pour éviter l'erreur OPTIONS 404
CORS(app, resources={r"/api/*": {"origins": "*", "methods": ["GET", "POST", "OPTIONS"], "allow_headers": ["Content-Type"]}})

CHOIX_INTERVALLE = "24h"               
DUREE_VEILLE_SECONDES = 24 * 60 * 60   
VEILLE_ACTIVE = True                   

CONVERTISSEUR_TEMPS = {
    "manual": 0,
    "15m": 15 * 60,
    "1h": 60 * 60,
    "12h": 12 * 60 * 60,
    "24h": 24 * 60 * 60,
    "7d": 7 * 24 * 60 * 60
}

# =========================================================================
# 1. CONFIGURATION ET CONNEXION AUX APIS (GROQ & DRIVE)
# =========================================================================
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") 
ID_DOSSIER_DRIVE = os.environ.get("ID_DOSSIER_DRIVE") 

client = Groq(api_key=GROQ_API_KEY)
SCOPES = ['https://www.googleapis.com/auth/drive']
creds = None

print("🚀 Démarrage de l'agent de veille juridique (Version Rigueur & Design)...")

if os.path.exists('token.pickle'):
    with open('token.pickle', 'rb') as token:
        creds = pickle.load(token)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            if os.path.exists('token.pickle'):
                os.remove('token.pickle')
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
    else:
        if not os.path.exists('client_secret.json'):
            print("❌ Erreur : Le fichier 'client_secret.json' est introuvable.")
            exit(1)
        flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
        creds = flow.run_local_server(port=0)
        
    with open('token.pickle', 'wb') as token:
        pickle.dump(creds, token)

drive_service = build('drive', 'v3', credentials=creds)

# =========================================================================
# 2. ACTIONS MÉTIERS (SCAN, LECTURE PDF, GENERATION PDF STYLISÉ)
# =========================================================================
def scanner_dossier_drive():
    query = f"'{ID_DOSSIER_DRIVE}' in parents and mimeType='application/pdf' and trashed=false"
    try:
        resultats = drive_service.files().list(q=query, fields="files(id, name)").execute()
        return resultats.get('files', [])
    except Exception as e:
        print(f"❌ Erreur lors du scan du Drive : {e}")
        return []

def lire_contenu_pdf(file_id):
    try:
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        fh.seek(0)
        lecteur_pdf = PdfReader(fh)
        texte_total = ""
        for page in lecteur_pdf.pages[:10]:
            texte_total += page.extract_text() or ""
        return texte_total[:8000]
    except Exception as e:
        return f"Erreur lors de la lecture du fichier : {str(e)}"

def modifier_et_remplacer_pdf(nom_fichier, nouveau_contenu_texte, id_original):
    try:
        doc = SimpleDocTemplate(nom_fichier, pagesize=letter, rightMargin=45, leftMargin=45, topMargin=45, bottomMargin=45)
        styles = getSampleStyleSheet()
        
        style_titre = ParagraphStyle(name='Titre_Pedago', parent=styles['Heading1'], fontSize=22, leading=26, textColor=colors.HexColor("#1A365D"), spaceAfter=6, alignment=1)
        style_intertitre = ParagraphStyle(name='Intertitre_Pedago', parent=styles['Heading2'], fontSize=13, leading=17, textColor=colors.HexColor("#2C5282"), spaceBefore=14, spaceAfter=8, keepWithNext=True)
        style_texte = ParagraphStyle(name='Texte_Pedago', parent=styles['Normal'], fontSize=10.5, leading=15, textColor=colors.HexColor("#2D3748"), spaceAfter=8)
        style_encadre = ParagraphStyle(name='Encadre_Pedago', parent=styles['Normal'], fontSize=10, leading=14, textColor=colors.HexColor("#2C5282"), backColor=colors.HexColor("#EBF8FF"), borderColor=colors.HexColor("#3182CE"), borderWidth=1, borderPadding=8, spaceBefore=10, spaceAfter=10)
        
        histoire = []
        nom_propre = nom_fichier.replace('.pdf', '').replace('MAJ_', '').replace('_', ' ').title()
        histoire.append(Paragraph(f"<b>FICHE DE SYNTHÈSE : {nom_propre}</b>", style_titre))
        
        ligne_titre = Drawing(520, 10)
        ligne_titre.add(Line(0, 5, 520, 5, strokeColor=colors.HexColor("#3182CE"), strokeWidth=2))
        histoire.append(ligne_titre)
        histoire.append(Spacer(1, 15))
        
        paragraphes = nouveau_contenu_texte.split('\n')
        for p in paragraphes:
            p_strip = p.strip()
            if not p_strip: continue
            
            p_clean = p_strip.replace('& ', '&amp; ')
            est_titre_markdown = False
            if p_clean.startswith("###"):
                p_clean = p_clean.replace("###", "").strip()
                est_titre_markdown = True

            while "**" in p_clean:
                p_clean = p_clean.replace("**", "<b>", 1)
                p_clean = p_clean.replace("**", "</b>", 1)
                
            if p_clean.startswith("* "):
                p_clean = p_clean.replace("* ", "• ", 1)
                
            if p_clean.count("<b>") > p_clean.count("</b>"): p_clean += "</b>"
            if p_clean.count("<u>") > p_clean.count("</u>"): p_clean += "</u>"
            
            if "• Schéma de la théorie de Shannon & Weaver" in p_clean:
                histoire.append(Paragraph(p_clean, style_texte))
                schema_sw = Drawing(520, 40)
                schema_sw.add(Rect(5, 5, 80, 25, fillColor=colors.HexColor("#E2E8F0"), strokeColor=colors.HexColor("#4A5568"), strokeWidth=1))
                schema_sw.add(String(45, 13, "Émetteur", textAnchor="middle", fontSize=8, fontName="Helvetica-Bold"))
                schema_sw.add(Line(85, 17, 145, 17, strokeColor=colors.HexColor("#4A5568"), strokeWidth=1.5))
                schema_sw.add(Rect(145, 5, 100, 25, fillColor=colors.HexColor("#EDF2F7"), strokeColor=colors.HexColor("#4A5568"), strokeWidth=1))
                schema_sw.add(String(195, 13, "Codage / Canal", textAnchor="middle", fontSize=8))
                schema_sw.add(Line(245, 17, 305, 17, strokeColor=colors.HexColor("#4A5568"), strokeWidth=1.5))
                schema_sw.add(Rect(305, 5, 110, 25, fillColor=colors.HexColor("#EDF2F7"), strokeColor=colors.HexColor("#4A5568"), strokeWidth=1))
                schema_sw.add(String(360, 13, "Message (Signal)", textAnchor="middle", fontSize=8))
                schema_sw.add(Line(415, 17, 440, 17, strokeColor=colors.HexColor("#4A5568"), strokeWidth=1.5))
                schema_sw.add(Rect(440, 5, 75, 25, fillColor=colors.HexColor("#E2E8F0"), strokeColor=colors.HexColor("#4A5568"), strokeWidth=1))
                schema_sw.add(String(477, 13, "Récepteur", textAnchor="middle", fontSize=8, fontName="Helvetica-Bold"))
                histoire.append(schema_sw)
                continue
                
            elif "• Schéma de la théorie de Lasswell" in p_clean:
                histoire.append(Paragraph(p_clean, style_texte))
                schema_l = Drawing(520, 35)
                questions = ["Qui ?", "Dit quoi ?", "Quel canal ?", "À qui ?", "Quel effet ?"]
                x_pos = 10
                for i, q in enumerate(questions):
                    schema_l.add(Rect(x_pos, 5, 80, 22, fillColor=colors.HexColor("#EDF2F7"), strokeColor=colors.HexColor("#2B6CB0"), strokeWidth=1))
                    schema_l.add(String(x_pos + 40, 12, q, textAnchor="middle", fontSize=8, fillColor=colors.HexColor("#2B6CB0"), fontName="Helvetica-Bold"))
                    if i < 4:
                        schema_l.add(Line(x_pos + 80, 16, x_pos + 105, 16, strokeColor=colors.HexColor("#718096"), strokeWidth=1))
                    x_pos += 105
                histoire.append(schema_l)
                continue
            
            if est_titre_markdown or p_clean.startswith("PARTIE") or p_clean.startswith("TITRE") or p_clean.startswith("SECTION") or (p_clean.replace("<b>","").replace("</b>","").isupper() and len(p_clean) < 80):
                titre_final = p_clean.replace("<b>", "").replace("</b>", "")
                histoire.append(Paragraph(f"<b>{titre_final}</b>", style_intertitre))
            elif p_clean.upper().startswith("IMPORTANT") or p_clean.upper().startswith("DÉFINITION") or p_clean.upper().startswith("ATTENTION") or p_clean.startswith("💡") or p_clean.startswith("■"):
                p_encadre = p_clean.replace("■", "💡 ", 1) if p_clean.startswith("■") else p_clean
                histoire.append(Paragraph(p_encadre, style_encadre))
            else:
                histoire.append(Paragraph(p_clean, style_texte))
        
        histoire.append(Spacer(1, 15))
        histoire.append(Paragraph("<b>📊 SCHÉMA DE SYNTHÈSE : Processus d'Actualisation Continue</b>", style_intertitre))
        schema = Drawing(520, 50)
        schema.add(Rect(10, 10, 140, 30, fillColor=colors.HexColor("#2B6CB0"), strokeColor=None))
        schema.add(String(80, 20, "1. TEXTE ORIGINAL", textAnchor="middle", fillColor=colors.white, fontSize=9, fontName="Helvetica-Bold"))
        schema.add(Line(160, 25, 190, 25, strokeColor=colors.HexColor("#718096"), strokeWidth=2))
        schema.add(Rect(200, 10, 140, 30, fillColor=colors.HexColor("#319795"), strokeColor=None))
        schema.add(String(270, 20, "2. VEILLE JURIDIQUE", textAnchor="middle", fillColor=colors.white, fontSize=9, fontName="Helvetica-Bold"))
        schema.add(Line(350, 25, 380, 25, strokeColor=colors.HexColor("#718096"), strokeWidth=2))
        schema.add(Rect(390, 10, 120, 30, fillColor=colors.HexColor("#D69E2E"), strokeColor=None))
        schema.add(String(450, 20, "3. COURS ENRICHI", textAnchor="middle", fillColor=colors.white, fontSize=9, fontName="Helvetica-Bold"))
        histoire.append(schema)
        
        doc.build(histoire)
        time.sleep(2)  
        
        metadata_fichier = {'name': nom_fichier, 'parents': [ID_DOSSIER_DRIVE]}
        with open(nom_fichier, 'rb') as f_upload:
            media = MediaFileUpload(nom_fichier, mimetype='application/pdf', resumable=True)
            drive_service.files().create(body=metadata_fichier, media_body=media, fields='id').execute()
        
        time.sleep(1)
        if os.path.exists(nom_fichier):
            try: os.remove(nom_fichier)
            except: pass
            
        drive_service.files().update(fileId=id_original, body={'trashed': True}).execute()
        return f"Succès ! Le cours '{nom_fichier}' a été transformé."
    except Exception as e:
        if os.path.exists(nom_fichier):
            try: os.remove(nom_fichier)
            except: pass
        return f"Erreur : {str(e)}"

# =========================================================================
# 🎛️ 3. CORE LOGIC : FONCTION DE VEILLE & BOUCLE TEMPORELLE
# =========================================================================
def executer_session_de_veille():
    print("\n[ROUTINE] 🔍 Lancement de l'analyse des cours...")
    fichiers_a_traiter = scanner_dossier_drive()

    if not fichiers_a_traiter:
        print("[ROUTINE] 🎉 Parfait ! Tout est à jour dans le Drive.")
        return

    for f in fichiers_a_traiter:
        id_fichier = f.get('id')
        nom_fichier = f.get('name')
        
        texte_cours = lire_contenu_pdf(id_fichier)
        print(f"[ROUTINE] 🧠 Audit juridique par Groq pour : '{nom_fichier}'...")
        
        prompt_analyse = (
            f"Tu es un éminent professeur de droit français. Analyse le cours suivant :\n\n"
            f"--- DÉBUT DU COURS ---\n{texte_cours}\n--- FIN DU COURS ---\n\n"
            "Mission : Réécris ce texte pour le rendre conforme en 2026. Sers-toi de sources officielles."
        )
        
        try:
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt_analyse}],
                model="llama-3.1-8b-instant",
                temperature=0.1
            )
            texte_mis_a_jour = chat_completion.choices[0].message.content
            
            if texte_mis_a_jour and len(texte_mis_a_jour) > 100:
                resultat = modifier_et_remplacer_pdf(nom_fichier, texte_mis_a_jour, id_fichier)
                print(f"   ↳ {resultat}")
            else:
                print("   ⚠️ Alerte : Contenu renvoyé par Groq vide.")
            time.sleep(4)  
        except Exception as e:
            if "429" in str(e):
                print("\n⏳ Pause forcée de 30 secondes (Rate Limit)...")
                time.sleep(30)
            else:
                print(f"🚨 Erreur fichier : {e}")
                time.sleep(5)
    print("\n🎉 Session de veille achevée.")

def boucle_temporelle_de_veille():
    global DUREE_VEILLE_SECONDES, CHOIX_INTERVALLE, VEILLE_ACTIVE
    print("[SYSTEME] Gestionnaire de tâches d'arrière-plan démarré.")
    
    while VEILLE_ACTIVE:
        if CHOIX_INTERVALLE == "manual":
            time.sleep(2)
            continue
            
        temps_a_attendre = DUREE_VEILLE_SECONDES
        print(f"[SYSTEME] Attente planifiée : Prochain check dans {CHOIX_INTERVALLE}.")
        
        for _ in range(int(temps_a_attendre)):
            if not VEILLE_ACTIVE or CHOIX_INTERVALLE == "manual" or temps_a_attendre != DUREE_VEILLE_SECONDES:
                break
            time.sleep(1)
            
        if temps_a_attendre != DUREE_VEILLE_SECONDES or CHOIX_INTERVALLE == "manual":
            continue

        try: executer_session_de_veille()
        except Exception as e: print(f" Erreur boucle : {e}")

# =========================================================================
# 🌐 4. ROUTES API (SYNCHRONISATION ET ANALYSE MANUELLE)
# =========================================================================
@app.route('/api/schedule', methods=['POST', 'OPTIONS'])
def update_schedule():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
        
    global CHOIX_INTERVALLE, DUREE_VEILLE_SECONDES
    data = request.get_json()
    if not data or 'interval' not in data:
        return jsonify({"status": "error", "message": "Données incorrectes"}), 400
        
    laps_de_temps = data['interval']
    if laps_de_temps in CONVERTISSEUR_TEMPS:
        CHOIX_INTERVALLE = laps_de_temps
        DUREE_VEILLE_SECONDES = CONVERTISSEUR_TEMPS[laps_de_temps]
        print(f"\n[API] Nouvelle fréquence reçue : {CHOIX_INTERVALLE}")
        return jsonify({"status": "success", "message": "Fréquence synchronisée"}), 200
    return jsonify({"status": "error", "message": "Option inconnue"}), 400

@app.route('/api/analyze', methods=['POST', 'OPTIONS'])
def trigger_manual_analyze():
    """Intercepte le pré-flight OPTIONS et traite l'analyse forcée"""
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200
        
    print("\n[API] ⚡ Déclenchement forcé de l'analyse IA via l'interface web.")
    try:
        executer_session_de_veille()
        return jsonify({"status": "success", "message": "Analyse achevée !"}), 200
    except Exception as e:
        print(f"🚨 Erreur lors de l'analyse : {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    messages = data.get('messages', [])
    derniere_question = messages[-1]['content'] if messages else ""
    try:
        chat_completion = client.chat.completions.create(messages=[{"role": "user", "content": derniere_question}], model="llama-3.1-8b-instant")
        reponse_ia = chat_completion.choices[0].message.content
    except Exception as e: reponse_ia = f"Erreur : {e}"
    return jsonify({"choices": [{"message": {"role": "assistant", "content": reponse_ia}}]}), 200

if __name__ == '__main__':
    thread_veille = threading.Thread(target=boucle_temporelle_de_veille)
    thread_veille.daemon = True
    thread_veille.start()
    
    print("Serveur Flask disponible sur http://localhost:3000")
    app.run(host='0.0.0.0', port=3000, debug=False)