import os
import difflib
import pypdf
import pandas as pd
from datetime import datetime

def get_file_info(dir_path):
    """
    Scans a directory and returns a dictionary {filename: {path, size, mtime}}
    """
    files_info = {}
    if not os.path.exists(dir_path):
        return files_info

    for root, _, files in os.walk(dir_path):
        for f in files:
            # We only care about relative path to the version root for comparison
            # But here we might just compare flat filenames if requested, 
            # or relative paths if the structure is preserved.
            # unique ID usually is the relative path.
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, dir_path)
            
            try:
                stat = os.stat(full_path)
                mtime = datetime.fromtimestamp(stat.st_mtime)
                size = stat.st_size
            except:
                mtime = datetime.now()
                size = 0
                
            files_info[rel_path] = {
                "path": full_path,
                "size": size,
                "mtime": mtime,
                "name": f
            }
    return files_info

def compare_folders(dir_v1, dir_v2):
    """
    Compares two directories. 
    Returns a DataFrame with columns: [File, Status, PathV1, PathV2, DateV1, DateV2]
    Status: NEW, REMOVED, MODIFIED, SAME
    """
    v1_files = get_file_info(dir_v1)
    v2_files = get_file_info(dir_v2)
    
    all_files = set(v1_files.keys()) | set(v2_files.keys())
    
    results = []
    
    for f in all_files:
        in_v1 = f in v1_files
        in_v2 = f in v2_files
        
        status = "UNKNOWN"
        p1 = v1_files[f]["path"] if in_v1 else None
        p2 = v2_files[f]["path"] if in_v2 else None
        d1 = v1_files[f]["mtime"] if in_v1 else None
        d2 = v2_files[f]["mtime"] if in_v2 else None
        s1 = v1_files[f]["size"] if in_v1 else 0
        s2 = v2_files[f]["size"] if in_v2 else 0
        
        if in_v1 and in_v2:
            # Check for modification (size or content - here just size/name for speed, 
            # maybe precise later)
            if s1 != s2:
                status = "MODIFIED"
            else:
                status = "SAME"
        elif in_v2 and not in_v1:
            status = "NEW"
        elif in_v1 and not in_v2:
            status = "REMOVED"
            
        results.append({
            "Archivo": f,
            "Estado": status,
            "PathV1": p1,
            "PathV2": p2,
            "Fecha V1": d1,
            "Fecha V2": d2,
            "SizeV1": s1,
            "SizeV2": s2
        })
        
    return pd.DataFrame(results)

def extract_pdf_text(filepath, max_pages=None):
    """
    Extracts text from a PDF.
    """
    text = ""
    try:
        reader = pypdf.PdfReader(filepath)
        num_pages = len(reader.pages)
        if max_pages:
            num_pages = min(num_pages, max_pages)
            
        for i in range(num_pages):
            page = reader.pages[i]
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    except Exception as e:
        return f"Error leyendo PDF: {e}"
        
    return text

def generate_text_diff(text1, text2):
    """
    Generates a HTML diff of two texts.
    """
    t1_lines = text1.splitlines()
    t2_lines = text2.splitlines()
    
    # Simple unified diff for now, or we can use difflib.HtmlDiff
    d = difflib.HtmlDiff()
    return d.make_file(t1_lines, t2_lines, fromdesc="Versión Anterior (V1)", todesc="Versión Actual (V2)")

def summarize_changes(text1, text2):
    """
    Returns a list of structured changes.
    """
    t1_lines = [l.strip() for l in text1.splitlines() if l.strip()]
    t2_lines = [l.strip() for l in text2.splitlines() if l.strip()]
    
    diff = difflib.ndiff(t1_lines, t2_lines)
    
    changes = {
        "added": [],
        "removed": [],
        "modified_hint": [] # We will try to detect modifications roughly
    }
    
    for line in diff:
        if line.startswith('+ '):
            changes["added"].append(line[2:])
        elif line.startswith('- '):
            changes["removed"].append(line[2:])
            
    # Simple heuristic to pair up modifications (if a remove is followed closely by an add)
    # For now, just listing them is enough as a "written conclusion"
    
    summary = []
    
    if not changes["added"] and not changes["removed"]:
        summary.append("✅ No se detectaron cambios textuales significativos.")
    else:
        if changes["removed"]:
            summary.append(f"🔴 **{len(changes['removed'])} líneas eliminadas/cambiadas (V1):**")
            for l in changes["removed"][:10]: # Limit usage
                 summary.append(f"   - {l}")
            if len(changes["removed"]) > 10: summary.append("   - ...")
            
        if changes["added"]:
            summary.append(f"🟢 **{len(changes['added'])} líneas agregadas/nuevas (V2):**")
            for l in changes["added"][:10]:
                 summary.append(f"   - {l}")
            if len(changes["added"]) > 10: summary.append("   - ...")
            
    return summary
