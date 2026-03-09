import pytest
from unittest.mock import patch

# Le client et la db_connection sont automatiquement injectés par Pytest grâce aux fixtures
# définies dans conftest.py (il suffit de les déclarer en arguments de la fonction).

def test_get_top_flaws(client, db_connection):
    """
    Test d'intégration de la route GET /api/top-flaws.
    Vérifie le calcul (HAVING volume >= 5, moyenne) et le format de la réponse.
    """
    # 1. PRÉPARATION (Arrange) : Insertion de données fictives dans notre DB SQLite en mémoire
    cursor = db_connection.cursor()
    cursor.execute("INSERT INTO feedbacks (id, texte_brut) VALUES ('F1', 'test_requetes')")
    
    # La requête api pose une condition STRICTE (HAVING volume >= 5).
    # Il faut au moins 5 lignes de la catégorie 'livraison'
    for _ in range(5):
        cursor.execute("""
            INSERT INTO aspects_analyses (feedback_id, categorie_macro, aspect_exact, score)
            VALUES ('F1', 'livraison', 'colis abîmé', -4)
        """)
        
    # Insérons également 5 avis de 'produit' (positifs = score 3) pour tester le tri croissant.
    for _ in range(5):
        cursor.execute("""
            INSERT INTO aspects_analyses (feedback_id, categorie_macro, aspect_exact, score)
            VALUES ('F1', 'produit', 'belle qualité', 3)
        """)
        
    db_connection.commit() # Important, sinon FastAPI n'y verra rien
    
    # 2. ACTION (Act) : Appel HTTP vers l'API sans l'allumer (TestClient)
    response = client.get("/api/top-flaws")
    
    # 3. VERIFICATION (Assert) : Contrôle des résultats
    assert response.status_code == 200
    data = response.json()
    
    assert len(data) == 2, "La route doit renvoyer nos 2 catégories macro qualifiées"
    
    # Vérification strict du tri (la pire catégorie en premier) 
    # score moyen 'livraison' = -4.0, volume = 5
    assert data[0]["categorie_macro"] == "livraison"
    assert float(data[0]["score_moyen"]) == -4.0
    assert data[0]["volume"] == 5
    
    # score moyen 'produit' = 3.0, volume = 5
    assert data[1]["categorie_macro"] == "produit"
    assert float(data[1]["score_moyen"]) == 3.0


# Préparation du chemin pour le mock LLM selon le contexte (root vs backend directory)
try:
    import llm_service
    target_mock_llm = "llm_service.analyser_texte"
except ImportError:
    target_mock_llm = "backend.llm_service.analyser_texte"

@patch(target_mock_llm)
def test_analyser_texte_est_moke_sans_frais(mock_analyser):
    """
    Test unitaire illustrant le Mock d'un appel API externe Vertex AI coûteux.
    La vraie fonction 'analyser_texte' n'est jamais exécutée pendant ce test.
    """
    # 1. PRÉPARATION : On configure la fausse réponse que le MOCK retournera
    # quand n'importe qui l'appellera.
    mock_analyser.return_value = [
        {"categorie_macro": "prix", "aspect_exact": "trop cher", "score": -3}
    ]
    
    # 2. ACTION : On exécute du code qui appelle le service LLM
    try:
        from llm_service import analyser_texte
    except ImportError:
        from backend.llm_service import analyser_texte
        
    # Ce n'est pas le vrai service qui est appelé, mais notre mock
    resultat = analyser_texte("Le produit est super cher par rapport à la concurrence.")
    
    # 3. VERIFICATION
    # On garantit que notre code a bien simulé la transmission du message exact au service tier.
    mock_analyser.assert_called_once_with("Le produit est super cher par rapport à la concurrence.")
    
    # Et on s'assure que le pipeline de retour est conforme
    assert len(resultat) == 1
    assert resultat[0]["categorie_macro"] == "prix"
    assert resultat[0]["score"] == -3
