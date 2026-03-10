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


# --- PHASE 2 : REDUCE (Embeddings → KMeans → Labellisation LLM) ---

from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
import numpy as np
import logging

# Chargement du modèle d'embeddings (une seule fois au niveau du module)
logging.info("[REDUCE] Chargement du modèle d'embeddings all-MiniLM-L6-v2...")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
logging.info("[REDUCE] Modèle d'embeddings chargé ✓")

MAX_CLUSTERS = 7  # Nombre maximum de catégories macro


def _labelliser_cluster(mots_du_cluster: list[str]) -> str:
    """
    Fait un appel LLM très simple pour nommer un cluster de mots-clés.
    Retourne un nom de catégorie en UN seul mot, minuscules, sans accents.
    """
    mots_str = ", ".join(mots_du_cluster)
    
    prompt = f"""
    Voici des mots-clés extraits d'avis clients qui parlent tous de la même thématique :
    [{mots_str}]
    
    Donne-moi UN SEUL MOT générique (en minuscules, sans accents) qui résume ce groupe.
    Exemples de bons noms : "tarifs", "livraison", "application", "securite", "technique", "service".
    
    Réponds UNIQUEMENT avec le mot, rien d'autre. Format JSON : {{"label": "ton_mot"}}
    """
    
    try:
        response = model.generate_content(
            prompt,
            generation_config=GenerationConfig(temperature=0.0, response_mime_type="application/json")
        )
        result = json.loads(response.text)
        return result.get("label", "divers").lower().strip()
    except Exception as e:
        print(f"[ERREUR LABELLISATION] {e}")
        return "divers"


def generer_taxonomie(liste_aspects_bruts: list[str]) -> dict:
    """
    Phase REDUCE hybride : Embeddings → KMeans → Labellisation LLM.
    
    1. Vectorise les aspects bruts avec sentence-transformers (all-MiniLM-L6-v2).
    2. Regroupe les vecteurs en N clusters avec KMeans (N ≤ MAX_CLUSTERS).
    3. Pour chaque cluster, demande au LLM de nommer la catégorie en UN mot.
    4. Retourne { "aspect_brut": "categorie_macro", ... }
    """
    if not liste_aspects_bruts:
        return {}

    # --- Étape 0 : Dédoublonnage ---
    aspects_uniques = list(set(liste_aspects_bruts))
    logging.info(f"[REDUCE] {len(aspects_uniques)} aspects uniques à clusteriser.")

    # Cas trivial : très peu d'aspects — un seul cluster suffit
    if len(aspects_uniques) == 1:
        label = _labelliser_cluster(aspects_uniques)
        return {aspects_uniques[0]: label}

    # --- Étape 1 : Vectorisation (Embeddings) ---
    logging.info("[REDUCE] Étape 1/3 : Vectorisation des aspects (embeddings)...")
    embeddings = embedding_model.encode(aspects_uniques, show_progress_bar=False)

    # --- Étape 2 : Clustering KMeans ---
    n_clusters = min(MAX_CLUSTERS, len(aspects_uniques))
    logging.info(f"[REDUCE] Étape 2/3 : Clustering KMeans en {n_clusters} groupes...")
    
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings)

    # Regrouper les aspects par cluster
    clusters: dict[int, list[str]] = {}
    for i, aspect in enumerate(aspects_uniques):
        cluster_id = int(labels[i])
        clusters.setdefault(cluster_id, []).append(aspect)

    logging.info(f"[REDUCE] {len(clusters)} clusters créés : {[len(v) for v in clusters.values()]} éléments chacun.")

    # --- Étape 3 : Labellisation LLM par cluster ---
    logging.info("[REDUCE] Étape 3/3 : Labellisation LLM de chaque cluster...")
    taxonomie_finale = {}

    for cluster_id, mots_du_cluster in clusters.items():
        label = _labelliser_cluster(mots_du_cluster)
        logging.info(f"  → Cluster {cluster_id} ({len(mots_du_cluster)} mots) → \"{label}\"")
        
        for aspect in mots_du_cluster:
            taxonomie_finale[aspect] = label

    logging.info(f"[REDUCE] Taxonomie générée : {len(set(taxonomie_finale.values()))} catégories macro finales.")
    return taxonomie_finale