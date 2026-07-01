# src/reranker.py    —  Phase 4
# Cross-encoder re-ranking
# Scores (query, passage) pairs jointly for better precision
# pip install sentence-transformers (already installed)

import sys, os
sys.path.append(os.path.dirname(__file__))

_reranker = None

def get_reranker():
    global _reranker
    if _reranker is None:
        local_path = "./models/cross-encoder"
        
        if os.path.exists(local_path):
            print("  [SYSTEM] Loading Cross-Encoder from LOCAL DISK 🚀")
            from sentence_transformers.cross_encoder import CrossEncoder
            _reranker = CrossEncoder(local_path)
        else:
            from sentence_transformers.cross_encoder import CrossEncoder
            _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker


def rerank(question: str, chunks: list, top_k: int = 3) -> list:
    """
    Re-ranks retrieved chunks using cross-encoder.

    Why cross-encoder beats bi-encoder:
    - Bi-encoder: embed query separately, embed chunk separately, compare
    - Cross-encoder: reads query AND chunk TOGETHER, scores jointly
    - Cross-encoder sees interactions between every query word and chunk word
    - Much more accurate but slower (only run on top 10, not all chunks)

    Args:
        question: user's question
        chunks: list of retrieved chunks (from hybrid search or dense)
        top_k: how many to return after reranking

    Returns: top_k chunks sorted by cross-encoder score
    """
    if not chunks:
        return []
    if len(chunks) <= top_k:
        return chunks

    reranker = get_reranker()

    # Create (query, passage) pairs for scoring
    pairs = [(question, chunk["text"]) for chunk in chunks]

    # Score all pairs — returns a score per pair
    scores = reranker.predict(pairs)

    # Attach scores to chunks
    for i, chunk in enumerate(chunks):
        chunk["rerank_score"] = float(scores[i])

    # Sort by rerank score (highest = most relevant)
    reranked = sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)

    return reranked[:top_k]

def full_retrieval_pipeline(question: str, user_id: str ,
                             final_k: int = 3) -> list:
    """
    Complete Phase 4 retrieval pipeline:
    1. Hybrid search (BM25 + dense) → top 10
    2. MMR for diversity → top 8
    3. Cross-encoder reranking → top 3

    This 3-stage pipeline gives the best quality results.
    """
    from hybrid_search  import hybrid_search
    from mmr_retrieval  import mmr_retrieval

    # Stage 1: Hybrid search — get top 10 candidates
    hybrid_results = hybrid_search(question, user_id=user_id, n=10)
    if not hybrid_results:
        return []

    # Stage 2: MMR — reduce redundancy, keep top 8
    diverse_results = mmr_retrieval.__wrapped__(hybrid_results, question) \
        if hasattr(mmr_retrieval, '__wrapped__') else hybrid_results[:8]

    # Stage 3: Cross-encoder reranking — pick best 3
    final_results = rerank(question, hybrid_results[:8], top_k=final_k)

    return final_results

if __name__ == "__main__":
    print("Testing reranker...")
    # Simple test with dummy chunks
    test_chunks = [
        {"text": "RAG stands for Retrieval Augmented Generation.",
         "page": 1, "source": "test.pdf"},
        {"text": "The weather is sunny today.",
         "page": 2, "source": "test.pdf"},
        {"text": "Vector databases store embeddings for similarity search.",
         "page": 3, "source": "test.pdf"},
    ]
    results = rerank("What is RAG?", test_chunks, top_k=2)
    print(f"Reranked top 2:")
    for r in results:
        print(f"  Score {r['rerank_score']:.3f}: {r['text'][:60]}...")
