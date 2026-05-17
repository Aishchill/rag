import os
import uuid
import PyPDF2
import docx
from flask import current_app


def allowed_file(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


def save_upload(file):
    ext = file.filename.rsplit(".", 1)[-1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_name)
    file.save(path)
    return unique_name, ext


def extract_text(filepath, file_type):
    if file_type == "txt":
        with open(filepath, "r", errors="ignore") as f:
            return f.read()
    if file_type == "pdf":
        text = []
        with open(filepath, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text.append(page.extract_text() or "")
        return "\n".join(text)
    if file_type == "docx":
        doc = docx.Document(filepath)
        return "\n".join(p.text for p in doc.paragraphs)
    return ""


def chunk_text(text, size=500, overlap=50):
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunk = " ".join(words[i:i + size])
        if chunk.strip():
            chunks.append(chunk)
        i += size - overlap
    return chunks
