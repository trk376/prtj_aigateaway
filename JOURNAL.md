# Journal

## Session 1 - Objectif : Dialogue avec une IA pour developer l'idee de projet (architecture, base de données, prompt systeme , etc)

J'utilise gemni pro en ligne pour discuter a propos du projet puis je lui demandes des prompts pour l'agent de coding.

J'ai donnée a Gemini Pro le dossier de cadrage du projet et à l'issu d'un dialogue, permettant de developper plus precisement les idees du projet d'un point de vue technique , je lui ai demandé d'écrire des prompts permettant a l'agent de coding de creer une base solide pour le projet etape par etape. 

Prompt :
 "Tu es un développeur backend Python expert. 
CONTEXTE : Nous construisons un MVP de dashboard d'analyse de feedbacks clients. L'architecture repose sur FastAPI et SQLite. 
TA TÂCHE : Écrire un script Python autonome nommé `init_db.py` qui initialise une base de données SQLite `database.db`.

CONTRAINTES ET SCHÉMA :
Tu dois créer 2 tables avec du SQL brut (utilise le module natif `sqlite3`, n'utilise PAS d'ORM comme SQLAlchemy) :
1. Table `feedbacks` :
   - `id` : TEXT (Primary Key, sera l'ID du CSV)
   - `date_creation` : DATE
   - `texte_brut` : TEXT
   - `hash_texte` : TEXT (pour éviter les doublons)
   - `is_analyzed` : BOOLEAN (par défaut False)

2. Table `aspects_analyses` :
   - `id` : INTEGER (Primary Key, Auto Increment)
   - `feedback_id` : TEXT (Foreign Key vers feedbacks.id)
   - `categorie_macro` : TEXT (ex: "livraison")
   - `aspect_exact` : TEXT (ex: "facteur")
   - `score` : INTEGER (allant de -5 à +5)

MÉTHODOLOGIE :
1. Réfléchis étape par étape : explique d'abord comment tu vas structurer ton code et gérer la création des tables si elles existent déjà (IF NOT EXISTS).
2. Fournis ensuite le code complet, propre et documenté."

Prompt : "Tu es un ingénieur IA et développeur Python.
CONTEXTE : Nous analysons des avis clients. Nous avons besoin d'une fonction qui prend un texte brut et retourne une extraction structurée via un LLM.

TA TÂCHE : Écrire un module `llm_service.py` contenant une fonction `analyser_texte(texte: str) -> list[dict]`.

CONTRAINTES :
1. Utilise le package de ton choix (ex: `openai` ou `google-genai`), mais isole l'appel dans un bloc `try/except` robuste.
2. Tronque le texte en entrée à 2000 caractères maximum pour éviter les erreurs de tokens.
3. Rédige un prompt système ultra-strict pour le LLM. Le LLM DOIT retourner un tableau JSON valide.
4. Structure du JSON attendu par le LLM : `[{"categorie_macro": "...", "aspect_exact": "...", "score": entier_entre_-5_et_5}]`.
5. Si le texte est vide ou indéchiffrable, la fonction doit retourner une liste vide `[]`.
6. Si l'API plante ou si le JSON est invalide, la fonction doit faire un print de l'erreur et retourner `[]` (pour ne pas faire crasher la boucle d'ingestion).

MÉTHODOLOGIE :
1. Réfléchis étape par étape sur la façon de forcer le LLM à répondre en JSON (ex: utilisation de response_format ou parsing strict).
2. Fournis le code complet."

Prompt : "Tu es un Data Engineer expert en Python.
CONTEXTE : Nous devons populer notre base SQLite `database.db` avec les données d'un fichier `feedbacks.csv` et les faire analyser par notre module IA.

TA TÂCHE : Écrire un script `import_data.py` qui lit le CSV et orchestre l'ingestion en base.

CONTRAINTES D'IDEMPOTENCE (Très important) :
1. Le CSV contient les colonnes : `id`, `date`, `texte`.
2. Pour chaque ligne, vérifie dans SQLite si l'ID (ou le hash du texte) existe déjà.
3. Si OUI : passe au suivant (continue).
4. Si NON : 
   - Insère le feedback brut dans la table `feedbacks` (is_analyzed = False).
   - Appelle la fonction `analyser_texte(texte)` (que tu importeras depuis `llm_service`).
   - Insère chaque élément de la liste retournée dans la table `aspects_analyses`.
   - Mets à jour `is_analyzed = True` pour ce feedback.
5. Utilise la librairie native `csv` ou `pandas`, et `sqlite3`. Utilise des requêtes paramétrées (?) pour éviter les injections SQL.
6. Fais des `commit()` réguliers.

MÉTHODOLOGIE :
1. Réfléchis étape par étape : détaille ta logique de boucle et de gestion des transactions base de données.
2. Fournis le code complet."

Prompt : "Tu es un développeur Backend Python expert en FastAPI.
CONTEXTE : Notre base de données SQLite `database.db` est pleine de feedbacks analysés. Nous devons exposer ces données à un front-end React via une API REST.

TA TÂCHE : Écrire un fichier `api.py` contenant l'application FastAPI.

CONTRAINTES :
1. AJOUTE OBLIGATOIREMENT le `CORSMiddleware` en autorisant toutes les origines (`allow_origins=["*"]`), sinon le front-end sera bloqué.
2. Crée deux routes GET en écrivant des requêtes SQL brutes avec `sqlite3` :
   - Route `/api/stats` : Retourne le nombre total d'avis et la moyenne globale de tous les scores.
   - Route `/api/top-flaws` : Retourne les pires catégories. La requête SQL doit faire un GROUP BY `categorie_macro`, calculer la moyenne de `score` (nommé `score_moyen`), compter le volume (nommé `volume`), filtrer avec HAVING `volume` >= 5, et trier par `score_moyen` ASC. Limite à 5 résultats.
3. Gère l'ouverture et la fermeture de la connexion SQLite proprement pour chaque requête.

MÉTHODOLOGIE :
1. Réfléchis étape par étape : explique tes requêtes SQL avant de les coder.
2. Fournis le code complet."

Prompt : "Tu es un développeur Front-end expert en Next.js (App Router) et TailwindCSS.
CONTEXTE : Nous avons un backend FastAPI qui tourne sur `http://localhost:8000`. Nous devons construire le dashboard utilisateur.

TA TÂCHE : Écrire le code d'une page Next.js (par exemple `app/page.tsx`) qui affiche les données.

CONTRAINTES :
1. Utilise `fetch` pour appeler `/api/stats` et `/api/top-flaws` au chargement du composant (utilise `useEffect` si composant client, ou fetch côté serveur si Server Component, choisis l'approche la plus simple).
2. Affiche 2 "Cards" (Cartes KPI) en haut : "Total des avis" et "Score moyen global".
3. Utilise la librairie `recharts` (que je vais installer) pour afficher un graphique `BarChart`. Ce graphique doit afficher les données de `/api/top-flaws` (L'axe X est la `categorie_macro`, l'axe Y est le `score_moyen`).
4. Gère les états de chargement (loading) et les erreurs potentielles de l'API proprement.
5. Fais un design épuré, sombre ou clair, en utilisant les classes Tailwind classiques (p-4, rounded-lg, shadow, etc.).

MÉTHODOLOGIE :
1. Réfléchis étape par étape à la structuration de ton composant et à la gestion de l'état.
2. Fournis le code complet du composant."

Probleme : Je ne pas rencontrer de probleme pour le moment autre que trouver un model qui fonctionnait dans l'api Vertex AI.



