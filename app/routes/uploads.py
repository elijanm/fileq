from fastapi import APIRouter, HTTPException,UploadFile,File, Form, Header,Request,Query,BackgroundTasks
from pydantic import BaseModel
from fastapi.responses import JSONResponse, PlainTextResponse,RedirectResponse,FileResponse
from bson import ObjectId
from minio import Minio
from datetime import timedelta,datetime,timezone
from botocore.exceptions import ClientError
from botocore.config import Config
from typing import Optional,List
from minio.error import S3Error
import uuid
import os,time
import tempfile
import boto3,math
import logging
import asyncio
import secrets
from routes.auth import get_current_user,checker,Depends,SessionInfo
import pytz
from utils.media_tools import (BASE_TOOLS,MIME_TOOLS)

router = APIRouter(prefix="/uploads", tags=["uploads"])
logger=logging.getLogger(__file__)
# ---------------------------------------------------
# MinIO client
# ---------------------------------------------------
# - "8714:9000"
# - "8715:9001"
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "95.110.228.29:8714")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")

TERMS_OF_SERVICE = """
================ TERMS OF SERVICE ================
1. You must not upload illegal,pornographic, harmful, or copyrighted content.
2. Files may be deleted at any time.
3. By uploading, you agree we are not liable for misuse.
==================================================
To continue with curl:
    curl -F "file=@%s" -F "tos_accept=true" http://localhost:8000/uploads/media
"""

minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

BUCKET = "public"
EXPIRY = timedelta(minutes=10)  # presigned URL expiry

temp_users={}

# Ensure bucket exists
if not minio_client.bucket_exists(BUCKET):
    minio_client.make_bucket(BUCKET)

def report_usage_sync(request, ext_id: str, size: int, object_name: str, file):
    """Background task: upload to MinIO, then push Lago usage."""

    try:
        # 1. Blocking MinIO upload
        with open(file, "rb") as f:
            result = minio_client.put_object(
                BUCKET,
                object_name,
                f,                 # file-like object
                length=-1,                 # unknown length → multipart
                part_size=10 * 1024 * 1024 # 10 MB chunks
            )
            print(f"✅ Uploaded {object_name} to {BUCKET}, etag={result.etag}")

        # 2. Run async Lago calls inside sync func
        async def _report():
            await request.app.state.lago_service.track_usage(
                user_id=ext_id,
                metric_code="cloud_storage_bytes",
                transaction_id=f"evt_{uuid.uuid4().hex}",
                properties={"disk_size": size},
            )
            await request.app.state.lago_service.track_usage(
                user_id=ext_id,
                metric_code="ingress_bytes",
                transaction_id=f"evt_{uuid.uuid4().hex}",
                properties={"file_upload": size},
            )
            return request.app.state.lago_service.check_quota(ext_id)

        quota = asyncio.run(_report())

        # 3. Generate presigned download URL
       

        # print(f"🔗 Download URL: {download_url}")
        print(f"📊 Quota: {quota}")

    except Exception as e:
        print(f"❌ Background task failed: {e}")
    finally:
        # Always cleanup temp file
        if os.path.exists(file):
            os.remove(file)
            print(f"🗑️ Deleted temp file {file}")



def getS3():
     return boto3.client(
        "s3",
        endpoint_url= os.getenv("MINIO_ENDPOINT", "http://95.110.228.29:8714"),   # your MinIO endpoint
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name="us-east-1",
        config=Config(
            signature_version='s3v4',
            s3={'addressing_style': 'path'}  # Important for MinIO
        )
    )
def choose_part_size(total_size: int, min_size=5*1024*1024, max_parts=10000) -> int:
    """
    Pick a part size so that number of parts <= max_parts.
    """
    part_size = max(min_size, math.ceil(total_size / max_parts))
    # Round up to nearest MB for neatness
    return int(math.ceil(part_size / (1024*1024)) * 1024*1024)
# ---------------------------------------------------
# Schemas
# ---------------------------------------------------
class SimpleUploadRequest(BaseModel):
    filename: str
    content_type: str

class PartReport(BaseModel):
    upload_id: str
    part_number: int
    etag: str
    size: int
class MultipartInitRequest(BaseModel):
    batch_id:Optional[str]=None
    filename: str
    total_size: int
    tos_accept: bool = False
    content_type:str
    upload_token: Optional[str]=None
    meta:Optional[dict]={}
    # part_size: int = 5 * 1024 * 1024  # default 5MB


class MultipartInitResponse(BaseModel):
    filename: str
    file_id: str
    upload_id: str
    part_size: int
    parts: list
    upload_token: Optional[str]=None


class MultipartCompleteRequest(BaseModel):
    file_id: str
    upload_id: str
    parts: list  # [{"part_number": 1, "etag": "xxx"}]
    filename: str
    
class BatchInitRequest(BaseModel):
    files: List[MultipartInitRequest]
    tos_accept: bool
    upload_token: str
    manifest:Optional[dict]={}

# ---------------------------------------------------
# Routes
# ---------------------------------------------------
def days_until_expiry(expiry_iso: str) -> int:
    expiry_date = datetime.fromisoformat(expiry_iso.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc).replace(tzinfo=expiry_date.tzinfo)
    delta = expiry_date - now
    return max(delta.days, 0)
def format_size(bytes_size: int) -> str:
    """Format file size into MB with 2 decimals"""
    if bytes_size is None:
        return "unknown"
    return f"{bytes_size / (1024 * 1024):.2f} MB"
def make_upload_box(token: str, filename: str,filesize:int, short_url: str,expiry_date:str,downloads:int=0,title="File uploaded successfully!") -> str:
    deletion_date=expiry_date+timedelta(days=1)
    exp = f"{days_until_expiry(expiry_date.isoformat())}days"
    lines = [
        f"Upload Token: {token}",
        f"File Name: {filename}",
        f"File Size: {format_size(filesize)}",
        f"Download Url: {short_url}",
        f"Downloads: {downloads}",
        f"Expiry In: {exp}",
        f"Deletion Date: {deletion_date}"
    ]
    width = max(len(line) for line in lines + [title])
    border = "+" + "-" * (width + 2) + "+"
    box = [
        border,
        f"| {title.ljust(width)} |",
        border,
    ]
    for line in lines:
        box.append(f"| {line.ljust(width)} |")
    box.append(border)
    return "\n".join(box)
def is_file_ready(minio_client_,bucket, object_name):
    try:
        minio_client_.stat_object(bucket, object_name)
        return True
    except S3Error as e:
        if e.code == "NoSuchKey":
            return False
        raise
def make_tip(token: str, filename: str) -> str:
    return f"""
Tip: Save your Upload Token and reuse it:
    curl -F "file=@{filename}" -F "tos_accept=true" \\
         -F "token={token}" http://localhost:8000/uploads/media
"""

    return "\n".join(box) + tip
@router.post("/media")
@checker.require_role("guest")
async def upload_file(request:Request,file: UploadFile = File(...),
                      tos_accept: bool = Form(False),
                      user:SessionInfo=Depends(get_current_user),
                      background_tasks: BackgroundTasks=None
                      ):
    """
    Upload an actual file (<250MB) directly.
    """
    request.app.state.metrics.files_uploading.inc()
    
    file.file.seek(0, os.SEEK_END)
    size_bytes = file.file.tell()
    file.file.seek(0)
    start = time.time()
    
    request.app.state.metrics.file_size_bytes.observe(size_bytes)
    
    ext_id=None
    if user.is_guest:
       ext_id= user.metadata["lago_customer"]["customer"]["external_id"]
    
    import uuid
    user_agent = request.headers.get("user-agent", "").lower()
    if file:
      tos_text = TERMS_OF_SERVICE % file.filename
    else:
      tos_text = TERMS_OF_SERVICE % "myFile.txt"
    if not tos_accept:
        request.app.state.metrics.files_failed_total.labels(reason="term_of_service_not_checked").inc()
        
        if "curl" in user_agent:
            
            return PlainTextResponse(tos_text, status_code=400)
        return JSONResponse(
            status_code=400,
            content={"error": "You must accept the Terms of Service", "terms": tos_text}
        )
    file_id = str(uuid.uuid4())
    object_name = f"{file_id}_{file.filename}"
    
    try:
        # Upload file stream
        start_minio = time.time()
        # minio_client.put_object(
        #     BUCKET,
        #     object_name,
        #     file.file,                # file-like object
        #     length=-1,                # unknown length, use multipart
        #     part_size=10*1024*1024    # 10MB chunks
        # )
        
        
        tmp = tempfile.NamedTemporaryFile(delete=False)
        contents = await file.read()
        tmp.write(contents)
        tmp.close()
        
        size_mb = size_bytes / (1024 ** 2)
        elapsed = time.time() - start_minio
        print(f"Took {elapsed:.2f} seconds to upload {size_mb:.2f} MB to write to disk")
    
        gb = size_bytes / (1024 ** 3)
        size = float(f"{gb:.6f}")
        start_usage = time.time()
        background_tasks.add_task(
        report_usage_sync,
            request,
            ext_id,
            size,
            object_name,
            tmp.name
        )
        elapsed = time.time() - start_usage
        print(f"Took {elapsed:.2f} seconds to upload {size_mb:.2f} MB to report usage in bg")
        
        request.app.state.metrics.files_uploaded_total.labels(method="simple_upload", status="uploaded").inc()
        request.app.state.metrics.ingress_bytes_total.inc(size)
        
        # Generate a download URL
        download_url = minio_client.presigned_get_object(
            BUCKET, object_name, expires=timedelta(seconds=3600),
            response_headers={
            "response-content-disposition": f'attachment; filename="{file.filename}"'
        }
        )
        from collections import Counter
      
        created_at = datetime.now(timezone.utc)
        expiry_date = created_at + timedelta(days=31)
        file_entry = {
            "timestamp": created_at.isoformat(),
            "file_name": file.filename,
            "object_name": object_name,
            "user_token":user.user_id,
            "expiry_date":expiry_date,
            "downloads":0,
            "download_info":[],
            "file_size":file.size,
            "safe_status":"pending",
            "ip_address": request.client.host,
            "user_agent": user_agent,
            "download_url": download_url,
            "tmp_path":tmp.name,
            "session_id": secrets.token_urlsafe(8),
            "meta":{
                "mime_type":file.content_type or "application/octet-stream"
            }
        }
        
#         # Store in database
        request.app.state.db.files.insert_one(file_entry)
        short_url = f"http://localhost:8000/uploads/download/{file_entry['session_id']}"
        if "curl" in user_agent:
            box = make_upload_box(user.user_id,file.filename,size_bytes,short_url,expiry_date)
            tip = make_tip(user.user_id, file.filename)
           
            return PlainTextResponse(box + "\n\n" + tip)
        
        mime_type = file.content_type or "application/octet-stream"
        category = mime_type.split("/")[0]
        
        tools = BASE_TOOLS.copy()
        if category in MIME_TOOLS:
            tools.extend(MIME_TOOLS[category])
        return {
            "user_id":user.user_id,
            "file_id": file_id,
            "file_name": file.filename,
            "file_size": format_size(size_bytes),
            "download_url": short_url,
            "tools":tools
        }
    except Exception as e:
        request.app.state.metrics.files_failed_total.labels(reason=str(e)).inc()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        request.app.state.metrics.files_uploading.dec()
        elapsed = time.time() - start
        size_mb = size_bytes / (1024 ** 2)  # MB
        print(f"Took {elapsed:.2f} seconds to upload {size_mb:.2f} MB")
        request.app.state.metrics.upload_duration_seconds.observe(time.time() - start)
    

@router.get("/media/list/{upload_token}")
async def list_files(
    request: Request,
    upload_token: str,
    page: int = Query(1, ge=1)
):
    user_agent = request.headers.get("user-agent", "").lower()

    # Pagination logic
    if "curl" in user_agent:
        per_page = 2
    else:
        per_page = 10

    skip = (page - 1) * per_page
    cursor = request.app.state.db.files.find({"user_token":upload_token}).sort("timestamp", -1).skip(skip).limit(per_page)
    docs = list(cursor)
    
    # Format output
    if "curl" in user_agent:
        boxes = [make_upload_box(doc['user_token'],doc['file_name'],doc['file_size'],f"http://localhost:8000/uploads/download/{doc['session_id']}",doc['expiry_date'],doc['downloads'],title="File Details") for doc in docs]
        return PlainTextResponse("\n\n".join(boxes))
    else:
        # Clean Mongo ObjectId for JSON
        for d in docs:
            d["_id"] = str(d["_id"])
        return JSONResponse(docs)

@router.get("/download/{token}")
async def download_file(token: str, request: Request, tz: str = "UTC",user:SessionInfo=Depends(get_current_user)):
    country = request.state.ip_country
    
    with request.app.state.metrics.download_duration_seconds.labels(country=country).time():
        # find the file
        file_entry = request.app.state.db.files.find_one({"session_id": token})
        if not file_entry:
            raise HTTPException(status_code=404, detail="File not found")

        # prepare download metadata
        ip = request.state.geo_id
        ua = request.headers.get("user-agent", "unknown")
        mime=file_entry.get("meta",{}).get("mime_type","application/octet-stream")
        file_type = mime.split("/")[0]
        try:
            tz_obj = pytz.timezone(tz)
        except Exception:
            tz_obj = pytz.UTC

        now = datetime.now(tz_obj).isoformat()

        download_event = {
            "ip": ip,
            "country_iso":country,
            "user_agent": ua,
            "timestamp": now,
            "timezone": str(tz_obj)
        }
        
        
        

        # increment downloads and append download_info
        request.app.state.db.files.update_one(
            {"_id": file_entry["_id"]},
            {
                "$inc": {"downloads": 1},
                "$push": {"download_info": download_event}
            }
        )
        
        try:
            if is_file_ready(minio_client,BUCKET, file_entry["object_name"]):
                request.app.state.metrics.files_downloaded_total.labels(source="minio", file_type=file_type,country=country).inc()
                request.app.state.metrics.files_downloaded_bytes_total.labels(source="minio", file_type=file_type,country=country).inc(file_entry["file_size"])
                
                url = minio_client.presigned_get_object(
                        BUCKET,
                        file_entry["object_name"],
                        expires=timedelta(minutes=10),
                        response_headers={
                            "response-content-disposition": f"attachment; filename=\"{file_entry['file_name']}\""
                        }
                    )
                
                return RedirectResponse(url)
        except Exception as e:
            pass
        # 🚧 File still uploading, serve temp file if available
        tmp_path = file_entry.get("tmp_path")
        
        if tmp_path and os.path.exists(tmp_path):
            request.app.state.metrics.files_downloaded_total.labels(source="tmp", file_type=file_type,country=country).inc()
            request.app.state.metrics.files_downloaded_bytes_total.labels(source="tmp", file_type=file_type,country=country).inc(file_entry["file_size"])
            return FileResponse(
                tmp_path,
                filename=file_entry["file_name"],
                media_type=mime
            )
        request.app.state.metrics.files_downloaded_fail_total.labels(source="tmp", file_type=file_type,country=country).inc()
        # ❌ Neither ready in MinIO nor temp file exists
        return JSONResponse(
            status_code=202,
            content={"status": "pending", "message": "File is still being processed"}
        )
    

import re
import unicodedata
from urllib.parse import quote

def sanitize_s3_key(filename, max_length=255):
    """
    Comprehensive S3 key sanitization.
    
    S3 key naming rules:
    - Can be up to 1024 characters
    - Can contain letters, numbers, and these characters: ! - _ . * ' ( )
    - Should avoid: spaces, &, $, @, =, ;, :, +, ,, ?
    """
    if not filename:
        return "unnamed_file"
    
    # Normalize unicode characters
    filename = unicodedata.normalize('NFKD', filename)
    
    # Replace spaces and common problematic chars
    replacements = {
        ' ': '_',
        '&': 'and',
        '@': 'at',
        '+': 'plus',
        '=': 'equals',
        '#': 'hash',
        '%': 'percent',
        '?': '',
        ':': '_',
        ';': '_',
        ',': '_',
        '|': '_',
        '<': '',
        '>': '',
        '"': '',
        "'": '',
        '\\': '_',
        '/': '_',
        '*': '_star_',
        '~': '_',
        '`': '',
        '^': '',
        '[': '(',
        ']': ')',
        '{': '(',
        '}': ')',
    }
    
    for old, new in replacements.items():
        filename = filename.replace(old, new)
    
    # Keep only safe characters (more restrictive approach)
    filename = re.sub(r'[^\w\-_\.\(\)]', '', filename)
    
    # Remove consecutive underscores
    filename = re.sub(r'_+', '_', filename)
    
    # Remove leading/trailing dots, dashes, underscores
    filename = filename.strip('._-')
    
    # Ensure minimum length
    if not filename:
        filename = "file"
    
    # Truncate if too long (leave room for file_id prefix)
    if max_length and len(filename) > max_length:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        max_name_len = max_length - len(ext) - 1 if ext else max_length
        filename = name[:max_name_len] + ('.' + ext if ext else '')
    
    return filename



@router.post("/multipart/init", response_model=MultipartInitResponse)
async def multipart_init(req: MultipartInitRequest,request:Request):
    
    MIN_MULTIPART_SIZE = 5 * 1024 * 1024  # 5MB minimum for S3
    if req.total_size < MIN_MULTIPART_SIZE:
        raise HTTPException(
            status_code=400, 
            detail=f"File too small for multipart upload. Minimum size: {MIN_MULTIPART_SIZE:,} bytes, got: {req.total_size:,} bytes. Use simple upload endpoint instead."
        )
        
    _id = ObjectId()
    file_id = str(uuid.uuid4())

    object_name = f"{file_id}_{sanitize_s3_key(req.filename)}"
    s3_client = getS3()
    user_agent = request.headers.get("user-agent", "").lower()
    try:
        # Start upload
        resp = s3_client.create_multipart_upload(
            Bucket=BUCKET,
            Key=object_name,
            ContentType=req.content_type or "application/octet-stream"
        )
        upload_id = resp["UploadId"]
        if not req.upload_token:
            req.upload_token = str(uuid.uuid4())
        # Calculate part count
        part_size = choose_part_size(req.total_size)
        part_count = (req.total_size + part_size - 1) // part_size

        # Generate presigned URLs
        parts = []
        for i in range(1, part_count + 1):
            url = s3_client.generate_presigned_url(
                "upload_part",
                Params={
                    "Bucket": BUCKET,
                    "Key": object_name,
                    "UploadId": upload_id,
                    "PartNumber": i,
                },
                ExpiresIn= 7*24*3600,
                HttpMethod='PUT'
            )
            parts.append({"part_number": i, "url": url})
        created_at = datetime.now(timezone.utc)
        expiry_date = created_at + timedelta(days=31)
        
        file_entry = {
            "_id":_id,
            "batch_id":req.batch_id,
            "timestamp": created_at.isoformat(),
            "file_name": req.filename,
            "object_name": object_name,
            "user_token":req.upload_token,
            "expiry_date":expiry_date,
            "downloads":0,
            "download_info":[],
            "file_size":req.total_size,
            "safe_status":"pending",
            "ip_address": request.client.host,
            "user_agent": user_agent,
            "download_url": None,
            "session_id": secrets.token_urlsafe(8),
            "meta":{
                "mime_type":req.content_type or "application/octet-stream",
                "upload_id":upload_id,
                "file_id":file_id,
                "part_size": part_size,
                "parts":parts,
                "completed_parts": []
            }
        }
        
#         # Store in database
        u = request.app.state.db.files.insert_one(file_entry)
        # file_id=str(u.inserted_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Init multipart failed: {e}")

    return MultipartInitResponse(
        filename= req.filename,
        file_id=file_id,
        upload_id=upload_id,
        part_size=part_size,
        parts=parts,
        upload_token=req.upload_token
    )
@router.get("/test-s3")
async def test_s3():
    try:
        s3_client = getS3()
        buckets = s3_client.list_buckets()
        return {"status": "success", "buckets": [b['Name'] for b in buckets['Buckets']]}
    except Exception as e:
        return {"status": "error", "message": str(e)}
@router.post("/multipart/complete")
async def multipart_complete(req: MultipartCompleteRequest):
    object_name = f"{req.file_id}_{sanitize_s3_key(req.filename)}"
    s3_client = getS3()

    try:
        # Build the part list with proper ETag validation
        parts = []
        for p in req.parts:
            etag = p.get("etag")
            part_number = p.get("part_number")
            
            # Validate required fields
            if not etag or not part_number:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Missing ETag or part number for part {part_number}"
                )
            
            # Clean and validate ETag format
            etag = etag.strip().strip('"').strip("'")
            if len(etag) < 32:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid ETag format for part {part_number}: '{etag}'"
                )
            
            parts.append({
                "ETag": f'"{etag}"',  # S3 expects ETags to be quoted
                "PartNumber": part_number
            })

        # Sort parts by part number to ensure correct order
        parts.sort(key=lambda x: x["PartNumber"])
        
        # Debug logging
        logger.info(f"Completing multipart upload for {req.filename}")
        logger.info(f"Upload ID: {req.upload_id}")
        logger.info(f"Parts count: {len(parts)}")
        if len(parts) <= 10:  # Only log for small number of parts
            for part in parts:
                logger.debug(f"Part {part['PartNumber']}: ETag {part['ETag']}")

        # Complete upload
        response = s3_client.complete_multipart_upload(
            Bucket=BUCKET,
            Key=object_name,
            UploadId=req.upload_id,
            MultipartUpload={"Parts": parts},
        )
        
        logger.info(f"S3 completion response: {response.get('ETag', 'No ETag')}")

        # Final download URL
        download_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": object_name},
            ExpiresIn=(10 * 24 * 60 * 60), #10 days
        )

    except ClientError as e:
        
        try:
            parts_response = s3_client.list_parts(
                Bucket=BUCKET,
                Key=object_name,
                UploadId=req.upload_id
            )
            print(parts_response)
        except Exception as x:
            print(x)
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        logger.error(f"S3 ClientError: {error_code} - {error_message}")
        logger.error(f"Upload ID: {req.upload_id}")
        logger.error(f"Object: {object_name}")
        
        if error_code == "InvalidPart":
            # Provide detailed error information
            logger.error("InvalidPart error details:")
            for i, part in enumerate(parts):
                logger.error(f"  Part {part['PartNumber']}: ETag {part['ETag']}")
            
            raise HTTPException(
                status_code=500, 
                detail=f"S3 InvalidPart error: {error_message}. Check upload logs for part details."
            )
        elif error_code == "NoSuchUpload":
            raise HTTPException(
                status_code=404,
                detail=f"Upload session not found: {req.upload_id}"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"S3 error ({error_code}): {error_message}"
            )
            
    except Exception as e:
        logger.error(f"Unexpected error in multipart complete: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Complete multipart failed: {e}")

    return {
        "file_id": req.file_id,
        "download_url": download_url,
        "status": "completed"
    }
@router.post("/report-part")
async def report_part(report: PartReport, request: Request):
    db = request.app.state.db
    files = db.files
    
    # Log for debugging
    print(f"Looking for upload_id: {report.upload_id}")
    
    # Add completed part to the array
    result =  files.update_one(
        {"meta.upload_id": report.upload_id},
        {"$push": {"meta.completed_parts": report.dict()}}
    )
    
    print(f"Update result: matched={result.matched_count}, modified={result.modified_count}")
    
    if result.matched_count == 0:
        # Debug: show what documents exist
        sample_docs = list(files.find({}, {"meta.upload_id": 1, "file_name": 1}).to_list(5))
        print(f"Sample documents: {sample_docs}")
        raise HTTPException(status_code=404, detail=f"Upload not found: {report.upload_id}")

    return {"status": "ok", "upload_id": report.upload_id}


@router.get("/progress/{upload_id}")
async def get_progress(upload_id: str, request: Request):
    db    = request.app.state.db
    files = db.files
    doc   = files.find_one({"meta.upload_id": upload_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Upload not found")

    total_size      = doc.get("file_size", 0)
    completed_parts = doc.get("meta", {}).get("completed_parts", [])
    original_parts  = doc.get("meta", {}).get("parts", [])
    
    # Calculate uploaded bytes using part_size * completed_parts_count
    # Get part_size from the upload session (should be stored in meta)
    part_size = doc.get("meta", {}).get("part_size", 0)
    
    if part_size > 0:
        # Use part_size * number of completed parts
        uploaded_bytes = len(completed_parts) * part_size
        # But cap it at total_size for the last part
        uploaded_bytes = min(uploaded_bytes, total_size)
    else:
        # Fallback: try to sum from completed_parts if they have size
        uploaded_bytes = sum(part.get("size", 0) for part in completed_parts)
    
    progress = round(uploaded_bytes / total_size * 100, 2) if total_size > 0 else 0
    
    return {
        "upload_id": upload_id,
        "file_name": doc.get("file_name"),
        "uploaded_bytes": uploaded_bytes,
        "total_size": total_size,
        "progress": progress,
        "parts_done": len(completed_parts),
        "parts_total": len(original_parts)
    }

@router.post("/multipart/init-batch")
async def multipart_init_batch(req: BatchInitRequest, request: Request):
    sessions = []
    simple_uploads = []
    created_at = datetime.now(timezone.utc)
    expiry_date = created_at + timedelta(days=31)
    
    manifest = {
        "_id": ObjectId(),
        "manifest": req.manifest,
        "created_at": created_at,
        "expiry_date": expiry_date,
    }
    u = request.app.state.db.folder_manifest.insert_one(manifest)
    
    MIN_MULTIPART_SIZE = 5 * 1024 * 1024  # 5MB
    
    for f in req.files:
        if f.total_size < MIN_MULTIPART_SIZE:
            # Mark for simple upload
            simple_uploads.append({
                "filename": f.filename,
                "total_size": f.total_size,
                "content_type": f.content_type,
                "reason": "file_too_small_for_multipart"
            })
        else:
            # Use multipart for larger files
            try:
                single = await multipart_init(
                    MultipartInitRequest(
                        batch_id=str(u.inserted_id),
                        filename=f.filename,
                        total_size=f.total_size,
                        meta=f.meta or {},
                        tos_accept=req.tos_accept,
                        upload_token=req.upload_token,
                        content_type=f.content_type or "application/octet-stream"
                    ), request
                )
                sessions.append(single)
            except HTTPException as e:
                # If multipart init fails, add to simple uploads
                simple_uploads.append({
                    "filename": f.filename,
                    "total_size": f.total_size,
                    "content_type": f.content_type,
                    "reason": str(e.detail)
                })
    
    return {
        "sessions": sessions,
        "simple_uploads": simple_uploads,
        "message": f"Created {len(sessions)} multipart sessions, {len(simple_uploads)} files need simple upload"
    }
@router.post("/minio/init")
async def admin_mino(request: Request):
   # Usage
    from services.minio_admin import MinIOAdminAPI
    admin_api = MinIOAdminAPI(
        endpoint="http://95.110.228.29:8714",
        access_key="minioadmin", 
        secret_key="minioadmin"
    )

    # Create user
    result = admin_api.create_user("uploader", "upload123secret")
    return result

@router.get("/files/tools/{file_id}")
async def get_file_tools(file_id: str, request: Request):
    file_entry = request.app.state.db.files.find_one({"session_id": file_id})
    if not file_entry:
        raise HTTPException(404, "File not found")
    
    mime_type = file_entry.get("meta",{}).get("mime_type", "application/octet-stream")
    category = mime_type.split("/")[0]
    
    tools = BASE_TOOLS.copy()
    if category in MIME_TOOLS:
        tools.extend(MIME_TOOLS[category])
    
    return {
        "file_id": file_id,
        "mime_type": mime_type,
        "tools": tools
    }