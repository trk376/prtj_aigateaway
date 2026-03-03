import csv
import sqlite3
import hashlib
import logging

# On importe ton module fraîchement refactorisé
from llm_service import analyser_texte

# Configuration des logs pour suivre l'état de l'ingestion
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DATABASE_NAME = "data/database.db"
CSV_FILE_PATH = "data/feedbacks.csv"
COMMIT_BATCH_SIZE = 10 # Nombre de feedbacks à analyser avant de forcer un commit

def generer_hash(texte: str) -> str:
    """Génère un hash SHA-256 pour un texte donné afin de détecter les doublons."""
    return hashlib.sha256(texte.encode('utf-8')).hexdigest()

def importer_feedbacks():
    """
    Lit le fichier CSV 'feedbacks.csv', vérifie les doublons en BDD,
    insère les nouveaux feedbacks, appelle le LLM pour les analyser,
    et enregistre les résultats de l'analyse.
    """
    try:
        # Ouverture de la connexion SQLite
        with sqlite3.connect(DATABASE_NAME) as conn:
            cursor = conn.cursor()
            
            # Pour activer les contraintes de clés étrangères (comme ON DELETE CASCADE défini dans init_db.py)
            cursor.execute("PRAGMA foreign_keys = ON;")
            
            try:
                # Lecture du fichier CSV via la lib native (optimisé pour la mémoire)
                with open(CSV_FILE_PATH, mode='r', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    
                    compteur_ignores = 0
                    compteur_analyses = 0
                    
                    for i, row in enumerate(reader):
                        # Extraction des données de la ligne CSV
                        fb_id = row.get('id', '').strip()
                        date_fb = row.get('date', '').strip()
                        texte_brut = row.get('texte', '').strip()
                        
                        # Si la ligne est globalement vide ou invalide, on passe
                        if not fb_id or not texte_brut:
                            continue
                            
                        hash_txt = generer_hash(texte_brut)
                        
                        # ==========================================================
                        # 1. VÉRIFICATION D'IDEMPOTENCE
                        # ==========================================================
                        # On vérifie si l'ID (du CSV) ou le texte (via son hash) existe déjà.
                        cursor.execute("SELECT id FROM feedbacks WHERE id = ? OR hash_texte = ?", (fb_id, hash_txt))
                        if cursor.fetchone():
                            compteur_ignores += 1
                            # Si on le trouve en BDD, on ignore cette ligne pour éviter les doublons ou re-analyses.
                            continue
                            
                        # ==========================================================
                        # 2. INSERTION DU FEEDBACK BRUT
                        # ==========================================================
                        # On l'insère avec is_analyzed = False par défaut (0 en SQLite)
                        cursor.execute("""
                            INSERT INTO feedbacks (id, date_creation, texte_brut, hash_texte, is_analyzed)
                            VALUES (?, ?, ?, ?, ?)
                        """, (fb_id, date_fb, texte_brut, hash_txt, 0))
                        
                        logging.info(f"Nouveau feedback détécté ({fb_id}). Début de l'analyse LLM...")
                        
                        # ==========================================================
                        # 3. ANALYSE VIA LE LLM (Vertex AI)
                        # ==========================================================
                        # Appel de ton service : si crash ou refus, il retourne []
                        extractions = analyser_texte(texte_brut)
                        
                        if extractions:
                            # ==========================================================
                            # 4. INSERTION DES RÉSULTATS D'ANALYSE
                            # ==========================================================
                            for aspect in extractions:
                                cursor.execute("""
                                    INSERT INTO aspects_analyses (feedback_id, categorie_macro, aspect_exact, score)
                                    VALUES (?, ?, ?, ?)
                                """, (
                                    fb_id, 
                                    aspect.get("categorie_macro", ""), 
                                    aspect.get("aspect_exact", ""), 
                                    aspect.get("score", 0)
                                ))
                                
                            # ==========================================================
                            # 5. MISE À JOUR DU STATUT
                            # ==========================================================
                            # On passe la ligne de feedback à l'état "Analysé" (True / 1)
                            cursor.execute("UPDATE feedbacks SET is_analyzed = ? WHERE id = ?", (1, fb_id))
                            
                            compteur_analyses += 1
                            logging.info(f"Feedback {fb_id} analysé avec succès. ({len(extractions)} aspects trouvés)")
                        else:
                            logging.warning(f"Feedback {fb_id} ingéré mais l'analyse LLM a retourné un résultat vide/en erreur.")
                            
                        # Batch Commit (sauvegarder les données de façon incrémentale)
                        if (compteur_analyses + compteur_ignores) % COMMIT_BATCH_SIZE == 0:
                            conn.commit()
                            
            except FileNotFoundError:
                logging.error(f"Le fichier CSV '{CSV_FILE_PATH}' est introuvable !")
                return
            
            # Commit final de tout ce qui n'a pas été capturé par le modulo COMMIT_BATCH_SIZE
            conn.commit()
            
            logging.info("---")
            logging.info("IMPORT ET ANALYSE TERMINÉS.")
            logging.info(f"-> Nouveaux feedbacks ingérés et analysés : {compteur_analyses}")
            logging.info(f"-> Feedbacks ignorés (déjà existants) : {compteur_ignores}")
                
    except sqlite3.Error as e:
        logging.error(f"Erreur grave avec la base de données : {e}")
        
if __name__ == "__main__":
    importer_feedbacks()
