import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime
import time
import pypdf
import subprocess
import altair as alt
import re
import base64
import locale
import random
import version_comparator # New module
try:
    from supabase_sync import SupabaseSync
    SUPABASE = SupabaseSync()
except ImportError:
    SUPABASE = None

# Try to set locale to Spanish for date formatting
try:
    locale.setlocale(locale.LC_TIME, 'Spanish')
except:
    try:
        locale.setlocale(locale.LC_TIME, 'es_ES')
    except:
        pass # Fallback to default

# --- Configuration ---
# Detect Cloud Mode (Streamlit Cloud uses secrets)
IS_CLOUD = "google" in st.secrets

if IS_CLOUD:
    DATA_DIR = None 
    ROOT_FOLDER_ID = st.secrets["google"].get("root_folder_id", "1f16OjsyvYfDXgdWT5t-mc43gd1IkaFN1")
else:
    DATA_DIR = r"C:\Users\L14\Documents\ThinkPad\Estructuras Control Documental"

NOTES_FILE = "notes.json"
CACHE_TTL = 300

st.set_page_config(
    page_title="Control Documental Pro", 
    layout="wide", 
    page_icon="🏗️",
    initial_sidebar_state="expanded"
)

# --- Custom CSS ---
st.markdown("""
<style>
    /* --- GLOBAL THEME --- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&family=Outfit:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    h1, h2, h3, .custom-title {
        font-family: 'Outfit', sans-serif !important;
    }
    
    .stApp {
        background-color: #F0F2F6;
        background-image: radial-gradient(#E0E7FF 1px, transparent 1px);
        background-size: 20px 20px;
    }

    /* --- STYLING CONTAINERS (GLASSMORPHISM) --- */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #FFFFFF;
        border-radius: 8px;
        color: #64748B;
        font-weight: 600;
        border: 1px solid #E2E8F0;
        transition: all 0.3s ease;
        padding: 0 20px;
        min-width: 140px;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #132B4F 0%, #1D3D6E 100%);
        color: #FFFFFF !important;
        border: none;
        box-shadow: 0 4px 6px -1px rgba(19, 43, 79, 0.3);
    }
    
    /* --- CUSTOM METRIC CARDS --- */
    div[data-testid="stMetric"] {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        border-left: 5px solid #132B4F;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        transition: transform 0.2s;
    }
    
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }

    div[data-testid="stMetric"] label {
        color: #64748B;
        font-size: 0.85rem;
    }
    
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #132B4F;
        font-size: 1.8rem;
        font-weight: 700;
    }

    /* --- SIDEBAR POLISH --- */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E2E8F0;
    }
    
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        height: 2.8em;
        transition: all 0.2s;
        border: 1px solid #132B4F;
        color: #132B4F;
    }
    
    .stButton>button:hover {
        transform: scale(1.02);
        background-color: #F0F4F8;
        color: #132B4F;
    }

    /* Primary Button Style */
    button[kind="primary"] {
        background: linear-gradient(90deg, #132B4F 0%, #1D3D6E 100%);
        border: none;
        box-shadow: 0 4px 6px rgba(19, 43, 79, 0.3);
        color: white !important;
    }

    /* --- DATA FRAME / TABLE --- */
    div[data-testid="stDataEditor"] {
        border-radius: 10px;
        border: 1px solid #E2E8F0;
        overflow: hidden;
        background: white;
    }
    
    /* --- NOTIFICATIONS --- */
    .stToast {
        background-color: #132B4F !important;
        color: white;
        border-radius: 8px;
    }
    
    /* --- MOBILE RESPONSIVENESS --- */
    @media (max-width: 768px) {
        div[data-testid="stMetric"] {
            padding: 15px;
            margin-bottom: 10px;
        }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            font-size: 1.4rem !important;
        }
        h1 {
            font-size: 1.8rem !important;
        }
        .stApp {
            background-size: 40px 40px;
        }
        .block-container {
            padding-top: 1rem;
        }
        .logo-circular {
            width: 60px !important;
            height: 60px !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# --- Persistence Layer ---
DRIVE_MAP_FILE = "drive_map.json"

@st.cache_data
def load_drive_map():
    if os.path.exists(DRIVE_MAP_FILE):
        try:
            with open(DRIVE_MAP_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
    return {}

def find_drive_link(file_name, project, drive_map):
    """
    Intenta encontrar el link de Drive buscando por nombre de archivo.
    A veces la estructura local no es idéntica a Drive, así que buscamos
    por coincidencia del nombre del archivo al final de las claves del mapa.
    """
    # 1. Búsqueda exacta por nombre de archivo
    for path_key, link in drive_map.items():
        if path_key.endswith(file_name) or path_key.endswith(f"/{file_name}"):
             return link
    return None

def load_notes():
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except: return {}
    return {}

def save_notes(notes_data):
    try:
        # Save main file first for speed
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(notes_data, f, indent=4, ensure_ascii=False)

        # Backup Mechanism (Probabilistic optimization)
        # Only run backup 20% of the time or if it's been a while, to save IO
        if random.random() < 0.2:
            backup_dir = "backups"
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(backup_dir, f"notes_backup_{timestamp}.json")
            
            with open(backup_file, "w", encoding="utf-8") as f:
                json.dump(notes_data, f, indent=4, ensure_ascii=False)
                
            # Optional: Clean old backups (keep last 50)
            # Only do this very rarely
            if random.random() < 0.1:
                backups = sorted([os.path.join(backup_dir, f) for f in os.listdir(backup_dir)], key=os.path.getmtime)
                if len(backups) > 50:
                    for b in backups[:-50]:
                        try: os.remove(b)
                        except: pass
        
        # --- NEW: Supabase Cloud Sync ---
        if SUPABASE:
            for path_key, meta in notes_data.items():
                SUPABASE.sync_oficio(path_key, meta)
                
    except Exception as e: st.error(f"Error Saving DB/Backup: {e}")

# --- Core Logic & Caching ---

def extract_version(filename):
    # Match patterns like v1, V2, rev3, R01, etc.
    patterns = [
        r"[-_ ]v(\d+)",       # _v1, -v2
        r"[-_ ]ver(\d+)",     # _ver1
        r"[-_ ]rev(\d+)",     # _rev0
        r"[-_ ]R(\d+)",       # _R1
    ]
    for p in patterns:
        match = re.search(p, filename, re.IGNORECASE)
        if match:
            return f"V{match.group(1)}"
    return "V1" # Default

def extract_base_name(filename):
    name, ext = os.path.splitext(filename)
    # Remove version suffix patterns like _v1, -V2, _R1, etc.
    patterns = [
        r"[-_ ]v\d+$", 
        r"[-_ ]ver\d+$", 
        r"[-_ ]rev\d+$", 
        r"[-_ ]R\d+$",
        r"v\d+$"
    ]
    clean = name
    for p in patterns:
        clean = re.sub(p, "", clean, flags=re.IGNORECASE)
    return clean.strip()

def extract_subcategory(filename, category):
    # Rule: Memorias -> Memoria
    if category == "Memorias":
        return "MEMORIA"
    
    name = filename.upper()
    
    # Rule: NU 200 -> PREFABRICADOS
    if "NU-200" in name or "NU 200" in name:
        return "PREFABRICADOS"

    # Keywords for automatic subcategorization
    keywords = [
        "CABALLETE", "ZAPATA", "PILOTE", "TERRACERIA", "EXCAVACION", 
        "COLUMNA", "VIGA", "LOSA", "ACERO", "MONTAJE", "TRABE", 
        "PARAPETO", "PROCESO", "GEOMETRICO", "TOPOGRAFIA", "ODT",
        "ALERO", "ESTRIBO", "DIAFRAGMA", "PRELOSA", "GUARNICION",
        "BANCO", "TOPE", "NEOPRENO", "MURETE", "PREFABRICADOS", "CABEZAL"
    ]
    
    for k in keywords:
        if k in name:
            return k
            
    return "GENERAL"

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def scan_directory(base_dir):
    """
    Scans the directory and returns a raw list of file dictionaries.
    In CLOUD mode, it uses the drive_map.json as the inventory source.
    """
    if IS_CLOUD:
        drive_map = load_drive_map()
        raw_files = []
        for rel_key, link in drive_map.items():
            # rel_key is something like "ProjectName/20260220/Person/File.pdf"
            parts = rel_key.split('/')
            project = parts[0] if len(parts) > 0 else "General"
            
            # Simple metadata extraction from name/path
            filename = parts[-1]
            ext = filename.split('.')[-1].upper() if '.' in filename else ""
            
            # Try to find date and person (mimicking local structure)
            date_folder = ""
            person = "Desconocido"
            if len(parts) > 2 and parts[1].isdigit() and len(parts[1]) == 8:
                d_str = parts[1]
                date_folder = f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:]}"
                if len(parts) > 3: person = parts[2]

            final_date = date_folder if date_folder else datetime.now().strftime("%Y-%m-%d")
            version = extract_version(filename)
            
            raw_files.append({
                "ID": rel_key,
                "Proyecto": project,
                "Fecha": final_date,
                "FechaCreacion": "Sincronizado de Drive", # We don't have ctime easily without API call
                "Responsable": person,
                "Documento": filename,
                "Ext": ext,
                "Ruta": rel_key, # In Cloud, ID and Ruta are the same rel_key
                "ModTime": datetime.now(),
                "Versión": version
            })
        return raw_files

    if not os.path.exists(base_dir): return []
    
    raw_files = []
    
    for root, dirs, files in os.walk(base_dir):
        rel_path = os.path.relpath(root, base_dir)
        parts = rel_path.split(os.sep)
        
        # Structure Parsing
        project = parts[0] if len(parts) > 0 and parts[0] != "." else "General"
        date_folder = ""
        person = "Desconocido"
        
        # Try to find Date (YYYYMMDD) and Person
        if len(parts) > 1 and parts[1].isdigit() and len(parts[1]) == 8:
            try:
                # Validate date format (YYYYMMDD)
                d_str = parts[1]
                datetime.strptime(d_str, "%Y%m%d") # Raises ValueError if invalid
                date_folder = f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:]}"
            except ValueError:
                # Invalid date format in folder name, ignore
                date_folder = ""
                
            if len(parts) > 2: person = parts[2]
            
        for file in files:
            if file.lower().endswith(('.pdf', '.dwg', '.rvt', '.xlsx', '.doc', '.docx')):
                full_path = os.path.join(root, file)
                fid = os.path.relpath(full_path, base_dir)
                
                try:
                    stat = os.stat(full_path)
                    # Helper for strict creation date formatting
                    dt_obj = datetime.fromtimestamp(stat.st_ctime)
                    ctime = dt_obj.strftime("%A, %d de %B de %Y")
                    # Capitalize first letter (Miércoles...)
                    ctime = ctime.capitalize()
                    
                    mod_time = datetime.fromtimestamp(stat.st_mtime)
                except:
                    ctime = datetime.now().strftime("%A, %d de %B de %Y")
                    mod_time = datetime.now()

                final_date = date_folder if date_folder else datetime.now().strftime("%Y-%m-%d")
                
                ext = file.split('.')[-1].upper()
                version = extract_version(file)
                
                raw_files.append({
                    "ID": fid,
                    "Proyecto": project,
                    "Fecha": final_date,
                    "FechaCreacion": ctime, # Formatted String
                    "Responsable": person,
                    "Documento": file,
                    "Ext": ext,
                    "Ruta": full_path,
                    "ModTime": mod_time,
                    "Versión": version
                })
                
    return raw_files

def get_pdf_metadata(file_path):
    try:
        reader = pypdf.PdfReader(file_path)
        if reader.metadata and "/CreationDate" in reader.metadata:
            d = reader.metadata["/CreationDate"]
            if d.startswith("D:"): d = d[2:]
            if len(d) >= 8: return datetime.strptime(d[:8], "%Y%m%d").strftime("%Y-%m-%d")
    except: pass
    return None

def categorize_document(filename, path_context, description=""):
    text = (filename + " " + path_context + " " + description).upper()
    
    # Priority Categories
    if any(k in text for k in ["MEMORIA", "CALCULO", "MC", "DESIGN"]): return "Memorias"
    if any(k in text for k in ["PROCESO", "CONSTRUCTIVO", "PROCEDIMIENTO", "MANUAL", "METODOLOGIA"]): return "Proceso Constructivo"
    if any(k in text for k in ["GEOMETRICO", "TRAZO", "TOPOGRAFIA", "ALINEAMIENTO", "PERFIL"]): return "Geométrico"
    if any(k in text for k in ["ODT", "ORDEN DE TRABAJO"]): return "ODT"

    # Standard Categories
    if any(k in text for k in ["CIMENTACION", "ZAPATA", "PILOTE", "TERRACERIA", "EXCAVACION"]): return "Subestructura"
    if any(k in text for k in ["COLUMNA", "VIGA", "LOSA", "ACERO", "ESTRUCTURA", "MONTAJE", "TRABE", "CABALLETE", "NU 200", "NU-200", "CABEZAL"]): return "Superestructura"
    if any(k in text for k in ["ARQUITECTURA", "ACABADO", "MURO", "FACHADA"]): return "Arquitectura"
    
    return "General"

def generate_auto_description(file_path):
    try:
        reader = pypdf.PdfReader(file_path)
        if len(reader.pages) > 0:
            text = reader.pages[0].extract_text()
            if not text: return ""
            lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 3]
            keywords = ["CONTENIDO", "PLANO:", "PROYECTO:", "CONTIENE:", "TITULO:"]
            summary = []
            for line in lines:
                for k in keywords:
                    if k in line.upper():
                        val = line.upper().split(k, 1)[-1].strip()
                        if len(val) > 2: summary.append(f"{k.title()} {val}")
            
            if not summary:
                 caps = [l for l in lines if l.isupper() and not l.replace(' ','').isdigit()]
                 summary = caps[:3]
            return " | ".join(summary[:4])
    except: return ""
    return ""

def open_file_system(path):
    if IS_CLOUD:
        return False, "Operación no disponible en la nube."
    try:
        os.startfile(path)
        return True, "Abriendo archivo..."
    except Exception as e:
        return False, str(e)

def open_folder_select(path):
    if IS_CLOUD:
        return False, "Operación no disponible en la nube."
    try:
        # Windows specific: select file in explorer
        subprocess.Popen(f'explorer /select,"{path}"')
        return True, "Abriendo ubicación..."
    except Exception as e:
        return False, str(e)

# --- Optimized Data Processing ---
@st.cache_data(show_spinner=False)
def build_dataframe(raw_files, notes_db, drive_map):
    full_data = []
    
    for f in raw_files:
        # Get DB data directly (notes_db is just a dict)
        db_entry = notes_db.get(f["ID"], {})
        if isinstance(db_entry, str): db_entry = {"notes": db_entry} # Compat
        
        # Defaults
        status = db_entry.get("status", "Pendiente")
        notes = db_entry.get("notes", "")
        desc = db_entry.get("description", "")
        reviewed = db_entry.get("reviewed", False) # New field
        
        # Auto-Category
        cat = categorize_document(f["Documento"], f["Ruta"], desc)
        # Sub-Category
        subcat = extract_subcategory(f["Documento"], cat)
        
        # Drive Link
        drive_link = find_drive_link(f["Documento"], f["Proyecto"], drive_map)

        # Base Name for Version Grouping
        base_name = extract_base_name(f["Documento"])
        
        # Numeric Version for Sorting
        ver_str = f["Versión"] 
        try:
            ver_num = int(ver_str[1:])
        except:
            ver_num = 1

        # Build complete row
        row = f.copy()
        row.update({
            "Ver": False,
            "Revisado": reviewed,
            "Estado": status,
            "Notas": notes,
            "Descripción": desc,
            "Categoría": cat,
            "Subcategoría": subcat,
            "DriveLink": drive_link,
            "BaseName": base_name,
            "VersionNum": ver_num
        })
        full_data.append(row)
    
    return pd.DataFrame(full_data)

# --- App Loading ---

# HEADER SECTION
c_logo, c_title = st.columns([1, 6])
with c_logo:
    # Try to load local logo (JPEG)
    logo_path = "Logo F12.jpg"
    
    if os.path.exists(logo_path):
        # We need to render it as a circle using HTML/CSS because st.image is rectangular
        # Read and encode image
        try:
            with open(logo_path, "rb") as f:
                img_data = f.read()
            encoded_img = base64.b64encode(img_data).decode()
            
            st.markdown(
                f"""
                <style>
                    .logo-container {{
                        display: flex;
                        justify-content: center;
                        align-items: center;
                    }}
                    img.logo-circular {{
                        border-radius: 50%;
                        width: 90px;
                        height: 90px;
                        object-fit: cover;
                        border: 3px solid #E3F2FD;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                        transition: transform 0.3s ease;
                    }}
                    img.logo-circular:hover {{
                        transform: scale(1.05) rotate(5deg);
                    }}
                </style>
                <div class="logo-container">
                    <img src="data:image/jpeg;base64,{encoded_img}" class="logo-circular">
                </div>
                """, 
                unsafe_allow_html=True
            )
        except Exception as e:
            st.error(f"Error cargando logo: {e}")
    else:
        st.markdown("# 🚄") # Fallback icon

with c_title:
    st.markdown("""
        <div style="padding-top: 15px;">
            <h1 style="margin:0; font-size: 2.5rem; color: #0F172A; text-transform: uppercase; letter-spacing: -1px;">
                Frente 12 <span style="color: #132B4F; font-weight: 300;">| Control Documental</span>
            </h1>
            <p style="margin:0; color: #64748B; font-size: 1rem; font-family: 'Inter';">
                Tablero de Gestión de Proyectos Ferroviarios
            </p>
        </div>
    """, unsafe_allow_html=True)

st.divider()

st.sidebar.title("🎛️ Panel de Control")

# 1. Load Data (Cached)
with st.spinner("Cargando repositorio..."):
    raw_files = scan_directory(DATA_DIR)

# 2. Merge with DB and Drive Map using Session State
if 'notes_db' not in st.session_state:
    st.session_state['notes_db'] = load_notes()

# Access data via session state
notes_db = st.session_state['notes_db']
drive_map = load_drive_map()

# Build Dataframe (Cached Processing)
df = build_dataframe(raw_files, notes_db, drive_map)

# --- Interaction Handlers ---

# Sidebar Actions
if st.sidebar.button("✨ Analizar PDFs (IA)"):
    progress_bar = st.sidebar.progress(0)
    count = 0
    total = len(df[df["Ext"] == "PDF"])
    
    for idx, row in df.iterrows():
        if row["Ext"] == "PDF" and not row["Descripción"]:
            new_desc = generate_auto_description(row["Ruta"])
            if new_desc:
                # Update DB
                fid = row["ID"]
                current = notes_db.get(fid, {})
                if isinstance(current, str): current = {"notes": current}
                current["description"] = new_desc
                notes_db[fid] = current
                count += 1
            if total > 0: progress_bar.progress(count / total)
            
    # Save to session and disk
    st.session_state['notes_db'] = notes_db
    save_notes(notes_db)
    st.cache_data.clear() # Clear cache to refresh dataframe
    st.sidebar.success(f"Analizados {count} documentos.")
    st.rerun()

st.sidebar.divider()

# Refresh Drive Map Action
if st.sidebar.button("🔄 Refrescar Mapa Drive"):
    with st.spinner("Conectando a Drive..."):
        try:
            subprocess.run(["python", "drive_service.py"], check=True)
            st.cache_data.clear()
            st.success("Mapa de Drive actualizado!")
            st.rerun()
        except Exception as e:
            st.error(f"Error actualizando Drive: {e}")

st.sidebar.divider()

# Filters
if not df.empty:
    sel_proj = st.sidebar.multiselect("Filtrar Proyecto", df["Proyecto"].unique())
    sel_cat = st.sidebar.multiselect("Filtrar Categoría", df["Categoría"].unique())
    sel_stat = st.sidebar.multiselect("Filtrar Estado", ["Pendiente", "En Revisión", "Aprobado", "Rechazado"])
    
    filter_reviewed = st.sidebar.checkbox("Ocultar Revisados", value=False)
    
    # Extension Filter
    ext_filter = st.sidebar.radio("Tipo de Archivo", ["Todos", "PDF", "DWG"], horizontal=True)
    if ext_filter == "PDF": df = df[df["Ext"] == "PDF"]
    elif ext_filter == "DWG": df = df[df["Ext"] == "DWG"]

    if sel_proj: df = df[df["Proyecto"].isin(sel_proj)]
    if sel_cat: df = df[df["Categoría"].isin(sel_cat)]
    if sel_stat: df = df[df["Estado"].isin(sel_stat)]
    if filter_reviewed: df = df[df["Revisado"] == False]

    search = st.sidebar.text_input("🔍 Buscar Documento")
    if search:
        df = df[df["Documento"].str.contains(search, case=False) | df["Responsable"].str.contains(search, case=False)]

# --- Interface Tabs ---

tab1, tab2, tab3 = st.tabs(["📊 Dashboard Gerencial", "📂 Explorador de Documentos", "⚖️ Comparador de Versiones"])

# TAB 1: DASHBOARD
with tab1:
    if df.empty:
        st.info("No hay datos para mostrar.")
    else:
        # Top Metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Documentos", len(df), delta=f"{len(df[df['Fecha'] == datetime.now().strftime('%Y-%m-%d')])} hoy")
        c2.metric("Pendientes", len(df[df["Estado"] == "Pendiente"]), delta_color="off")
        c3.metric("Aprobados", len(df[df["Estado"] == "Aprobado"]), delta_color="normal")
        c4.metric("Por Revisar", len(df[df["Revisado"] == False]), delta_color="inverse")
        
        st.divider()
        
        # Charts
        col_charts_1, col_charts_2 = st.columns(2)
        
        with col_charts_1:
            st.subheader("Documentos por Proyecto")
            
            # Group by Project
            proj_counts = df["Proyecto"].value_counts().reset_index()
            proj_counts.columns = ["Proyecto", "Cantidad"]
            
            # Horizontal Bar Chart
            c_proj = alt.Chart(proj_counts).mark_bar().encode(
                x=alt.X('Cantidad', title='Total Documentos'),
                y=alt.Y('Proyecto', sort='-x', title=''),
                color=alt.Color('Proyecto', legend=None, scale=alt.Scale(scheme='tableau10')),
                tooltip=['Proyecto', 'Cantidad']
            ).properties(height=300).configure(background='transparent')
            
            st.altair_chart(c_proj, use_container_width=True)

            st.markdown("---")
            st.subheader("Documentos por Disciplina")
            # Bar chart of Categoría
            chart_data = df["Categoría"].value_counts().reset_index()
            chart_data.columns = ["Categoría", "Cantidad"]
            
            c_cat = alt.Chart(chart_data).mark_bar().encode(
                 x=alt.X('Categoría', sort='-y'),
                 y=alt.Y('Cantidad'),
                 color='Categoría'
            ).configure(background='transparent')
            st.altair_chart(c_cat, use_container_width=True)
            
        with col_charts_2:
            st.subheader("Estado de Aprobación")
            status_counts = df["Estado"].value_counts().reset_index()
            status_counts.columns = ["Estado", "Cantidad"]
            
            # Interactive Selection Definition
            # We use a point selection bound to the 'Estado' field using a specific name
            selection = alt.selection_point(name="EstadoSelect", fields=['Estado'])
            
            c = alt.Chart(status_counts).mark_arc(innerRadius=60).encode(
                theta=alt.Theta(field="Cantidad", type="quantitative"),
                color=alt.Color(field="Estado", type="nominal", 
                                scale=alt.Scale(domain=["Aprobado", "Pendiente", "En Revisión", "Rechazado", "Obsoleto"], 
                                              range=["#10B981", "#F59E0B", "#3B82F6", "#EF4444", "#6B7280"])),
                tooltip=["Estado", "Cantidad"],
                opacity=alt.condition(selection, alt.value(1), alt.value(0.3))
            ).add_params(
                selection
            ).configure(background='transparent')
            
            # Render and Capture Selection
            event = st.altair_chart(c, use_container_width=True, on_select="rerun")
            
            # Drill-down Logic
            selected_states = []
            
            # Check if we have a selection for our named parameter
            if event and "selection" in event and "EstadoSelect" in event["selection"]:
                # The format is typically [{'Estado': 'Pendiente'}, ...]
                selection_data = event["selection"]["EstadoSelect"]
                if selection_data:
                    selected_states = [item["Estado"] for item in selection_data]
                
            if selected_states:
                st.markdown(f"##### 📂 Detalle: {', '.join(selected_states)}")
                
                # Filter main dataframe based on selection
                drill_df = df[df["Estado"].isin(selected_states)]
                
                st.dataframe(
                    drill_df[["Documento", "Proyecto", "Fecha", "DriveLink"]],
                    column_config={
                        "Documento": st.column_config.TextColumn("Documento", width="medium"),
                        "Proyecto": st.column_config.TextColumn("Proyecto", width="small"),
                        "DriveLink": st.column_config.LinkColumn("☁️", display_text="Ver"),
                    },
                    hide_index=True,
                    use_container_width=True,
                    height=200
                )
            else:
                st.caption("👆 Haz clic en los colores del gráfico para ver la lista de documentos.")

        st.divider()

        st.subheader("Desglose por Tipo de Elemento (Subcategoría)")
        
        if "Subcategoría" in df.columns:
            subcat_counts = df["Subcategoría"].value_counts().reset_index()
            subcat_counts.columns = ["Subcategoría", "Cantidad"]
            
            c_sub = alt.Chart(subcat_counts).mark_bar().encode(
                x=alt.X('Cantidad', title='Número de Documentos'),
                y=alt.Y('Subcategoría', sort='-x', title=''),
                color=alt.Color('Subcategoría', legend=None, scale=alt.Scale(scheme='tableau20')),
                tooltip=['Subcategoría', 'Cantidad']
            ).properties(height=400).configure(background='transparent')
            
            st.altair_chart(c_sub, use_container_width=True)

        st.divider()
        
        # --- NEW TIMELINE SECTION ---
        st.subheader("📅 Cronograma de Actividad (Entregas)")
        
        if not df.empty:
            # Prepare Data for Layout
            source = df.copy()
            # Ensure proper datetime format
            source["Fecha_DT"] = pd.to_datetime(source["Fecha"], errors='coerce')
            source = source.dropna(subset=["Fecha_DT"])
            
            # Interactive Timeline (Heatmap Style)
            # X: Time, Y: Project, Color: Count
            timeline = alt.Chart(source).mark_rect(cornerRadius=4).encode(
                x=alt.X('yearmonthdate(Fecha_DT):O', title='Fecha de Entrega', axis=alt.Axis(labelAngle=-45, format='%d %b')),
                y=alt.Y('Proyecto:N', title=None),
                color=alt.Color('count()', title='Docs', scale=alt.Scale(scheme='lightgreyteal')),
                tooltip=[
                    alt.Tooltip('yearmonthdate(Fecha_DT):T', title='Fecha', format='%d %b %Y'),
                    alt.Tooltip('Proyecto:N'),
                    alt.Tooltip('count()', title='Total Documentos'),
                    alt.Tooltip('Estado:N', title='Estado Predominante') # Just simplistic
                ]
            ).properties(
                height=350,
                title="Intensidad de Entregas por Proyecto"
            ).configure(
                background='transparent'
            ).configure_view(
                strokeWidth=0
            ).configure_axis(
                grid=False,
                domain=False
            )
            
            st.altair_chart(timeline, use_container_width=True)
            
            st.caption("💡 Este mapa de calor muestra qué días hubo mayor actividad de recepción de documentos en cada proyecto.")


# TAB 2: EXPLORER FRAGMENT
# Try to obtain fragment decorator for isolation
try:
    if hasattr(st, "fragment"):
        explorer_fragment = st.fragment
    elif hasattr(st, "experimental_fragment"):
        explorer_fragment = st.experimental_fragment
    else:
        # Fallback: simple decorator (no fragment, full reload on change)
        def explorer_fragment(func):
            return func
except:
    def explorer_fragment(func):
        return func

@explorer_fragment
def show_explorer(df):
    if df.empty:
        st.warning("No se encontraron documentos.")
        return

    # Header with Toggle and Global Save
    c_head_1, c_head_2, c_head_3 = st.columns([2, 1, 1])
    c_head_1.subheader(f"Listado Maestro ({len(df)})")
    
    # Store view_mode in session to persist within fragment?
    # No, radio handles itself usually.
    view_mode = c_head_2.radio("Modo", ["📊 Resumida", "✏️ Detallada"], horizontal=True, label_visibility="collapsed")
    
    # Placeholder for Save Button
    save_clicked = False
    if view_mode == "✏️ Detallada":
            save_clicked = c_head_3.button("💾 Guardar Todo", type="primary", key="global_save_top")

    # Helpers
    def make_link(row):
            if row.get("DriveLink"): return row["DriveLink"]
            return None

    def style_status(val):
        if val == "Aprobado": return 'background-color: #d1fae5; color: #065f46; font-weight: 600; border-radius: 4px;' 
        elif val == "Rechazado": return 'background-color: #fee2e2; color: #991b1b; font-weight: 600; border-radius: 4px;' 
        elif val == "En Revisión": return 'background-color: #dbeafe; color: #1e40af; font-weight: 600; border-radius: 4px;' 
        return ''

    # Unique Categories (Sorted)
    cats = sorted(df["Categoría"].unique())
    tabs = st.tabs([f"🔹 {cat}" for cat in cats])
    
    # Store editors to process updates later
    editors_db = {} 

    for cat, tab in zip(cats, tabs):
        with tab:
            # Filter Data
            cat_df = df[df["Categoría"] == cat].copy()
            if cat_df.empty:
                st.info("No hay documentos en esta categoría.")
                continue
            
            # Metric
            st.caption(f"Total documentos: {len(cat_df)}")

            # Logic Breakdown: If "Superestructura", we subdivide by Subcategoría
            if cat == "Superestructura":
                    # Get Subcategories
                    subcats = sorted(cat_df["Subcategoría"].unique())
                    
                    for sub in subcats:
                        sub_df = cat_df[cat_df["Subcategoría"] == sub].copy()
                        if sub_df.empty: continue
                        
                        # Sub-Header Bar
                        st.markdown(f"""
                        <div style="background-color: #E2E8F0; color: #1e293b; padding: 5px 10px; border-radius: 4px; font-weight: 600; margin-top: 15px; margin-bottom: 5px; font-size: 0.9em; border-left: 4px solid #3b82f6;">
                            🏗️ {sub.upper()} <span style="font-weight:400; font-size:0.9em;">({len(sub_df)})</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Render Tables
                        if view_mode == "📊 Resumida":
                            view_df = sub_df.sort_values(by=["ID"]).copy()
                            view_df["LinkURL"] = view_df.apply(make_link, axis=1)
                            # COLS: Added Responsable
                            cols = ["Proyecto", "Documento", "LinkURL", "Responsable", "Estado", "Fecha", "Notas"]
                            for c in cols:
                                if c not in view_df.columns: view_df[c] = ""
                            view_df = view_df[cols]
                            styled_df = view_df.style.map(style_status, subset=["Estado"])
                            
                            st.dataframe(
                                styled_df, 
                                column_config={
                                    "LinkURL": st.column_config.LinkColumn("Link", display_text="☁️", width="small"),
                                    "Responsable": st.column_config.TextColumn("Resp.", width="small")
                                },
                                use_container_width=True, 
                                hide_index=True
                            )
                        else:
                            # Edit Mode
                            sub_df = sub_df.sort_values(by=["Proyecto", "BaseName", "VersionNum"], ascending=[True, True, False])
                            sub_df = sub_df.drop_duplicates(subset=["Proyecto", "BaseName"], keep="first")
                            
                            ed = st.data_editor(
                                sub_df[["Ver", "Revisado", "Estado", "Proyecto", "Fecha", "Documento", "Versión", "DriveLink", "Responsable", "Notas", "ID", "Ruta", "Descripción", "Ext", "Categoría", "Subcategoría", "FechaCreacion"]],
                                column_config={
                                    "ID": None, "Ruta": None, "Ext": None, "Descripción": None, "Categoría": None, "Subcategoría": None,
                                    "Versión": None, "Fecha": st.column_config.TextColumn("Fecha", width="small", disabled=True),
                                    "Ver": st.column_config.CheckboxColumn("👁️", width="small", default=False),
                                    "Revisado": st.column_config.CheckboxColumn("Ok", width="small", default=False),
                                    "Estado": st.column_config.SelectboxColumn("Estado", options=["Pendiente", "En Revisión", "Aprobado", "Rechazado", "Obsoleto"], required=True, width="medium"),
                                    "Proyecto": st.column_config.TextColumn(width="small", disabled=True),
                                    "Documento": st.column_config.TextColumn(width="large", disabled=True),
                                    "DriveLink": st.column_config.LinkColumn("Link", display_text="☁️", width="small"),
                                    "Responsable": st.column_config.TextColumn("Resp.", width="small", disabled=True),
                                    "FechaCreacion": st.column_config.TextColumn("Creado el", width="small", disabled=True),
                                    "Notas": st.column_config.TextColumn("Notas", width="medium"),
                                },
                                hide_index=True, use_container_width=True, key=f"editor_{cat}_{sub}"
                            )
                            editors_db[f"{cat}_{sub}"] = ed
            else:
                    # Normal Rendering for other Categories
                    if view_mode == "📊 Resumida":
                        view_df = cat_df.sort_values(by=["ID"]).copy()
                        view_df["LinkURL"] = view_df.apply(make_link, axis=1)
                        # COLS: Added Responsable
                        cols = ["Proyecto", "Documento", "LinkURL", "Responsable", "Estado", "Fecha", "Notas"]
                        for c in cols:
                            if c not in view_df.columns: view_df[c] = ""
                        view_df = view_df[cols]
                        
                        styled_df = view_df.style.map(style_status, subset=["Estado"])
                        
                        st.dataframe(
                            styled_df, 
                            column_config={
                                "LinkURL": st.column_config.LinkColumn("Link", display_text="☁️", width="small"),
                                "Responsable": st.column_config.TextColumn("Resp.", width="small")
                            },
                            use_container_width=True, 
                            hide_index=True
                        )
                    else:
                        cat_df = cat_df.sort_values(by=["Proyecto", "BaseName", "VersionNum"], ascending=[True, True, False])
                        cat_df = cat_df.drop_duplicates(subset=["Proyecto", "BaseName"], keep="first")
                        
                        ed = st.data_editor(
                            cat_df[["Ver", "Revisado", "Estado", "Proyecto", "Fecha", "Subcategoría", "Documento", "Versión", "DriveLink", "Responsable", "Notas", "ID", "Ruta", "Descripción", "Ext", "Categoría", "FechaCreacion"]],
                            column_config={
                                "ID": None, "Ruta": None, "Ext": None, "Descripción": None, "Categoría": None,
                                "Subcategoría": st.column_config.TextColumn("Tipo", width="small"), 
                                "Versión": None, 
                                "Ver": st.column_config.CheckboxColumn("👁️", width="small", default=False),
                                "Revisado": st.column_config.CheckboxColumn("Ok", width="small", default=False),
                                "Estado": st.column_config.SelectboxColumn("Estado", options=["Pendiente", "En Revisión", "Aprobado", "Rechazado", "Obsoleto"], required=True, width="medium"),
                                "Proyecto": st.column_config.TextColumn(width="small", disabled=True),
                                "Fecha": st.column_config.TextColumn("Fecha", width="small", disabled=True),
                                "Documento": st.column_config.TextColumn(width="large", disabled=True),
                                "DriveLink": st.column_config.LinkColumn("Link", display_text="☁️", width="small"),
                                "Responsable": st.column_config.TextColumn("Resp.", width="small", disabled=True),
                                "FechaCreacion": st.column_config.TextColumn("Creado el", width="small", disabled=True),
                                "Notas": st.column_config.TextColumn("Notas", width="medium"),
                            },
                            hide_index=True, use_container_width=True, key=f"editor_{cat}"
                        )
                        editors_db[cat] = ed

    # --- LOGIC PROCESSING ---
    if view_mode == "✏️ Detallada":
        
        # Save Action
        if save_clicked:
            changes_count = 0
            current_db = st.session_state['notes_db']
            
            # Iterate over all editors
            for key_id, edited_df in editors_db.items():
                for index, row in edited_df.iterrows():
                    fid = row["ID"]
                    match = df[df["ID"] == fid]
                    if not match.empty:
                        original_row = match.iloc[0]
                        if (row["Revisado"] != original_row["Revisado"] or 
                            row["Estado"] != original_row["Estado"] or 
                            row["Notas"] != original_row["Notas"]):
                            
                            entry = current_db.get(fid, {})
                            if isinstance(entry, str): entry = {"notes": entry}
                            
                            entry["reviewed"] = bool(row["Revisado"])
                            entry["status"] = row["Estado"]
                            entry["notes"] = row["Notas"]
                            if "description" not in entry and original_row["Descripción"]:
                                entry["description"] = original_row["Descripción"]
                                
                            current_db[fid] = entry
                            changes_count += 1
            
            if changes_count > 0:
                st.session_state['notes_db'] = current_db
                save_notes(current_db)
                st.cache_data.clear()
                st.toast(f"✅ Se guardaron {changes_count} cambios!")
                time.sleep(0.5)
                st.rerun()
            else:
                st.info("No hay cambios.")

        # Preview Logic
        st.divider()
        sel_row = None
        for key_id, edited_df in editors_db.items():
            sel_rows = edited_df[edited_df["Ver"] == True]
            if not sel_rows.empty:
                sel_row = sel_rows.iloc[0]
                break 
        
        st.markdown("### 🔍 Vista Previa")
        if sel_row is None:
            st.info("👆 Selecciona '👁️' en alguna fila para ver detalles.")
        else:
                c_data, c_preview = st.columns([1, 1.5])
                with c_data:
                # Use current selection directly
                    doc_name = sel_row['Documento']
                    st.info(f"**{doc_name}**")
                    st.text(f"Versión: {sel_row.get('Versión', 'V1')}")
                    st.text(f"Categoría: {sel_row['Categoría']}")
                    if sel_row.get("Subcategoría"): st.text(f"Tipo: {sel_row['Subcategoría']}")
                    if sel_row["Descripción"]: st.caption(f"📝 {sel_row['Descripción']}")
                    if sel_row.get("FechaCreacion"): st.caption(f"📅 Creado: {sel_row['FechaCreacion']}")
                    
                    if sel_row.get("DriveLink"): st.success("✅ En Drive")
                    else: st.caption("⚠️ No sincronizado")

                    c_act_1, c_act_2 = st.columns(2)
                    with c_act_1:
                            if not IS_CLOUD:
                                if st.button("📂 Local", key="btn_open_quick"): open_file_system(sel_row["Ruta"])
                            else:
                                st.button("📂 Local (No disp.)", disabled=True, key="btn_open_quick_cloud")
                    with c_act_2:
                            if sel_row.get("DriveLink"): st.link_button("☁️ Drive", sel_row["DriveLink"])
                    
                    st.divider()
                    st.caption("🔄 Comparación de Versiones")
                    c_comp_1, c_comp_2 = st.columns(2)
                    with c_comp_1:
                        if st.button("Seleccionar como V1", key=f"btn_v1_{sel_row['ID']}"):
                            st.session_state['selected_v1'] = sel_row["Ruta"]
                            st.toast(f"✅ V1: {doc_name}")
                    with c_comp_2:
                        if st.button("Seleccionar como V2", key=f"btn_v2_{sel_row['ID']}"):
                            st.session_state['selected_v2'] = sel_row["Ruta"]
                            st.toast(f"✅ V2: {doc_name}")
                    st.divider()
                    
                    st.write("📝 **Nota Rápida**")
                    current_note_val = sel_row["Notas"] if sel_row["Notas"] and str(sel_row["Notas"]) != "nan" else ""
                    new_note_val = st.text_area("Edición rápida", value=current_note_val, height=100, key=f"note_prev_{sel_row['ID']}", label_visibility="collapsed")
                    
                    if st.button("Guardar Nota", key=f"save_btn_{sel_row['ID']}"):
                            if new_note_val != current_note_val:
                                current_db = st.session_state['notes_db']
                                entry = current_db.get(sel_row["ID"], {})
                                if isinstance(entry, str): entry = {"notes": entry}
                                entry["notes"] = new_note_val
                                if "description" not in entry and sel_row["Descripción"]: entry["description"] = sel_row["Descripción"]
                                if "status" not in entry and sel_row["Estado"]: entry["status"] = sel_row["Estado"]
                                current_db[sel_row["ID"]] = entry
                                st.session_state['notes_db'] = current_db
                                save_notes(current_db)
                                st.toast("✅ Nota guardada.")
                                st.cache_data.clear()
                                st.rerun()

                with c_preview:
                    if sel_row["Ext"] == "PDF":
                        if not IS_CLOUD and os.path.exists(sel_row["Ruta"]):
                            # We must handle large files carefully.
                            try:
                                with open(sel_row["Ruta"], "rb") as f:
                                    base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                                st.markdown(f'<iframe src="data:application/pdf;base64,{base64_pdf}#toolbar=0&navpanes=0&scrollbar=0" width="100%" height="500"></iframe>', unsafe_allow_html=True)
                            except Exception as e:
                                st.error(f"Error cargando PDF: {e}")
                        elif IS_CLOUD and sel_row.get("DriveLink"):
                            # In Cloud, use an embed/iframe with the Drive link (sharing must be public or session-based)
                            # Drive preview links look like: https://drive.google.com/file/d/ID/preview
                            link = sel_row["DriveLink"]
                            if "/view" in link:
                                preview_link = link.replace("/view", "/preview")
                                st.markdown(f'<iframe src="{preview_link}" width="100%" height="500"></iframe>', unsafe_allow_html=True)
                            else:
                                st.info("Usa el botón '☁️ Drive' para ver este documento.")
                        else:
                            st.info("Sin vista previa disponible.")
                    else:
                        st.info("Sin vista previa.")

# CALL THE FRAGMENT INSIDE TAB 2
with tab2:
    show_explorer(df)

# TAB 3: VERSION COMPARATOR
with tab3:
    st.header("⚖️ Comparador de Versiones")
    st.caption("Compara el contenido de dos carpetas para identificar cambios en archivos y texto de PDFs.")
    
    col_config_1, col_config_2 = st.columns(2)
    
    # Session state for paths
    if 'v1_path' not in st.session_state: st.session_state['v1_path'] = ""
    if 'v2_path' not in st.session_state: st.session_state['v2_path'] = ""
    
    with col_config_1:
        st.info("Versión Anterior (V1)")
        v1_input = st.text_input("Ruta V1", value=st.session_state['v1_path'], key="input_v1")
        if st.button("📂 Seleccionar V1"):
            # Simple fallback for folder selection if not using a specific dialog per OS
            # For now rely on text input or copy-paste
            pass

    with col_config_2:
        st.info("Versión Actual (V2)")
        v2_input = st.text_input("Ruta V2", value=st.session_state['v2_path'], key="input_v2")
    
    # Update state
    st.session_state['v1_path'] = v1_input
    st.session_state['v2_path'] = v2_input
    
    # Check for selected files from Explorer
    if 'selected_v1' in st.session_state and st.session_state['selected_v1']:
        st.info(f"📄 Archivo V1 seleccionado: {st.session_state['selected_v1']}")
        v1_input = st.session_state['selected_v1']
        
    if 'selected_v2' in st.session_state and st.session_state['selected_v2']:
        st.info(f"📄 Archivo V2 seleccionado: {st.session_state['selected_v2']}")
        v2_input = st.session_state['selected_v2']

    if st.button("🚀 Comparar Versiones", type="primary"):
        if os.path.isfile(v1_input) and os.path.isfile(v2_input):
             # File-to-File Comparison
             with st.spinner("Comparando documentos individuales..."):
                 # Mock a dataframe result for single file comparison
                 # We need to adapt logic or create a specific function
                 # For now, let's treat them as "Modified" if name matches or just force comparison
                 
                 # Extract text
                 t1 = version_comparator.extract_pdf_text(v1_input)
                 t2 = version_comparator.extract_pdf_text(v2_input)
                 
                 st.session_state['comp_text_v1'] = t1
                 st.session_state['comp_text_v2'] = t2
                 st.session_state['comp_mode'] = "FILE"
                 st.success("Comparación lista.")
                 
        elif not os.path.isdir(v1_input) or not os.path.isdir(v2_input):
            st.error("Por favor ingresa rutas válidas (Carpetas o Archivos).")
        else:
            with st.spinner("Analizando archivos y diferencias..."):
                # Run Comparison
                comp_df = version_comparator.compare_folders(v1_input, v2_input)
                st.session_state['comp_df'] = comp_df
                st.session_state['comp_mode'] = "FOLDER"
                st.success("Análisis completado.")
    
    # Display Results
    if 'comp_mode' in st.session_state and st.session_state['comp_mode'] == "FILE":
        st.divider()
        st.subheader("🔍 Comparación Directa de Archivos")
        c_diff_1, c_diff_2 = st.columns(2)
        
        t1 = st.session_state.get('comp_text_v1', "")
        t2 = st.session_state.get('comp_text_v2', "")
        
        with c_diff_1:
            st.text("Documento V1")
            st.text_area("V1", t1[:500]+"...", height=150, disabled=True)
        
        with c_diff_2:
            st.text("Documento V2")
            st.text_area("V2", t2[:500]+"...", height=150, disabled=True)
        
        # Written Conclusion
        st.subheader("📝 Conclusión de Cambios Detectados")
        summary_lines = version_comparator.summarize_changes(t1, t2)
        
        if summary_lines:
            for line in summary_lines:
                st.write(line)
        else:
             st.info("No se encontraron diferencias de texto.")

        # Diff
        with st.expander("Ver Diferencias Completas (HTML)", expanded=False):
            diff_html = version_comparator.generate_text_diff(t1, t2)
            st.components.v1.html(diff_html, height=400, scrolling=True)

    elif 'comp_df' in st.session_state:
        res_df = st.session_state['comp_df']
        
        # Metrics
        m1, m2, m3 = st.columns(3)
        m1.metric("Nuevos", len(res_df[res_df["Estado"] == "NEW"]))
        m2.metric("Eliminados", len(res_df[res_df["Estado"] == "REMOVED"]))
        m3.metric("Modificados", len(res_df[res_df["Estado"] == "MODIFIED"]))
        
        st.dataframe(
            res_df,
            column_config={
                "Estado": st.column_config.Column(
                    "Estado",
                    help="Estado del archivo",
                    width="medium",
                ),
                "PathV1": None, "PathV2": None, "SizeV1": None, "SizeV2": None
            },
            use_container_width=True
        )
        
        # Detail View
        st.divider()
        st.subheader("🔍 Inspector de Diferencias (PDF)")
        
        # Filter for modified or new PDFs
        mod_pdfs = res_df[
            ((res_df["Estado"] == "MODIFIED") | (res_df["Estado"] == "NEW")) & 
            (res_df["Archivo"].str.lower().str.endswith(".pdf"))
        ]
        
        if mod_pdfs.empty:
            st.info("No hay PDFs modificados para inspeccionar texto.")
        else:
            sel_file = st.selectbox("Selecciona un archivo para ver detalles:", mod_pdfs["Archivo"].unique())
            
            if sel_file:
                row = res_df[res_df["Archivo"] == sel_file].iloc[0]
                
                c_diff_1, c_diff_2 = st.columns(2)
                
                text_v1 = ""
                text_v2 = ""
                
                # Extract Text
                if row["PathV1"] and os.path.exists(row["PathV1"]):
                    text_v1 = version_comparator.extract_pdf_text(row["PathV1"])
                
                if row["PathV2"] and os.path.exists(row["PathV2"]):
                    text_v2 = version_comparator.extract_pdf_text(row["PathV2"])
                
                with c_diff_1:
                    st.text("Texto V1 (Extracto)")
                    st.text_area("V1", text_v1[:500]+"...", height=150, disabled=True)
                
                with c_diff_2:
                    st.text("Texto V2 (Extracto)")
                    st.text_area("V2", text_v2[:500]+"...", height=150, disabled=True)
                
                # Written Conclusion
                st.subheader("📝 Conclusión de Cambios Detectados")
                summary_lines = version_comparator.summarize_changes(text_v1, text_v2)
                
                if summary_lines:
                    for line in summary_lines:
                        st.write(line)
                else:
                     st.info("No se encontraron diferencias de texto.")

                # Diff
                with st.expander("Ver Diferencias Completas (HTML)", expanded=False):
                    diff_html = version_comparator.generate_text_diff(text_v1, text_v2)
                    st.components.v1.html(diff_html, height=400, scrolling=True)

# Footer
st.markdown("---")
st.caption(f"Sistema de Control Documental v3.1 (Fragments) | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
