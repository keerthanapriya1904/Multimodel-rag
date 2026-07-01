import uuid
import os
import qdrant_client
from config import QDRANT_URL, QDRANT_API_KEY
from qdrant_client import QdrantClient
from qdrant_client.http import models


# ── 1. GLOBAL CONNECTION (Singleton) ──
_client = None

def get_qdrant():
    """Returns a single connection to the Sydney Cloud cluster"""
    global _client
    if _client is None:
        if not QDRANT_URL or not QDRANT_API_KEY:
            raise ValueError("CRITICAL: Qdrant Cloud keys missing in .env")
    
        _client = QdrantClient(
            url=QDRANT_URL, 
            api_key=QDRANT_API_KEY
        )
        print("  [SYSTEM] Sydney Qdrant Cloud Link Established ")
    return _client

# ── 2. SAVE LOGIC (Ingestion) ──
def save_to_qdrant(chunks, user_id):
    """
    Takes text chunks and saves them to the cloud.
    Automatically creates a room (collection) for the user if it doesn't exist.
    """
    client = get_qdrant()
    collection_name = f"user_{user_id}"
    
    # A. Check if the user's collection exists
    collections = client.get_collections().collections
    if not any(c.name == collection_name for c in collections):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=384, # Dimensions for all-MiniLM-L6-v2
                distance=models.Distance.COSINE
            )
        )

        client.create_payload_index(
            collection_name=collection_name,
            field_name="source",
            field_schema=models.PayloadSchemaType.KEYWORD,
            wait=True
        )

        client.create_payload_index(
            collection_name=collection_name,
            field_name="user_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
            wait=True
        )

        print(f"  [DB] Created new secure vault for: {user_id}")
        print(f"  [DB] Created payload indexes (source ,user_id)")

    # B. Prepare data for the cloud (Points)
    points = []
    for c in chunks:
        points.append(models.PointStruct(
            id=str(uuid.uuid4()), # Digital Fingerprint
            vector=c["vector"],   # Mathematical meaning
            payload={             # Actual human data
                "text": c["text"],
                "page": c["page"],
                "source": c["source"],
                "user_id": user_id,
                "content_type": c.get("content_type",c.get( "type","text"))
            }
        ))
    
    # C. Upload to Sydney
    client.upsert(collection_name=collection_name, points=points)
    print(f"  [DB] Successfully synced {len(points)} items to Sydney.")

# ── 3. SEARCH LOGIC (Retrieval) ──
def search_qdrant(query_vector, user_id, limit=5):
    """Searches the user's private cloud vault for the most relevant facts"""
    client = get_qdrant()
    collection_name = f"user_{user_id}"
    
    # Search command
    results = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=limit,
        with_payload=True
    )
    
    # Format results to match what rag.py expects
    return [{
        "text": r.payload["text"],
        "page": r.payload["page"],
        "source": r.payload["source"],
        "score": r.score
    } for r in results.points]

from config import get_clean_name

def purge_file_vectors(filename: str, user_id: str):
    client = get_qdrant()
    collection_name = f"user_{user_id}"
    
    # ── THE FIX: Clean the incoming name before searching ──
    clean_filename = get_clean_name(filename)
    
    print(f"Delete collection : {collection_name}")
    try:
        client.delete(
            collection_name=collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        # This now matches the 'clean' name stored in metadata
                        models.FieldCondition(key="source", match=models.MatchValue(value=clean_filename)),
                        models.FieldCondition(key="user_id", match=models.MatchValue(value=str(user_id)))
                    ]
                )
            )
        )
        print(f"  [CLEANUP] Purged vectors for sanitized name: {clean_filename}")
    except Exception as e:
        print(repr(e))
        raise