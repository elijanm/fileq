import requests, os
from fastapi import HTTPException, Depends

KETO_READ_URL = os.getenv("KETO_READ_URL", "http://keto:4466")

def check_permission(subject: str, relation: str, object_: str):
    payload = {"namespace": "fileq", "object": object_, "relation": relation, "subject_id": subject}
    r = requests.post(f"{KETO_READ_URL}/check", json=payload)
    if r.status_code != 200 or not r.json().get("allowed"):
        raise HTTPException(status_code=403, detail="Permission denied")
    return True

# Usage in routes
# @router.delete("/files/{file_id}")
# def delete_file(file_id: str, user=Depends(get_current_user)):
#     check_permission(f"user:{user['id']}", "delete", f"file:{file_id}")
#     # proceed to delete