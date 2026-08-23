# 🎙️ Detailed Stage-by-Stage Talking Points & HITL Supervisor Agent Playbook

This master guide provides **exhaustive talking points for every single stage of the pipeline**, along with an in-depth breakdown of **how the Human-in-the-Loop (HITL) Supervisor Agent works under the hood**.

---

## 📌 Stage-by-Stage Deep Dive Talking Points

### 1️⃣ STAGE 1: Identity & Taxonomy Resolution Engine (`node_identity` & `node_taxonomy`)

#### 🗣️ Detailed Talking Points:
* *"Stage 1 is all about **cleaning dirty supplier inputs** and resolving industrial taxonomy."*
* *"Dirty feeds often contain abbreviated brand names (like `APPDE` or `FLK`). `node_identity` normalizes manufacturer names against our canonical alias database."*
* *"Next, `node_taxonomy` uses our LLM taxonomy engine to map the product into its official **8-Digit UNSPSC Category Code** (e.g., `82111101` for Digital Multimeters)."*
* *"Based on the UNSPSC category, the system dynamically constructs the required **Attribute Schema** (`expected_fields`)—such as `Voltage_Rating`, `Current_Rating`, `IP_Rating`, and `Operating_Temp`."*

#### 💡 Key Technical Metrics:
* **8-Digit UNSPSC Code**: Standardized international commodity classification.
* **Dynamic Schema Construction**: Different categories require different attribute schemas (e.g., Multimeters vs. Sanding Discs vs. Ball Bearings).

---

### 2️⃣ STAGE 2: Autonomous Web Sourcing & Vector Ingestion (`node_retrieve`)

#### 🗣️ Detailed Talking Points:
* *"Stage 2 handles **harvesting official manufacturer documentation**."*
* *"Instead of relying on random web content, our autonomous scraper targets trusted manufacturer domains (`fluke.com`, `3m.com`, `whirlpool.com`)."*
* *"It downloads official technical datasheet PDFs, parses tables and raw text, and chunks the content into a **ChromaDB Vector Store** for semantic retrieval."*
* *"It also extracts digital asset links—such as high-res product photos, PDF spec sheets, and user manuals—which are passed directly into the catalog export."*

#### 💡 Key Technical Metrics:
* **ChromaDB Vector Store**: Indexes PDF chunks with metadata tracking (`page_number`, `document_id`, `table_location`).
* **Trusted OEM Scraper**: Prevents ingestion of noisy e-commerce reseller pages.

---

### 3️⃣ STAGE 3: Series Knowledge Graph & Multi-Pass RAG Extractor (`node_series` & `node_extract`)

#### 🗣️ Detailed Talking Points:
* *"Stage 3 is our core innovation: **The Series Knowledge Graph**."*
* *"In industrial manufacturing, products belong to product families (like the *Fluke 110 Series* or *3M 775L Cubitron II*). Sibling products share 80% of their core engineering specifications."*
* *"Before running expensive LLM queries, `node_series` checks `knowledge_store.db`. If a sibling SKU was previously enriched, the new SKU auto-inherits shared series memory with the purple **`Series Knowledge Graph`** badge."*
* *"For variant-specific attributes, `node_extract` runs multi-pass RAG queries against ChromaDB PDF chunks, extracting exact numerical values and mapping standardized **Units of Measure (UOM)** (e.g. `600`, `V`)."*

#### 💡 Key Technical Metrics:
* **90% Token Savings**: Shared series memory skips redundant web scraping and LLM extraction calls.
* **UOM Normalization**: Maps raw strings into standard industrial units (`V`, `A`, `kW`, `mm`, `kg`).

---

### 4️⃣ STAGE 4: 5-Tier Validation & Anti-Hallucination Router (`node_validate` & `node_review_gate`)

#### 🗣️ Detailed Talking Points:
* *"Stage 4 guarantees **zero hallucinations** through mathematical scoring."*
* *"Extracted fields start with a **Base Provenance Score** (e.g. 98% for OEM Webpages, 92% for Series Memory, 88% for PDF Datasheets)."*
* *"Next, the validator applies strict penalties:*
  * **-25% Hallucination Penalty**: If the extracted quote string does not exist verbatim inside ChromaDB vector chunks.
  * **-30% Physical Sanity Penalty**: If values exceed physical bounds (e.g. negative voltage).
  * **-35% Semantic Category Penalty**: If raw materials like `"Copper"` are placed in the `"Color"` field.*"
* *"If the overall confidence score is **≥ 80%**, the product auto-completes (**Fast Path**). If confidence is **< 80%**, it enters **HITL Escrow** for human confirmation."*

#### 💡 Key Technical Metrics:
* **Formula**: $\text{Final Score} = \text{Base Provenance} - (\text{Hallucination Penalty} + \text{Sanity Penalty} + \text{Semantic Penalty})$.
* **Management by Exception**: 85% of SKUs auto-pass; only uncertain edge cases pause for human review.

---

### 5️⃣ STAGE 5: HITL Supervisor Agent & Master 252-Column Export (`hitl_agent.py` & `node_finalize`)

#### 🗣️ Detailed Talking Points:
* *"Stage 5 provides the **Human-in-the-Loop Escrow Console** and **Master Catalog Export**."*
* *"If a record pauses in review, catalog managers don't have to edit raw code. They can talk to our **Supervisor Agent** in plain English."*
* *"Once approved, `node_finalize` unrolls all attributes into the **252-Column Unilog Master Schema**—including invoice descriptions (≤40 uppercase characters), marketing bullets, and digital assets—and updates `Master_Unilog_Output.csv` with 1 click!"*

---

## 🧠 How the HITL Supervisor Agent Works (Under the Hood)

When a human cataloger types an instruction into the Supervisor Agent prompt bar (e.g. *"Set Voltage to 600V"* or *"Reclassify to Digital Multimeter"*), here is the exact code execution pipeline inside `hitl_agent.py`:

```
           [ Human Types Natural Language Prompt ]
                              │
                              ▼
            [ LLM Master Controller Router Agent ]
                              │
  ┌───────────────────────────┼───────────────────────────┐
  ▼                           ▼                           ▼
1. Taxonomy Overrides   2. Custom Web Search     3. Direct Value Overrides
(Triggers Stage 1)      (Triggers Stage 2)       (100% Verified Boost)
  │                           │                           │
  └───────────────────────────┼───────────────────────────┘
                              │
                              ▼
           [ Re-run node_extract & node_validate ]
                              │
                              ▼
        [ Update State ➔ Advance to Next Graph Stage ]
```

### 🛠️ Internal Step-by-Step Code Execution:

1. **Natural Language Parsing**:
   The prompt is passed to the LLM master controller agent with a strict JSON schema:
   ```json
   {
     "run_taxonomy": boolean,
     "taxonomy_overrides": { "category": "...", "unspsc": "..." },
     "add_expected_fields": ["IP_Rating"],
     "custom_urls": ["https://media.fluke.com/datasheet.pdf"],
     "search_query": "Fluke 117 IP rating datasheet",
     "field_overrides": { "Voltage_Rating": "600V" },
     "reasoning": "Human requested manual voltage override."
   }
   ```

2. **Tool / Node Execution**:
   * **If Category Override**: Executes `node_taxonomy` (Stage 1) to rebuild expected attribute schema.
   * **If New URL or Web Search**: Executes `_search_web` (Stage 2) and indexes new chunks into ChromaDB.
   * **If Direct Field Override**: Applies value directly and boosts confidence to **1.0 (100% Human Verified)**.

3. **Graph State Resume & Validation**:
   The agent re-executes `node_extract` and `node_validate`, updating the graph state. If confidence is now ≥80%, the job transitions from `needs_review` ➔ `complete`! 🚀
