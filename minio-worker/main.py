from fastapi import FastAPI, HTTPException, Request, Header, Depends, Body
from pydantic import BaseModel
import subprocess
import json
import tempfile
import os
from datetime import datetime
from typing import Optional
# import docker

app = FastAPI()

# === SECURITY ===
API_TOKEN = os.getenv("API_TOKEN", "d5524c96-298a-4b42-bed3-98850ffb2d6d")

def verify_token(x_api_token: str = Header(...)):
    if x_api_token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")

# === MODELS ===
class User(BaseModel):
    username: str
    password: str
    create_bucket: Optional[bool] = True

class UpdateUserRequest(BaseModel):
    password: str
    policy: str | None = None

class PolicyData(BaseModel):
    name: str
    username: str | None = None
    bucket: str
    prefix: str | None = "*"
    permissions: list[str] = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]

# === UTILS ===
def run_mc_command(cmd: list[str]) -> str:
    """Run mc command inside MinIO container and return output"""
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"mc command failed: {e.stderr or str(e)}")

def get_minio_container() -> str:
    """Detect running MinIO container name dynamically"""
    return "myminio"
    client = docker.from_env()
    containers = client.containers.list(filters={"ancestor": "minio/minio"})
    if not containers:
        raise RuntimeError("No MinIO container found")
    return containers[0].name

def get_first_valid_arn() -> str:
    """Fetch the first valid ARN from MinIO config (no docker exec needed)."""
    return "arn:minio:sqs::minio_worker_hook:webhook"
    try:
        result = subprocess.run(
            ["mc", "admin", "info", "--json", "myminio"],
            capture_output=True, text=True, check=True
        )
        sqs_arns = json.loads(result.stdout)["info"].get("sqsARN", [])
        if not sqs_arns:
            raise HTTPException(status_code=500, detail="No valid SQS ARNs found in MinIO")
        return sqs_arns[0]
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch ARNs: {e.stderr or str(e)}")


def create_user_bucket_policy(username: str, bucket: str):
    """Restrict user to upload (PutObject) only into their bucket path"""
    policy = {
        "Version": "2012-10-17",
        "Metadata": {
            "created_for": username,
            "bucket": bucket,
            "created_at": datetime.utcnow().isoformat(),
            "purpose": "upload-only policy for user bucket"
        },
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:PutObject"],
                "Resource": [f"arn:aws:s3:::{bucket}/{username}/*"]
            }
        ]
    }
    policy_name = f"policy-{username}"
    with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as f:
        json.dump(policy, f)
        f.flush()
        run_mc_command(["mc", "admin", "policy", "create", "myminio", policy_name, f.name])
        run_mc_command(["mc", "admin", "policy", "attach", "myminio", policy_name, "--user", username])

# === ROUTES ===

@app.post("/buckets/{bucket}/notifications", dependencies=[Depends(verify_token)])
async def set_bucket_notification(bucket: str):
    """Configure MinIO bucket notification for PUT, DELETE, GET events."""
    arn = get_first_valid_arn()
    try:
        subprocess.run(
            ["mc", "event", "add", f"myminio/{bucket}", arn, "--event", "put,delete,get"],
            check=True, capture_output=True, text=True
        )
        return {"status": "success", "bucket": bucket, "arn": arn, "events": ["put", "delete", "get"]}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to set notification: {e.stderr or str(e)}")


@app.delete("/buckets/{bucket}/notifications", dependencies=[Depends(verify_token)])
async def remove_bucket_notification(bucket: str):
    """Remove all notification webhooks from a bucket."""
    try:
        subprocess.run(
            ["mc", "event", "remove", f"myminio/{bucket}", "--force"],
            check=True, capture_output=True, text=True
        )
        return {"status": "removed", "bucket": bucket}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to remove notification: {e.stderr or str(e)}")


@app.get("/buckets/{bucket}/notifications", dependencies=[Depends(verify_token)])
async def list_bucket_notifications(bucket: str):
    """List current notification webhooks on a bucket."""
    try:
        result = subprocess.run(
            ["mc", "event", "list", f"myminio/{bucket}"],
            check=True, capture_output=True, text=True
        )
        return {
            "status": "success",
            "bucket": bucket,
            "notifications": result.stdout.strip().splitlines()
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to list notifications: {e.stderr or str(e)}")
@app.post("/users", dependencies=[Depends(verify_token)])
def create_user(user: User):
    try:
        # 1. Create MinIO user
        subprocess.run(
            ["mc", "admin", "user", "add", "myminio", user.username, user.password],
            check=True
        )

        # 2. Create the user's bucket (bucket name == username)
        bucket_name = user.username
        create_bucket(bucket_name)

        # 3. Add default subfolders (.keep placeholders)
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            empty_file_path = tmp.name

        subfolders = ["Raw", "Approved", "Quarantined"]
        for folder in subfolders:
            target_path = f"myminio/{bucket_name}/{folder}/.keep"
            subprocess.run(["mc", "cp", empty_file_path, target_path], check=True)

        os.remove(empty_file_path)

        # 4. Create policy specific to this bucket
        create_user_bucket_policy(username=user.username, bucket=bucket_name)

        # 5. Auto–configure notification webhook
        arn = get_first_valid_arn()
        subprocess.run(
            [
                "mc", "event", "add",
                f"myminio/{bucket_name}",
                arn,
                "--event", "put,delete,get"
            ],
            check=True, capture_output=True, text=True
        )

        return {
            "status": "User created with bucket",
            "username": user.username,
            "bucket": bucket_name,
            "notifications": ["put", "delete", "get"]
        }

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=400, detail=f"Failed to create user: {e.stderr or str(e)}")


@app.get("/users", dependencies=[Depends(verify_token)])
def list_users():
    result = run_mc_command(["mc", "admin", "user", "list", "myminio"])
    users = []
    for line in result.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            username, status = parts[0], parts[1]
            try:
                policy_info = run_mc_command(["mc", "admin", "policy", "info", "myminio", "--user", username])
                policy_name = policy_info.splitlines()[0] if policy_info else None
            except Exception:
                policy_name = None
            users.append({"username": username, "status": status, "policy": policy_name})
    return {"users": users}

@app.delete("/users/{username}", dependencies=[Depends(verify_token)])
def delete_user(username: str):
    bucket_name = username
    try:
        # 1. Remove bucket notifications first
        try:
            subprocess.run(
                ["mc", "event", "remove", f"myminio/{bucket_name}", "--force"],
                check=True, capture_output=True, text=True
            )
        except subprocess.CalledProcessError:
            pass  # ignore if no events exist

        # 2. Remove the user's bucket and all contents
        subprocess.run(
            ["mc", "rb", "--force", f"myminio/{bucket_name}"],
            check=True
        )

        # 3. Remove the user account
        subprocess.run(
            ["mc", "admin", "user", "remove", "myminio", username],
            check=True
        )

        return {"status": f"User '{username}' and bucket '{bucket_name}' deleted successfully."}

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to delete user or bucket: {e.stderr or str(e)}"
        )


@app.put("/users/{username}", dependencies=[Depends(verify_token)])
def update_user(username: str, data: UpdateUserRequest):
    run_mc_command(["mc", "admin", "user", "add", "myminio", username, data.password])
    if data.policy:
        run_mc_command(["mc", "admin", "policy", "set", "myminio", data.policy, username])
    return {"status": f"User '{username}' updated", "policy": data.policy or "unchanged"}

@app.post("/buckets", dependencies=[Depends(verify_token)])
def create_bucket(bucket_name: str = Body(..., embed=True)):
    run_mc_command(["mc", "mb", "--ignore-existing", f"myminio/{bucket_name}"])
    return {"status": f"Bucket '{bucket_name}' created or already exists"}

@app.post("/policies", dependencies=[Depends(verify_token)])
def create_policy(policy: PolicyData):
    policy_json = {
        "Version": "2012-10-17",
        "Metadata": {
            "created_for": policy.username,
            "bucket": policy.bucket,
            "created_at": datetime.utcnow().isoformat(),
            "purpose": "upload-only policy for user bucket"
        },
        "Statement": [{
            "Effect": "Allow",
            "Action": policy.permissions,
            "Resource": [
                f"arn:aws:s3:::{policy.bucket}",
                f"arn:aws:s3:::{policy.bucket}/{policy.prefix or '*'}"
            ]
        }]
    }
    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
        json.dump(policy_json, f, indent=2)
        temp_path = f.name
    run_mc_command(["mc", "admin", "policy", "create", "myminio", policy.name, temp_path])
    if policy.username:
        run_mc_command(["mc", "admin", "policy", "set", "myminio", policy.name, policy.username])
    os.remove(temp_path)
    return {"status": "Policy created", "policy": policy.name, "applied_to": policy.username or None}
@app.post("/buckets/{bucket}/test-notification", dependencies=[Depends(verify_token)])
def test_bucket_notification(bucket: str):
    """
    Test MinIO bucket notifications by performing PUT, GET, and DELETE
    on a test object inside the bucket.
    """
    test_file = "notification_test.txt"
    local_path = os.path.join(tempfile.gettempdir(), test_file)
    object_path = f"myminio/{bucket}/{test_file}"

    try:
        # 1. Create a test file
        with open(local_path, "w") as f:
            f.write("This is a test file for bucket notification.")

        # 2. PUT (upload to MinIO)
        subprocess.run(["mc", "cp", local_path, object_path], check=True)

        # 3. GET (download back to temp to trigger GET event)
        download_path = os.path.join(tempfile.gettempdir(), f"downloaded_{test_file}")
        subprocess.run(["mc", "cp", object_path, download_path], check=True)

        # 4. DELETE (remove the test object)
        subprocess.run(["mc", "rm", object_path], check=True)

        # Cleanup local files
        if os.path.exists(local_path):
            os.remove(local_path)
        if os.path.exists(download_path):
            os.remove(download_path)

        return {
            "status": "success",
            "bucket": bucket,
            "actions": ["put", "get", "delete"],
            "note": "Check your webhook logs to confirm events were received."
        }

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed during test notification process: {e.stderr or str(e)}"
        )

@app.post("/notifications")
async def receive_minio_notification(request: Request):
    event = await request.json()
    event["client_ip"] = request.client.host
    print("MinIO Event Received:", json.dumps(event, indent=2))
    return {"status": "ok", "received_from": request.client.host}
