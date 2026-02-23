import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Si modificas estos scopes, borra el archivo token.json.
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_service():
    """Muestra la autenticación básica con la API de Drive."""
    creds = None
    # El archivo token.json almacena los tokens de acceso y actualización del usuario,
    # y se crea automáticamente cuando el flujo de autorización se completa por primera vez.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # Si no hay credenciales (válidas) disponibles, deja que el usuario inicie sesión.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Guarda las credenciales para la próxima ejecución
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)

import json

def build_drive_map(folder_id, current_path=""):
    """
    Recursively scans a Google Drive folder and builds a map of:
    Relative Path -> WebViewLink
    
    Returns a dictionary.
    """
    service = get_drive_service()
    drive_map = {}
    
    print(f"Escaneando: {current_path if current_path else 'RAIZ'} ({folder_id})...")

    try:
        # Query for files AND folders in the current folder
        query = f"'{folder_id}' in parents and trashed = false"
        
        page_token = None
        while True:
            results = service.files().list(
                q=query,
                pageSize=1000, # Max allowed per page
                fields="nextPageToken, files(id, name, mimeType, webViewLink)",
                pageToken=page_token
            ).execute()
            
            items = results.get('files', [])
            
            for item in items:
                name = item['name']
                item_type = item['mimeType']
                
                # Construct relative path key
                # If current_path is empty, it's just "Name"
                # If current_path is "Folder", it's "Folder/Name"
                # We use forward slashes for the key to be consistent
                rel_key = f"{current_path}/{name}" if current_path else name
                
                if item_type == 'application/vnd.google-apps.folder':
                    # Recursive call for folders
                    # Warning: This can take time if structure is deep
                    sub_map = build_drive_map(item['id'], rel_key)
                    drive_map.update(sub_map)
                else:
                    # It's a file
                    link = item.get("webViewLink", "")
                    drive_map[rel_key] = link
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
                
    except Exception as e:
        print(f"Error escaneando carpeta {folder_id}: {e}")
        
    return drive_map

if __name__ == '__main__':
    # ID de carpeta proporcionado por el usuario (Raiz del repositorio en Drive)
    ROOT_FOLDER_ID = '1f16OjsyvYfDXgdWT5t-mc43gd1IkaFN1' 
    
    print("Iniciando mapeo de Google Drive (esto puede demorar unos minutos)...")
    
    full_map = build_drive_map(ROOT_FOLDER_ID)
    
    # Save to JSON
    output_file = 'drive_map.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(full_map, f, indent=4, ensure_ascii=False)
        
    print(f"\n¡Éxito! Se mapearon {len(full_map)} archivos.")
    print(f"El mapa se guardó en: {output_file}")
