from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
import sqlite3

# Création de l'application FastAPI
app = FastAPI(title="Feedbacks Dashboard API")

# 1. CONTRAINTE : Configuration CORS OBLIGATOIRE
# Permet au front-end React (qui tourne sur un autre port, ex: localhost:3000) 
# de faire des requêtes vers FastAPI sans être bloqué par le navigateur.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Autorise toutes les origines
    allow_credentials=True,
    allow_methods=["*"],  # Autorise toutes les méthodes (GET, POST...)
    allow_headers=["*"],  # Autorise tous les headers
)

DATABASE_NAME = "data/database.db"

def get_db_connection():
    """
    Ouvre et retourne une connexion à la base de données SQLite.
    Configure row_factory pour récupérer les résultats sous forme de dictionnaire (clé-valeur)
    au lieu de simples tuples, facilitant ainsi la sérialisation en JSON par FastAPI.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/api/stats", response_model=Dict[str, Any])
def get_global_stats():
    """
    Retourne le nombre total de feedbacks analysés et la moyenne globale 
    de tous les scores attribués aux différents aspects.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Requête SQL : 
        # - COUNT(DISTINCT feedback_id) : compte les feedbacks uniques ayant au moins un aspect
        # - AVG(score) : calcule la moyenne de la colonne "score" sur toutes les lignes
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT feedback_id) as total_feedbacks_analyses,
                AVG(score) as moyenne_globale
            FROM aspects_analyses
        """)
        row = cursor.fetchone()
        
        # Si la base est encore vide, avg_score vaudra None
        avg = row["moyenne_globale"]
        
        return {
            "total_feedbacks": row["total_feedbacks_analyses"],
            "score_moyen": round(avg, 2) if avg is not None else 0
        }
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erreur base de données : {e}")
    finally:
        # 3. CONTRAINTE : Fermeture propre de la connexion garantie par le fully
        conn.close()

@app.get("/api/top-flaws", response_model=List[Dict[str, Any]])
def get_top_flaws():
    """
    Retourne les 5 pires catégories (celles ayant le pire score moyen).
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # Requête SQL expliquée (Contrainte 2) :
        # - GROUP BY categorie_macro : on rassemble les lignes par catégorie (ex: livraison, produit...)
        # - AVG(score) as score_moyen : on calcule la moyenne des scores du groupe
        # - COUNT(*) as volume : on calcule le nombre de mentions pour ce groupe
        # - HAVING volume >= 5 : filtre post-groupage pour ignorer les catégories citées moins de 5 fois (évite qu'un seul avis en -5 ruine les stats)
        # - ORDER BY score_moyen ASC : on trie du du plus petit (pire) au plus grand.
        # - LIMIT 5 : on ne garde que le top 5 des pires aspects
        cursor.execute("""
            SELECT 
                categorie_macro,
                AVG(score) as score_moyen,
                COUNT(*) as volume
            FROM aspects_analyses
            GROUP BY categorie_macro
            HAVING volume >= 5
            ORDER BY score_moyen ASC
            LIMIT 5
        """)
        rows = cursor.fetchall()
        
        # Transformation des résultats bruts sqlite3.Row en dict classique
        flaws = []
        for row in rows:
            flaws.append({
                "categorie_macro": row["categorie_macro"],
                "score_moyen": round(row["score_moyen"], 2),
                "volume": row["volume"]
            })
            
        return flaws
        
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erreur base de données : {e}")
    finally:
        # 3. CONTRAINTE : Fermeture propre
        conn.close()

# Si tu lances `python3 api.py` localement, le serveur se démarre
if __name__ == "__main__":
    import uvicorn
    # Démarre l'API sur http://localhost:8000
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
