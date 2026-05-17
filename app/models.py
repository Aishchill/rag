from .db import query


# ── Users ──────────────────────────────────────────────────────────────
def create_user(username, email, password_hash):
    return query(
        "INSERT INTO users (username, email, password_hash) VALUES (%s,%s,%s)",
        (username, email, password_hash), commit=True,
    )

def get_user_by_email(email):
    return query("SELECT * FROM users WHERE email=%s", (email,), one=True)

def get_user_by_id(uid):
    return query("SELECT * FROM users WHERE id=%s", (uid,), one=True)


# ── Documents ──────────────────────────────────────────────────────────
def create_document(user_id, filename, original_name, file_type):
    return query(
        "INSERT INTO documents (user_id, filename, original_name, file_type) VALUES (%s,%s,%s,%s)",
        (user_id, filename, original_name, file_type), commit=True,
    )

def get_documents(user_id):
    return query("SELECT * FROM documents WHERE user_id=%s ORDER BY uploaded_at DESC", (user_id,))

def get_document(doc_id):
    return query("SELECT * FROM documents WHERE id=%s", (doc_id,), one=True)

def delete_document(doc_id):
    query("DELETE FROM document_chunks WHERE document_id=%s", (doc_id,), commit=True)
    query("DELETE FROM documents WHERE id=%s", (doc_id,), commit=True)


# ── Chunks ─────────────────────────────────────────────────────────────
def save_chunk(doc_id, chunk_text, chunk_index, vector_id):
    query(
        "INSERT INTO document_chunks (document_id, chunk_text, chunk_index, vector_id) VALUES (%s,%s,%s,%s)",
        (doc_id, chunk_text, chunk_index, vector_id), commit=True,
    )

def get_chunks_by_vector_ids(vector_ids):
    if not vector_ids:
        return []
    placeholders = ",".join(["%s"] * len(vector_ids))
    return query(
        f"SELECT dc.*, d.original_name FROM document_chunks dc "
        f"JOIN documents d ON dc.document_id=d.id "
        f"WHERE dc.vector_id IN ({placeholders})",
        tuple(vector_ids),
    )


def get_chunks_by_text_search(keyword, user_id, limit=6):
    """Full-text LIKE search on chunk_text — fallback for numbered/specific queries."""
    return query(
        "SELECT dc.*, d.original_name FROM document_chunks dc "
        "JOIN documents d ON dc.document_id=d.id "
        "WHERE d.user_id=%s AND dc.chunk_text LIKE %s "
        "ORDER BY dc.chunk_index ASC LIMIT %s",
        (user_id, f"%{keyword}%", limit),
    )


# ── Chats ──────────────────────────────────────────────────────────────
def save_chat(user_id, question, answer, sources):
    return query(
        "INSERT INTO chats (user_id, question, answer, sources) VALUES (%s,%s,%s,%s)",
        (user_id, question, answer, sources), commit=True,
    )

def get_chats(user_id, limit=20):
    return query(
        "SELECT * FROM chats WHERE user_id=%s ORDER BY created_at DESC LIMIT %s",
        (user_id, limit),
    )
