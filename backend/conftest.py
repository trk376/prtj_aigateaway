import pytest
import sqlite3
from fastapi.testclient import TestClient
from unittest.mock import patch

# On importe l'application FastAPI depuis le module.
# Le try-except permet aux tests de fonctionner que l'on lance pytest 
# depuis la racine du projet ou depuis le dossier backend.
try:
    from api import app
except ImportError:
    from backend.api import app


class MockConnectionWrapper:
    """
    Un wrapper pour empêcher FastAPI de fermer notre base de données SQLite en mémoire.
    Comme api.py appelle `conn.close()` dans un bloc `finally`, sans ce wrapper, 
    la base de données serait détruite après la première requête HTTP du TestClient !
    """
    def __init__(self, real_conn):
        self._conn = real_conn

    def cursor(self):
        return self._conn.cursor()

    def commit(self):
        return self._conn.commit()
    
    def execute(self, *args, **kwargs):
        return self._conn.execute(*args, **kwargs)

    def close(self):
        # ON NE FAIT RIEN : on bloque la fermeture, on garde la DB en mémoire pour le test.
        pass

    @property
    def row_factory(self):
        return self._conn.row_factory

    @row_factory.setter
    def row_factory(self, v):
        self._conn.row_factory = v


@pytest.fixture(name="db_connection")
def fixture_db_connection():
    """
    Initialise une base de données en mémoire pour les tests.
    Elle est recréée vide à chaque test car le scope par défaut d'une fixture est "function".
    """
    # check_same_thread=False est VITAL car le TestClient de FastAPI (Starlette)
    # peut exécuter les requêtes dans un thread séparé de celui où se joue le test pytest.
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # 1. Création du schéma SQLite identique à la prod (basé sur init_db.py)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedbacks (
            id TEXT PRIMARY KEY,
            date_creation DATE,
            texte_brut TEXT,
            hash_texte TEXT,
            is_analyzed BOOLEAN DEFAULT FALSE
        )
    """)
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
    conn.commit()
    
    yield conn  # La base est prête et passée au test
    
    # Après le test, on force la vraie fermeture pour libérer la mémoire proprement.
    real_close = getattr(conn, "close")
    real_close()


@pytest.fixture(name="client")
def fixture_client(db_connection):
    """
    Fixture qui remplace la connexion de api.py par notre fausse DB en mémoire.
    Fournit un TestClient prêt à l'emploi.
    """
    wrapper = MockConnectionWrapper(db_connection)
    
    # On détermine le bon chemin de mock selon d'où est lancé pytest
    try:
        import api
        target_patch = "api.get_db_connection"
    except ImportError:
        target_patch = "backend.api.get_db_connection"
        
    # On utilise unittest.mock.patch pour forcer "get_db_connection" à retourner
    # notre wrapper persisté avec sa DB SQLite :memory: !
    with patch(target_patch, return_value=wrapper):
        with TestClient(app) as test_client:
            yield test_client
