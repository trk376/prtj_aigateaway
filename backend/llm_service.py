import warnings
warnings.filterwarnings("ignore")

import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
import json
import asyncio

PROJECT_ID = "aigateaway" 
LOCATION = "us-central1"

vertexai.init(project=PROJECT_ID, location=LOCATION)
model = GenerativeModel("gemini-2.5-flash")

# ============================================================================
# ANCIENNE FONCTION (synchrone / unitaire) [Conservée pour rétrocompatibilité]
# ============================================================================
def analyser_texte(texte: str, categories_existantes: list = None) -> list:
    if not texte or len(texte.strip()) == 0:
        return []

    texte_tronque = texte[:2000]

    prompt_systeme = """
    Tu es un expert intraitable en analyse sémantique de feedback client. 
    Pour le texte fourni, extrais les thèmes abordés. 
    Le format de réponse DOIT être un tableau JSON strict contenant des objets avec 3 clés :
    - "categorie_macro" : le grand thème du feedback.
    - "aspect_exact" : le mot exact utilisé par le client.
    - "score" : un entier entre -5 (très négatif) et 5 (très positif), 0 étant neutre.
    
    Si le texte ne contient aucun retour pertinent, renvoie un tableau vide [].
    """

    if categories_existantes:
        categories_str = ", ".join([f'"{c}"' for c in categories_existantes])
        prompt_systeme += f"""
        
    =========================================
    RÈGLES CRITIQUES DE MATCHING SÉMANTIQUE :
    =========================================
    Voici la liste des catégories qui existent DÉJÀ dans notre base de données :
    [{categories_str}]

    AVANT de définir la "categorie_macro" d'un aspect extrait, tu DOIS te poser cette question :
    "Est-ce qu'un synonyme, une variante orthographique (singulier/pluriel, majuscule/minuscule, accentuation), ou un concept extrêmement proche existe déjà dans la liste fournie ?"
    
    1. Si l'évaluation sémantique est OUI :
       IL T'EST STRICTEMENT INTERDIT DE CRÉER UNE NOUVELLE CATÉGORIE.
       Tu DOIS recopier la chaîne de caractères EXACTE telle qu'écrite dans la liste fournie.
       
    2. Si l'évaluation sémantique est NON :
       Tu es autorisé à inventer une nouvelle "categorie_macro" claire et concise.
    """

    prompt = f"{prompt_systeme}\n\nTexte à analyser :\n{texte_tronque}"

    generation_config = GenerationConfig(
        temperature=0.1,
        response_mime_type="application/json",
    )

    try:
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[ERREUR VERTEX AI] L'extraction a échoué : {e}")
        return []

# ============================================================================
# NOUVELLE ARCHITECTURE MAP-REDUCE
# ============================================================================

from concurrent.futures import ThreadPoolExecutor

# --- PHASE 1 : MAP (Extraction brute multithreadée) ---
def analyser_texte_brut(texte: str) -> list[dict]:
    """Extrait uniquement les aspects et scores d'un texte, sans macro-catégorie."""
    if not texte or len(texte.strip()) == 0:
        return []

    prompt = f"""
    Extrais les aspects abordés dans ce feedback, ainsi que le sentiment associé.
    Ne crée PAS de 'categorie_macro'.
    
    Format JSON de réponse exigé :
    [
      {{
        "aspect_exact": "le mot ou l'expression exacte du client",
        "score": entier de -5 à +5
      }}
    ]
    Si aucun aspect pertinent, renvoie [].
    
    Texte :
    {texte[:2000]}
    """
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=GenerationConfig(temperature=0.1, response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[ERREUR THREAD AI] {e}")
        return []

def extraire_aspects_batch(avis_batch: list[dict]) -> dict:
    """
    Prend une liste de dict `[{"id": "...", "texte": "..."}]`.
    Utilise `ThreadPoolExecutor` pour envoyer les appels à Vertex AI en parallèle.
    Retourne un dictionnaire { "id_avis": [liste_extractions] }.
    """
    resultats = {}
    
    def traiter_un_avis(avis):
        extractions = analyser_texte_brut(avis["texte"])
        return avis["id"], extractions

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(traiter_un_avis, avis): avis for avis in avis_batch}
        for future in futures:
            fb_id, extractions = future.result()
            resultats[fb_id] = extractions
            
    return resultats


# --- PHASE 2 : REDUCE (Création de la taxonomie unifiée) ---
def generer_taxonomie(liste_aspects_bruts: list[str]) -> dict:
    """
    Prend tous les 'aspect_exact' extraits du batch, et fait un seul appel LLM
    pour les mapper vers des 'categorie_macro' unifiées.
    """
    if not liste_aspects_bruts:
        return {}
        
    # On déduplique la liste Python brute avant envoi
    aspects_uniques = list(set(liste_aspects_bruts))
    
    prompt = f"""
    Voici une liste d'aspects bruts extraits de feedbacks clients :
    {json.dumps(aspects_uniques, ensure_ascii=False)}
    
    TA TÂCHE : Regrouper ces aspects bruts sous des 'categorie_macro' unifiées.
    - Les 'categorie_macro' doivent être génériques (ex: "livraison", "prix", "application_mobile", "service_client").
    - Elles doivent être écrites en minuscules, sans accents de préférence.
    
    Format JSON de réponse exigé (un dictionnaire qui mappe chaque aspect brut EXACT à sa macro-catégorie) :
    {{
       "aspect brut 1": "categorie_macro",
       "aspect brut 2": "categorie_macro"
    }}
    Ne modifie SURTOUT PAS les clés (les aspects bruts), elles doivent correspondre exactement à l'entrée.
    """
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=GenerationConfig(temperature=0.0, response_mime_type="application/json")
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"[ERREUR TAXONOMIE AI] {e}")
        return {}