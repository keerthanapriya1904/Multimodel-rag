# DocMind --- Multi-Source Multimodal RAG System

A privacy-conscious AI document assistant that helps users ask questions
about uploaded documents and retrieve context from multiple sources.
DocMind combines Retrieval-Augmented Generation (RAG), document parsing,
vector search, vision-assisted PDF understanding, and tool routing in
one modular application.

**Academic context:** MCA final-year project / working prototype\
**Design goal:** useful document understanding on a resource-constrained
machine (approximately 4 GB RAM)\
**Repository:**
[keerthanapriya1904/Multimodel-rag](https://github.com/keerthanapriya1904/Multimodel-rag)


## Table of Contents

-   [Live Demo](#live-demo)
-   [Why DocMind?](#why-docmind)
-   [Features](#features)
-   [System Architecture](#system-architecture)
-   [Request and Ingestion Workflows](#request-and-ingestion-workflows)
-   [Technology Stack](#technology-stack)
-   [Repository Structure](#repository-structure)
-   [Models and Services](#models-and-services)
-   [Configuration](#configuration)
-   [Run Locally](#run-locally)
-   [Document Processing Settings](#document-processing-settings)
-   [Security and Privacy](#security-and-privacy)
-   [Deployment](#deployment)
-   [Known Limitations](#known-limitations)
-   [Troubleshooting](#troubleshooting)
-   [Future Improvements](#future-improvements)
-   [Academic Project](#academic-project)

## Live Demo

-   **Frontend:** https://multimodel-rag-seven.vercel.app
-   **Backend API:** https://multimodel-rag-vnz1.onrender.com
-   **GitHub repository:**
    https://github.com/keerthanapriya1904/Multimodel-rag

The backend uses a free hosting tier and may sleep when idle. The first
request after inactivity can therefore take longer than usual.

## Why DocMind?

Traditional document workflows often require manually searching long
PDFs, reports, or Word files. A basic chatbot can also produce
unsupported answers if it is not grounded in the relevant source
material.

DocMind uses a RAG workflow: retrieve relevant document passages first,
then provide those passages to a language model as context for its
response. For PDFs containing visual information, the system can also
use page-image analysis to describe content such as charts, tables, and
diagrams.

The application is designed as a **modular monolith**: the frontend and
backend are separate deployable applications, while backend capabilities
are organized as modules rather than a set of memory-heavy
microservices.

## Features

### Document question answering

-   Upload supported documents and ask natural-language questions.
-   Extract document content and split it into smaller, overlapping
    chunks.
-   Retrieve relevant chunks using vector similarity search.
-   Use retrieved context to help the language model produce a grounded
    answer.

### Multi-format document ingestion

The project's documented ingestion flow supports:

-   PDF (`.pdf`)
-   Plain text (`.txt`)
-   Microsoft Word (`.docx`)

The exact handling of individual file features depends on the relevant
parser and the document's structure.

### Multimodal PDF understanding

-   Extract ordinary text from PDF pages.
-   Use a vision model to analyze selected page images when visual
    context is useful.
-   Support interpretation of visual elements such as charts, tables,
    and diagrams.
-   Store extracted image descriptions as searchable context where
    supported by the ingestion pipeline.

### Tool routing

The backend includes an agent-style routing layer that can choose an
appropriate capability for a request, including:

-   **Document/PDF retrieval** --- answer from indexed document content.
-   **Web search** --- obtain external context when required.
-   **Vision analysis** --- interpret visual information from a document
    page.

Routing is intended to select a relevant tool, not to guarantee that
every question will use every tool.

### Authentication and user separation

-   Login/authentication based on JSON Web Tokens (JWT).
-   Password hashing using bcrypt-compatible libraries.
-   User records stored in Supabase PostgreSQL.
-   User-scoped identifiers used when storing/retrieving document
    vectors.

### Voice input

-   Speech-to-text input through the Groq Whisper API.
-   Intended to make asking questions more convenient than typing every
    query.

### Privacy-conscious file lifecycle

Uploaded source files are intended to be temporary: the backend
processes the upload and removes the original file rather than keeping a
permanent archive of uploads. This should not be interpreted as a
guarantee that every derived artifact is automatically erased; see
[Security and Privacy](#security-and-privacy).

## System Architecture

``` text
┌────────────────────────────────────┐
│            Web Browser              │
│  React + Vite + Tailwind CSS        │
│  Login / Chat / Upload interface    │
└──────────────────┬─────────────────┘
                   │ Axios / HTTP
                   ▼
┌────────────────────────────────────┐
│          FastAPI Backend            │
│                                     │
│  Authentication and request checks  │
│  Upload validation and ingestion    │
│  RAG orchestration / tool routing   │
│  Chat response generation           │
└───────┬──────────────┬─────────────┘
        │              │
        ▼              ▼
┌────────────────┐  ┌────────────────────┐
│ Supabase       │     │ Qdrant Cloud        │
│ PostgreSQL     │     │ Vector embeddings   │
│ User records   │     │ and searchable data │
└────────────────┘  └──────────┬─────────┘
                               │
                   ┌───────────┼───────────┐
                   ▼           ▼           ▼
              Document      Web search   Vision
              retrieval                  analysis
                   │             │             │
                   └───────────┼───────────┘
                               ▼
                    LLM response generation
                    Groq / Gemini services
```

### Main components

  -----------------------------------------------------------------------
  Component                           Responsibility
  ----------------------------------- -----------------------------------
  React frontend                      User interface for login, chat, and
                                      document upload

  FastAPI backend                     API layer, validation,
                                      authentication, ingestion,
                                      retrieval, and orchestration

  Supabase PostgreSQL                 Relational storage for
                                      user/authentication records

  Qdrant Cloud                        Vector storage and similarity
                                      retrieval

  Sentence Transformers               Convert text chunks into embedding
                                      vectors

  Groq LLM API                        Generate answers and support
                                      request-routing workflows

  Gemini vision API                   Analyze visual content from
                                      selected PDF pages

  Groq Whisper                        Convert speech to text

  Web-search integration              Retrieve external information when
                                      the router selects web search
  -----------------------------------------------------------------------

## Request and Ingestion Workflows

### 1. Upload and indexing

1.  The user signs in and selects a supported file.
2.  The frontend sends the upload to the FastAPI backend.
3.  The backend validates the file and enforces the configured upload
    limit.
4.  The relevant parser extracts text from the file.
5.  PDF processing can include a vision-assisted path for selected page
    images.
6.  Extracted content is split into chunks with overlap so that useful
    context is retained across chunk boundaries.
7.  An embedding model converts text chunks into numerical vectors.
8.  The vectors and associated metadata are written to Qdrant using
    user-scoped identifiers.
9.  The original uploaded file is removed according to the
    temporary-upload workflow.

### 2. Question answering

1.  The user submits a question in the chat interface.
2.  The backend authenticates and processes the request.
3.  The routing logic determines whether document retrieval, web search,
    or vision analysis is appropriate.
4.  For document questions, Qdrant retrieves relevant chunks from the
    indexed content.
5.  The selected language model receives the question and relevant
    context.
6.  The backend returns the generated answer to the frontend.

RAG can reduce unsupported answers by grounding generation in retrieved
context, but it does not eliminate hallucinations. Users should verify
important facts against the source document.

### 3. Authentication

1.  The user submits login credentials.
2.  The backend verifies the stored password hash.
3.  On successful authentication, a signed JWT is issued.
4.  The frontend stores the token for authenticated requests.
5.  Protected backend routes validate the token before handling
    requests.

The current frontend implementation has used browser `localStorage` keys
such as `rag_token` and `rag_user`. Browser storage has security
trade-offs; see the security notes below.

## Technology Stack

  -----------------------------------------------------------------------------
  Layer                               Technologies
  ----------------------------------- -----------------------------------------
  Frontend framework                  React

  Frontend tooling                    Vite

  Styling                             Tailwind CSS

  HTTP client                         Axios

  Routing                             React Router

  Backend framework                   FastAPI

  ASGI server                         Uvicorn

  Request protection                  SlowAPI rate limiting

  Authentication                      JWT, `python-jose`, bcrypt / Passlib

  Relational database                 Supabase PostgreSQL

  Vector database                     Qdrant Cloud

  Embedding models                    `all-MiniLM-L6-v2`,
                                      `paraphrase-multilingual-MiniLM-L12-v2`

  Text splitting                      LangChain text splitters

  PDF processing                      PyMuPDF, pdfplumber

  Word document parsing               python-docx

  Web content parsing                 BeautifulSoup

  LLM provider                        Groq

  Vision provider                     Google Gemini API

  Speech-to-text                      Groq Whisper

  Deployment                          Vercel frontend, Render backend
  -----------------------------------------------------------------------------

The public `requirements.txt` also includes libraries such as `torch`,
`transformers`, `sentence-transformers`, `qdrant-client`, `faiss-cpu`,
`requests`, `numpy`, `duckduckgo-search`, and `psycopg2-binary`. Not
every dependency is necessarily used by every active request path.

## Repository Structure

The public repository currently shows the following top-level structure:

``` text
Multimodel-rag/
├── data/               # Project data/resources (some runtime data is ignored)
├── frontend/           # React + Vite client application
├── src/                # Python backend and RAG modules
├── .gitignore
├── .python-version     # Python runtime version configuration
├── README.md
└── requirements.txt    # Python dependencies
```

Runtime artifacts such as uploaded files, temporary images, model
caches, local databases, and generated vector-store files should not be
committed unless there is a deliberate reason to include them.

## Models and Services

### Text embeddings

The project has used Sentence Transformers models including:

-   `all-MiniLM-L6-v2` --- compact general-purpose text embeddings;
    commonly produces 384-dimensional vectors.
-   `paraphrase-multilingual-MiniLM-L12-v2` --- multilingual sentence
    embeddings.

The selected model and vector dimension must match the Qdrant collection
configuration. If the embedding model changes, the collection may need
to be recreated and documents re-indexed.

### Language generation

-   **Groq:** LLM inference and request-routing support.
-   **Llama 3.1 8B Instant:** documented generation model used by the
    project.

Model identifiers and provider availability can change. Use the exact
model name configured in the current source code.

### Vision analysis

-   **Gemini vision API:** analyzes selected PDF page snapshots for
    visual information that may not be represented well by ordinary text
    extraction.

Vision processing adds network calls and memory/latency overhead. The
project uses constrained image dimensions and resolution to reduce
resource usage.

### Vector search

-   **Qdrant Cloud:** hosted vector database for storing and retrieving
    embeddings.
-   Vectors are associated with metadata and user-scoped identifiers to
    help keep retrieval tied to the relevant user's data.

### Speech-to-text and web search

-   **Groq Whisper (`whisper-large-v3`):** converts speech to text for
    voice input.
-   **DuckDuckGo search integration:** supplies external web context
    when the routing logic chooses the web-search tool.

## Configuration

Create environment variables for the services enabled by your
deployment. Do not commit secrets to GitHub.

The following names reflect the project's documented configuration;
check the source for the exact names currently read by the application.

``` env
GROQ_API_KEY=your_groq_api_key
GEMINI_API_KEY=your_gemini_api_key
QDRANT_URL=your_qdrant_cluster_url
QDRANT_API_KEY=your_qdrant_api_key
HF_TOKEN=your_huggingface_token
JWT_SECRET_KEY=use_a_long_random_secret
```

You may also need Supabase/PostgreSQL connection settings and a frontend
API base URL. Configure those using the variable names expected by the
current backend and frontend code.

### Service setup checklist

-   [ ] Create a Supabase project and configure the PostgreSQL
    connection.
-   [ ] Create a Qdrant Cloud cluster and a collection with the correct
    vector dimensions.
-   [ ] Create API credentials for the LLM and vision services you use.
-   [ ] Set a strong JWT secret in the backend environment.
-   [ ] Configure the frontend API base URL for the chosen backend.
-   [ ] Confirm CORS allows the deployed frontend origin.
-   [ ] Confirm secrets are configured in the hosting provider rather
    than committed to the repository.

## Run Locally

### Prerequisites

-   Python version compatible with `.python-version`
-   Node.js and npm
-   Git
-   Credentials for the external services you plan to use
-   Sufficient RAM and disk space for Python dependencies and model
    downloads

### 1. Clone the repository

``` bash
git clone https://github.com/keerthanapriya1904/Multimodel-rag.git
cd Multimodel-rag
```

### 2. Create a Python virtual environment

``` bash
python -m venv .venv
```

Activate it on Windows:

``` powershell
.venv\Scripts\Activate.ps1
```

Or on macOS/Linux:

``` bash
source .venv/bin/activate
```

### 3. Install backend dependencies

``` bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Some ML dependencies may download large wheels or models. On a
low-memory computer, install and test the environment before running the
complete application.

### 4. Configure backend environment variables

Set the required variables in your local environment or an ignored
`.env` file, following the variable names read by the source code. Never
add `.env` to Git.

### 5. Start the backend

The exact ASGI import path should be confirmed from the current files in
`src/`. A typical FastAPI command has this form:

``` bash
uvicorn <module_path>:app --reload
```

Replace `<module_path>` with the module that defines the FastAPI `app`
instance. Do not copy this placeholder literally.

### 6. Start the frontend

``` bash
cd frontend
npm install
npm run dev
```

Set the frontend API URL to the local backend using the variable name
expected by the Vite application. Vite-exposed environment variables
commonly use the `VITE_` prefix, but the exact key depends on the
implementation.

### 7. Test the application

-   Sign in with a valid account.
-   Upload a small PDF, TXT, or DOCX file.
-   Ask a question whose answer is clearly present in the document.
-   Check that the response uses relevant source content.
-   Test other tools separately and check backend logs if a request
    fails.

## Document Processing Settings

The prototype has used the following representative settings:

  ------------------------------------------------------------------------
  Setting                                      Value Purpose
  --------------------- ---------------------------- ---------------------
  Maximum upload size                          10 MB Limits upload size

  Text chunk size                     500 characters Controls the
                                                     approximate size of
                                                     each chunk

  Chunk overlap                        50 characters Retains some context
                                                     between neighboring
                                                     chunks

  Retrieved chunks                             Top 5 Limits the number of
                                                     passages passed
                                                     forward

  Generation token                      1,024 tokens Limits response
  limit                                              generation

  MiniLM embedding                               384 Must match the
  dimension                                          selected embedding
                                                     model and vector
                                                     collection

  PDF page image DPI                             150 Balances visual
                                                     detail and processing
                                                     cost

  PDF page image                            1,200 px Helps constrain image
  maximum dimension                                  payload size
  ------------------------------------------------------------------------

These are documented project settings, not guaranteed defaults for every
branch or deployment. Confirm the active values in the code before
changing them.

## Security and Privacy

This project is a student prototype, not a certified production security
platform.

-   **Secrets:** Keep API keys, database credentials, and JWT secrets
    outside source control.
-   **Password storage:** Store password hashes rather than plain-text
    passwords.
-   **Authentication:** Validate JWTs on protected routes and use an
    appropriate token lifetime.
-   **User separation:** Ensure retrieval filters and vector identifiers
    are scoped to the authenticated user, not an arbitrary
    client-supplied user ID.
-   **Temporary uploads:** Verify cleanup paths for successful requests,
    failures, and interrupted requests.
-   **Derived data:** Removing the original upload does not
    automatically prove that every embedding, extracted description,
    log, or cached artifact has been removed.
-   **Browser storage:** A token in `localStorage` can be exposed if a
    successful cross-site scripting (XSS) attack occurs. Avoid unsafe
    HTML rendering and keep frontend dependencies updated.
-   **Prompt injection:** Treat document text and web pages as untrusted
    data. Instructions found inside retrieved content must not override
    system rules or authorize external actions.
-   **Sensitive documents:** Do not upload confidential or regulated
    information unless the data handling and provider terms have been
    reviewed.
-   **Production readiness:** Add security tests, monitoring, backups,
    retention policies, and a formal review before real-world
    deployment.

## Deployment

### Frontend --- Vercel

The frontend is deployed at:

https://multimodel-rag-seven.vercel.app

When deploying frontend changes:

1.  Confirm the production API base URL is correct.
2.  Confirm the backend CORS configuration includes the deployed
    frontend origin.
3.  Ensure required Vite environment variables are configured in Vercel.
4.  Build and test the frontend before relying on the deployment.

### Backend --- Render

The backend is deployed at:

https://multimodel-rag-vnz1.onrender.com

The free hosting tier has a limited memory budget. Large ML
dependencies, model initialization, uploads, PDF image generation, and
retrieval can exceed that budget or trigger request timeouts. A
successful health check does not guarantee that every upload or
question-answering workflow will complete.

## Known Limitations

-   **Limited backend memory:** Vision and embedding workflows can be
    memory intensive on a free-tier service.
-   **Cold starts:** The backend may take time to start after
    inactivity.
-   **Model loading:** The first request that uses a model can be slower
    than later requests.
-   **Temporary chat history:** Chat history has been held in backend
    memory rather than a persistent conversation database, so it may
    disappear after a restart.
-   **External dependencies:** Requests can fail when a provider is
    unavailable, credentials are incorrect, quotas are reached, or
    network calls time out.
-   **Document extraction quality:** Scanned PDFs, unusual layouts,
    complex tables, and low-quality page images may produce incomplete
    context.
-   **Generated answers:** Retrieval-augmented generation can still
    produce incorrect or incomplete answers.
-   **Prototype status:** Automated evaluation, observability,
    persistence, and production hardening remain areas for improvement.

## Troubleshooting

### Backend is slow or appears unavailable

-   Wait for the free-tier service to wake up, then retry.
-   Check the hosting provider's logs for startup errors, memory
    exhaustion, and timeouts.
-   Test a small text-based document before trying a large or
    image-heavy PDF.

### Upload fails

-   Confirm the file type is supported.
-   Check the upload-size limit.
-   Inspect backend logs for parser errors, temporary-file permissions,
    and memory use.
-   Try a small PDF or TXT file to isolate the problem.

### Answers do not match the document

-   Check whether text extraction produced the expected content.
-   Try a more specific question using terminology from the source.
-   Verify that the correct user-scoped vectors were indexed and
    retrieved.
-   Review chunk size, overlap, and retrieval settings before changing
    the model.

### Authentication fails

-   Confirm the backend environment variables and database connection.
-   Check whether the JWT secret is configured consistently.
-   Inspect the browser's network response and backend logs.
-   Confirm that the frontend is calling the correct API URL.

### Vector dimension or collection errors

-   Confirm the configured embedding model.
-   Confirm that the Qdrant collection's vector size matches the
    embedding output.
-   If the model or dimension changed, create a compatible collection
    and re-index the documents.

### Deployment shows a red cross on GitHub

A red cross beside a commit normally means a check or workflow reported
failure. Open the commit's **Checks** details or the repository's
**Actions** tab, open the failed run, and inspect the first failing
step. A deployment status and a GitHub Actions status can represent
different systems.

## Future Improvements

-   Persist chat history with user/session isolation.
-   Add automated tests for authentication, ingestion, retrieval, and
    tool routing.
-   Add evaluation datasets and retrieval-quality measurements.
-   Improve citation display so answers can be checked against source
    passages and pages.
-   Move heavy processing into bounded background tasks where the
    hosting environment supports them.
-   Add stronger cleanup guarantees for temporary files and derived
    data.
-   Add structured logging, monitoring, and clear user-facing error
    messages.
-   Improve resilience to provider errors, rate limits, and cold starts.
-   Review authentication and browser token storage for a production
    deployment.

## Academic Project

**Title:** Multi-Source Multimodal RAG System (DocMind)

**Objective:** Explore how Retrieval-Augmented Generation, vector
search, document parsing, vision-assisted analysis, and tool routing can
be combined in a lightweight application for document understanding.

**Design constraint:** The project was developed with limited local RAM
and free-tier hosting constraints in mind. This informed the choice of a
modular monolith and the reduction of memory-intensive retrieval steps
when they caused deployment failures.

## Acknowledgements

This project brings together open-source libraries and hosted AI
services, including FastAPI, React, Sentence Transformers, Qdrant,
Supabase, Groq, Google Gemini, and Vercel/Render hosting.

## License

No license has been confirmed in this README. If you want others to
reuse or redistribute the project, add a `LICENSE` file and select a
license that fits your intentions.
