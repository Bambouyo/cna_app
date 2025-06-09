import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import datetime
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
import base64
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from contextlib import contextmanager

# Configuration de la page
st.set_page_config(
    page_title="CNA - Centre National des Archives",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personnalisé pour l'interface
def load_css():
    st.markdown("""
    <style>
        .main-header {
            background: linear-gradient(135deg, #1f2937 0%, #f59e0b 50%, #10b981 100%);
            padding: 1.5rem;
            border-radius: 10px;
            color: white;
            text-align: center;
            margin-bottom: 2rem;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        
        .header-content {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 20px;
            flex-wrap: wrap;
        }
        
        .logo-cna {
            display: flex;
            align-items: center;
            font-family: 'Arial Black', Arial, sans-serif;
            font-size: 3rem;
            font-weight: 900;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .logo-c {
            background: #f59e0b;
            color: white;
            border-radius: 50%;
            width: 60px;
            height: 60px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 5px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.2);
        }
        
        .logo-na {
            color: #10b981;
            margin-left: -5px;
        }
        
        .header-title {
            margin-left: 20px;
            text-align: left;
        }
        
        .header-title h1 {
            margin: 0;
            font-size: 2.2rem;
            font-weight: 700;
            text-shadow: 1px 1px 3px rgba(0,0,0,0.3);
        }
        
        .header-title p {
            margin: 5px 0 0 0;
            font-size: 1rem;
            opacity: 0.9;
            font-weight: 300;
        }
        
        .metric-card {
            background: white;
            padding: 1rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 4px solid #f59e0b;
        }
        
        .success-msg {
            background-color: #d4edda;
            color: #155724;
            padding: 0.75rem;
            border-radius: 5px;
            border: 1px solid #c3e6cb;
        }
        
        .warning-msg {
            background-color: #fff3cd;
            color: #856404;
            padding: 0.75rem;
            border-radius: 5px;
            border: 1px solid #ffeaa7;
        }
        
        @media (max-width: 768px) {
            .header-content {
                flex-direction: column;
                text-align: center;
            }
            
            .header-title {
                margin-left: 0;
                text-align: center;
            }
            
            .logo-cna {
                font-size: 2.5rem;
            }
            
            .logo-c {
                width: 50px;
                height: 50px;
            }
        }
    </style>
    """, unsafe_allow_html=True)

# Gestionnaire de contexte pour les connexions DB
@contextmanager
def get_db_connection():
    conn = sqlite3.connect('archives.db')
    try:
        yield conn
    finally:
        conn.close()

# Initialisation de la base de données
def init_database():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Table des utilisateurs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'archiviste',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table des fonds documentaires
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fonds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT UNIQUE NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table des objets
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS objets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT UNIQUE NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table des dossiers
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dossiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fonds_id INTEGER,
                objet_id INTEGER,
                analyse TEXT,
                mots_cles TEXT,
                date_debut DATE,
                date_fin DATE,
                archiviste_id INTEGER,
                date_traitement TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                temps_saisie INTEGER,
                FOREIGN KEY (fonds_id) REFERENCES fonds (id),
                FOREIGN KEY (objet_id) REFERENCES objets (id),
                FOREIGN KEY (archiviste_id) REFERENCES users (id)
            )
        ''')
        
        # Table des objectifs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS objectifs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                objectif_quotidien INTEGER DEFAULT 10,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insérer l'administrateur par défaut
        admin_password = hashlib.sha256("admin123".encode()).hexdigest()
        cursor.execute('''
            INSERT OR IGNORE INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
        ''', ("admin", admin_password, "administrateur"))
        
        # Insérer des fonds par défaut
        fonds_defaut = [
            ("RESSOURCES HUMAINES", "Gestion du personnel"),
            ("COMPTABILITÉ", "Documents comptables et financiers"),
            ("TECHNIQUE", "Documentation technique"),
            ("COMMERCIAL", "Documents commerciaux"),
            ("JURIDIQUE", "Documents juridiques et contrats")
        ]
        
        for fonds, desc in fonds_defaut:
            cursor.execute('INSERT OR IGNORE INTO fonds (nom, description) VALUES (?, ?)', (fonds, desc))
        
        # Insérer des objets par défaut
        objets_defaut = [
            ("Dossier individuel", "Dossier personnel d'un agent"),
            ("Contrat", "Documents contractuels"),
            ("Facture", "Documents de facturation"),
            ("Procès-verbal", "Comptes-rendus de réunions"),
            ("Correspondance", "Échanges de courrier")
        ]
        
        for objet, desc in objets_defaut:
            cursor.execute('INSERT OR IGNORE INTO objets (nom, description) VALUES (?, ?)', (objet, desc))
        
        # Insérer objectif par défaut
        cursor.execute('INSERT OR IGNORE INTO objectifs (objectif_quotidien) VALUES (?)', (10,))
        
        conn.commit()

# Fonctions d'authentification
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, password_hash):
    return hash_password(password) == password_hash

def authenticate_user(username, password):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, password_hash, role FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        
        if user and verify_password(password, user[1]):
            return {"id": user[0], "username": username, "role": user[2]}
        return None

# Fonctions utilitaires
def get_fonds():
    with get_db_connection() as conn:
        return pd.read_sql_query('SELECT * FROM fonds ORDER BY nom', conn)

def get_objets():
    with get_db_connection() as conn:
        return pd.read_sql_query('SELECT * FROM objets ORDER BY nom', conn)

def get_archivistes():
    with get_db_connection() as conn:
        return pd.read_sql_query('SELECT id, username FROM users WHERE role = "archiviste" ORDER BY username', conn)

def get_objectif_quotidien():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT objectif_quotidien FROM objectifs ORDER BY updated_at DESC LIMIT 1')
        result = cursor.fetchone()
        return result[0] if result else 10

def display_header(title, subtitle):
    """Affiche l'en-tête standardisé avec logo CNA"""
    st.markdown(f'''
    <div class="main-header">
        <div class="header-content">
            <div class="logo-cna">
                <div class="logo-c">C</div>
                <div class="logo-na">NA</div>
            </div>
            <div class="header-title">
                <h1>{title}</h1>
                <p>{subtitle}</p>
            </div>
        </div>
    </div>
    ''', unsafe_allow_html=True)

# Fonction pour générer l'analyse des statistiques
def generer_analyse_statistiques():
    with get_db_connection() as conn:
        # Données pour l'analyse
        total_dossiers = pd.read_sql_query('SELECT COUNT(*) as count FROM dossiers', conn).iloc[0]['count']
        
        # Analyse par période
        stats_hebdo = pd.read_sql_query('''
            SELECT 
                COUNT(*) as dossiers_semaine,
                AVG(temps_saisie) as temps_moyen_semaine
            FROM dossiers 
            WHERE date_traitement >= date('now', '-7 days')
        ''', conn)
        
        stats_mensuel = pd.read_sql_query('''
            SELECT 
                COUNT(*) as dossiers_mois,
                AVG(temps_saisie) as temps_moyen_mois
            FROM dossiers 
            WHERE date_traitement >= date('now', '-30 days')
        ''', conn)
        
        # Performance par archiviste
        perf_archivistes = pd.read_sql_query('''
            SELECT 
                u.username,
                COUNT(d.id) as total_dossiers,
                AVG(d.temps_saisie) as temps_moyen,
                COUNT(CASE WHEN DATE(d.date_traitement) >= date('now', '-7 days') THEN 1 END) as dossiers_7j
            FROM users u
            LEFT JOIN dossiers d ON u.id = d.archiviste_id
            WHERE u.role = 'archiviste'
            GROUP BY u.id, u.username
            ORDER BY total_dossiers DESC
        ''', conn)
        
        # Répartition par fonds
        repartition_fonds = pd.read_sql_query('''
            SELECT 
                f.nom,
                COUNT(d.id) as count,
                CASE 
                    WHEN (SELECT COUNT(*) FROM dossiers) > 0 
                    THEN ROUND(COUNT(d.id) * 100.0 / (SELECT COUNT(*) FROM dossiers), 2)
                    ELSE 0
                END as pourcentage
            FROM fonds f
            LEFT JOIN dossiers d ON f.id = d.fonds_id
            GROUP BY f.id, f.nom
            ORDER BY count DESC
        ''', conn)
        
        objectif = get_objectif_quotidien()
        
        # Valeurs par défaut si pas de données
        dossiers_semaine = 0
        temps_moyen_semaine = 0
        dossiers_mois = 0
        temps_moyen_mois = 0
        
        if not stats_hebdo.empty:
            dossiers_semaine = stats_hebdo.iloc[0]['dossiers_semaine'] or 0
            temps_moyen_semaine = stats_hebdo.iloc[0]['temps_moyen_semaine'] or 0
            
        if not stats_mensuel.empty:
            dossiers_mois = stats_mensuel.iloc[0]['dossiers_mois'] or 0
            temps_moyen_mois = stats_mensuel.iloc[0]['temps_moyen_mois'] or 0
        
        # Génération de l'analyse textuelle
        analyse = f"""
## 📊 ANALYSE DÉTAILLÉE DES STATISTIQUES

### 📈 Vue d'ensemble
- **Total des dossiers traités :** {total_dossiers:,}
- **Objectif quotidien actuel :** {objectif} dossiers/jour

### ⏱️ Performance temporelle
- **Cette semaine :** {dossiers_semaine} dossiers traités
- **Temps moyen de saisie (7j) :** {temps_moyen_semaine:.1f} minutes
- **Ce mois :** {dossiers_mois} dossiers traités
- **Temps moyen de saisie (30j) :** {temps_moyen_mois:.1f} minutes

### 👥 Performance des archivistes
"""
        
        if not perf_archivistes.empty:
            for _, archiviste in perf_archivistes.iterrows():
                if archiviste['total_dossiers'] and archiviste['total_dossiers'] > 0:
                    efficacite = "🟢 Excellent" if archiviste['dossiers_7j'] >= objectif * 5 else "🟡 Bon" if archiviste['dossiers_7j'] >= objectif * 3 else "🔴 À améliorer"
                    temps_moyen = archiviste['temps_moyen'] if pd.notna(archiviste['temps_moyen']) else 0
                    analyse += f"""
- **{archiviste['username']}**
  - Total : {archiviste['total_dossiers']} dossiers
  - Cette semaine : {archiviste['dossiers_7j']} dossiers
  - Temps moyen : {temps_moyen:.1f} minutes
  - Status : {efficacite}
"""
        else:
            analyse += "\nAucun archiviste trouvé dans le système.\n"
        
        analyse += "\n### 📁 Répartition par fonds documentaires\n"
        
        if not repartition_fonds.empty:
            fonds_avec_dossiers = False
            for _, fonds in repartition_fonds.iterrows():
                if fonds['count'] and fonds['count'] > 0:
                    fonds_avec_dossiers = True
                    pourcentage = fonds['pourcentage'] if pd.notna(fonds['pourcentage']) else 0
                    analyse += f"- **{fonds['nom']}** : {fonds['count']} dossiers ({pourcentage:.1f}%)\n"
            
            if not fonds_avec_dossiers:
                analyse += "Aucun dossier n'a été saisi pour le moment.\n"
        else:
            analyse += "Aucun fonds documentaire trouvé dans le système.\n"
        
        # Recommandations
        if temps_moyen_mois > 15:
            recommandation = "🔴 Le temps de saisie moyen est élevé. Considérez une formation ou une simplification du processus."
        elif temps_moyen_mois > 10:
            recommandation = "🟡 Le temps de saisie est acceptable mais peut être optimisé."
        elif temps_moyen_mois > 0:
            recommandation = "🟢 Excellent temps de saisie ! L'équipe est très efficace."
        else:
            recommandation = "ℹ️ Pas assez de données pour évaluer l'efficacité de saisie."
        
        # Projection
        moyenne_jour = dossiers_semaine / 7 if dossiers_semaine > 0 else 0
        projection_annuelle = int(moyenne_jour * 365)
        
        analyse += f"""

### 💡 Recommandations
{recommandation}

### 🎯 Projection
"""
        
        if moyenne_jour > 0:
            analyse += f"""Au rythme actuel ({moyenne_jour:.1f} dossiers/jour), 
l'équipe pourrait traiter {projection_annuelle:,} dossiers cette année."""
        else:
            analyse += "Pas assez de données pour établir une projection annuelle."
        
        return analyse

# Page de connexion
def login_page():
    display_header("Centre National des Archives", "Système de gestion et traitement des dossiers d'archives")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### 🔐 Connexion")
        
        with st.form("login_form"):
            username = st.text_input("Nom d'utilisateur")
            password = st.text_input("Mot de passe", type="password")
            submit = st.form_submit_button("Se connecter", use_container_width=True)
            
            if submit:
                user = authenticate_user(username, password)
                if user:
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Nom d'utilisateur ou mot de passe incorrect")
        
        st.markdown("---")
        st.info("💡 **Information :** Contactez l'administrateur système pour obtenir vos identifiants de connexion.")
        st.warning("⚠️ **Sécurité :** Pensez à changer votre mot de passe après votre première connexion.")

# Page tableau de bord
def dashboard_page():
    display_header("📊 Tableau de Bord", "Centre National des Archives - Vue d'ensemble")
    
    # Métriques principales
    with get_db_connection() as conn:
        # Statistiques générales
        total_dossiers = pd.read_sql_query('SELECT COUNT(*) as count FROM dossiers', conn).iloc[0]['count']
        
        today = datetime.now().date()
        dossiers_aujourd_hui = pd.read_sql_query(
            'SELECT COUNT(*) as count FROM dossiers WHERE DATE(date_traitement) = ?', 
            conn, params=[today]
        ).iloc[0]['count']
        
        # Objectif quotidien
        objectif = get_objectif_quotidien()
        taux_objectif = (dossiers_aujourd_hui / objectif * 100) if objectif > 0 else 0
        
        # Affichage des métriques
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total dossiers", total_dossiers)
        
        with col2:
            st.metric("Dossiers aujourd'hui", dossiers_aujourd_hui)
        
        with col3:
            st.metric("Objectif quotidien", objectif)
        
        with col4:
            st.metric("Taux d'objectif", f"{taux_objectif:.1f}%")
        
        # Graphiques
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📈 Évolution des saisies (7 derniers jours)")
            
            # Données des 7 derniers jours
            week_data = pd.read_sql_query('''
                SELECT DATE(date_traitement) as date, COUNT(*) as count
                FROM dossiers
                WHERE date_traitement >= date('now', '-7 days')
                GROUP BY DATE(date_traitement)
                ORDER BY date
            ''', conn)
            
            if not week_data.empty:
                fig = px.line(week_data, x='date', y='count', markers=True)
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Aucune donnée disponible pour les 7 derniers jours")
        
        with col2:
            st.markdown("### 📊 Répartition par fonds")
            
            fonds_data = pd.read_sql_query('''
                SELECT f.nom, COUNT(d.id) as count
                FROM fonds f
                LEFT JOIN dossiers d ON f.id = d.fonds_id
                GROUP BY f.id, f.nom
                ORDER BY count DESC
            ''', conn)
            
            if not fonds_data.empty and fonds_data['count'].sum() > 0:
                fig = px.pie(fonds_data[fonds_data['count'] > 0], values='count', names='nom')
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Aucune donnée disponible")

# Page de saisie de dossier
def saisie_dossier_page():
    display_header("📝 Saisie de Dossier", "Centre National des Archives - Nouvelle saisie")
    
    # Enregistrer l'heure de début de saisie
    if 'debut_saisie' not in st.session_state:
        st.session_state.debut_saisie = datetime.now()
    
    with st.form("saisie_dossier"):
        col1, col2 = st.columns(2)
        
        with col1:
            # Fonds documentaire
            fonds_df = get_fonds()
            if not fonds_df.empty:
                fonds_options = dict(zip(fonds_df['nom'], fonds_df['id']))
                fonds_selected = st.selectbox("Fonds documentaire *", options=list(fonds_options.keys()))
            else:
                st.error("Aucun fonds documentaire disponible")
                return
            
            # Objet du dossier
            objets_df = get_objets()
            if not objets_df.empty:
                objets_options = dict(zip(objets_df['nom'], objets_df['id']))
                objet_selected = st.selectbox("Objet du dossier *", options=list(objets_options.keys()))
            else:
                st.error("Aucun objet disponible")
                return
            
            # Dates extrêmes
            date_debut = st.date_input("Date de début", value=datetime(2000, 1, 1).date())
            date_fin = st.date_input("Date de fin", value=datetime.now().date())
        
        with col2:
            # Analyse du dossier
            analyse = st.text_area("Analyse du dossier *", height=100, 
                                 placeholder="Décrivez le contenu du dossier...")
            
            # Mots-clés
            mots_cles = st.text_area("Mots-clés (séparés par des virgules)", height=80,
                                   placeholder="mot1, mot2, mot3...")
        
        submitted = st.form_submit_button("💾 Enregistrer le dossier", use_container_width=True)
        
        if submitted:
            if not analyse.strip():
                st.error("L'analyse du dossier est obligatoire")
            elif date_debut > date_fin:
                st.error("La date de début ne peut pas être postérieure à la date de fin")
            else:
                # Calculer le temps de saisie
                temps_saisie = int((datetime.now() - st.session_state.debut_saisie).total_seconds() / 60)
                
                # Insérer en base
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO dossiers (fonds_id, objet_id, analyse, mots_cles, date_debut, date_fin, archiviste_id, temps_saisie)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        fonds_options[fonds_selected],
                        objets_options[objet_selected],
                        analyse,
                        mots_cles,
                        date_debut,
                        date_fin,
                        st.session_state.user['id'],
                        temps_saisie
                    ))
                    conn.commit()
                
                st.success(f"✅ Dossier enregistré avec succès ! (Temps de saisie: {temps_saisie} minutes)")
                
                # Réinitialiser le temps de début
                st.session_state.debut_saisie = datetime.now()

# Page de recherche
def recherche_page():
    display_header("🔍 Recherche de Dossiers", "Centre National des Archives - Moteur de recherche")
    
    # Filtres de recherche
    with st.expander("🔧 Filtres de recherche", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            mot_cle = st.text_input("Mot-clé")
            
            fonds_df = get_fonds()
            fonds_filter = st.multiselect("Fonds", options=fonds_df['nom'].tolist() if not fonds_df.empty else [])
        
        with col2:
            date_debut_filter = st.date_input("Date début (après)", value=None)
            date_fin_filter = st.date_input("Date fin (avant)", value=None)
        
        with col3:
            objets_df = get_objets()
            objets_filter = st.multiselect("Objets", options=objets_df['nom'].tolist() if not objets_df.empty else [])
            
            archivistes_df = get_archivistes()
            archivistes_filter = st.multiselect("Archivistes", options=archivistes_df['username'].tolist() if not archivistes_df.empty else [])
    
    # Construction de la requête
    with get_db_connection() as conn:
        query = '''
            SELECT 
                d.id,
                f.nom as fonds,
                o.nom as objet,
                d.analyse,
                d.mots_cles,
                d.date_debut,
                d.date_fin,
                u.username as archiviste,
                d.date_traitement,
                d.temps_saisie
            FROM dossiers d
            JOIN fonds f ON d.fonds_id = f.id
            JOIN objets o ON d.objet_id = o.id
            JOIN users u ON d.archiviste_id = u.id
            WHERE 1=1
        '''
        params = []
        
        # Appliquer les filtres
        if mot_cle:
            query += " AND (d.analyse LIKE ? OR d.mots_cles LIKE ?)"
            params.extend([f"%{mot_cle}%", f"%{mot_cle}%"])
        
        if fonds_filter:
            placeholders = ",".join(["?" for _ in fonds_filter])
            query += f" AND f.nom IN ({placeholders})"
            params.extend(fonds_filter)
        
        if objets_filter:
            placeholders = ",".join(["?" for _ in objets_filter])
            query += f" AND o.nom IN ({placeholders})"
            params.extend(objets_filter)
        
        if archivistes_filter:
            placeholders = ",".join(["?" for _ in archivistes_filter])
            query += f" AND u.username IN ({placeholders})"
            params.extend(archivistes_filter)
        
        if date_debut_filter:
            query += " AND d.date_debut >= ?"
            params.append(date_debut_filter)
        
        if date_fin_filter:
            query += " AND d.date_fin <= ?"
            params.append(date_fin_filter)
        
        query += " ORDER BY d.date_traitement DESC"
        
        # Exécuter la recherche
        resultats = pd.read_sql_query(query, conn, params=params)
    
    # Afficher les résultats
    st.markdown(f"### 📋 Résultats ({len(resultats)} dossier(s) trouvé(s))")
    
    if not resultats.empty:
        # Options d'affichage
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("📥 Exporter CSV"):
                csv = resultats.to_csv(index=False)
                st.download_button(
                    label="Télécharger CSV",
                    data=csv,
                    file_name=f"recherche_archives_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        
        # Affichage paginé
        items_per_page = 10
        total_pages = (len(resultats) - 1) // items_per_page + 1
        
        if total_pages > 1:
            page = st.selectbox("Page", options=range(1, total_pages + 1))
            start_idx = (page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            resultats_page = resultats.iloc[start_idx:end_idx]
        else:
            resultats_page = resultats
        
        # Affichage des résultats sous forme de cartes
        for _, row in resultats_page.iterrows():
            with st.container():
                st.markdown(f"""
                <div style="border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin: 1rem 0; background: white;">
                    <h4>📁 {row['fonds']} - {row['objet']}</h4>
                    <p><strong>Analyse:</strong> {row['analyse']}</p>
                    <p><strong>Mots-clés:</strong> {row['mots_cles'] if row['mots_cles'] else 'Aucun'}</p>
                    <div style="display: flex; gap: 2rem; font-size: 0.9em; color: #666;">
                        <span>📅 {row['date_debut']} - {row['date_fin']}</span>
                        <span>👤 {row['archiviste']}</span>
                        <span>🕒 {row['date_traitement']}</span>
                        <span>⏱️ {row['temps_saisie']} min</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Aucun dossier ne correspond aux critères de recherche")

# Page tableau des saisies
def tableau_saisies_page():
    display_header("📋 Tableau des Saisies", "Centre National des Archives - Historique des saisies")
    
    # Filtres
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        periode_filter = st.selectbox("Période", [
            "Toutes les données",
            "Aujourd'hui", 
            "Cette semaine",
            "Ce mois",
            "Période personnalisée"
        ])
    
    with col2:
        if st.session_state.user['role'] == 'administrateur':
            archivistes_df = get_archivistes()
            archiviste_filter = st.selectbox("Archiviste", 
                ["Tous"] + archivistes_df['username'].tolist())
        else:
            archiviste_filter = st.session_state.user['username']
            st.info(f"Vos saisies : {archiviste_filter}")
    
    with col3:
        fonds_df = get_fonds()
        fonds_filter = st.selectbox("Fonds", ["Tous"] + fonds_df['nom'].tolist())
    
    with col4:
        tri_options = ["Date (récent)", "Date (ancien)", "Temps de saisie", "Alphabétique"]
        tri_filter = st.selectbox("Trier par", tri_options)
    
    # Gestion période personnalisée
    if periode_filter == "Période personnalisée":
        col1, col2 = st.columns(2)
        with col1:
            date_debut_custom = st.date_input("Date de début")
        with col2:
            date_fin_custom = st.date_input("Date de fin")
    
    # Construction de la requête
    with get_db_connection() as conn:
        query = '''
            SELECT 
                d.id,
                f.nom as fonds,
                o.nom as objet,
                d.analyse,
                d.mots_cles,
                d.date_debut,
                d.date_fin,
                u.username as archiviste,
                DATE(d.date_traitement) as date_saisie,
                TIME(d.date_traitement) as heure_saisie,
                d.temps_saisie
            FROM dossiers d
            JOIN fonds f ON d.fonds_id = f.id
            JOIN objets o ON d.objet_id = o.id
            JOIN users u ON d.archiviste_id = u.id
            WHERE 1=1
        '''
        params = []
        
        # Filtres de période
        if periode_filter == "Aujourd'hui":
            query += " AND DATE(d.date_traitement) = date('now')"
        elif periode_filter == "Cette semaine":
            query += " AND d.date_traitement >= date('now', '-7 days')"
        elif periode_filter == "Ce mois":
            query += " AND d.date_traitement >= date('now', '-30 days')"
        elif periode_filter == "Période personnalisée":
            query += " AND DATE(d.date_traitement) BETWEEN ? AND ?"
            params.extend([date_debut_custom, date_fin_custom])
        
        # Filtre archiviste
        if st.session_state.user['role'] != 'administrateur':
            query += " AND d.archiviste_id = ?"
            params.append(st.session_state.user['id'])
        elif archiviste_filter != "Tous":
            query += " AND u.username = ?"
            params.append(archiviste_filter)
        
        # Filtre fonds
        if fonds_filter != "Tous":
            query += " AND f.nom = ?"
            params.append(fonds_filter)
        
        # Tri
        if tri_filter == "Date (récent)":
            query += " ORDER BY d.date_traitement DESC"
        elif tri_filter == "Date (ancien)":
            query += " ORDER BY d.date_traitement ASC"
        elif tri_filter == "Temps de saisie":
            query += " ORDER BY d.temps_saisie DESC"
        elif tri_filter == "Alphabétique":
            query += " ORDER BY d.analyse ASC"
        
        # Exécuter la requête
        saisies_df = pd.read_sql_query(query, conn, params=params)
    
    # Statistiques rapides
    if not saisies_df.empty:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total saisies", len(saisies_df))
        with col2:
            temps_moyen = saisies_df['temps_saisie'].mean()
            st.metric("Temps moyen", f"{temps_moyen:.1f} min")
        with col3:
            temps_total = saisies_df['temps_saisie'].sum()
            st.metric("Temps total", f"{temps_total:.0f} min")
        with col4:
            fonds_uniques = saisies_df['fonds'].nunique()
            st.metric("Fonds différents", fonds_uniques)
    
    # Boutons d'action
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col2:
        if st.button("📊 Analyser", use_container_width=True):
            if not saisies_df.empty:
                st.session_state.show_analysis = True
            else:
                st.warning("Aucune donnée à analyser")
    
    with col3:
        if not saisies_df.empty:
            # Export CSV
            csv = saisies_df.to_csv(index=False)
            st.download_button(
                label="📥 Export CSV",
                data=csv,
                file_name=f"saisies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    # Affichage de l'analyse si demandée
    if hasattr(st.session_state, 'show_analysis') and st.session_state.show_analysis and not saisies_df.empty:
        with st.expander("📈 Analyse détaillée", expanded=True):
            # Statistiques descriptives
            st.markdown("### Analyse de la période sélectionnée")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📊 Répartition par fonds:**")
                fonds_stats = saisies_df['fonds'].value_counts()
                for fonds, count in fonds_stats.items():
                    pourcentage = (count / len(saisies_df)) * 100
                    st.write(f"- {fonds}: {count} ({pourcentage:.1f}%)")
            
            with col2:
                st.markdown("**⏱️ Analyse temporelle:**")
                st.write(f"- Temps min: {saisies_df['temps_saisie'].min():.0f} min")
                st.write(f"- Temps max: {saisies_df['temps_saisie'].max():.0f} min")
                st.write(f"- Médiane: {saisies_df['temps_saisie'].median():.1f} min")
                
                temps_moyen = saisies_df['temps_saisie'].mean()
                efficacite = "🟢 Très efficace" if temps_moyen <= 8 else "🟡 Efficace" if temps_moyen <= 12 else "🔴 À améliorer"
                st.write(f"- Efficacité: {efficacite}")
            
            # Graphique des saisies par jour
            if len(saisies_df) > 1:
                daily_stats = saisies_df.groupby('date_saisie').agg({
                    'id': 'count',
                    'temps_saisie': 'mean'
                }).reset_index()
                daily_stats.columns = ['date', 'nombre_saisies', 'temps_moyen']
                
                fig = px.bar(daily_stats, x='date', y='nombre_saisies', 
                           title="Évolution des saisies par jour")
                st.plotly_chart(fig, use_container_width=True)
        
        # Bouton pour fermer l'analyse
        if st.button("Fermer l'analyse"):
            st.session_state.show_analysis = False
            st.rerun()
    
    # Affichage du tableau principal
    st.markdown("### 📋 Liste des saisies")
    
    if not saisies_df.empty:
        # Configuration de l'affichage
        items_per_page = st.selectbox("Éléments par page", [10, 25, 50, 100], index=1)
        
        # Pagination
        total_pages = (len(saisies_df) - 1) // items_per_page + 1
        
        if total_pages > 1:
            page_num = st.selectbox("Page", options=range(1, total_pages + 1))
            start_idx = (page_num - 1) * items_per_page
            end_idx = start_idx + items_per_page
            saisies_page = saisies_df.iloc[start_idx:end_idx]
        else:
            saisies_page = saisies_df
        
        # Affichage du tableau avec colonnes configurables
        colonnes_affichage = st.multiselect(
            "Colonnes à afficher",
            options=['fonds', 'objet', 'analyse', 'mots_cles', 'date_debut', 'date_fin', 
                    'archiviste', 'date_saisie', 'heure_saisie', 'temps_saisie'],
            default=['fonds', 'objet', 'analyse', 'archiviste', 'date_saisie', 'temps_saisie']
        )
        
        if colonnes_affichage:
            # Renommer les colonnes pour l'affichage
            colonnes_renommees = {
                'fonds': 'Fonds',
                'objet': 'Objet', 
                'analyse': 'Analyse',
                'mots_cles': 'Mots-clés',
                'date_debut': 'Date début',
                'date_fin': 'Date fin',
                'archiviste': 'Archiviste',
                'date_saisie': 'Date saisie',
                'heure_saisie': 'Heure',
                'temps_saisie': 'Temps (min)'
            }
            
            tableau_affichage = saisies_page[colonnes_affichage].rename(columns=colonnes_renommees)
            
            # Affichage avec style
            st.dataframe(
                tableau_affichage,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Analyse": st.column_config.TextColumn("Analyse", width="large"),
                    "Temps (min)": st.column_config.NumberColumn("Temps (min)", format="%.0f"),
                }
            )
            
            # Informations de pagination
            if total_pages > 1:
                st.info(f"Page {page_num} sur {total_pages} - Affichage de {len(saisies_page)} sur {len(saisies_df)} saisies")
        else:
            st.warning("Veuillez sélectionner au moins une colonne à afficher")
    else:
        st.info("Aucune saisie ne correspond aux critères sélectionnés")

# Page des statistiques (CORRIGÉE)
def statistiques_page():
    # Vérification des droits d'accès - ADMINISTRATEUR UNIQUEMENT
    if st.session_state.user['role'] != 'administrateur':
        st.error("🚫 Accès réservé aux administrateurs")
        st.info("Cette fonctionnalité est accessible uniquement aux administrateurs du système.")
        return
    
    display_header("📈 Statistiques et Analyses", "Centre National des Archives - Reporting et analyses (Administrateur)")
    
    # Sélecteur de période
    periode = st.selectbox("Période d'analyse", [
        "Toutes les données",
        "7 derniers jours",
        "30 derniers jours",
        "Année en cours"
    ])
    
    with get_db_connection() as conn:
        # Construction du filtre de période
        date_filter = ""
        params = []
        
        if periode == "7 derniers jours":
            date_filter = "WHERE d.date_traitement >= date('now', '-7 days')"
        elif periode == "30 derniers jours":
            date_filter = "WHERE d.date_traitement >= date('now', '-30 days')"
        elif periode == "Année en cours":
            date_filter = "WHERE strftime('%Y', d.date_traitement) = strftime('%Y', 'now')"
        
        # Statistiques par archiviste
        st.markdown("### 👥 Statistiques par archiviste")
        
        query_archivistes = f'''
            SELECT 
                u.username,
                COUNT(d.id) as total_dossiers,
                AVG(d.temps_saisie) as temps_moyen,
                MIN(d.date_traitement) as premiere_saisie,
                MAX(d.date_traitement) as derniere_saisie
            FROM users u
            LEFT JOIN dossiers d ON u.id = d.archiviste_id
            {date_filter.replace('WHERE', 'AND' if 'WHERE' not in date_filter else 'WHERE u.role = "archiviste" AND')}
            WHERE u.role = "archiviste"
            GROUP BY u.id, u.username
            ORDER BY total_dossiers DESC
        '''
        
        stats_archivistes = pd.read_sql_query(query_archivistes, conn)
        
        if not stats_archivistes.empty:
            # Formater les données pour l'affichage
            stats_archivistes['temps_moyen'] = stats_archivistes['temps_moyen'].apply(
                lambda x: f"{x:.1f} min" if pd.notna(x) else "N/A"
            )
            stats_archivistes['premiere_saisie'] = pd.to_datetime(stats_archivistes['premiere_saisie']).dt.strftime('%d/%m/%Y')
            stats_archivistes['derniere_saisie'] = pd.to_datetime(stats_archivistes['derniere_saisie']).dt.strftime('%d/%m/%Y')
            
            st.dataframe(stats_archivistes, use_container_width=True)
        else:
            st.info("Aucune donnée disponible pour la période sélectionnée")
        
        # Graphiques temporels
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📈 Évolution des saisies")
            
            query_evolution = f'''
                SELECT 
                    DATE(date_traitement) as date,
                    COUNT(*) as count
                FROM dossiers d
                {date_filter}
                GROUP BY DATE(date_traitement)
                ORDER BY date
            '''
            
            evolution = pd.read_sql_query(query_evolution, conn)
            
            if not evolution.empty:
                fig = px.bar(evolution, x='date', y='count', title="Nombre de dossiers par jour")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Aucune donnée pour la période sélectionnée")
        
        with col2:
            st.markdown("### ⏱️ Temps de saisie moyen")
            
            query_temps = f'''
                SELECT 
                    DATE(date_traitement) as date,
                    AVG(temps_saisie) as temps_moyen
                FROM dossiers d
                {date_filter}
                GROUP BY DATE(date_traitement)
                ORDER BY date
            '''
            
            temps_saisie = pd.read_sql_query(query_temps, conn)
            
            if not temps_saisie.empty:
                fig = px.line(temps_saisie, x='date', y='temps_moyen', 
                            title="Temps moyen de saisie (minutes)", markers=True)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Aucune donnée pour la période sélectionnée")
        
        # Répartition par fonds
        st.markdown("### 📁 Répartition par fonds documentaires")
        
        query_fonds = f'''
            SELECT 
                f.nom,
                COUNT(d.id) as count,
                AVG(d.temps_saisie) as temps_moyen
            FROM fonds f
            LEFT JOIN dossiers d ON f.id = d.fonds_id
            {date_filter.replace('WHERE', 'AND' if 'WHERE' not in date_filter else 'WHERE')}
            GROUP BY f.id, f.nom
            ORDER BY count DESC
        '''
        
        fonds_stats = pd.read_sql_query(query_fonds, conn)
        
        if not fonds_stats.empty and fonds_stats['count'].sum() > 0:
            col1, col2 = st.columns(2)
            
            with col1:
                fig = px.pie(fonds_stats[fonds_stats['count'] > 0], values='count', names='nom',
                           title="Répartition des dossiers par fonds")
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fonds_stats['temps_moyen'] = fonds_stats['temps_moyen'].apply(
                    lambda x: f"{x:.1f}" if pd.notna(x) else "0"
                )
                st.dataframe(
                    fonds_stats[['nom', 'count', 'temps_moyen']].rename(columns={
                        'nom': 'Fonds',
                        'count': 'Nombre de dossiers',
                        'temps_moyen': 'Temps moyen (min)'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
        
        # Objectifs et projections
        st.markdown("### 🎯 Suivi des objectifs")
        
        objectif = get_objectif_quotidien()
        today = datetime.now().date()
        
        # Dossiers aujourd'hui
        dossiers_aujourd_hui = pd.read_sql_query(
            'SELECT COUNT(*) as count FROM dossiers WHERE DATE(date_traitement) = ?',
            conn, params=[today]
        ).iloc[0]['count']
        
        # Moyenne sur les 7 derniers jours
        moyenne_7j_result = pd.read_sql_query('''
            SELECT AVG(daily_count) as moyenne FROM (
                SELECT COUNT(*) as daily_count
                FROM dossiers
                WHERE date_traitement >= date('now', '-7 days')
                GROUP BY DATE(date_traitement)
            )
        ''', conn)
        
        moyenne_7j = moyenne_7j_result.iloc[0]['moyenne'] if not moyenne_7j_result.empty and moyenne_7j_result.iloc[0]['moyenne'] is not None else 0
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            taux_objectif = (dossiers_aujourd_hui / objectif * 100) if objectif > 0 else 0
            color = "🟢" if taux_objectif >= 90 else "🟡" if taux_objectif >= 70 else "🔴"
            st.metric(f"Objectif du jour {color}", f"{dossiers_aujourd_hui}/{objectif}", f"{taux_objectif:.1f}%")
        
        with col2:
            st.metric("Moyenne 7 jours", f"{moyenne_7j:.1f}", 
                     f"vs objectif: {(moyenne_7j/objectif*100):.1f}%" if objectif > 0 else "")
        
        with col3:
            # Projection annuelle
            if moyenne_7j > 0:
                projection_annuelle = int(moyenne_7j * 365)
                st.metric("Projection annuelle", f"{projection_annuelle:,}", "Au rythme actuel")
            else:
                st.metric("Projection annuelle", "N/A", "Données insuffisantes")
        
        # Boutons d'action
        col1, col2 = st.columns(2)
        
        with col1:
            # Bouton pour générer l'analyse complète
            if st.button("📄 Générer rapport détaillé", use_container_width=True):
                try:
                    with st.spinner("Génération du rapport..."):
                        analyse = generer_analyse_statistiques()
                        st.markdown(analyse)
                except Exception as e:
                    st.error(f"Erreur lors de la génération du rapport : {str(e)}")
                    st.info("Vérifiez qu'il y a des données dans le système ou contactez l'administrateur.")
        
        with col2:
            # Bouton pour exporter en PDF
            if st.button("📥 Exporter PDF", use_container_width=True):
                try:
                    with st.spinner("Génération du PDF..."):
                        pdf_buffer = export_pdf_stats()
                        st.download_button(
                            label="Télécharger le rapport PDF",
                            data=pdf_buffer,
                            file_name=f"rapport_statistiques_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf"
                        )
                except Exception as e:
                    st.error(f"Erreur lors de la génération du PDF : {str(e)}")

# Page d'administration
def admin_page():
    if st.session_state.user['role'] != 'administrateur':
        st.error("Accès réservé aux administrateurs")
        return
    
    display_header("⚙️ Administration", "Centre National des Archives - Gestion du système")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["👥 Utilisateurs", "📁 Fonds", "📄 Objets", "🎯 Objectifs", "🗑️ Gestion"])
    
    # Gestion des utilisateurs
    with tab1:
        st.markdown("### Gestion des utilisateurs")
        
        # Ajouter un utilisateur
        with st.expander("➕ Ajouter un utilisateur"):
            with st.form("add_user"):
                col1, col2 = st.columns(2)
                with col1:
                    new_username = st.text_input("Nom d'utilisateur")
                    new_password = st.text_input("Mot de passe", type="password")
                with col2:
                    new_role = st.selectbox("Rôle", ["archiviste", "administrateur"])
                
                if st.form_submit_button("Ajouter"):
                    if new_username and new_password:
                        try:
                            with get_db_connection() as conn:
                                cursor = conn.cursor()
                                password_hash = hash_password(new_password)
                                cursor.execute(
                                    'INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
                                    (new_username, password_hash, new_role)
                                )
                                conn.commit()
                            st.success(f"Utilisateur {new_username} ajouté avec succès")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Ce nom d'utilisateur existe déjà")
        
        # Changer mot de passe
        with st.expander("🔐 Changer mot de passe"):
            with st.form("change_password"):
                # Récupérer la liste des utilisateurs
                with get_db_connection() as conn:
                    users_list = pd.read_sql_query('SELECT id, username, role FROM users ORDER BY username', conn)
                
                # Sélection de l'utilisateur
                user_options = ["Mon compte"] + [f"{row['username']} ({row['role']})" for _, row in users_list.iterrows() if row['username'] != st.session_state.user['username']]
                selected_user = st.selectbox("Utilisateur", options=user_options)
                
                col1, col2 = st.columns(2)
                with col1:
                    new_password = st.text_input("Nouveau mot de passe", type="password")
                with col2:
                    confirm_password = st.text_input("Confirmer le mot de passe", type="password")
                
                if st.form_submit_button("Changer le mot de passe"):
                    if new_password and confirm_password:
                        if new_password == confirm_password:
                            if len(new_password) >= 6:
                                try:
                                    with get_db_connection() as conn:
                                        cursor = conn.cursor()
                                        password_hash = hash_password(new_password)
                                        
                                        if selected_user == "Mon compte":
                                            # Changer son propre mot de passe
                                            cursor.execute(
                                                'UPDATE users SET password_hash = ? WHERE id = ?',
                                                (password_hash, st.session_state.user['id'])
                                            )
                                            st.success("Votre mot de passe a été changé avec succès")
                                        else:
                                            # Changer le mot de passe d'un autre utilisateur
                                            username = selected_user.split(" (")[0]
                                            cursor.execute(
                                                'UPDATE users SET password_hash = ? WHERE username = ?',
                                                (password_hash, username)
                                            )
                                            st.success(f"Le mot de passe de {username} a été changé avec succès")
                                        
                                        conn.commit()
                                except Exception as e:
                                    st.error(f"Erreur lors du changement de mot de passe : {str(e)}")
                            else:
                                st.error("Le mot de passe doit contenir au moins 6 caractères")
                        else:
                            st.error("Les mots de passe ne correspondent pas")
                    else:
                        st.error("Veuillez remplir tous les champs")
        
        # Liste des utilisateurs
        with get_db_connection() as conn:
            users_df = pd.read_sql_query('SELECT id, username, role, created_at FROM users ORDER BY created_at DESC', conn)
        
        st.markdown("### 📋 Liste des utilisateurs")
        
        # Ajouter une option de suppression pour chaque utilisateur
        for _, user in users_df.iterrows():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            with col1:
                st.text(f"👤 {user['username']}")
            with col2:
                st.text(f"📋 {user['role']}")
            with col3:
                st.text(f"📅 {user['created_at']}")
            with col4:
                # Ne pas permettre la suppression de l'admin actuel ou du compte admin par défaut
                if user['username'] != st.session_state.user['username'] and user['username'] != 'admin':
                    if st.button("🗑️", key=f"del_{user['id']}", help=f"Supprimer {user['username']}"):
                        if st.session_state.get(f"confirm_del_{user['id']}", False):
                            with get_db_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute('DELETE FROM users WHERE id = ?', (user['id'],))
                                conn.commit()
                            st.success(f"Utilisateur {user['username']} supprimé")
                            st.rerun()
                        else:
                            st.session_state[f"confirm_del_{user['id']}"] = True
                            st.warning(f"Cliquez à nouveau pour confirmer la suppression de {user['username']}")
            st.divider()
    
    # Gestion des fonds
    with tab2:
        st.markdown("### Gestion des fonds documentaires")
        
        # Ajouter un fonds
        with st.expander("➕ Ajouter un fonds"):
            with st.form("add_fonds"):
                col1, col2 = st.columns(2)
                with col1:
                    new_fonds_nom = st.text_input("Nom du fonds")
                with col2:
                    new_fonds_desc = st.text_input("Description")
                
                if st.form_submit_button("Ajouter"):
                    if new_fonds_nom:
                        try:
                            with get_db_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    'INSERT INTO fonds (nom, description) VALUES (?, ?)',
                                    (new_fonds_nom, new_fonds_desc)
                                )
                                conn.commit()
                            st.success(f"Fonds {new_fonds_nom} ajouté avec succès")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Ce fonds existe déjà")
        
        # Liste des fonds
        with get_db_connection() as conn:
            fonds_df = pd.read_sql_query('SELECT * FROM fonds ORDER BY nom', conn)
        st.dataframe(fonds_df, use_container_width=True)
    
    # Gestion des objets
    with tab3:
        st.markdown("### Gestion des objets")
        
        # Ajouter un objet
        with st.expander("➕ Ajouter un objet"):
            with st.form("add_objet"):
                col1, col2 = st.columns(2)
                with col1:
                    new_objet_nom = st.text_input("Nom de l'objet")
                with col2:
                    new_objet_desc = st.text_input("Description")
                
                if st.form_submit_button("Ajouter"):
                    if new_objet_nom:
                        try:
                            with get_db_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    'INSERT INTO objets (nom, description) VALUES (?, ?)',
                                    (new_objet_nom, new_objet_desc)
                                )
                                conn.commit()
                            st.success(f"Objet {new_objet_nom} ajouté avec succès")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Cet objet existe déjà")
        
        # Liste des objets
        with get_db_connection() as conn:
            objets_df = pd.read_sql_query('SELECT * FROM objets ORDER BY nom', conn)
        st.dataframe(objets_df, use_container_width=True)
    
    # Gestion des objectifs
    with tab4:
        st.markdown("### Gestion des objectifs")
        
        objectif_actuel = get_objectif_quotidien()
        
        with st.form("update_objectif"):
            nouveau_objectif = st.number_input("Objectif quotidien (dossiers/jour)", 
                                             value=objectif_actuel, min_value=1, max_value=100)
            
            if st.form_submit_button("Mettre à jour"):
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('INSERT INTO objectifs (objectif_quotidien) VALUES (?)', (nouveau_objectif,))
                    conn.commit()
                st.success(f"Objectif mis à jour: {nouveau_objectif} dossiers/jour")
                st.rerun()
        
        st.info(f"Objectif actuel: {objectif_actuel} dossiers par jour")
    
    # Gestion/suppression
    with tab5:
        st.markdown("### Gestion des données")
        
        st.warning("⚠️ Zone dangereuse - Actions irréversibles")
        
        with get_db_connection() as conn:
            # Statistiques générales
            total_dossiers = pd.read_sql_query('SELECT COUNT(*) as count FROM dossiers', conn).iloc[0]['count']
            total_users = pd.read_sql_query('SELECT COUNT(*) as count FROM users', conn).iloc[0]['count']
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total dossiers", total_dossiers)
            with col2:
                st.metric("Total utilisateurs", total_users)
            
            # Sauvegarde
            if st.button("💾 Exporter toutes les données"):
                # Export de tous les dossiers
                all_data = pd.read_sql_query('''
                    SELECT 
                        d.*,
                        f.nom as fonds_nom,
                        o.nom as objet_nom,
                        u.username as archiviste_nom
                    FROM dossiers d
                    JOIN fonds f ON d.fonds_id = f.id
                    JOIN objets o ON d.objet_id = o.id
                    JOIN users u ON d.archiviste_id = u.id
                    ORDER BY d.date_traitement DESC
                ''', conn)
                
                csv = all_data.to_csv(index=False)
                st.download_button(
                    label="📥 Télécharger l'export complet",
                    data=csv,
                    file_name=f"export_complet_archives_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )

# Page principale après connexion
def main_app():
    # Sidebar avec navigation
    with st.sidebar:
        # Logo CNA dans la sidebar
        st.markdown('''
        <div style="text-align: center; padding: 1rem 0; border-bottom: 1px solid #eee; margin-bottom: 1rem;">
            <div style="display: flex; align-items: center; justify-content: center; gap: 5px; font-family: Arial Black; font-size: 1.5rem; font-weight: 900;">
                <div style="background: #f59e0b; color: white; border-radius: 50%; width: 35px; height: 35px; display: flex; align-items: center; justify-content: center;">C</div>
                <div style="color: #10b981;">NA</div>
            </div>
            <div style="font-size: 0.8rem; color: #666; margin-top: 5px;">Centre National des Archives</div>
        </div>
        ''', unsafe_allow_html=True)
        
        st.markdown(f"### 👤 {st.session_state.user['username']}")
        st.markdown(f"**Rôle :** {st.session_state.user['role'].title()}")
        
        # Options du compte
        with st.expander("⚙️ Mon compte"):
            # Changer son mot de passe
            st.markdown("#### 🔐 Changer mon mot de passe")
            with st.form("sidebar_change_password"):
                current_password = st.text_input("Mot de passe actuel", type="password")
                new_password = st.text_input("Nouveau mot de passe", type="password")
                confirm_password = st.text_input("Confirmer le nouveau mot de passe", type="password")
                
                if st.form_submit_button("Changer"):
                    if current_password and new_password and confirm_password:
                        # Vérifier le mot de passe actuel
                        with get_db_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute('SELECT password_hash FROM users WHERE id = ?', (st.session_state.user['id'],))
                            user_data = cursor.fetchone()
                            
                            if user_data and verify_password(current_password, user_data[0]):
                                if new_password == confirm_password:
                                    if len(new_password) >= 6:
                                        password_hash = hash_password(new_password)
                                        cursor.execute(
                                            'UPDATE users SET password_hash = ? WHERE id = ?',
                                            (password_hash, st.session_state.user['id'])
                                        )
                                        conn.commit()
                                        st.success("Mot de passe changé avec succès!")
                                    else:
                                        st.error("Le nouveau mot de passe doit contenir au moins 6 caractères")
                                else:
                                    st.error("Les mots de passe ne correspondent pas")
                            else:
                                st.error("Mot de passe actuel incorrect")
                    else:
                        st.error("Veuillez remplir tous les champs")
        
        if st.button("🚪 Déconnexion"):
            del st.session_state.user
            st.rerun()
        
        st.markdown("---")
        
        # Menu de navigation
        pages = ["📊 Tableau de bord", "📝 Saisie de dossier", "📋 Tableau des saisies", "🔍 Recherche"]
        
        if st.session_state.user['role'] == 'administrateur':
            pages.extend(["📈 Statistiques", "⚙️ Administration"])
        
        page = st.selectbox("Navigation", pages)
    
    # Contenu principal selon la page sélectionnée
    if page == "📊 Tableau de bord":
        dashboard_page()
    elif page == "📝 Saisie de dossier":
        saisie_dossier_page()
    elif page == "📋 Tableau des saisies":
        tableau_saisies_page()
    elif page == "🔍 Recherche":
        recherche_page()
    elif page == "📈 Statistiques":
        statistiques_page()
    elif page == "⚙️ Administration":
        admin_page()

# Application principale
def main():
    # Charger le CSS
    load_css()
    
    # Initialiser la base de données
    init_database()
    
    # Vérifier l'authentification
    if 'user' not in st.session_state:
        login_page()
    else:
        main_app()

if __name__ == "__main__":
    main()

# Documentation technique (non affichée dans l'application)
# Pour installer les dépendances : pip install streamlit pandas plotly reportlab
