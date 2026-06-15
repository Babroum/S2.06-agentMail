import feedparser
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from groq import Groq
import re
import requests
import os 
from dotenv import load_dotenv

load_dotenv()  # Charger les variables d'environnement depuis le fichier .env


# --- Config ---

# Sources RSS de base (fallback)
FEEDS_RSS = [
    ("EducPros",              "https://www.letudiant.fr/educpros/rss.xml"),
    ("Le Monde Éco",          "https://www.lemonde.fr/economie/rss_full.xml"),
    ("Les Échos",             "https://www.lesechos.fr/rss/rss_une.xml"),
    ("The Conversation FR",   "https://theconversation.com/fr/articles.atom"),
    ("Cadremploi Actus",      "https://www.cadremploi.fr/rss/actualites.xml"),
]

# APIs de news (gratuit jusqu'à limites)
NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY")  # Gratuit, limité à 100 req/jour
NEWSAPI_URL = "https://newsapi.org/v2/everything"

# Bing News API (alternative, génère RSS dynamiquement)
def get_feeds_from_newsapi():
    """Récupère les articles via NewsAPI pour les mots-clés"""
    import requests
    feeds = []
    
    queries = [
        "économie France",
        "gestion entreprise", 
        "master MBA France",
        "éducation supérieure",
        "finance business",
        "startups entrepreneuriat",
        "transformation digitale",
        "management RH",
    ]
    
    for query in queries:
        try:
            response = requests.get(NEWSAPI_URL, params={
                "q": query,
                "language": "fr",
                "sortBy": "publishedAt",
                "apiKey": NEWSAPI_KEY,
                "pageSize": 5
            }, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("articles"):
                    feeds.append((f"NewsAPI: {query}", data.get("articles", [])))
                    print(f"✅ {len(data.get('articles', []))} articles trouvés pour '{query}'")
        except Exception as e:
            print(f"⚠️  Erreur NewsAPI pour '{query}': {e}")
    
    return feeds


def get_feeds_from_rss():
    """Récupère les flux RSS"""
    articles_par_sujet = []
    for nom, url in FEEDS_RSS:
        try:
            feed = feedparser.parse(url)
            articles = []
            for entry in feed.entries:
                texte = (entry.title + entry.get("summary", "")).lower()
                if any(mot in texte for mot in MOTS_CLES):
                    articles.append({
                        "title":   entry.title,
                        "link":    entry.link,
                        "summary": entry.get("summary", "")
                    })
                if len(articles) == 5:
                    break
            if articles:
                articles_par_sujet.append((nom, articles))
                print(f"✅ {len(articles)} articles trouvés dans {nom}")
        except Exception as e:
            print(f"⚠️  Erreur en parsant {nom}: {e}")
    return articles_par_sujet

EMAIL_EXPEDITEUR = os.environ.get("EMAIL_EXPEDITEUR")  # Récupéré depuis .env
EMAIL_MOT_DE_PASSE = os.environ.get("EMAIL_MOT_DE_PASSE")  # Récupéré depuis .env
DESTINATAIRES = [
    "kriegelgael@gmail.com",
    "frtombunce@gmail.com"
]

MOTS_CLES = [
    "master", "licence", "bachelor", "mba", "doctorat", "formation",
    "diplôme", "certification", "accréditation", "cursus",
    "université", "iae", "école de commerce", "grande école",
    "enseignement supérieur", "campus", "faculté",
    "économie", "gestion", "management", "finance", "comptabilité",
    "marketing", "ressources humaines", "stratégie", "entrepreneuriat",
    "fiscalité", "audit", "contrôle de gestion",
    "intelligence artificielle", "transition écologique", "numérique",
    "insertion professionnelle", "classement", "parcoursup",
    "réforme", "accréditation aacsb", "accréditation equis",
    "étudiant", "professeur", "chercheur", "recrutement", "entreprise",
]

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")  # Récupéré depuis .env

# --- Récupération et filtrage ---
def fetch_articles():
    """Combine NewsAPI + RSS"""
    print("\n🔍 Récupération des articles...\n")
    articles_par_sujet = []
    
    # 1. Essayer NewsAPI en premier (+ rapide, + moderne)
    print("📡 NewsAPI en cours...", flush=True)
    newsapi_feeds = get_feeds_from_newsapi()
    
    for nom, articles_list in newsapi_feeds:
        filtered = []
        for article in articles_list:
            texte = (article.get("title", "") + article.get("description", "")).lower()
            if any(mot in texte for mot in MOTS_CLES):
                filtered.append({
                    "title":   article.get("title", ""),
                    "link":    article.get("url", ""),
                    "summary": article.get("description", "")
                })
        if filtered:
            articles_par_sujet.append((nom, filtered[:4]))
    
    # 2. Complémenter avec RSS (pour la diversité)
    print("📰 RSS en cours...", flush=True)
    rss_feeds = get_feeds_from_rss()
    articles_par_sujet.extend(rss_feeds)
    
    print(f"\n✅ Total: {sum(len(a) for _, a in articles_par_sujet)} articles collectés\n")
    return articles_par_sujet

def summarize_with_groq(articles_par_sujet):
    client = Groq(api_key=GROQ_API_KEY)

    # Aplatir tous les articles
    tous_les_articles = []
    for nom, articles in articles_par_sujet:
        for article in articles:
            tous_les_articles.append({**article, "source": nom})

    if not tous_les_articles:
        print("❌ Aucun article trouvé")
        return []

    print(f"📚 {len(tous_les_articles)} articles à traiter...")

    content = "\n\n".join([
        f"[{i+1}] ({a['source']}) {a['title']}\n{a['summary'][:200]}"
        for i, a in enumerate(tous_les_articles)
    ])

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0,
            max_tokens=100,
            messages=[
                {
                    "role": "system",
                    "content": "Tu réponds UNIQUEMENT avec une liste de numéros d'articles séparés par des virgules. Ex: 1,3,5,7"
                },
                {
                    "role": "user",
                    "content": f"""Sélectionne les 4 articles les plus importants pour un étudiant en économie-gestion.

Retourne JUSTE les numéros séparés par des virgules, rien d'autre.

Articles:
{content}"""
                }
            ]
        )

        raw = response.choices[0].message.content.strip()
        print(f"🔍 Réponse brute de Groq: '{raw}'")

        # Parser robuste: cherche tous les nombres
        numeros = []
        matches = re.findall(r'\d+', raw)
        for match in matches:
            idx = int(match) - 1
            if 0 <= idx < len(tous_les_articles):
                numeros.append(idx)

        print(f"✅ Articles sélectionnés: {[i+1 for i in numeros[:4]]}")
        return [tous_les_articles[i] for i in numeros[:4]]

    except Exception as e:
        print(f"❌ Erreur Groq: {e}")
        return []


def generate_resume(article):
    """Génère 2-3 phrases de résumé via Groq (sans préambule)"""
    client = Groq(api_key=GROQ_API_KEY)
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            max_tokens=200,  # Augmenté pour éviter les coupures
            messages=[
                {
                    "role": "system",
                    "content": "IMPORTANT: Réponds UNIQUEMENT avec 2-3 phrases de résumé. ZÉRO préambule, ZÉRO introduction, ZÉRO explication. Juste le texte brut."
                },
                {
                    "role": "user",
                    "content": f"""Titre: {article['title']}

Contenu:
{article['summary'][:600]}

Résume en 2-3 phrases simples et directes."""
                }
            ]
        )
        
        raw = response.choices[0].message.content.strip()
        
        # Nettoyer les réponses parasites communes
        phrases_a_enlever = [
            r"^Voici.*?:\s*",
            r"^Résumé.*?:\s*",
            r"^En résumé.*?:\s*",
            r"^Article.*?:\s*",
            r"^Ce.*?parle de.*?:\s*",
            r"^\*\*[^*]+\*\*\s*",  # Texte en bold markdown
        ]
        
        for pattern in phrases_a_enlever:
            raw = re.sub(pattern, "", raw, flags=re.IGNORECASE)
        
        # Enlever les tirets ou points d'énumération au début
        raw = re.sub(r"^[-•*]\s*", "", raw)
        
        return raw.strip()
    
    except Exception as e:
        print(f"⚠️  Erreur résumé: {e}")
        # Fallback : premiers 150 caractères du contenu original
        return (article['summary'][:150] + "...").replace("<br>", " ").replace("<p>", "").replace("</p>", "")


def send_email(resultats):
    if not resultats:
        print("⚠️  Pas d'articles à envoyer")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "📰 Veille académique - Économie & Gestion"
    msg["From"]    = EMAIL_EXPEDITEUR
    msg["To"]      = ", ".join(DESTINATAIRES)

    html = "<html><body><h2>📰 Articles essentiels du jour</h2><hr>"
    for i, article in enumerate(resultats, 1):
        resume = generate_resume(article)
        html += f"""
        <p>
            <strong>[{i}] {article['title']}</strong><br>
            <small style="color: #666;">Source: {article['source']}</small><br>
            <p style="margin: 10px 0; line-height: 1.5;">{resume}</p>
            <a href="{article['link']}" style="color: #0066cc; text-decoration: none;">→ Lire l'article complet</a>
        </p>
        <hr>
        """
    html += "</body></html>"

    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_EXPEDITEUR, EMAIL_MOT_DE_PASSE)
            server.sendmail(EMAIL_EXPEDITEUR, DESTINATAIRES, msg.as_string())
            print(f"✉️  Email envoyé à {len(DESTINATAIRES)} destinataire(s)")
    except Exception as e:
        print(f"❌ Erreur email: {e}")

# --- Main ---
print("🚀 Démarrage de la veille...")
articles_par_sujet = fetch_articles()

if not articles_par_sujet:
    print("❌ Aucun flux accessible")
    exit()

resultats = summarize_with_groq(articles_par_sujet)

if resultats:
    send_email(resultats)
else:
    print("⚠️  Groq n'a rien sélectionné")
