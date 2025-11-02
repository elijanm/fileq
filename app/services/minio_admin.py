import requests
import json
import hashlib
import hmac
from datetime import datetime
import urllib.parse

class MinIOAdminAPI:
    def __init__(self, endpoint, access_key, secret_key):
        self.endpoint = endpoint.rstrip('/')
        self.access_key = access_key
        self.secret_key = secret_key
    
    def _sign_request(self, method, path, query_params="", payload=""):
        """
        Sign MinIO admin API request
        """
        # This is simplified - real implementation needs proper AWS4 signing
        timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
        
        # Create canonical request
        canonical_request = f"{method}\n{path}\n{query_params}\n\n{payload}"
        
        # Sign with HMAC-SHA256 (simplified)
        signature = hmac.new(
            self.secret_key.encode(),
            canonical_request.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return {
            'Authorization': f'AWS4-HMAC-SHA256 Credential={self.access_key}/{timestamp}',
            'X-Amz-Date': timestamp,
            'X-Amz-Content-Sha256': hashlib.sha256(payload.encode()).hexdigest()
        }
    
    def create_user(self, username, password):
        """
        Create user via MinIO Admin API
        """
        url = f"{self.endpoint}/minio/admin/v3/add-user"
        
        payload = {
            "accessKey": username,
            "secretKey": password,
            "status": "enabled"
        }
        
        headers = {
            'Content-Type': 'application/json',
            **self._sign_request('POST', '/minio/admin/v3/add-user', payload=json.dumps(payload))
        }
        
        response = requests.post(url, json=payload, headers=headers)
        return response.json()
    
    def list_users(self):
        """
        List all users
        """
        url = f"{self.endpoint}/minio/admin/v3/list-users"
        
        headers = self._sign_request('GET', '/minio/admin/v3/list-users')
        
        response = requests.get(url, headers=headers)
        return response.json()
# # Usage
# admin_api = MinIOAdminAPI(
#     endpoint="http://95.110.228.29:8714",
#     access_key="minioadmin", 
#     secret_key="your_admin_password"
# )

# # Create user
# result = admin_api.create_user("uploader", "upload123secret")
# print(result)