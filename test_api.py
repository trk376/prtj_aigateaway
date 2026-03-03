import sqlite3

def fill_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM aspects_analyses")
    cursor.execute("DELETE FROM feedbacks")
    
    # Insert 15 feedbacks to test HAVING >= 5
    for i in range(15):
        cursor.execute(f"INSERT INTO feedbacks (id, date_creation, texte_brut, hash_texte, is_analyzed) VALUES ('{i}', '2023-01-01', 'test', 'hash{i}', 1)")
        
    # Insert flaws
    # Livraison: 6 mentions, score moyen = -3
    for i in range(6):
        cursor.execute(f"INSERT INTO aspects_analyses (feedback_id, categorie_macro, aspect_exact, score) VALUES ('{i}', 'livraison', 'retard', -3)")
        
    # Produit: 8 mentions, score moyen = 2
    for i in range(8):
        cursor.execute(f"INSERT INTO aspects_analyses (feedback_id, categorie_macro, aspect_exact, score) VALUES ('{i+6}', 'produit', 'qualité', 2)")
        
    # Service client: 2 mentions (should be filtered out by HAVING >= 5), score moyen = -5
    for i in range(2):
        cursor.execute(f"INSERT INTO aspects_analyses (feedback_id, categorie_macro, aspect_exact, score) VALUES ('0', 'service client', 'nul', -5)")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    fill_db()
    print("DB filled for testing")
