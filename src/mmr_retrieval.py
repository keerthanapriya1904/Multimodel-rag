# src/mmr_retrieval.py  —  Day 34  —  Phase 4
# Maximal Marginal Relevance (MMR) retrieval
# Reduces redundancy by selecting DIVERSE results
# lambda=0.7 means: 70% relevance + 30% diversity

import sys, os
import numpy as np
sys.path.append(os.path.dirname(__file__))
from ingestion import get_embed_model, retrieve as dense_retrieve

def cosine_similarity(a: list, b: list) -> float:
    """Calculate cosine similarity between two vectors"""
    a, b = np.array(a), np.array(b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    return float(np.dot(a, b) / denom) if denom > 0 else 0.0

def mmr_retrieval(question: str, user_id: str ,
                  n: int = 5, lambda_param: float = 0.7) -> list:
    """
    Maximal Marginal Relevance retrieval:

    1. Get 20 candidates from dense search
    2. Embed all candidates
    3. Iteratively pick chunks that are:
       - Relevant to the query (high similarity to question)
       - Diverse from already selected chunks (low similarity to selected)

    lambda_param = 0.7 means:
       score = 0.7 * relevance - 0.3 * similarity_to_selected
       Higher lambda = more relevance-focused
       Lower lambda  = more diversity-focused
    """
    # Step 1: Get candidates
    candidates = dense_retrieve(question, user_id=user_id, n=20)
    if not candidates:
        return []
    if len(candidates) <= n:
        return candidates

    # Step 2: Embed query and all candidate texts
    model    = get_embed_model()
    q_embed  = model.encode([question])[0]
    c_embeds = model.encode([c["text"] for c in candidates],
                             show_progress_bar=False)

    # Calculate relevance scores (similarity to query)
    relevance_scores = [
        cosine_similarity(q_embed.tolist(), emb.tolist())
        for emb in c_embeds
    ]

    # Step 3: MMR iterative selection
    selected_indices  = []
    remaining_indices = list(range(len(candidates)))

    for _ in range(n):
        best_idx   = None
        best_score = -999.0

        for idx in remaining_indices:
            # Relevance to query
            relevance = relevance_scores[idx]

            # Diversity: max similarity to any already selected chunk
            if selected_indices:
                max_sim_to_selected = max(
                    cosine_similarity(
                        c_embeds[idx].tolist(),
                        c_embeds[sel].tolist()
                    )
                    for sel in selected_indices
                )
            else:
                max_sim_to_selected = 0.0

            # MMR score formula
            mmr_score = (lambda_param * relevance
                         - (1 - lambda_param) * max_sim_to_selected)

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx   = idx

        if best_idx is not None:
            selected_indices.append(best_idx)
            remaining_indices.remove(best_idx)

    return [candidates[i] for i in selected_indices]

if __name__ == "__main__":
    print("Testing MMR retrieval...")
    results = mmr_retrieval("main topics", user_id="test_user", n=5)
    print(f"MMR returned {len(results)} diverse results")
    for i, r in enumerate(results):
        print(f"  {i+1}. Page {r['page']}: {r['text'][:80]}...")
