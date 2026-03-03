import sqlite3
import logging

# Configuration du logging pour suivre l'exécution
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DATABASE_NAME = "data/database.db"

def init_db():
    """
    Initialise la base de données SQLite en créant les tables `feedbacks` 
    et `aspects_analyses` si elles n'existent pas déjà.
    """
    try:
        # Connexion à la base de données (le fichier est créé s'il n'existe pas)
        with sqlite3.connect(DATABASE_NAME) as conn:
            cursor = conn.cursor()
            
            # Activation des clés étrangères (souvent désactivé par défaut sur SQLite)
            cursor.execute("PRAGMA foreign_keys = ON;")
            
            # 1. Création de la table `feedbacks`
            # On utilise IF NOT EXISTS pour rendre le script idempotent (ne recrée pas si existant)
            # Boolean dans SQLite est souvent représenté par un entier (0 = False, 1 = True)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedbacks (
                    id TEXT PRIMARY KEY,
                    date_creation DATE,
                    texte_brut TEXT,
                    hash_texte TEXT,
                    is_analyzed BOOLEAN DEFAULT FALSE
                )
            """)
            
            # 2. Création de la table `aspects_analyses`
            # On utilise CHECK pour s'assurer que le score reste entre -5 et 5
            # On définit la clé étrangère pour lier au feedback parent
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS aspects_analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feedback_id TEXT,
                    categorie_macro TEXT,
                    aspect_exact TEXT,
                    score INTEGER CHECK(score >= -5 AND score <= 5),
                    FOREIGN KEY (feedback_id) REFERENCES feedbacks(id) ON DELETE CASCADE
                )
            """)
            
            # Les modifications sont automatiquement validées (commit) grâce au gestionnaire de contexte "with",
            # mais on peut forcer un commit au cas où.
            conn.commit()
            
            logging.info("L'initialisation de la base de données est terminée avec succès.")

    except sqlite3.Error as e:
        logging.error(f"Une erreur SQLite est survenue : {e}")
    except Exception as e:
        logging.error(f"Une erreur inattendue est survenue : {e}")

if __name__ == "__main__":
    logging.info("Lancement du script d'initialisation de la base de données...")
    init_db()
