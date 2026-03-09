import pytest

# Prise en charge de l'import selon que pytest est lancé depuis la racine ou depuis le dossier `backend`
try:
    from llm_service import analyser_texte
except ImportError:
    from backend.llm_service import analyser_texte

# ============================================================================== #
# TESTS D'ÉVALUATION LLM (Vertex AI) - AUCUN MOCK
# Attention : Ces tests font de VRAIS appels réseaux à Gemini.
# Ils testent la qualité des prompts, la pertinence du modèle et sa ponctualité.
# L'API étant non-déterministe, les assertions sont volontairement souples.
# ============================================================================== #

def test_llm_bruit():
    """
    Cas "Bruit" : Entrée valant "RAS" ou "ok".
    Assertion : Le résultat doit être une liste vide `[]`.
    Idéal pour valider que le modèle ne force pas l'invention d'aspects.
    """
    mots_bruit = ["RAS", "ok"]
    
    for texte in mots_bruit:
        resultat = analyser_texte(texte)
        
        # Assertion structurelle
        assert isinstance(resultat, list), f"Le modèle aurait dû renvoyer une liste pour '{texte}'."
        
        # Assertion IA
        assert len(resultat) == 0, f"Le texte de bruit '{texte}' a généré un feedback inattendu : {resultat}"


def test_llm_sarcasme():
    """
    Cas "Sarcasme" : Phrase cynique dont le sens profond est fortement négatif.
    Assertion : La liste ne doit pas être vide, et le score doit être inférieur à 0.
    """
    texte = "Génial, la livraison a pris 3 semaines, changez rien les gars 👍"
    resultat = analyser_texte(texte)
    
    # On garantit d'abord que le modèle a répondu quelque chose
    assert len(resultat) > 0, "Le modèle n'a extrait aucun aspect du texte sarcastique (ou plantage réseau)."
    
    # On vérifie la logique (compréhension du sentiment).
    # Même s'il a généré plusieurs mots exacts, au moins un d'eux doit cibler le sentiment final négatif.
    scores_negatifs = [aspect["score"] for aspect in resultat if aspect.get("score", 0) < 0]
    
    assert len(scores_negatifs) > 0, (
        f"Le modèle a mal interprété le sarcasme et n'a détecté aucun score négatif. "
        f"Résultat brut : {resultat}"
    )


def test_llm_double_aspect_oppose():
    """
    Cas "Double aspect opposé" : Phrase contenant du positif (téléphone) et du négatif (batterie).
    Assertion : Au moins 2 éléments, dont l'un a un score > 0 et l'autre un score < 0.
    """
    texte = "Le téléphone est magnifique, mais la batterie se vide en 2 heures"
    resultat = analyser_texte(texte)
    
    # Le modèle peut séparer en plusieurs éléments, on s'attend à en avoir au moins 2.
    assert len(resultat) >= 2, f"Le modèle n'a pas scindé les aspects. Il n'a trouvé que : {resultat}"
    
    # Extraction des scores pour simplifier l'assertion
    scores = [aspect.get("score", 0) for aspect in resultat]
    
    a_du_positif = any(score > 0 for score in scores)
    a_du_negatif = any(score < 0 for score in scores)
    
    # Pour ne pas coincer sur un simple mot ("téléphone" vs "design"), on valide simplement la logique polaire
    assert a_du_positif, f"Le modèle n'a pas détecté l'aspect positif (téléphone magnifique). Tous les scores : {scores}"
    assert a_du_negatif, f"Le modèle n'a pas détecté l'aspect négatif (batterie faible). Tous les scores : {scores}"


def test_llm_structure_json():
    """
    Cas "Structure JSON" : Vérifie la robustesse du prompt face aux consignes de typage.
    Assertion : Présence de 'categorie_macro', 'aspect_exact', 'score', et type int pour le score.
    """
    texte = "Bon produit"
    resultat = analyser_texte(texte)
    
    assert len(resultat) > 0, "Réponse vide inattendue."
    
    cles_attendues = {"categorie_macro", "aspect_exact", "score"}
    
    for aspect in resultat:
        # Vérification des clés rigoureuses
        assert set(aspect.keys()) == cles_attendues, (
            f"Les clés extraites ne correspondent pas à l'attente. "
            f"Clés présentes : {list(aspect.keys())}"
        )
        
        # Le prompt oblige un "entier". On vérifie que c'est bien respecté au moment du json.loads.
        score = aspect["score"]
        assert isinstance(score, int), f"Le score n'est pas un entier (type reçu: {type(score)}). Valeur: {score}"
        
        # Vérification optionnelle de contrainte métier
        assert -5 <= score <= 5, f"LLM hors contrainte d'échelle (-5, 5). Score reçu: {score}"


def test_reutilisation_categories():
    """
    Cas "Réutilisation de catégories" : Vérifie la capacité de l'IA à utiliser un registre imposé.
    Assertion : Ne pas inventer de catégories génériques (livraison, prix) quand des catégories
    correspondantes existent déjà ("logistique_externe", "politique_tarifaire").
    """
    categories_fournies = ["logistique_externe", "politique_tarifaire"]
    texte = "Le colis est arrivé en retard et c'était vraiment trop cher pour ce que c'est."
    
    resultat = analyser_texte(texte, categories_existantes=categories_fournies)
    
    assert len(resultat) > 0, "Le modèle n'a extrait aucun aspect."
    
    categories_utilisees = [aspect.get("categorie_macro", "") for aspect in resultat]
    
    # On s'attend à ce que le modèle ait compris le rapprochement de sens
    assert "logistique_externe" in categories_utilisees, (
        f"Le modèle n'a pas réutilisé la catégorie 'logistique_externe'. "
        f"Catégories générées : {categories_utilisees}"
    )
    
    assert "politique_tarifaire" in categories_utilisees, (
        f"Le modèle n'a pas réutilisé la catégorie 'politique_tarifaire'. "
        f"Catégories générées : {categories_utilisees}"
    )
    
    # Et on s'assure qu'il n'a pas mis les termes classiques
    mots_interdits = ["livraison", "prix", "retard", "cher"]
    for mot in mots_interdits:
        assert mot not in categories_utilisees, (
            f"Le modèle a inventé la catégorie générique '{mot}' au lieu d'utiliser celles fournies."
        )

