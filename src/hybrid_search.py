# src/hybrid_search.py 
# Combines BM25 keyword search + dense vector search
# Merges using Reciprocal Rank Fusion (RRF)
# pip install rank-bm25

import sys, os
sys.path.append(os.path.dirname(__file__))
from rank_bm25 import BM25Okapi
from ingestion import retrieve as dense_retrieve, get_embed_model

def reciprocal_rank_fusion(results_list: list, k: int = 60) -> list:
    """
    Merge multiple ranked lists using RRF formula:
    score = sum(1 / (k + rank)) for each result across all lists

    k=60 is the standard constant that prevents very high ranks
    from dominating the final score.
    """
    scores = {}
    texts  = {}

    for results in results_list:
        for rank, item in enumerate(results):
            key = f"{item['source']}_{item['page']}_{hash(item['text'])}" # use first 100 chars as unique key
            if key not in scores:
                scores[key] = 0.0
                texts[key]  = item
            scores[key] += 1.0 / (k + rank + 1)

    # Sort by RRF score descending
    sorted_keys = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    return [texts[k] for k in sorted_keys]

def hybrid_search(question: str, user_id: str ,
                  n: int = 5) -> list:
    """
    Hybrid search combining:
    1. Dense vector search (finds semantically similar text)
    2. BM25 sparse search (finds exact keyword matches)
    3. RRF merging (combines both rankings fairly)

    Returns top-n results from merged ranking.
    """
    # Step 1: Dense retrieval — gets top 20 semantically similar chunks
    dense_results = dense_retrieve(question, user_id=user_id, n=20)
    if not dense_results:
        return []

    # Step 2: BM25 sparse retrieval on the same 20 candidates
    # BM25 works on tokenized (split into words) text
    corpus   = [r["text"] for r in dense_results]
    tokenized_corpus = [doc.lower().split() for doc in corpus]
    tokenized_query  = question.lower().split()

    bm25 = BM25Okapi(tokenized_corpus)
    bm25_scores = bm25.get_scores(tokenized_query)

    # Create BM25 results sorted by score (highest first)
    bm25_results = sorted(
        [{"text": dense_results[i]["text"],
          "page": dense_results[i]["page"],
          "source": dense_results[i]["source"],
          "bm25_score": float(bm25_scores[i])}
         for i in range(len(dense_results))],
        key=lambda x: x["bm25_score"], reverse=True
    )

    # Step 3: RRF merge — pass both ranked lists
    merged = reciprocal_rank_fusion([dense_results, bm25_results])

    return merged[:n]

if __name__ == "__main__":
    print("Testing hybrid search...")
    results = hybrid_search("main topics", user_id="test_user", n=5)
    print(f"Retrieved {len(results)} results")
    for i, r in enumerate(results):
        print(f"  {i+1}. Page {r['page']}: {r['text'][:80]}...")
