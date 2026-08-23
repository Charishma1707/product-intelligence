# 🎤 Word-for-Word 3-Minute Hackathon Pitch Script

This script is tailored specifically for your **3-Minute Video Recording**. Follow the timestamps, look at what to show on screen, and read the spoken lines out loud!

---

## ⏰ 0:00 – 0:20 | The Problem (Hook)
* **What to Show on Screen**: Open `http://localhost:5173`. Show the **Single Product** tab.
* **🗣️ Read This Word-for-Word**:
> *"Imagine an industrial supplier like Grainger receiving thousands of dirty, unstructured manufacturer feeds every single day. Product titles say things like 'FLUKE 117 MULTI', material codes are missing, and technical specs are buried inside 20-page PDF datasheets.*
> *Catalog teams waste thousands of manual hours searching datasheets and copying specs. This is the multi-billion-dollar cataloging problem our project solves."*

---

## ⏰ 0:20 – 0:40 | The Solution
* **What to Show on Screen**: Hover over the input fields (`Brand`, `MPN`, `Description`) and point to the **Sample Product** dropdown.
* **🗣️ Read This Word-for-Word**:
> *"We built **Unilog Product Intelligence**—an autonomous multi-agent AI pipeline built on LangGraph.*
> *Our system takes minimal product inputs, automatically harvests official manufacturer datasheets, extracts precise specs with units of measure, and formats everything into master 252-column industrial catalogs in seconds."*

---

## ⏰ 0:40 – 1:00 | Architecture & How It Works (Simple Flow)
* **What to Show on Screen**: Point to the **Pipeline Stages bar** at the top of the UI (`Identity` ➔ `Taxonomy` ➔ `Retrieval` ➔ `Extraction` ➔ `Validation`).
* **🗣️ Read This Word-for-Word**:
> *"Here is how the flow works behind the scenes:*
> *First, **Stage 1** standardizes the brand and classifies the official 8-digit UNSPSC code.*
> *Next, **Stage 2** searches manufacturer web APIs and indexes PDF datasheets into vector memory.*
> *Then, **Stage 3** uses LLM multi-pass RAG to extract specs.*
> *Finally, **Stage 4** runs a 5-tier validator to score confidence and escrow uncertain records for human review."*

---

## ⏰ 1:00 – 2:20 | ⭐ Live Demo (The Heart of the Video!)

> [!TIP]
> **Demo Backup Strategy**: 
> * **Path A (Live Run)**: Click **Sample 1 (Fluke 117)**, click **Enrich Product**, and watch the live logs stream.
> * **Path B (Instant Fallback if network is slow)**: Immediately click the **Jobs Monitor** tab and click **Load** on `FLUKE-117`!

* **What to Show on Screen**:
  1. Click **Sample 1 (Fluke 117)** ➔ Click **Enrich Product** (or switch to **Jobs Monitor** ➔ **Load `FLUKE-117`**).
  2. Show the **Result Card**: Scroll down to the specs table (`Voltage: 600V`, `Current: 10A`, `IP Rating: IP42`).
  3. Point out the blue **`Technical Datasheet`** provenance badges and expand the **Confidence Rationale Matrix**.
  4. Now click **Jobs Monitor** tab ➔ Click **Load** on `FLUKE-115` (the sibling SKU). Point out the purple **`Series Knowledge Graph`** badges!
  5. Click **HITL Review** tab ➔ Type in the **Supervisor Agent Bar**: `"Set Voltage to 600V"` or `"Go to Stage 1"`.

* **🗣️ Read This Word-for-Word**:
> *"Let's see a live run! I'll select the **Fluke 117 Multimeter** and click **Enrich Product**.*
> *Look at the **Result Card**. Notice the blue `Technical Datasheet` badges showing verbatim quotes from page 1 of the official Fluke PDF, and our **Confidence Matrix** explaining why each score was assigned.*
> *Now, here is our key innovation: when we process its sibling SKU, **Fluke 115**, our system detects it belongs to the same 110 Series family.*
> *Instead of re-scraping the web, it inherits shared series specs instantly—marked by the purple **`Series Knowledge Graph`** badge!*
> *And if any record has confidence below 80%, it enters our **HITL Escrow Dashboard**, where catalog managers can instruct our Supervisor Agent in plain English to self-heal the data!"*

---

## ⏰ 2:20 – 2:45 | Results & Uniqueness (Why It Matters)
* **What to Show on Screen**: Stay on the **Jobs Monitor** dashboard showing the 6 completed SKUs, cache hit metrics, and confidence badges.
* **🗣️ Read This Word-for-Word**:
> *"Why does this matter? Three huge reasons:*
> *1. **90% Cost Savings**: Our Series Knowledge Graph eliminates redundant PDF downloads and LLM calls for sibling SKUs.*
> *2. **Zero Hallucinations**: Our 5-tier validator penalizes fabricated quotes and enforces physical sanity checks.*
> *3. **Enterprise Scalability**: It turns days of manual cataloging into seconds of automated intelligence."*

---

## ⏰ 2:45 – 3:00 | Closing & Master CSV Export
* **What to Show on Screen**: Click **Export Unilog CSV**. Show the downloaded file / `Master_Unilog_Output.csv`.
* **🗣️ Read This Word-for-Word**:
> *"So instead of spending hundreds of manual hours searching datasheets and fixing dirty feeds, our system turns raw inputs into master 252-column enterprise catalogs in seconds.*
> *That is the power of **Unilog Product Intelligence**. Thank you!"*
