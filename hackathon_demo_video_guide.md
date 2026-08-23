# 🎥 Hackathon Demo Video Guide: Unilog Product Intelligence

This guide gives you the exact **screen recording instructions**, the **technical deep dive** of what happens behind the scenes when you click **Enrich Product**, and a **step-by-step 3-minute pitch script**.

---

## 🛠️ Part 1: How to Record your Video & Screen Sharing

### Recommended Recording Tools (Free & Easy):
1. **Loom (Best & Easiest)**:
   * Download Loom or install the Chrome Extension.
   * Select **Screen + Camera** (bubble camera in corner) or **Screen Only**.
   * It gives you an instant link and lets you trim/download your MP4.
2. **OBS Studio (Highest Quality)**:
   * Free & open-source. Select **Display Capture** or **Window Capture (Vite + React UI)**.
3. **Windows Game Bar (Built-in)**:
   * Press `Win + Alt + R` to instantly start recording your screen.

### 💡 Recording Best Practices:
* **Resolution**: Record at **1080p (1920x1080)** full screen.
* **Tabs to keep open**:
  1. `http://localhost:5173` (React UI).
  2. `Master_Unilog_Output.csv` or Excel (to show the 252-column export).
* **Audio**: Speak clearly in a quiet room with enthusiasm!

---

## ⚙️ Part 2: Technical Deep-Dive — What Happens Behind the Scenes When You Click "Enrich Product"?

When you enter a product (e.g., `Fluke Corporation`, `FLUKE-115`) and click **Enrich Product**, here is the exact 4-stage background execution lifecycle:

```
[ User Clicks Enrich Product ]
             │
             ▼
[ Stage 1: Interpretation & Taxonomy ] (Standardizes Brand/MPN, UNSPSC Code, Schema)
             │
             ▼
[ Stage 2: Series Knowledge Graph Check ]
     ├── Vector Cache Hit ──► Inherits Series Baseline Data (90% Cost & Time Savings!)
     └── Cache Miss ───────► OEM Web Harvesting & PDF RAG (Downloads PDF & Chunks to Vector DB)
             │
             ▼
[ Stage 3: LLM Multi-Pass Extraction ] (Semantic RAG & Metric Formatting with UOMs)
             │
             ▼
[ Stage 4: 5-Tier Confidence Scoring & HITL Escrow ]
     ├── Confidence >= 80% ──► Auto-Completes & Updates Master CSV
     └── Confidence < 80%  ──► Pauses in Review Queue for Supervisor Agent Guidance
```

### Detailed Background Steps:

1. **Stage 1 — Interpretation & Category Resolution (`interpreter.py`)**:
   * Takes the raw input (`Brand`, `MPN`, `Description`).
   * Queries LLM taxonomy engine to classify the official **UNSPSC 8-Digit Code** (e.g., `82111101`) and category taxonomy.
   * Dynamically constructs the **Custom Attribute Schema** (`expected_fields`) required for that category.

2. **Stage 2 — Series Knowledge Graph Check (`knowledge_store.py`)**:
   * Checks our SQLite vector database (`knowledge_store.db`) to see if another product in the **"Fluke 110 Series"** was previously ingested.
   * **If Series Hit (e.g. FLUKE-115 after FLUKE-117)**: Automatically inherits shared series attributes (Enclosure IP rating, Operating Temp, Display Counts) with `Series Knowledge Graph` provenance, saving **90% API costs** and speeding up execution!

3. **Stage 2 (Fallback) — OEM Harvesting & PDF RAG (`retriever.py`)**:
   * If not cached, the web scraper autonomously searches manufacturer domains (`fluke.com`) for official technical datasheets.
   * Downloads the PDF, extracts structured text, and chunks it into **ChromaDB Vector Store**.

4. **Stage 3 — LLM Multi-Pass Extraction (`extractor.py`)**:
   * Performs semantic RAG queries against ChromaDB chunks for each expected attribute.
   * Extracts values with strict **Units of Measure (UOM)** (e.g. `600 V`, `10 A`).

5. **Stage 4 — 5-Tier Confidence Scoring & HITL Escrow (`validator.py`)**:
   * Evaluates exact MPN match (+30%), manufacturer domain trust (+25%), table vs. body structural match (+25%), and metric consistency (+20%).
   * **If Overall Confidence >= 80%**: Marks job `Complete` and updates `Master_Unilog_Output.csv`.
   * **If Overall Confidence < 80%**: Pauses record in **HITL Review Queue** for human verification or Supervisor Agent guidance.

---

## 📜 Part 3: Step-by-Step 3-Minute Video Demo Script

Follow this script section by section during your screen recording:

---

### **0:00 – 0:30 | Introduction & Problem Statement**
* **On Screen**: Show the **Single Product** tab (`http://localhost:5173`).
* **What to Say**:
  > *"Hi everyone! Today we are introducing the **Unilog Product Intelligence Pipeline**—an enterprise multi-agent AI system built to solve a multi-billion dollar problem in industrial e-commerce.*
  > *Industrial distributors like Grainger or Fastenal receive thousands of dirty, unstructured manufacturer product feeds with missing specs and wrong taxonomy. Manual cataloging takes hundreds of hours. Our platform enriches dirty feeds into master 252-column industrial catalogs in seconds with zero hallucinations."*

---

### **0:30 – 1:30 | Live Single Product Enrichment & Provenance Transparency**
* **On Screen**: Click on **Sample Product 1 (3M Cubitron Disc)** or **Fluke 117**, then click **Enrich Product**.
* **What to Say**:
  > *"Let me show you a live run. I’ll select the **Fluke 117 Multimeter**. When I click **Enrich Product**, our 4-stage LangGraph engine kicks off.*
  > *In Stage 1, it standardizes the brand and assigns the official **UNSPSC Code 82111101**. In Stage 2, it harvests the official technical datasheet PDF. In Stage 3, it extracts specs with exact units of measure.*
  > *Look at the **Result Card**. We don't just show data; we show **Proven Transparency**. Notice the blue `Technical Datasheet` badges showing exact verbatim snippets from page 1 of the PDF, and our **Confidence Rationale Matrix** explaining why each score was assigned."*

---

### **1:30 – 2:15 | Series Knowledge Graph & Vector Reuse (The USP!)**
* **On Screen**: Click **Jobs Monitor** tab, point to `FLUKE-117` (Fresh Harvest) vs `FLUKE-115` (100% Vector Cache Hit). Click **Load** on `FLUKE-115`.
* **What to Say**:
  > *"Now, here is our key innovation: the **Series Knowledge Graph**.*
  > *When we process a sibling SKU like `FLUKE-115`, our system detects it belongs to the same 110 Series memory. Instead of re-scraping the web, it inherits shared attributes instantly!*
  > *Notice the purple **`Series Knowledge Graph`** provenance badge. This eliminates redundant web searches, reduces LLM cost by **90%**, and guarantees catalog-wide consistency."*

---

### **2:15 – 2:45 | Supervisor Agent & HITL Review Console**
* **On Screen**: Click **HITL Review Queue** tab. Type `"Set Voltage to 600V"` or `"Go to Stage 1 and re-classify"` in the **Agent Prompt Bar**.
* **What to Say**:
  > *"For safety-critical industrial parts, black-box AI is dangerous. If confidence falls below 80%, records enter our **HITL Escrow Dashboard**.*
  > *Reviewers can inspect verbatim evidence or use our **Supervisor Agent** to issue plain-English commands like 'Go to Stage 1 and re-classify' or 'Override Voltage to 600V'. Once confirmed, the AI learns and auto-updates future series runs."*

---

### **2:45 – 3:00 | Conclusion & 252-Column CSV Export**
* **On Screen**: Click **Export Unilog CSV**. Open `Master_Unilog_Output.csv` in Excel or VS Code.
* **What to Say**:
  > *"Finally, with 1 click on **Export Unilog CSV**, all enriched products are formatted into the master 252-column Unilog schema, ready for instant upload into enterprise ERP and PIM systems.*
  > *Unilog Product Intelligence: Fast, Verifiable, and Zero-Hallucination Industrial Cataloging. Thank you!"*

---

## 🎯 Quick Checklist Before Hitting Record:
- [x] Backend running on `localhost:8000`
- [x] Frontend running on `localhost:5173`
- [x] Pre-populated 6 SKUs in `Jobs Monitor` (by running `populate_demo_db.py`)
- [x] Mic tested & resolution set to 1080p! 🚀
