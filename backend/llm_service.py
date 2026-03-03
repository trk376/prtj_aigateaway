import warnings
warnings.filterwarnings("ignore") # Cache le spam des FutureWarning de Python 3.10

import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
import json

# Configuration Vertex AI
PROJECT_ID = "aigateaway" 
LOCATION = "us-central1" # Région où le modèle est garanti d'être dispo

# Initialisation
vertexai.init(project=PROJECT_ID, location=LOCATION)
model = GenerativeModel("gemini-2.5-flash") # Version stable générique

def analyser_texte(texte: str) -> list:
    if not texte or len(texte.strip()) == 0:
        return []

    texte_tronque = texte[:2000]

    prompt_systeme = """
    Tu es un expert en analyse de feedback client. 
    Pour le texte fourni, extrais les thèmes abordés. 
    Le format de réponse DOIT être un tableau JSON strict contenant des objets avec 3 clés :
    - "categorie_macro" : le grand thème (ex: "livraison", "produit", "service_client", "prix").
    - "aspect_exact" : le mot exact utilisé par le client.
    - "score" : un entier entre -5 (très négatif) et 5 (très positif), 0 étant neutre.
    
    Si le texte ne contient aucun retour pertinent, renvoie un tableau vide [].
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

# --- ZONE DE TEST LOCAL ---
if __name__ == "__main__":
    print("🚀 Lancement du test Vertex AI (Gemini)...\n")
    
    texte_test = "La livraison a été catastrophique, le facteur m'a jeté le carton ! Par contre, la qualité de ce produit est excellente."
    print(f"Texte : '{texte_test}'\n")
    
    resultat = analyser_texte(texte_test)
    print(f"Résultat : {json.dumps(resultat, indent=2, ensure_ascii=False)}\n")