import os
import json
import markdown
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, session, jsonify, current_app,
)
from .auth import hash_password, check_password, login_user, logout_user, login_required
from .models import (
    create_user, get_user_by_email, get_user_by_id,
    create_document, get_documents, get_document, delete_document,
    save_chunk, get_chunks_by_vector_ids, get_chunks_by_text_search,
    save_chat, get_chats,
)
from .utils import allowed_file, save_upload, extract_text, chunk_text
from .ai_service import add_embeddings, search_similar, generate_answer

bp = Blueprint("main", __name__)


# ── Auth ───────────────────────────────────────────────────────────────
@bp.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("main.login"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        if get_user_by_email(email):
            flash("Email already registered.", "danger")
            return redirect(url_for("main.register"))
        create_user(username, email, hash_password(password))
        flash("Account created! Please log in.", "success")
        return redirect(url_for("main.login"))
    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = get_user_by_email(email)
        if user and check_password(password, user["password_hash"]):
            login_user(user)
            return redirect(url_for("main.dashboard"))
        flash("Invalid credentials.", "danger")
    return render_template("login.html")


@bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("main.login"))


# ── Dashboard ──────────────────────────────────────────────────────────
@bp.route("/dashboard")
@login_required
def dashboard():
    docs = get_documents(session["user_id"])
    return render_template("dashboard.html", docs=docs)


# ── Upload ─────────────────────────────────────────────────────────────
@bp.route("/upload", methods=["POST"])
@login_required
def upload():
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("No file selected.", "warning")
        return redirect(url_for("main.dashboard"))
    if not allowed_file(file.filename):
        flash("File type not allowed. Use PDF, DOCX, or TXT.", "danger")
        return redirect(url_for("main.dashboard"))

    unique_name, ext = save_upload(file)
    doc_id = create_document(session["user_id"], unique_name, file.filename, ext)

    filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_name)
    text = extract_text(filepath, ext)
    chunks = chunk_text(
        text,
        current_app.config["CHUNK_SIZE"],
        current_app.config["CHUNK_OVERLAP"],
    )

    if chunks:
        try:
            vector_ids = add_embeddings(chunks)
            for idx, (chunk, vid) in enumerate(zip(chunks, vector_ids)):
                save_chunk(doc_id, chunk, idx, vid)
            flash(f"'{file.filename}' uploaded and processed ({len(chunks)} chunks).", "success")
        except RuntimeError as e:
            flash(f"File saved but AI indexing skipped: {e}", "warning")
        except Exception as e:
            flash(f"File saved but embedding failed: {e}", "danger")
    else:
        flash("File uploaded but no text could be extracted.", "warning")

    return redirect(url_for("main.dashboard"))


# ── Delete Document ────────────────────────────────────────────────────
@bp.route("/delete/<int:doc_id>", methods=["POST"])
@login_required
def delete_doc(doc_id):
    doc = get_document(doc_id)
    if doc and doc["user_id"] == session["user_id"]:
        filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], doc["filename"])
        if os.path.exists(filepath):
            os.remove(filepath)
        delete_document(doc_id)
        flash("Document deleted.", "success")
    return redirect(url_for("main.dashboard"))


# ── Chat ───────────────────────────────────────────────────────────────
@bp.route("/chat")
@login_required
def chat():
    history = get_chats(session["user_id"])
    return render_template("chat.html", history=history)


@bp.route("/api/ask", methods=["POST"])
@login_required
def ask():
    data = request.get_json()
    question = (data or {}).get("question", "").strip()
    if not question:
        return jsonify({"error": "Question is required."}), 400

    try:
        uid = session["user_id"]
        k = current_app.config["TOP_K_RESULTS"]

        # ── 1. Semantic (vector) search ──────────────────────────────
        vector_ids = search_similar(question, k=k)
        semantic_chunks = get_chunks_by_vector_ids(vector_ids)

        # ── 2. Keyword fallback search ───────────────────────────────
        # Extract meaningful keywords from the question (skip short stop-words)
        stop_words = {"what","is","the","a","an","in","of","to","and","or",
                      "this","that","it","for","on","at","by","with","me",
                      "my","give","tell","show","exact","please","pdf","file",
                      "document","from","about","how","can","you","its"}
        keywords = [
            w for w in question.lower().split()
            if len(w) > 2 and w not in stop_words
        ]

        keyword_chunks = []
        seen_ids = {c["id"] for c in semantic_chunks}
        for kw in keywords[:4]:   # search top-4 keywords
            for c in get_chunks_by_text_search(kw, uid, limit=4):
                if c["id"] not in seen_ids:
                    seen_ids.add(c["id"])
                    keyword_chunks.append(c)

        # ── 3. Merge: semantic first, then keyword extras ────────────
        chunks = semantic_chunks + keyword_chunks

        if not chunks:
            return jsonify({
                "answer": "No relevant documents found. Please upload some documents first.",
                "answer_html": "<p>No relevant documents found. Please upload some documents first.</p>",
                "sources": [],
            })

        answer = generate_answer(question, chunks)
        answer_html = markdown.markdown(answer, extensions=['fenced_code', 'tables', 'nl2br', 'sane_lists'])
        sources = list({c["original_name"] for c in chunks})
        save_chat(uid, question, answer, json.dumps(sources))
        return jsonify({"answer": answer, "answer_html": answer_html, "sources": sources})

    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        current_app.logger.exception("Error in /api/ask")
        return jsonify({"error": f"AI service error: {str(e)}"}), 500


# ── Chat History API ───────────────────────────────────────────────────
@bp.route("/api/history")
@login_required
def history():
    chats = get_chats(session["user_id"], limit=20)
    for c in chats:
        c["sources"] = json.loads(c["sources"] or "[]")
        c["created_at"] = str(c["created_at"])
        c["answer_html"] = markdown.markdown(c["answer"], extensions=['fenced_code', 'tables', 'nl2br', 'sane_lists'])
    return jsonify(chats)
