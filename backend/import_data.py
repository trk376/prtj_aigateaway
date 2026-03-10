import csv
import sqlite3
import hashlib
import logging
import asyncio
import inspect

# On importe ton module fraîchement refactorisé
from llm_service import extraire_aspects_batch, generer_taxonomie

# Configuration des logs pour suivre l'état de l'ingestion
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DATABASE_NAME = "data/database.db"
CSV_FILE_PATH = "data/feedbacks.csv"
BATCH_SIZE = 30 # Nombre de feedbacks à grouper pour la phase MAP

def generer_hash(texte: str) -> str:
    """Génère un hash SHA-256 pour un texte donné afin de détecter les doublons."""
    return hashlib.sha256(texte.encode('utf-8')).hexdigest()

def importer_feedbacks():
    """
    Lit le fichier CSV, insère les feedbacks bruts puis lance l'architecture
    Map-Reduce par lots pour optimiser les appels LLM et unifier les taxonomies.
    """
    try:
        with sqlite3.connect(DATABASE_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            
            # 1. Lecture du CSV et isolation des nouveaux feedbacks
            nouveaux_feedbacks = []
            compteur_ignores = 0
            
            try:
                with open(CSV_FILE_PATH, mode='r', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        fb_id = row.get('id', '').strip()
                        date_fb = row.get('date', '').strip()
                        texte_brut = row.get('texte', '').strip()
                        
                        if not fb_id or not texte_brut:
                            continue
                            
                        hash_txt = generer_hash(texte_brut)
                        
                        # Vérification d'idempotence stricte (insertion si nouveau)
                        cursor.execute("SELECT id FROM feedbacks WHERE id = ? OR hash_texte = ?", (fb_id, hash_txt))
                        if cursor.fetchone():
                            compteur_ignores += 1
                            continue
                            
                        # Insertion du feedback brut (is_analyzed = False)
                        cursor.execute("""
                            INSERT INTO feedbacks (id, date_creation, texte_brut, hash_texte, is_analyzed)
                            VALUES (?, ?, ?, ?, ?)
                        """, (fb_id, date_fb, texte_brut, hash_txt, 0))
                        
            except FileNotFoundError:
                logging.error(f"Le fichier CSV '{CSV_FILE_PATH}' est introuvable !")
                return
                
            conn.commit()
            
            # 2. Récupération de TOUS les feedbacks non analysés (même suite à un crash passé)
            cursor.execute("SELECT id, texte_brut FROM feedbacks WHERE is_analyzed = 0")
            rows = cursor.fetchall()
            nouveaux_feedbacks = [{"id": row[0], "texte": row[1]} for row in rows]
            
            if not nouveaux_feedbacks:
                logging.info("Aucun nouveau feedback à traiter.")
                logging.info(f"-> Feedbacks ignorés (déjà existants) : {compteur_ignores}")
                return
                
            logging.info(f"Début du traitement de {len(nouveaux_feedbacks)} nouveaux feedbacks en architecture Map-Reduce.")
            
            # Traitement par lots (Batches)
            for i in range(0, len(nouveaux_feedbacks), BATCH_SIZE):
                batch = nouveaux_feedbacks[i:i+BATCH_SIZE]
                logging.info(f"--- BATCH {i//BATCH_SIZE + 1} ({len(batch)} feedbacks) ---")
                
                # ==========================================================
                # PHASE 1 : MAP (Extraction brute multithreadée)
                # ==========================================================
                logging.info("Exécution Phase 1: MAP (Extraction brute multithreadée...)")
                extractions_brutes_par_avis = extraire_aspects_batch(batch)
                
                # Collecte des aspects uniques pour le batch
                tous_aspects_bruts = set()
                for extractions in extractions_brutes_par_avis.values():
                    if extractions and isinstance(extractions, list):
                        for aspect in extractions:
                            if isinstance(aspect, dict):
                                asp = aspect.get("aspect_exact")
                                if asp:
                                    tous_aspects_bruts.add(asp)
                
                # ==========================================================
                # PHASE 2 : REDUCE (Création de Catégories Macros Unifiées)
                # ==========================================================
                logging.info(f"Exécution Phase 2: REDUCE (Synthèse de {len(tous_aspects_bruts)} aspects uniques...)")
                taxonomie = generer_taxonomie(list(tous_aspects_bruts))
                if not taxonomie: taxonomie = {}
                
                # ==========================================================
                # PHASE 3 : INSERTION SQL ET MAPPING FINAL
                # ==========================================================
                logging.info("Exécution Phase 3: INSERTION (Mapping local et SQLite executemany...)")
                
                lignes_aspects_a_inserer = []
                ids_a_valider = []
                
                for fb_id, extractions in extractions_brutes_par_avis.items():
                    if extractions and isinstance(extractions, list):
                        for asp in extractions:
                            if isinstance(asp, dict):
                                aspect_exact = asp.get("aspect_exact", "")
                                score = asp.get("score", 0)
                                if aspect_exact:
                                    # Mapping final : si non trouvé dans la taxonomie, catégorie 'autre'
                                    cat_macro = taxonomie.get(aspect_exact, "autre").lower()
                                    lignes_aspects_a_inserer.append((fb_id, cat_macro, aspect_exact, score))
                    
                    ids_a_valider.append((1, fb_id))
                    
                # Insertion très rapide en base
                if lignes_aspects_a_inserer:
                    cursor.executemany("""
                        INSERT INTO aspects_analyses (feedback_id, categorie_macro, aspect_exact, score)
                        VALUES (?, ?, ?, ?)
                    """, lignes_aspects_a_inserer)
                    
                # Validation des feedbacks comme "Analysés"
                if ids_a_valider:
                    cursor.executemany("UPDATE feedbacks SET is_analyzed = ? WHERE id = ?", ids_a_valider)
                
                conn.commit()
                logging.info(f"Batch {i//BATCH_SIZE + 1} complété avec succès. ({len(lignes_aspects_a_inserer)} aspects insérés)")
                
            logging.info("============= TERMINÉ ! =============")
            logging.info(f"-> Nouveaux feedbacks ingérés et analysés : {len(nouveaux_feedbacks)}")
            logging.info(f"-> Feedbacks ignorés (déjà existants) : {compteur_ignores}")
                
    except sqlite3.Error as e:
        logging.error(f"Erreur grave avec la base de données : {e}")
        
if __name__ == "__main__":
    importer_feedbacks()
