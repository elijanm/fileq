import base64
from uuid import uuid4
import os
from fastapi import FastAPI, HTTPException

BASE_TOOLS = [
    {"name": "Share Link", "action": "share", "icon": "link"},
    {"name": "Password Protect", "action": "password_protect", "icon": "lock"},
    {"name": "Download", "action": "download", "icon": "download"},
    {"name": "Delete", "action": "delete", "icon": "trash"},
    {"name": "Move to Folder", "action": "move", "icon": "folder"}
]

MIME_TOOLS = {
    # Category: Images
    "image": [
        {"name": "Preview", "action": "preview", "icon": "eye"},
        {"name": "Resize", "action": "resize", "icon": "crop"},
        {"name": "Crop", "action": "crop_tool", "icon": "crop"},
        {"name": "Rotate", "action": "rotate", "icon": "rotate-cw"},
        {"name": "Flip", "action": "flip", "icon": "flip-horizontal"},
        {"name": "Compress", "action": "compress", "icon": "compress"},
        {"name": "Convert to JPG", "action": "convert_jpg", "icon": "image"},
        {"name": "Convert to PNG", "action": "convert_png", "icon": "image"},
        {"name": "Convert to WebP", "action": "convert_webp", "icon": "image"},
        {"name": "Convert to PDF", "action": "convert_pdf", "icon": "file-pdf"},
        {"name": "Extract Text (OCR)", "action": "ocr", "icon": "scan"},
        {"name": "Watermark", "action": "watermark", "icon": "droplet"},
        {"name": "AI Enhance", "action": "ai_enhance", "icon": "wand"},
        {"name": "Blur/Redact", "action": "blur", "icon": "eye-off"}
    ],

    # Category: Video
    "video": [
        {"name": "Preview", "action": "preview", "icon": "play"},
        {"name": "Trim", "action": "trim", "icon": "scissors"},
        {"name": "Cut & Split", "action": "cut", "icon": "split-square-horizontal"},
        {"name": "Resize Resolution", "action": "resize", "icon": "expand"},
        {"name": "Compress", "action": "compress", "icon": "compress"},
        {"name": "Extract Audio", "action": "extract_audio", "icon": "music"},
        {"name": "Add Subtitles", "action": "add_subtitles", "icon": "subtitles"},
        {"name": "Burn Subtitles", "action": "burn_subtitles", "icon": "text"},
        {"name": "Convert to MP4", "action": "convert_mp4", "icon": "video"},
        {"name": "Convert to WebM", "action": "convert_webm", "icon": "video"},
        {"name": "Convert to GIF", "action": "convert_gif", "icon": "film"},
        {"name": "Generate Thumbnail", "action": "thumbnail", "icon": "image"},
        {"name": "Stabilize Video", "action": "stabilize", "icon": "move"},
        {"name": "AI Transcribe", "action": "transcribe", "icon": "mic"}
    ],

    # Category: Audio
    "audio": [
        {"name": "Preview", "action": "preview", "icon": "play"},
        {"name": "Trim", "action": "trim", "icon": "scissors"},
        {"name": "Merge", "action": "merge", "icon": "layers"},
        {"name": "Normalize Volume", "action": "normalize", "icon": "volume-2"},
        {"name": "Convert to MP3", "action": "convert_mp3", "icon": "music"},
        {"name": "Convert to WAV", "action": "convert_wav", "icon": "music"},
        {"name": "Convert to AAC", "action": "convert_aac", "icon": "music"},
        {"name": "Extract Metadata", "action": "metadata", "icon": "info"},
        {"name": "Add Metadata", "action": "add_metadata", "icon": "edit"},
        {"name": "Noise Reduction", "action": "denoise", "icon": "sliders"},
        {"name": "Voice Isolation", "action": "isolate_voice", "icon": "user-voice"},
        {"name": "AI Transcribe", "action": "transcribe", "icon": "mic"}
    ],

    # Exact: PDF
    "application/pdf": [
        {"name": "Preview", "action": "preview", "icon": "file"},
        {"name": "Split Pages", "action": "split", "icon": "columns"},
        {"name": "Merge PDFs", "action": "merge", "icon": "layers"},
        {"name": "Convert to Word", "action": "convert_docx", "icon": "file-word"},
        {"name": "Convert to Excel", "action": "convert_xlsx", "icon": "file-excel"},
        {"name": "Convert to PDF", "action": "convert_pdf", "icon": "file-pdf"},
        {"name": "Convert to Text", "action": "convert_txt", "icon": "file-text"},
        {"name": "Password Protect", "action": "pdf_password", "icon": "lock"},
        {"name": "Remove Password", "action": "pdf_unlock", "icon": "unlock"},
        {"name": "Add Watermark", "action": "pdf_watermark", "icon": "droplet"},
        {"name": "Sign Document", "action": "sign", "icon": "signature"},
        {"name": "OCR Scan", "action": "ocr", "icon": "scan"}
    ],

    # Exact: Word Documents
    "application/msword": [
        {"name": "Preview", "action": "preview", "icon": "file-word"},
        {"name": "Convert to PDF", "action": "convert_pdf", "icon": "file-pdf"},
        {"name": "Convert to Text", "action": "convert_txt", "icon": "file-text"},
    ],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
        {"name": "Preview", "action": "preview", "icon": "file-word"},
        {"name": "Convert to PDF", "action": "convert_pdf", "icon": "file-pdf"},
        {"name": "Convert to Text", "action": "convert_txt", "icon": "file-text"},
    ],

    # Archives
    "application/zip": [
        {"name": "Preview Contents", "action": "preview_contents", "icon": "archive"},
        {"name": "Extract", "action": "extract", "icon": "folder-open"},
        {"name": "Compress", "action": "compress", "icon": "compress"},
        {"name": "Encrypt Archive", "action": "encrypt", "icon": "lock"},
        {"name": "Convert to TAR", "action": "convert_tar", "icon": "archive"}
    ],
    "application/x-tar": [
        {"name": "Preview Contents", "action": "preview_contents", "icon": "archive"},
        {"name": "Extract", "action": "extract", "icon": "folder-open"},
        {"name": "Compress", "action": "compress", "icon": "compress"},
        {"name": "Encrypt Archive", "action": "encrypt", "icon": "lock"},
        {"name": "Convert to ZIP", "action": "convert_zip", "icon": "archive"}
    ],

    # Text Files
    "text": [
        {"name": "Preview", "action": "preview", "icon": "file-alt"},
        {"name": "Convert to PDF", "action": "convert_pdf", "icon": "file-pdf"},
    ],

    # Data Files
    "application/json": [
        {"name": "Preview", "action": "preview", "icon": "file-code"},
        {"name": "Convert to CSV", "action": "convert_csv", "icon": "file-csv"},
        {"name": "Visualize Data", "action": "visualize", "icon": "bar-chart"},
        {"name": "Compress", "action": "compress", "icon": "compress"},
        {"name": "Encrypt", "action": "encrypt", "icon": "lock"}
    ],
    "text/csv": [
        {"name": "Preview", "action": "preview", "icon": "table"},
        {"name": "Convert to JSON", "action": "convert_json", "icon": "file-code"},
        {"name": "Visualize Data", "action": "visualize", "icon": "bar-chart"},
        {"name": "Compress", "action": "compress", "icon": "compress"},
        {"name": "Encrypt", "action": "encrypt", "icon": "lock"}
    ]
}

def get_tools_for_mime(mime: str):
    tools = BASE_TOOLS.copy()
    category = mime.split("/")[0]

    # Exact MIME match first
    if mime in MIME_TOOLS:
        tools.extend(MIME_TOOLS[mime])
    # Category match fallback
    elif category in MIME_TOOLS:
        tools.extend(MIME_TOOLS[category])

    return tools


async def upload_image(image_data):

    
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_DIR = os.path.join(BASE_DIR,"..", "uploads")
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # 🧠 Detect if input is base64 instead of a URL
    if image_data.startswith("data:image"):
        try:
            header, encoded = image_data.split(",", 1)
            file_ext = header.split("/")[1].split(";")[0]  # e.g., 'png', 'jpeg'
            binary = base64.b64decode(encoded)
            filename = f"{uuid4()}.{file_ext}"
            filepath = os.path.join(UPLOAD_DIR, filename)

            # 📝 Write to disk
            with open(filepath, "wb") as f:
                f.write(binary)

            # ✅ Return a URL (assuming you serve /uploads)
            return {"url": f"/uploads/{filename}"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 image: {str(e)}")

    # If already a URL, just return as-is
    return {"url": image_data}