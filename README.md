# ⚡ Product Intelligence Pipeline — Powered by Groq (Llama 3.3) + DuckDuckGo + Trafilatura

An AI-powered full-stack application that takes minimal product info (Brand, MPN, Short Description) and outputs a rich, structured, commerce-ready product record with **explainability** and **confidence scoring** on every field.

---

## Architecture

```
User Input (brand, mpn, description)
        │
        ▼
┌─────────────────────────────────────────────┐
│            4-Stage Pipeline                 │
│                                             │
│  Stage 1 ─ Interpreter                      │
│    └── LLM classifies category + fields     │
│                                             │
│  Stage 2 ─ Retriever                        │
│    └── DuckDuckGo search + HTML/PDF fetch   │
│                                             │
│  Stage 3 ─ Extractor                        │
│    └── LLM structured JSON extraction       │
│                                             │
│  Stage 4 ─ Validator                        │
│    └── Snippet verification + confidence    │
└─────────────────────────────────────────────┘
        │
        ▼
  ProductRecord (JSON)
  - specifications: dict[field → {value, confidence, source, snippet}]
  - overall_confidence
  - flagged_for_review
```

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- An [Groq API key](https://console.groq.com) (completely **free** — no credit card needed)

---

## Setup

### 1. Clone & navigate

```bash
git clone <repo-url>
cd product-intelligence
```

### 2. Backend setup

```bash
cd backend

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux
```

Edit `.env` and add your API key:

```env
# Get a FREE Groq API key at: https://console.groq.com
GROQ_API_KEY=gsk_...
```

### 3. Frontend setup

```bash
cd frontend
npm install
```

---

## Running the Application

### Start the backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The API will be available at: http://localhost:8000  
Interactive docs: http://localhost:8000/docs

### Start the frontend

```bash
cd frontend
npm run dev
```

The app will be available at: http://localhost:5173

---

## Testing Pipeline Stages Standalone

Each pipeline stage can be tested independently:

```bash
cd backend

# Test Stage 1 — Interpreter
python -m pipeline.interpreter

# Test Stage 2 — Retriever
python -m pipeline.retriever

# Test Stage 3 — Extractor (requires stages 1 & 2)
python -m pipeline.extractor

# Test Stage 4 — Validator (requires stages 1, 2 & 3)
python -m pipeline.validator

# Test full pipeline on all 8 sample products
python -m pipeline.orchestrator

# Verify Pydantic models
python schema.py
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/sample-products` | Returns sample_products.csv as JSON |
| `POST` | `/enrich` | Enrich a single product |
| `POST` | `/enrich/batch` | Upload CSV, enrich all rows concurrently |
| `GET` | `/enrich/batch/download` | Download last batch result as CSV |

### POST /enrich example

```bash
curl -X POST http://localhost:8000/enrich \
  -H "Content-Type: application/json" \
  -d '{"brand": "Siemens", "mpn": "3RT2015-1BB41", "description": "Contactor 3-pole 7A 24VDC"}'
```

### POST /enrich/batch example

```bash
curl -X POST http://localhost:8000/enrich/batch \
  -F "file=@backend/sample_data/sample_products.csv"
```

---

## Output Schema

```json
{
  "brand": "Siemens",
  "mpn": "3RT2015-1BB41",
  "category": "Electrical Switchgear",
  "subcategory": "IEC Contactor",
  "description": "Contactor 3-pole 7A 24VDC coil",
  "specifications": {
    "rated_current_a": {
      "value": 7,
      "confidence": 0.92,
      "source": "https://example.com/datasheet.pdf",
      "method": "extracted",
      "source_snippet": "Rated operational current: 7 A at AC-3"
    }
  },
  "certifications": ["CE", "UL"],
  "flagged_for_review": ["weight_kg"],
  "overall_confidence": 0.84
}
```

### Confidence colour coding

| Confidence | Colour | Meaning |
|-----------|--------|---------|
| ≥ 0.8 | 🟢 Green | Extracted with verified source snippet |
| 0.5–0.8 | 🟡 Amber | Extracted without snippet, or inferred |
| < 0.5 | 🔴 Red | Hallucination detected or sanity check failed |

---

## Adding Offline Reference Docs

For demo reliability without live web search, place product datasheets in:

```
backend/sample_data/reference_docs/
```

Naming convention: filename must contain the MPN (case-insensitive).  
Supported formats: `.pdf`, `.html`, `.txt`

Example:
```
backend/sample_data/reference_docs/3RT2015-1BB41.pdf
backend/sample_data/reference_docs/6205-2RS1_datasheet.txt
```

---

## Project Structure

```
product-intelligence/
├── backend/
│   ├── main.py                 # FastAPI app
│   ├── schema.py               # Pydantic models
│   ├── .env.example            # Environment template
│   ├── requirements.txt
│   ├── pipeline/
│   │   ├── interpreter.py      # Stage 1: category classification
│   │   ├── retriever.py        # Stage 2: web search + extraction
│   │   ├── extractor.py        # Stage 3: LLM field extraction
│   │   ├── validator.py        # Stage 4: confidence scoring
│   │   └── orchestrator.py     # Pipeline orchestration
│   └── sample_data/
│       ├── sample_products.csv
│       └── reference_docs/     # (add datasheets here)
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── index.css           # Design system
│   │   ├── main.jsx
│   │   └── components/
│   │       ├── ProductForm.jsx
│   │       ├── PipelineStages.jsx
│   │       ├── ResultCard.jsx
│   │       └── BatchUpload.jsx
│   ├── package.json
│   ├── vite.config.js
│   └── index.html
└── README.md
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Groq (llama-3.3-70b-versatile) — **free tier** |
| Backend | Python 3.11, FastAPI, Uvicorn |
| Web Search | DuckDuckGo Search (duckduckgo-search) |
| HTML Extraction | Trafilatura |
| PDF Extraction | pypdf |
| Validation | Pydantic v2 |
| Frontend | React 18, Vite |
| Styling | Vanilla CSS with CSS custom properties |
