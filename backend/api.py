from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
import sqlite3

# Création de l'application FastAPI
app = FastAPI(title="Dashboard Feedbacks API", description="API servant les données aggrégées pour le dashboard React.")

# 1. CONTRAINTE : Configuration CORS OBLIGATOIRE
# Permet au front-end Next.js (qui tourne sur localhost:3000) 
# de faire des requêtes vers FastAPI (localhost:8000) sans erreur CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production, mettre ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"], 
)

DATABASE_NAME = "data/database.db"

def get_db_connection():
    """
    Ouvre et retourne une connexion SQLite.
    row_factory pour sérialiser en objet/dictionnaire au lieu de tuple natif.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def _build_date_clause(start_date: Optional[str], end_date: Optional[str], date_col: str = "f.date_creation") -> tuple[str, list]:
    """
    Construit dynamiquement la clause WHERE pour le filtrage par date.
    Retourne (clause_sql, params).
    """
    clauses = []
    params = []
    if start_date:
        clauses.append(f"{date_col} >= ?")
        params.append(start_date)
    if end_date:
        clauses.append(f"{date_col} <= ?")
        params.append(end_date)
    
    if clauses:
        return " AND ".join(clauses), params
    return "", []


# ==============================================================================
# ENDPOINT 1 : KPI OBSERVAUX
# ==============================================================================
@app.get("/api/kpi", response_model=Dict[str, Any])
def get_kpi(start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None)):
    """
    Retourne : total_avis, score_moyen, taux_frustration
    Filtrable par start_date et end_date (format YYYY-MM-DD).
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        date_clause, params = _build_date_clause(start_date, end_date)
        where_sql = f"WHERE {date_clause}" if date_clause else ""
        
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total_analyses,
                AVG(a.score) as score_moyen,
                SUM(CASE WHEN a.score < 0 THEN 1 ELSE 0 END) as avis_frustres
            FROM aspects_analyses a
            INNER JOIN feedbacks f ON a.feedback_id = f.id
            {where_sql}
        """, params)
        row = cursor.fetchone()
        
        if not row or row["total_analyses"] == 0:
            return {"total_avis": 0, "score_moyen": 0, "taux_frustration": 0}
            
        total = row["total_analyses"]
        score_moyen = row["score_moyen"]
        avis_frustres = row["avis_frustres"] or 0
        
        taux_frustration = (avis_frustres / total) * 100
        
        return {
            "total_avis": total,
            "score_moyen": round(score_moyen, 1) if score_moyen is not None else 0,
            "taux_frustration": round(taux_frustration, 1)
        }
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erreur DB : {e}")
    finally:
        conn.close()


# ==============================================================================
# ENDPOINT 2 : THEMES ET SENTIMENTS AVEC EXEMPLE
# ==============================================================================
@app.get("/api/themes", response_model=List[Dict[str, Any]])
def get_themes(start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None)):
    """
    Retourne la liste des thèmes agrégés avec leur volume, score moyen,
    et un exemple représentatif de texte brut extrait via JOIN.
    Filtrable par start_date et end_date.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        date_clause, params = _build_date_clause(start_date, end_date)
        where_sql = f"WHERE {date_clause}" if date_clause else ""
        
        cursor.execute(f"""
            SELECT 
                a.categorie_macro,
                COUNT(a.id) as volume,
                AVG(a.score) as score_moyen,
                MAX(f.texte_brut) as exemple_representatif
            FROM aspects_analyses a
            INNER JOIN feedbacks f ON a.feedback_id = f.id
            {where_sql}
            GROUP BY a.categorie_macro
            ORDER BY score_moyen DESC
        """, params)
        
        rows = cursor.fetchall()
        
        result = []
        for row in rows:
            result.append({
                "categorie_macro": row["categorie_macro"],
                "volume": row["volume"],
                "score_moyen": round(row["score_moyen"], 1),
                "exemple_representatif": row["exemple_representatif"]
            })
            
        return result
        
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erreur DB : {e}")
    finally:
        conn.close()


# ==============================================================================
# ENDPOINT 3 : TENDANCE TEMPORELLE
# ==============================================================================
@app.get("/api/timeline", response_model=List[Dict[str, Any]])
def get_timeline(start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None)):
    """
    Regroupe le score moyen de tous les avis par jour.
    Filtrable par start_date et end_date.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        date_clause, params = _build_date_clause(start_date, end_date)
        where_sql = f"WHERE {date_clause}" if date_clause else ""
        
        cursor.execute(f"""
            SELECT 
                STRFTIME('%Y-%m-%d', f.date_creation) as jour,
                AVG(a.score) as score_moyen,
                COUNT(a.id) as volume_jour
            FROM aspects_analyses a
            INNER JOIN feedbacks f ON a.feedback_id = f.id
            {where_sql}
            GROUP BY jour
            ORDER BY jour ASC
        """, params)
        
        rows = cursor.fetchall()
        
        timeline = []
        for row in rows:
            timeline.append({
                "date": row["jour"],
                "score_moyen": round(row["score_moyen"], 1) if row["score_moyen"] is not None else 0,
                "volume": row["volume_jour"]
            })
            
        return timeline
        
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Erreur DB : {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn
    # Démarre l'API en local sur le port 8000
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
