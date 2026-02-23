import requests
import json
import os

class SupabaseSync:
    def __init__(self):
        self.url = "https://ohkvhhqcrmqrluxhwxye.supabase.co"
        self.key = "sb_publishable_0-F9LPR5hE-1xHCIoO0 (truncated 35 bytes)"
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation, resolution=merge-duplicates"
        }
        self.project_id = "f8dbd24c-bf83-4173-aae7-9fd522b9e071" # Tren México-Querétaro

    def sync_oficio(self, path_key, metadata):
        """
        Synchronizes a single oficio to Supabase.
        """
        data = {
            "project_id": self.project_id,
            "document_number": str(path_key)[:100],
            "status": metadata.get("status", "Review"),
            "important": metadata.get("reviewed", False) or metadata.get("important", False),
            "notes": metadata.get("notes", ""),
            "description": metadata.get("description", "")
        }
        
        try:
            resp = requests.post(
                f"{self.url}/rest/v1/oficios",
                headers=self.headers,
                json=data
            )
            return resp.status_code in [200, 201, 204]
        except Exception:
            return False

    def get_all_oficios(self):
        try:
            resp = requests.get(
                f"{self.url}/rest/v1/oficios?project_id=eq.{self.project_id}",
                headers=self.headers
            )
            return resp.json() if resp.status_code == 200 else []
        except:
            return []
