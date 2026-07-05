# src/agent_router.py  
# Agentic Router — Groq decides which tool to use
# Tools: [PDF_RETRIEVER], [WEB_SEARCH], [VISION_ANALYSIS]
# Replaces the simple keyword-based needs_images() check
# with an LLM-powered intent classifier

import os, sys, json, re
sys.path.append(os.path.dirname(__file__))

from groq import Groq
from dotenv import load_dotenv
load_dotenv()

_client = None

def get_groq():
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _client

# ── Tool definitions 
TOOLS = {
    "PDF_RETRIEVER":    "Search through uploaded PDF/DOCX/TXT documents for text-based answers",
    "WEB_SEARCH":       "Search the web for current information not in uploaded documents",
    "VISION_ANALYSIS":  "Retrieve and analyze images, charts, diagrams, or figures from documents",
}

# ── System prompt for tool selection 
ROUTER_SYSTEM_PROMPT = """You are an intelligent query router for a document Q&A system.

Your job is to analyze a user's question and decide which tool to use.

Available tools:

- [PDF_RETRIEVER]   Use when the user asks about the contents of uploaded documents,
  such as summaries, sections, findings, methodology, or information
  that should come from the user's PDFs.

- [WEB_SEARCH]   Use for general knowledge, current events, recent information,
  facts outside the uploaded documents, or when the answer is unlikely
  to be found in the PDFs.

- [VISION_ANALYSIS]   Use when the question refers to images, figures, charts, graphs,
  tables, diagrams, screenshots, or other visual elements.

Examples:
Q: "What is the methodology in the paper?" → [PDF_RETRIEVER]
Q: "What does the architecture diagram show?" → [VISION_ANALYSIS]
Q: "What happened in AI news today?" → [WEB_SEARCH]
Q: "Explain Figure 3 in the document" → [VISION_ANALYSIS]
Q: "What are the key findings?" → [PDF_RETRIEVER]
Q: "What is the current price of GPT-4?" → [WEB_SEARCH]
Q: "https://www.google.com/?" → [WEB_SEARCH]  """

def select_tool(question: str) -> str:
    """
    Uses Groq LLaMA to classify which tool to use for a question.

    Returns one of:
        "PDF_RETRIEVER"
        "WEB_SEARCH"
        "VISION_ANALYSIS"

    Falls back to "PDF_RETRIEVER" on any error.
    """
    try:
        response = get_groq().chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system",  "content": ROUTER_SYSTEM_PROMPT},
                {"role": "user",    "content": question}
            ],
            max_tokens=20,       # only need the tool name
            temperature=0.0,     # deterministic — no randomness
        )
        raw    = response.choices[0].message.content.strip()
        # Extract tool name from brackets e.g. "[PDF_RETRIEVER]" → "PDF_RETRIEVER"
        match  = re.search(r'\[(\w+)\]', raw)
        tool   = match.group(1) if match else "PDF_RETRIEVER"

        # Validate it's a known tool
        if tool not in TOOLS:
            tool = "PDF_RETRIEVER"

        return tool

    except Exception as e:
        print(f"  Agent router error: {e} — defaulting to PDF_RETRIEVER")
        return "PDF_RETRIEVER"

def agent_orchestrator(question: str,
                        user_id: str  ,
                        chat_history: list = None,
                        stream: bool = False) -> dict:

    
    """
    Main agentic pipeline:
    1. Groq selects which tool to use
    2. Execute that tool
    3. Generate answer with page citations preserved

    This replaces the manual needs_images() keyword check
    with a proper LLM-powered intent router.
    """
    print(f"\n  [Agent] Routing question: '{question[:60]}'")
    tool = select_tool(question)
    print(f"  [Agent] Selected tool: [{tool}]")

    # ── Route to correct tool 
    if tool == "VISION_ANALYSIS":
        from multimodal_rag import ask_multimodal
        result = ask_multimodal(
            question,
            user_id=user_id,
            chat_history=chat_history,
            stream=stream
        )
        result["tool_used"] = "VISION_ANALYSIS"
        return result

    elif tool == "WEB_SEARCH":
        from web_search import ask_with_web_search
        result = ask_with_web_search(
            question,
            user_id=user_id,
            chat_history=chat_history
        )
        result["tool_used"] = "WEB_SEARCH"
        # Wrap non-streaming result for consistency
        if stream:
            def gen():
                for word in result.get("answer", "").split(" "):
                    yield word + " "
            result["stream"] = gen()
        return result

    else:  # PDF_RETRIEVER (default)
        from rag import ask_rag
        result = ask_rag(
            question,
            user_id=user_id,
            chat_history=chat_history,
            stream=stream
        )
        result["tool_used"] = "PDF_RETRIEVER"
        return result


# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("AGENT ROUTER TEST")
    print("=" * 50)

    test_cases = [
        ("What are the key findings in the paper?",        "PDF_RETRIEVER"),
        ("Show me the system architecture diagram",         "VISION_ANALYSIS"),
        ("What happened in AI news today?",                 "WEB_SEARCH"),
        ("Explain the methodology",                         "PDF_RETRIEVER"),
        ("What does Figure 2 show?",                        "VISION_ANALYSIS"),
        ("What is the latest version of Python?",           "WEB_SEARCH"),
        ("Summarize the conclusion",                        "PDF_RETRIEVER"),
        ("Describe the chart on page 5",                    "VISION_ANALYSIS"),
    ]

    correct = 0
    for question, expected in test_cases:
        selected = select_tool(question)
        status   = "good" if selected == expected else "notgood"
        print(f"  {status} '{question[:45]}'"
              f"\n     Expected: {expected} | Got: {selected}")
        if selected == expected:
            correct += 1

    print(f"\nAccuracy: {correct}/{len(test_cases)} "
          f"({correct/len(test_cases)*100:.0f}%)")
