"""Kingdom Core -- Local Knowledge Layer (Phase 6)

Design:
- ChromaDB embedded, no server
- MiniLM-L6-v2 embeddings (80MB, CPU-only)
- 512-character chunks (not tokenised)
- Top 5 retrieval limit
- 5,000 character hard cap on context added to handoffs
- File hashing to avoid re-indexing unchanged files
- Read-only context only -- never changes task state
- No auto-indexing -- ingestion is always deliberate

Concurrency:
- Single-process only. Ingest and search through FastAPI only.
- Daemon must never write to ChromaDB.
- No concurrent rebuild/search guarantees in Phase 6.
- Rebuild endpoint removed from Phase 6 -- add later with locking.

Excluded from indexing:
- .git, .venv, __pycache__, *.db, *.db-wal, *.db-shm
- .env, *.log, *.pyc, chroma_data/
"""
import hashlib
import os
import uuid
import aiosqlite
import chromadb
from datetime import datetime, timezone
from pathlib import Path
from sentence_transformers import SentenceTransformer
from db import DB_PATH

# -- Configuration ------------------------------------------------------------
CHROMA_DIR = "/home/kingdom-os/chroma_data"
COLLECTION_NAME = "kingdom"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 512          # characters (not tokens -- no tokeniser used)
CHUNK_OVERLAP = 50        # character overlap between chunks
MAX_RESULTS = 5           # top K retrieval limit
MAX_CONTEXT_CHARS = 5000  # hard cap on context added to handoffs

# Files/directories to never index
EXCLUDED_PATTERNS = [
    ".git", ".venv", "__pycache__",
    ".env", "chroma_data",
    "*.db", "*.db-wal", "*.db-shm",
    "*.log", "*.pyc", "*.sqlite",
]

# -- Utilities ----------------------------------------------------------------
def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def hash_file(path: str) -> str:
    """SHA256 hash of file contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def is_excluded(path: str) -> bool:
    """Check if a path matches any excluded pattern."""
    p = Path(path)
    for pattern in EXCLUDED_PATTERNS:
        if pattern.startswith("*."):
            ext = pattern[1:]
            if p.suffix == ext or str(p).endswith(ext):
                return True
        else:
            if pattern in p.parts or p.name == pattern:
                return True
    return False

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list:
    """Split text into overlapping chunks. Uses character counts, not tokens."""
    if overlap >= chunk_size:
        raise ValueError(f"overlap ({overlap}) must be smaller than chunk_size ({chunk_size})")
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        next_start = end - overlap
        # Ensure we always advance to prevent infinite loops
        if next_start <= start:
            next_start = start + 1
        start = next_start
        if start >= len(text):
            break
    return chunks

# -- ChromaDB Client ----------------------------------------------------------
_client = None
_collection = None
_model = None

def get_chroma():
    global _client, _collection
    if _collection is None:
        os.makedirs(CHROMA_DIR, exist_ok=True)
        _client = chromadb.PersistentClient(path=CHROMA_DIR)
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
    return _collection

def get_model():
    global _model
    if _model is None:
        import time
        print(f"[knowledge] Loading embedding model {EMBEDDING_MODEL} -- first request may be slow...")
        t = time.time()
        _model = SentenceTransformer(EMBEDDING_MODEL)
        print(f"[knowledge] Model loaded in {time.time()-t:.1f}s")
    return _model

# -- Ingestion ----------------------------------------------------------------
async def ingest_file(file_path: str) -> dict:
    """
    Ingest a single file into the knowledge base.
    Uses file hashing to skip unchanged files.
    Returns ingestion result.
    """
    path = Path(file_path).resolve()
    if not path.exists():
        raise ValueError(f"File not found: {file_path}")
    if not path.is_file():
        raise ValueError(f"Not a file: {file_path}")
    if is_excluded(str(path)):
        raise ValueError(f"File is excluded from indexing: {file_path}")

    file_hash = hash_file(str(path))

    # Check if already indexed with same hash
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id, file_hash, chunk_count FROM knowledge_documents WHERE source_path = ?",
            (str(path),)
        ) as cursor:
            existing = await cursor.fetchone()

    if existing and dict(existing)["file_hash"] == file_hash:
        return {
            "status": "skipped",
            "reason": "unchanged",
            "source_path": str(path),
            "chunk_count": dict(existing)["chunk_count"]
        }

    # Read file
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        raise ValueError(f"Cannot read file: {e}")

    if not text.strip():
        return {"status": "skipped", "reason": "empty file", "source_path": str(path)}

    # Chunk the text
    chunks = chunk_text(text)
    if not chunks:
        return {"status": "skipped", "reason": "no chunks produced", "source_path": str(path)}

    # Embed and store in ChromaDB
    model = get_model()
    collection = get_chroma()
    embeddings = model.encode(chunks).tolist()
    chroma_ids = [f"{path.name}-{i}-{uuid.uuid4().hex[:8]}" for i in range(len(chunks))]
    metadatas = [{"source_path": str(path), "chunk_index": i} for i in range(len(chunks))]

    # Remove old chunks for this file if re-indexing
    if existing:
        try:
            old_ids_result = collection.get(where={"source_path": str(path)})
            if old_ids_result and old_ids_result.get("ids"):
                collection.delete(ids=old_ids_result["ids"])
        except Exception:
            pass

    collection.add(
        ids=chroma_ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas
    )

    # Update SQLite metadata
    async with aiosqlite.connect(DB_PATH) as db:
        if existing:
            await db.execute(
                """UPDATE knowledge_documents
                   SET file_hash=?, chunk_count=?, updated_at=?
                   WHERE source_path=?""",
                (file_hash, len(chunks), now(), str(path))
            )
            doc_id = dict(existing)["id"]
            await db.execute(
                "DELETE FROM knowledge_chunks WHERE document_id=?", (doc_id,)
            )
        else:
            await db.execute(
                """INSERT INTO knowledge_documents
                   (source_path, file_hash, chunk_count, indexed_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (str(path), file_hash, len(chunks), now(), now())
            )
            async with db.execute("SELECT last_insert_rowid()") as cursor:
                row = await cursor.fetchone()
            doc_id = row[0]

        for i, (chunk, chroma_id) in enumerate(zip(chunks, chroma_ids)):
            await db.execute(
                """INSERT INTO knowledge_chunks
                   (document_id, chunk_index, chunk_text, chroma_id)
                   VALUES (?, ?, ?, ?)""",
                (doc_id, i, chunk, chroma_id)
            )
        await db.commit()

    return {
        "status": "indexed",
        "source_path": str(path),
        "chunk_count": len(chunks),
        "file_hash": file_hash[:12] + "..."
    }

async def ingest_directory(dir_path: str, extensions: list = None) -> dict:
    """
    Ingest all eligible files in a directory.
    extensions: list of extensions to include, e.g. ['.py', '.md']
    If extensions is None, includes .py, .md, .txt, .json, .yaml, .yml
    """
    if extensions is None:
        extensions = [".py", ".md", ".txt", ".json", ".yaml", ".yml"]

    path = Path(dir_path).resolve()
    if not path.exists() or not path.is_dir():
        raise ValueError(f"Directory not found: {dir_path}")

    results = {"indexed": 0, "skipped": 0, "failed": 0, "files": []}
    for file_path in path.rglob("*"):
        if not file_path.is_file():
            continue
        if is_excluded(str(file_path)):
            continue
        if file_path.suffix not in extensions:
            continue
        try:
            result = await ingest_file(str(file_path))
            if result["status"] == "indexed":
                results["indexed"] += 1
            else:
                results["skipped"] += 1
            results["files"].append(result)
        except Exception as e:
            results["failed"] += 1
            results["files"].append({
                "status": "failed",
                "source_path": str(file_path),
                "error": str(e)
            })
    return results

# -- Retrieval ----------------------------------------------------------------
def search(query: str, n_results: int = MAX_RESULTS) -> list:
    """
    Search the knowledge base for relevant chunks.
    Returns list of dicts with text, source, and distance.
    Read-only. Never changes state.
    """
    collection = get_chroma()
    model = get_model()
    if collection.count() == 0:
        return []

    query_embedding = model.encode([query]).tolist()
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(n_results, MAX_RESULTS, collection.count())
    )

    chunks = []
    if results and results.get("documents"):
        for doc, meta, distance in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ):
            chunks.append({
                "text": doc,
                "source_path": meta.get("source_path", "unknown"),
                "chunk_index": meta.get("chunk_index", 0),
                "distance": round(distance, 4)
            })
    return chunks

def build_context(query: str, max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """
    Build a context string from retrieved chunks.
    Hard cap at max_chars. Read-only. Never changes state.
    Returns empty string if nothing relevant found.
    """
    chunks = search(query)
    if not chunks:
        return ""

    context_parts = ["## Relevant Knowledge\n"]
    total_chars = len(context_parts[0])
    for chunk in chunks:
        entry = f"\n### From {Path(chunk['source_path']).name}\n{chunk['text']}\n"
        if total_chars + len(entry) > max_chars:
            remaining = max_chars - total_chars
            if remaining > 100:
                context_parts.append(entry[:remaining] + "\n[truncated]")
            break
        context_parts.append(entry)
        total_chars += len(entry)

    return "".join(context_parts)

# -- Status -------------------------------------------------------------------
async def get_knowledge_status() -> dict:
    """Return current state of the knowledge base."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT count(*) FROM knowledge_documents") as cursor:
            doc_count = (await cursor.fetchone())[0]
        async with db.execute("SELECT count(*) FROM knowledge_chunks") as cursor:
            chunk_count = (await cursor.fetchone())[0]
        async with db.execute(
            "SELECT source_path, chunk_count, indexed_at FROM knowledge_documents ORDER BY indexed_at DESC LIMIT 10"
        ) as cursor:
            recent = await cursor.fetchall()

    collection = get_chroma()
    chroma_count = collection.count()

    return {
        "documents_indexed": doc_count,
        "chunks_indexed": chunk_count,
        "chroma_vectors": chroma_count,
        "recent_documents": [
            {"source_path": r[0], "chunk_count": r[1], "indexed_at": r[2]}
            for r in recent
        ]
    }
