import os
import io
import json
import time
import pickle
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
# 1. CONFIGURATION ET CONNEXION AUX APIS
# =========================================================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY") 
ID_DOSSIER_DRIVE = os.environ.get("ID_DOSSIER_DRIVE") 

# Initialisation du client Groq
client = Groq(api_key=GROQ_API_KEY)

# Droits d'accès requis pour manipuler les fichiers du dossier Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive']
creds = None

print("🚀 Démarrage de l'agent de veille et mise à niveau continue (Version Rigueur & Design)...")

# Gestion automatique de l'authentification OAuth2 Google Drive via token permanent
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
            print("❌ Erreur : Le fichier 'client_secret.json' est introuvable dans le dossier du projet.")
            exit(1)
        flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
        creds = flow.run_local_server(port=0)
        
    with open('token.pickle', 'wb') as token:
        pickle.dump(creds, token)

# Création du point d'entrée vers les services Google Drive
drive_service = build('drive', 'v3', credentials=creds)


# =========================================================================
# 2. ACTIONS MÉTIERS (OUTILS EXÉCUTÉS PAR LE SCRIPT PYTHON)
# =========================================================================

def scanner_dossier_drive():
    """Scanne l'intégralité du dossier Drive ciblé à la recherche de PDF à analyser."""
    print("[Outil] Scan complet du dossier Google Drive...")
    query = f"'{ID_DOSSIER_DRIVE}' in parents and mimeType='application/pdf' and trashed=false"
    try:
        resultats = drive_service.files().list(q=query, fields="files(id, name)").execute()
        fichiers = resultats.get('files', [])
        print(f"   ↳ Fichiers détectés dans le dossier : {json.dumps(fichiers)}")
        return fichiers
    except Exception as e:
        print(f"❌ Erreur lors du scan du Drive : {e}")
        return []


def lire_contenu_pdf(file_id):
    """Télécharge temporairement le PDF depuis le Drive et en extrait le texte brut."""
    print(f"[Outil] Extraction et lecture du texte du PDF (ID: {file_id})...")
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
        # Extraction limitée aux 10 premières pages pour s'adapter au contexte de l'IA
        for page in lecteur_pdf.pages[:10]:
            texte_total += page.extract_text() or ""
        
        return texte_total[:8000] # Découpage de sécurité à 8000 caractères
    except Exception as e:
        return f"Erreur lors de la lecture du fichier : {str(e)}"


def modifier_et_remplacer_pdf(nom_fichier, nouveau_contenu_texte, id_original):
    """Génère localement un PDF hautement stylisé et pédagogique, puis remplace l'ancien sur le Drive."""
    print(f"[Outil] Modélisation graphique du PDF enrichi : {nom_fichier}...")
    
    try:
        # 1. Préparation du document local et marges de page
        doc = SimpleDocTemplate(nom_fichier, pagesize=letter, rightMargin=45, leftMargin=45, topMargin=45, bottomMargin=45)
        styles = getSampleStyleSheet()
        
        # Charte graphique : Palette de couleurs bleu académique et gris ardoise texturé
        style_titre = ParagraphStyle(
            name='Titre_Pedago', 
            parent=styles['Heading1'], 
            fontSize=22, 
            leading=26, 
            textColor=colors.HexColor("#1A365D"), 
            spaceAfter=6,
            alignment=1 
        )
        
        style_intertitre = ParagraphStyle(
            name='Intertitre_Pedago', 
            parent=styles['Heading2'], 
            fontSize=13, 
            leading=17, 
            textColor=colors.HexColor("#2C5282"), 
            spaceBefore=14,
            spaceAfter=8,
            keepWithNext=True
        )
        
        style_texte = ParagraphStyle(
            name='Texte_Pedago', 
            parent=styles['Normal'], 
            fontSize=10.5, 
            leading=15, 
            textColor=colors.HexColor("#2D3748"), 
            spaceAfter=8
        )
        
        style_encadre = ParagraphStyle(
            name='Encadre_Pedago', 
            parent=styles['Normal'], 
            fontSize=10, 
            leading=14, 
            textColor=colors.HexColor("#2C5282"),
            backColor=colors.HexColor("#EBF8FF"), 
            borderColor=colors.HexColor("#3182CE"), 
            borderWidth=1,
            borderPadding=8,
            spaceBefore=10,
            spaceAfter=10
        )
        
        histoire = []
        
        # --- BLOC EN-TÊTE / DESIGN DU TITRE PRINCIPAL ---
        nom_propre = nom_fichier.replace('.pdf', '').replace('MAJ_', '').replace('_', ' ').title()
        histoire.append(Paragraph(f"<b>FICHE DE SYNTHÈSE : {nom_propre}</b>", style_titre))
        
        # Dessin géométrique d'une ligne de séparation sous le titre principal
        ligne_titre = Drawing(520, 10)
        ligne_titre.add(Line(0, 5, 520, 5, strokeColor=colors.HexColor("#3182CE"), strokeWidth=2))
        histoire.append(ligne_titre)
        histoire.append(Spacer(1, 15))
        
        # --- PARCOURS ET RENDU INTELLIGENT DU TEXTE ENRICHI ---
        paragraphes = nouveau_contenu_texte.split('\n')
        for p in paragraphes:
            p_strip = p.strip()
            if not p_strip:
                continue
            
            p_clean = p_strip.replace('& ', '&amp; ') # Évite les conflits de caractères HTML
            
            # CORRECTION TECHNIQUE : Conversion automatique du Markdown (**) en balises HTML ReportLab (<b>)
            while "**" in p_clean:
                p_clean = p_clean.replace("**", "<b>", 1)
                p_clean = p_clean.replace("**", "</b>", 1)
                
            # Remplacement des puces Markdown classiques par un caractère spécial plus élégant
            if p_clean.startswith("* "):
                p_clean = p_clean.replace("* ", "• ", 1)
                
            # --- SECTEUR DE BLINDAGE ANTI-BUG : BALISES ORPHELINES ---
            # Si l'IA ouvre une balise sans la refermer en fin de ligne, Python la ferme de force
            if p_clean.count("<b>") > p_clean.count("</b>"):
                p_clean += "</b>"
            if p_clean.count("<u>") > p_clean.count("</u>"):
                p_clean += "</u>"
            
            # Détection automatique des rubriques du plan pour appliquer les titres
            if p_clean.startswith("PARTIE") or p_clean.startswith("TITRE") or p_clean.startswith("SECTION") or (p_clean.replace("<b>","").replace("</b>","").isupper() and len(p_clean) < 80):
                titre_final = p_clean.replace("<b>", "").replace("</b>", "")
                histoire.append(Paragraph(f"<b>{titre_final}</b>", style_intertitre))
                
            # Détection des mots magiques de l'IA pour créer les encadrés d'alertes visuelles
            elif p_clean.upper().startswith("IMPORTANT") or p_clean.upper().startswith("DÉFINITION") or p_clean.upper().startswith("ATTENTION") or p_clean.startswith("💡"):
                histoire.append(Paragraph(p_clean, style_encadre))
                
            else:
                histoire.append(Paragraph(p_clean, style_texte))
        
        histoire.append(Spacer(1, 15))
        
        # --- COMPOSANT GRAPHIQUE AUTOMATIQUE : SCHÉMA DE SYNTHÈSE DES INFOS ---
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
        
        # Compilation physique du PDF localement sur le disque dur
        doc.build(histoire)
        time.sleep(2)  
        
        # 2. Envoi de la nouvelle mouture enrichie sur Google Drive
        print(f"[Outil] Téléversement de la fiche actualisée vers Google Drive...")
        metadata_fichier = {
            'name': nom_fichier, 
            'parents': [ID_DOSSIER_DRIVE]
        }
        
        with open(nom_fichier, 'rb') as f_upload:
            media = MediaFileUpload(nom_fichier, mimetype='application/pdf', resumable=True)
            drive_service.files().create(body=metadata_fichier, media_body=media, fields='id').execute()
        
        time.sleep(1)

        # 3. Libération de l'espace et nettoyage du fichier temporaire sur Windows
        if os.path.exists(nom_fichier):
            try: os.remove(nom_fichier)
            except: pass
            
        # 4. Suppression immédiate de la version périmée (Mise à la corbeille)
        print(f"[Outil] Envoi de l'ancienne version obsolète à la corbeille (ID: {id_original})...")
        drive_service.files().update(fileId=id_original, body={'trashed': True}).execute()
        
        return f"Succès ! Le cours '{nom_fichier}' a été transformé en fiche pédagogique à jour."
        
    except Exception as e:
        print(f"Détail de l'erreur interceptée : {e}")
        if os.path.exists(nom_fichier):
            try: os.remove(nom_fichier)
            except: pass
        return f"Erreur lors de la construction du fichier stylisé : {str(e)}"


# =========================================================================
# 3. CONTRÔLEUR CENTRAL ET AUTOMATION DE L'AGENT INDÉPENDANT
# =========================================================================

fichiers_a_traiter = scanner_dossier_drive()

if not fichiers_a_traiter:
    print("\n🎉 Parfait ! Tous tes fichiers sont à jour. Aucun travail requis pour cette session.")
else:
    for f in fichiers_a_traiter:
        id_fichier = f.get('id')
        nom_fichier = f.get('name')
        
        texte_cours = lire_contenu_pdf(id_fichier)
        
        print(f"\n🧠 Audit juridique en cours par l'IA pour : '{nom_fichier}'...")
        
        prompt_analyse = (
            f"Tu es un éminent professeur de droit français, doublé d'un juriste d'une rigueur absolue. Analyse le cours suivant :\n\n"
            f"--- DÉBUT DU COURS ---\n{texte_cours}\n--- FIN DU COURS ---\n\n"
            "MISSION COMPLÈTE INDISPENSABLE :\n"
            "Réécris entièrement ce texte pour le rendre conforme à la législation et à la jurisprudence en vigueur en 2026. "
            "Chaque modification doit impérativement s'appuyer sur des sources officielles, vérifiées et incontestables du droit positif français.\n\n"
            "EXIGENCE DE SOURÇAGE OFFICIEL :\n"
            "1. Tu devez obligatoirement citer l'article précis du code concerné (ex: Code civil, Code de l'organisation judiciaire) pour justifier chaque mise à jour.\n"
            "2. Pour les réformes, cite explicitement le texte officiel d'origine (ex: 'en vertu de l'ordonnance n° 2016-131 du 10 février 2016' ou 'loi n° 2019-222 du 23 mars 2019').\n"
            "3. Il est strictement interdit d'inventer des lois, des numéros d'articles ou des dates. Si tu as un doute sur une source ou un numéro d'article précis, conserve la structure générale mais appuie-toi exclusivement sur des concepts juridiques avérés et vérifiables sur Légifrance.\n\n"
            "DIRECTIVES DE STRUCTURATION GÉOMÉTRIQUE :\n"
            "1. Utilise systématiquement la syntaxe Markdown standard **...** pour mettre en GRAS les termes techniques essentiels, dates fondamentales ou concepts pivots (ex: **Tribunal Judiciaire**, **effet rétroactif**).\n"
            "2. Utilise impérativement la balise <u>...</u> pour SOULIGNER toutes les mentions de sources officielles, d'articles légaux ou de grands arrêts (ex: <u>Article 1112-1 du Code civil</u>).\n"
            "3. ISOLEMENT DES NOTIONS CLÉS : Dès que tu rédiges une définition académique primordiale, un point de jurisprudence crucial ou un rappel de loi impératif, débute EXCLUSIVEMENT le paragraphe par le mot '💡 DÉFINITION:' ou '💡 IMPORTANT:' pour provoquer un encadré graphique.\n"
            "4. Rigueur absolue : Préserve intégralement la structure interne (titres, sous-sections, plan détaillé). Ne résume rien.\n"
            "5. Chasse aux anomalies : Convertis les Francs en Euros, supprime les références aux tribunaux d'instance/TGI au profit du Tribunal Judiciaire, intègre les règles modernes du droit des obligations.\n"
            "6. Interdiction : Ne fais absolument aucun ajout ou commentaire au sujet de l'intelligence artificielle ou du monde informatique.\n"
            "7. Production directe : Rends uniquement le texte formaté de la leçon. Pas de préambule de politesse."
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
                print("   ⚠️ Alerte : Contenu renvoyé par Groq vide ou incomplet. Document d'origine préservé.")
                
            time.sleep(4)  
            
        except Exception as e:
            msg_erreur = str(e)
            if "429" in msg_erreur:
                print("\n⏳ [Limite de requêtes atteinte] Pause forcée de l'agent pendant 30 secondes...")
                time.sleep(30)
            else:
                print(f"🚨 Erreur lors de la mise à jour du fichier : {e}")
                time.sleep(5)

print("\n🎉 Session de veille clôturée avec succès. Tous les fichiers cibles ont été vérifiés.")