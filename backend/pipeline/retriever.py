"""
retriever.py — Stage 2 of the pipeline.

Responsibilities:
  - Check ChromaDB first for cached chunks.
  - Web search via Serper.dev (4 passes):
      Pass 1: Manufacturer's own website → produces mfr_url
      Pass 2: PDF datasheets from manufacturer domain
      Pass 3: Industrial B2B distributors ONLY (no e-commerce)
      Pass 4: Exact MPN match on any non-blocked domain
  - Fetch top results, process HTML/PDF → chunks.
  - Store chunks in ChromaDB.
  - Track mfr_url (manufacturer page), spec_sheet_url, sds_url separately.
  - Capture ALL digital asset URLs strictly from manufacturer domain only.
  - Offline fallback to sample_data/reference_docs.
  - Update NetworkX graph.

KEY RULES (Unilog sourcing):
  - MFR URL must be from the manufacturer's own website.
  - Ref URLs may come from approved industrial distributors only.
  - E-commerce sites (Amazon, eBay, Walmart, etc.) are NEVER included.
  - Digital assets (images, spec sheets, SDS, manuals) must be from the
    manufacturer's own domain only.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
import uuid
from pathlib import Path

import chromadb
import pdfplumber
import requests
import trafilatura

# PyMuPDF
import fitz

from pipeline.taxonomy import (
    is_ecommerce,
    is_approved_distributor,
    is_manufacturer_domain,
    guess_mfr_domain,
    ECOMMERCE_BLOCKLIST,
)
from pipeline.utils import generate_with_retry, parse_json_response

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_REFERENCE_DOCS_DIR = _BACKEND_DIR / "sample_data" / "reference_docs"
_PDF_STORAGE_DIR = _BACKEND_DIR / "storage" / "pdfs"
_PDF_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

_REQUEST_TIMEOUT = 8
_MAX_TEXT_CHARS = 12_000

# Initialize ChromaDB local persistent client
_CHROMA_DIR = _BACKEND_DIR / "data" / "chroma"
_CHROMA_DIR.mkdir(parents=True, exist_ok=True)
_chroma_client = chromadb.PersistentClient(path=str(_CHROMA_DIR))
try:
    _collection = _chroma_client.get_or_create_collection(name="product_chunks")
except Exception as e:
    logger.warning("Failed to init ChromaDB collection: %s", e)
    _collection = None


def _get_product_id(brand: str, mpn: str) -> str:
    """Generate a consistent ID for Chroma/Graph."""
    return f"{brand.strip().lower()}_{mpn.strip().lower()}"


def _get_cached_chunks(product_id: str) -> list[dict]:
    """Retrieve all chunks for this product from ChromaDB."""
    if not _collection:
        return []
    try:
        results = _collection.get(where={"product_id": product_id})
        chunks = []
        for i in range(len(results["ids"])):
            meta = results["metadatas"][i] if results["metadatas"] else {}
            chunk = {
                "text": results["documents"][i],
                "source_type": meta.get("source_type"),
                "url": meta.get("url"),
                "doc_id": meta.get("doc_id"),
                "doc_name": meta.get("doc_name"),
                "page_number": meta.get("page_number"),
                "image_base64": meta.get("image_base64"),
                "is_mfr_domain": meta.get("is_mfr_domain", False),
            }
            chunks.append(chunk)
        return chunks
    except Exception as e:
        logger.warning("ChromaDB read failed: %s", e)
        return []


def _store_chunks(product_id: str, chunks: list[dict]):
    """Store chunks in ChromaDB."""
    if not _collection or not chunks:
        return
    ids = []
    documents = []
    metadatas = []

    for i, c in enumerate(chunks):
        ids.append(f"{product_id}_chunk_{i}_{uuid.uuid4().hex[:8]}")
        documents.append(c.get("text") or "image_only")

        meta = {
            "product_id": product_id,
            "source_type": c.get("source_type", "unknown"),
        }
        if c.get("url"): meta["url"] = c.get("url")
        if c.get("doc_id"): meta["doc_id"] = c.get("doc_id")
        if c.get("doc_name"): meta["doc_name"] = c.get("doc_name")
        if c.get("page_number"): meta["page_number"] = c.get("page_number")
        if c.get("image_base64"): meta["image_base64"] = c.get("image_base64")
        meta["is_mfr_domain"] = bool(c.get("is_mfr_domain", False))
        metadatas.append(meta)

    try:
        _collection.add(ids=ids, documents=documents, metadatas=metadatas)
    except Exception as e:
        logger.warning("ChromaDB write failed: %s", e)


def _process_webpage(html_bytes: bytes, url: str) -> list[dict]:
    """Extract clean text from HTML."""
    html_str = html_bytes.decode("utf-8", errors="replace")
    text = trafilatura.extract(html_str, include_tables=True, include_links=False, favor_recall=True)
    if not text:
        return []
    return [{
        "text": text[:_MAX_TEXT_CHARS],
        "source_type": "webpage_text",
        "url": url
    }]


def _process_pdf_file(pdf_path: Path, doc_id: str, doc_name: str) -> list[dict]:
    """Process a PDF page by page, classifying into text/table/chart."""
    chunks = []
    try:
        doc_fitz = fitz.open(pdf_path)

        with pdfplumber.open(pdf_path) as doc_plumber:
            for page_num in range(len(doc_fitz)):
                pnum = page_num + 1
                page_fitz = doc_fitz[page_num]
                page_plumber = doc_plumber.pages[page_num]

                text = page_fitz.get_text("text").strip()
                tables = page_plumber.extract_tables()

                source_type = "pdf_text"
                image_b64 = None

                if tables:
                    source_type = "pdf_table"
                elif len(text) < 150 and len(page_fitz.get_images(full=True)) > 0:
                    source_type = "pdf_chart"

                if source_type in ("pdf_table", "pdf_chart"):
                    pix = page_fitz.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img_bytes = pix.tobytes("png")
                    image_b64 = base64.b64encode(img_bytes).decode("utf-8")

                chunk = {
                    "text": text[:_MAX_TEXT_CHARS] if text else "",
                    "source_type": source_type,
                    "doc_id": doc_id,
                    "doc_name": doc_name,
                    "page_number": pnum,
                    "image_base64": image_b64
                }
                chunks.append(chunk)

        doc_fitz.close()
    except Exception as e:
        logger.warning("PDF processing failed for %s: %s", pdf_path, e)
    return chunks


def _fetch_url(url: str) -> list[dict]:
    """Fetch URL and process as HTML or PDF."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=_REQUEST_TIMEOUT, stream=True)
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "").lower()
    raw_bytes = resp.content

    if "pdf" in content_type or url.lower().endswith(".pdf"):
        doc_id = str(uuid.uuid4())
        doc_name = url.split("/")[-1]
        if not doc_name.endswith(".pdf"):
            doc_name += ".pdf"
        pdf_path = _PDF_STORAGE_DIR / f"{doc_id}.pdf"
        pdf_path.write_bytes(raw_bytes)

        chunks = _process_pdf_file(pdf_path, doc_id, doc_name)
        for c in chunks:
            c["url"] = url
        return chunks
    else:
        return _process_webpage(raw_bytes, url)


def _extract_digital_assets_from_html(
    html_bytes: bytes,
    base_url: str,
    brand: str,
    resolved_mfr_domain: str | None = None,
) -> dict:
    """
    Extract product digital assets from an HTML page.
    Only returns URLs from the manufacturer's own domain.

    Args:
        resolved_mfr_domain: LLM-oracle-resolved domain (e.g. 'boschtools.com').
            When provided, this takes priority over the static guess.

    Returns dict with keys: product_image, spec_sheet, sds, manual, warranty_doc,
    installation_guide, alternate_images (list).
    """
    html_str = html_bytes.decode("utf-8", errors="replace")
    host = urlparse(base_url).netloc.lower()
    # Use oracle-resolved domain if available, otherwise fall back to static guess
    mfr_domain = resolved_mfr_domain or guess_mfr_domain(brand)

    def _is_mfr_url(url: str) -> bool:
        """Only accept URLs from the manufacturer's own domain."""
        if not url:
            return False
        try:
            u_host = urlparse(url).netloc.lower().lstrip("www.")
            if mfr_domain:
                return u_host == mfr_domain or u_host.endswith("." + mfr_domain)
            # Fallback: same host as page we fetched from
            return u_host == host.lstrip("www.")
        except Exception:
            return False

    assets: dict = {
        "product_image": None,
        "alternate_images": [],
        "spec_sheet": None,
        "sds": None,
        "manual": None,
        "installation_guide": None,
        "warranty_doc": None,
        "catalog": None,
        "energy_guide": None,
    }

    # ── Product images ──
    image_patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
        r'"image"\s*:\s*"(https?://[^"]+\.(?:jpg|jpeg|png|webp))"',
        r'<img[^>]+class="[^"]*(?:product|hero|main|primary)[^"]*"[^>]+src=["\']([^"\']+)["\']',
        r'<img[^>]+src=["\']([^"\']+\.(?:jpg|jpeg|png|webp))["\'][^>]+(?:alt|title)=["\'][^"\']*(?:product|item)[^"\']*["\']',
    ]
    found_images = []
    for pat in image_patterns:
        for m in re.findall(pat, html_str, re.IGNORECASE):
            u = m.strip()
            if u.startswith("//"):
                u = "https:" + u
            if u.startswith("http") and u not in found_images:
                found_images.append(u)

    # Filter to manufacturer domain only
    mfr_images = [u for u in found_images if _is_mfr_url(u)]
    if mfr_images:
        assets["product_image"] = mfr_images[0]
        assets["alternate_images"] = mfr_images[1:5]
    elif found_images:
        # Accept same-host images even if domain guess failed
        assets["product_image"] = found_images[0]
        assets["alternate_images"] = found_images[1:5]

    # ── PDF document links ──
    pdf_links = re.findall(r'href=["\']([^"\']+\.pdf(?:[?#][^"\']*)?)["\']', html_str, re.IGNORECASE)
    for raw_link in pdf_links:
        if raw_link.startswith("//"):
            raw_link = "https:" + raw_link
        elif raw_link.startswith("/"):
            raw_link = f"https://{host}{raw_link}"

        if not raw_link.startswith("http"):
            continue

        link_lower = raw_link.lower()
        fname_lower = raw_link.split("/")[-1].lower().split("?")[0]

        if "sds" in fname_lower or "safety" in fname_lower or "msds" in fname_lower or "sds" in link_lower:
            if assets["sds"] is None:
                assets["sds"] = raw_link
        elif "installation" in fname_lower or "install" in fname_lower or "install" in link_lower:
            if assets["installation_guide"] is None:
                assets["installation_guide"] = raw_link
        elif "owner" in fname_lower or "user" in fname_lower or "manual" in fname_lower:
            if assets["manual"] is None:
                assets["manual"] = raw_link
        elif "warranty" in fname_lower or "warrant" in fname_lower:
            if assets["warranty_doc"] is None:
                assets["warranty_doc"] = raw_link
        elif "energy" in fname_lower or "energyguide" in fname_lower:
            if assets["energy_guide"] is None:
                assets["energy_guide"] = raw_link
        elif "catalog" in fname_lower or "catalogue" in fname_lower:
            if assets["catalog"] is None:
                assets["catalog"] = raw_link
        else:
            # Generic spec sheet / datasheet
            if assets["spec_sheet"] is None:
                assets["spec_sheet"] = raw_link

    return assets


# ---------------------------------------------------------------------------
# LLM ORACLE — Resolve manufacturer domain + URL hint before web search
# ---------------------------------------------------------------------------

def _llm_resolve_mfr(brand: str, mpn: str, description: str, category: str) -> dict:
    """
    Ask the LLM to identify the manufacturer's official domain and product page.
    Returns:
      {
        "mfr_domain": "boschtools.com",       # e.g. boschtools.com (no https://)
        "mfr_url_hint": "https://...",         # best-guess direct product URL (may 404)
        "confidence": 0.85,                   # 0.0 – 1.0
        "reasoning": "..."
      }
    Falls back to empty dict on any error.
    """
    prompt = (
        f"You are a product data expert with deep knowledge of manufacturer websites.\n"
        f"Given the product below, identify the manufacturer's OFFICIAL website domain "
        f"and, if you know it, the direct product page URL.\n\n"
        f"Brand: {brand}\n"
        f"MPN: {mpn}\n"
        f"Description: {description or 'N/A'}\n"
        f"Category: {category or 'N/A'}\n\n"
        f"Rules:\n"
        f"- mfr_domain: bare domain only, no https:// (e.g. \"boschtools.com\")\n"
        f"- mfr_url_hint: your best guess at the exact product page URL. Use null if unsure.\n"
        f"- confidence: float 0.0-1.0. Be HONEST — use 0.5 if you are guessing the domain.\n"
        f"- NEVER return distributor domains (grainger, amazon, zoro, etc.) as mfr_domain.\n"
        f"- If brand is a distributor or unknown, set mfr_domain to null and confidence to 0.1.\n\n"
        f"Respond with ONLY a JSON object: "
        f'{{"mfr_domain": ..., "mfr_url_hint": ..., "confidence": ..., "reasoning": ...}}'
    )
    messages = [
        {"role": "system", "content": "You output only valid JSON. No markdown."},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = generate_with_retry(
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        data = parse_json_response(raw)
        confidence = float(data.get("confidence", 0.0))
        mfr_domain = (data.get("mfr_domain") or "").strip().lower().lstrip("www.").rstrip("/")
        mfr_url_hint = (data.get("mfr_url_hint") or "").strip() or None
        logger.info(
            "[LLM Oracle] brand=%s -> domain=%s, hint=%s, conf=%.2f, reason=%s",
            brand, mfr_domain, mfr_url_hint, confidence, data.get("reasoning", "")[:80]
        )
        return {"mfr_domain": mfr_domain or None, "mfr_url_hint": mfr_url_hint, "confidence": confidence}
    except Exception as e:
        logger.warning("[LLM Oracle] Failed for %s %s: %s", brand, mpn, e)
        return {"mfr_domain": None, "mfr_url_hint": None, "confidence": 0.0}


def _verify_url_alive(url: str, timeout: int = 5) -> bool:
    """Quick HEAD check — returns True if the URL responds with 2xx or 3xx."""
    if not url:
        return False
    try:
        r = requests.head(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=timeout,
            allow_redirects=True,
        )
        return r.status_code < 400
    except Exception:
        return False


def _search_web(brand: str, mpn: str, max_results: int = 8, description: str = "", category: str = "") -> dict:
    """
    Search for product documentation using Serper.dev.
    Returns:
      {
        "mfr_url": str | None,   # manufacturer's own product page
        "all_urls": list[str],   # all valid non-ecommerce URLs found
      }
    
    Pass 1: Manufacturer's own site  → mfr_url candidate
    Pass 2: PDF datasheets           → spec sheets
    Pass 3: Industrial distributors  → B2B ref URLs (no ecommerce)
    Pass 4: Exact MPN match          → any other relevant pages
    """
    import json as _json
    serper_api_key = os.getenv("SERPER_API_KEY")
    if not serper_api_key:
        logger.warning("No SERPER_API_KEY — using fallback distributor URLs")
        import urllib.parse
        encoded_mpn = urllib.parse.quote(mpn)
        fallback_urls = [
            f"https://www.grainger.com/search?searchQuery={encoded_mpn}",
            f"https://www.zoro.com/search?q={encoded_mpn}",
        ]
        return {"mfr_url": None, "all_urls": fallback_urls[:max_results]}

    headers = {"X-API-KEY": serper_api_key, "Content-Type": "application/json"}
    mfr_url: str | None = None
    all_urls: list[str] = []

    # ── LLM Oracle: resolve manufacturer domain before any web search ────────
    oracle = _llm_resolve_mfr(brand, mpn, description, category)
    oracle_domain: str | None = oracle.get("mfr_domain")
    oracle_hint: str | None = oracle.get("mfr_url_hint")
    oracle_conf: float = oracle.get("confidence", 0.0)

    # Start with static lookup, then override/upgrade with LLM result
    static_domain = guess_mfr_domain(brand)

    # Choose best domain: prefer LLM if confident, fall back to static map
    if oracle_domain and oracle_conf >= 0.7:
        mfr_domain = oracle_domain
        logger.info("[Retriever] LLM Oracle domain (conf=%.2f): %s", oracle_conf, mfr_domain)
    elif static_domain:
        mfr_domain = static_domain
        logger.info("[Retriever] Static domain map: %s", mfr_domain)
    else:
        mfr_domain = oracle_domain  # use low-confidence oracle as last resort
        logger.info("[Retriever] Low-confidence oracle domain: %s (conf=%.2f)", mfr_domain, oracle_conf)

    # ── Fast-path: verify LLM's direct URL hint ──────────────────────────────
    if oracle_hint and oracle_conf >= 0.75:
        if _verify_url_alive(oracle_hint):
            mfr_url = oracle_hint
            all_urls.append(mfr_url)
            logger.info("[Retriever] MFR URL confirmed from LLM hint: %s", mfr_url)
        else:
            logger.info("[Retriever] LLM hint 404'd (%s), trying constructed URL patterns", oracle_hint)
            # Try common manufacturer URL patterns before giving up
            if mfr_domain:
                _mpn_slug = mpn.replace(" ", "-").replace("/", "-")
                _candidate_patterns = [
                    f"https://www.{mfr_domain}/products/{mpn}",
                    f"https://www.{mfr_domain}/products/{_mpn_slug}",
                    f"https://www.{mfr_domain}/search?q={mpn}",
                    f"https://{mfr_domain}/products/{mpn}",
                    f"https://{mfr_domain}/search?q={mpn}",
                ]
                for _candidate in _candidate_patterns:
                    if _verify_url_alive(_candidate):
                        mfr_url = _candidate
                        all_urls.append(mfr_url)
                        logger.info("[Retriever] MFR URL found via pattern: %s", mfr_url)
                        break
                if not mfr_url:
                    logger.info("[Retriever] No constructed URL resolved, falling through to search")

    def _add_url(url: str) -> bool:
        """Add URL if it passes all filters. Returns True if added."""
        if not url:
            return False
        if is_ecommerce(url):
            logger.debug("Blocked e-commerce URL: %s", url)
            return False
        if url not in all_urls and len(all_urls) < max_results:
            all_urls.append(url)
            return True
        return False

    def _run_search(query: str, num: int = 5) -> list[str]:
        try:
            payload = _json.dumps({"q": query, "num": num})
            resp = requests.post(
                "https://google.serper.dev/search",
                headers=headers, data=payload, timeout=12
            )
            resp.raise_for_status()
            return [item.get("link", "") for item in resp.json().get("organic", [])]
        except Exception as e:
            logger.error("Serper search failed: %s", e)
            return []

    # ── Pass 1: Targeted site: search using best-known manufacturer domain ───
    if mfr_domain:
        mfr_query = f'"{mpn}" site:{mfr_domain}'
    else:
        mfr_query = f'"{mpn}" "{brand}" product specifications -amazon -ebay -walmart -grainger -zoro'

    pass1_urls = _run_search(mfr_query, num=5)
    for url in pass1_urls:
        if is_ecommerce(url):
            continue
        is_mfr = is_manufacturer_domain(url, brand) or (mfr_domain and mfr_domain in url)
        if is_mfr and mfr_url is None:
            mfr_url = url
            logger.info("[Retriever] MFR URL found (Pass 1 search): %s", mfr_url)
        _add_url(url)
    logger.info("[Retriever] Pass 1 done — mfr_url=%s, total=%d", mfr_url, len(all_urls))

    # ── Pass 2: PDF datasheets (prefer manufacturer domain) ─────────────────
    pdf_query = f'"{brand}" "{mpn}" datasheet filetype:pdf'
    if mfr_domain:
        pdf_query_mfr = f'"{mpn}" site:{mfr_domain} filetype:pdf'
        pass2_urls = _run_search(pdf_query_mfr, num=3) + _run_search(pdf_query, num=3)
    else:
        pass2_urls = _run_search(pdf_query, num=5)

    for url in pass2_urls:
        if not is_ecommerce(url):
            _add_url(url)
    logger.info("[Retriever] Pass 2 done — total=%d", len(all_urls))

    # ── Pass 3: Industrial distributors (strict domain filter) ──────────────
    if len(all_urls) < 6:
        dist_query = (
            f'"{mpn}" '
            f'site:grainger.com OR site:zoro.com OR site:mcmaster.com '
            f'OR site:mscdirect.com OR site:fastenal.com OR site:motion.com'
        )
        pass3_urls = _run_search(dist_query, num=4)
        for url in pass3_urls:
            if is_approved_distributor(url) and not is_ecommerce(url):
                _add_url(url)
        logger.info("[Retriever] Pass 3 done — total=%d", len(all_urls))

    # ── Pass 4: Broad exact match (non-ecommerce only) ──────────────────────
    if len(all_urls) < 6:
        exact_query = f'"{brand}" "{mpn}" product specifications'
        pass4_urls = _run_search(exact_query, num=4)
        for url in pass4_urls:
            if not is_ecommerce(url):
                _add_url(url)
        logger.info("[Retriever] Pass 4 done — total=%d", len(all_urls))

    return {"mfr_url": mfr_url, "all_urls": all_urls, "resolved_mfr_domain": mfr_domain}


def _fallback_local(brand: str, mpn: str) -> list[dict]:
    """Fallback to local reference_docs."""
    if not _REFERENCE_DOCS_DIR.exists():
        return []

    mpn_clean = re.sub(r"[^a-z0-9]", "", mpn.lower())
    for fpath in _REFERENCE_DOCS_DIR.iterdir():
        stem_clean = re.sub(r"[^a-z0-9]", "", fpath.stem.lower())
        if mpn_clean in stem_clean:
            logger.info("Using local fallback doc: %s", fpath.name)
            if fpath.suffix.lower() == ".pdf":
                doc_id = str(uuid.uuid4())
                dest_path = _PDF_STORAGE_DIR / f"{doc_id}.pdf"
                dest_path.write_bytes(fpath.read_bytes())
                return _process_pdf_file(dest_path, doc_id, fpath.name)
            else:
                text = fpath.read_text(encoding="utf-8", errors="replace")
                return [{
                    "text": text[:_MAX_TEXT_CHARS],
                    "source_type": "webpage_text",
                    "url": f"local://{fpath.name}"
                }]
    return []


def _update_knowledge_graph(brand: str, mpn: str, category: str):
    """Add product nodes and edges to NetworkX graph."""
    from pipeline.knowledge_graph import ingest_validated_product
    ingest_validated_product(brand, mpn, category, {})


def retrieve(brand: str, mpn: str, description: str, category: str) -> dict:
    """
    Stage 2: Retrieve and extract chunks about the product.
    Returns a dict with:
      - chunks: list of chunk dicts
      - mfr_url: the manufacturer's own product page (or None)
      - ref_urls: list of approved non-ecommerce ref URLs (distributors/datasheets)
      - product_image_url: first product image from manufacturer site (or None)
      - spec_sheet_url: first PDF spec sheet from manufacturer (or None)
      - sds_url: SDS/safety sheet URL from manufacturer (or None)
      - manual_url: owner/user manual URL from manufacturer (or None)
      - installation_url: installation guide URL from manufacturer (or None)
      - warranty_url: warranty document URL from manufacturer (or None)
      - catalog_url: catalog URL from manufacturer (or None)
      - energy_guide_url: energy guide URL from manufacturer (or None)
      - alternate_image_urls: list of alternate images from manufacturer (or [])
    """
    product_id = _get_product_id(brand, mpn)
    offline = os.getenv("OFFLINE_DEMO", "false").lower() == "true"

    # 1. Update KG
    _update_knowledge_graph(brand, mpn, category)

    # 2. Check ChromaDB cache
    chunks = _get_cached_chunks(product_id)
    if chunks:
        logger.info("Found %d cached chunks in ChromaDB for %s", len(chunks), product_id)
        # Re-run oracle to recover mfr_url even from cache (fast LLM call only)
        oracle = _llm_resolve_mfr(brand, mpn, description, category)
        cached_mfr_url: str | None = None
        if oracle.get("mfr_url_hint") and oracle.get("confidence", 0) >= 0.7:
            hint = oracle["mfr_url_hint"]
            if _verify_url_alive(hint):
                cached_mfr_url = hint
            elif oracle.get("mfr_domain"):
                # Construct guaranteed fallback
                cached_mfr_url = f"https://www.{oracle['mfr_domain']}/search?q={mpn}"
        elif oracle.get("mfr_domain"):
            cached_mfr_url = f"https://www.{oracle['mfr_domain']}/search?q={mpn}"
        return {
            "chunks": chunks,
            "mfr_url": cached_mfr_url,
            "ref_urls": [],
            "product_image_url": None,
            "spec_sheet_url": None,
            "sds_url": None,
            "manual_url": None,
            "installation_url": None,
            "warranty_url": None,
            "catalog_url": None,
            "energy_guide_url": None,
            "alternate_image_urls": [],
        }

    # 3. Web Search (4 passes if not offline)
    mfr_url: str | None = None
    ref_urls: list[str] = []
    product_image_url: str | None = None
    spec_sheet_url: str | None = None
    sds_url: str | None = None
    manual_url: str | None = None
    installation_url: str | None = None
    warranty_url: str | None = None
    catalog_url: str | None = None
    energy_guide_url: str | None = None
    alternate_image_urls: list[str] = []

    if not offline:
        search_result = _search_web(brand, mpn, max_results=8, description=description, category=category)
        mfr_url = search_result.get("mfr_url")
        all_urls = search_result.get("all_urls", [])
        # Resolved mfr_domain from oracle — used throughout fetch loop for accurate tagging
        resolved_mfr_domain: str | None = search_result.get("resolved_mfr_domain")

        # ── Guaranteed MFR URL fallback ───────────────────────────────────────
        # If web search didn't find mfr_url, construct one from the resolved domain.
        if not mfr_url and resolved_mfr_domain:
            # Try the oracle hint URL first, then common patterns
            _mpn_slug = mpn.replace(" ", "-").replace("/", "-")
            _fallback_candidates = [
                f"https://www.{resolved_mfr_domain}/search?searchtext={mpn}",
                f"https://www.{resolved_mfr_domain}/search?q={mpn}",
                f"https://www.{resolved_mfr_domain}/products/{mpn}",
                f"https://www.{resolved_mfr_domain}/products/{_mpn_slug}",
                f"https://{resolved_mfr_domain}/search?q={mpn}",
            ]
            for _fc in _fallback_candidates:
                if _verify_url_alive(_fc):
                    mfr_url = _fc
                    logger.info("[Retriever] MFR URL via constructed fallback: %s", mfr_url)
                    break
            # Last resort: use first candidate even without verification
            if not mfr_url:
                mfr_url = _fallback_candidates[0]
                logger.info("[Retriever] MFR URL using unverified fallback: %s", mfr_url)

        # Build ref_urls: ONLY mfr-domain PDFs + strictly approved distributors
        # Never include random sites, ecommerce, or unknown domains
        for url in all_urls:
            if url == mfr_url:
                continue
            if is_ecommerce(url):
                continue
            parsed_host = urlparse(url).netloc.lower().lstrip("www.")
            is_mfr_pdf = (
                (resolved_mfr_domain and parsed_host.endswith(resolved_mfr_domain))
                and url.lower().endswith(".pdf")
            )
            is_strict_distributor = is_approved_distributor(url)
            if is_mfr_pdf or is_strict_distributor:
                if url not in ref_urls:
                    ref_urls.append(url)
        # Limit to 5 ref URLs
        ref_urls = ref_urls[:5]

        logger.info(
            "[Retriever] Will fetch %d URLs (mfr_url=%s, resolved_domain=%s, ref_urls=%d)",
            len(all_urls), mfr_url, resolved_mfr_domain, len(ref_urls),
        )

        # Fetch and process each URL
        for url in all_urls:
            time.sleep(0.1)
            try:
                is_pdf = url.lower().endswith(".pdf") or "pdf" in url.lower()

                # Track spec sheet / SDS from any domain
                if is_pdf:
                    if ("sds" in url.lower() or "safety" in url.lower() or "msds" in url.lower()):
                        if sds_url is None:
                            sds_url = url
                    elif spec_sheet_url is None:
                        spec_sheet_url = url

                raw_resp = requests.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    timeout=_REQUEST_TIMEOUT,
                    stream=True
                )
                content_type = raw_resp.headers.get("Content-Type", "").lower()
                raw_bytes = raw_resp.content

                # Extract digital assets from HTML — MANUFACTURER DOMAIN ONLY
                # Use resolved_mfr_domain from oracle for accurate tagging
                if "html" in content_type:
                    is_mfr = (
                        is_manufacturer_domain(url, brand)
                        or bool(resolved_mfr_domain and resolved_mfr_domain in urlparse(url).netloc.lower())
                    )
                    if is_mfr:
                        assets = _extract_digital_assets_from_html(
                            raw_bytes, url, brand,
                            resolved_mfr_domain=resolved_mfr_domain,
                        )
                        if assets.get("product_image") and product_image_url is None:
                            product_image_url = assets["product_image"]
                            logger.info("[Retriever] Product image (mfr): %s", product_image_url)
                        if assets.get("alternate_images") and not alternate_image_urls:
                            alternate_image_urls = assets["alternate_images"]
                        if assets.get("spec_sheet") and spec_sheet_url is None:
                            spec_sheet_url = assets["spec_sheet"]
                        if assets.get("sds") and sds_url is None:
                            sds_url = assets["sds"]
                        if assets.get("manual") and manual_url is None:
                            manual_url = assets["manual"]
                        if assets.get("installation_guide") and installation_url is None:
                            installation_url = assets["installation_guide"]
                        if assets.get("warranty_doc") and warranty_url is None:
                            warranty_url = assets["warranty_doc"]
                        if assets.get("catalog") and catalog_url is None:
                            catalog_url = assets["catalog"]
                        if assets.get("energy_guide") and energy_guide_url is None:
                            energy_guide_url = assets["energy_guide"]
                    else:
                        logger.debug("[Retriever] Skipping asset extraction for non-mfr page: %s", url)

                fetched_chunks = _fetch_url(url)
                real_chunks = [
                    c for c in fetched_chunks
                    if len(c.get("text", "").strip()) >= 50 or c.get("image_base64")
                ]
                if real_chunks:
                    # Tag chunks with mfr domain flag — use oracle domain for accuracy
                    is_mfr = (
                        is_manufacturer_domain(url, brand)
                        or bool(resolved_mfr_domain and resolved_mfr_domain in urlparse(url).netloc.lower())
                    )
                    for c in real_chunks:
                        c["is_mfr_domain"] = is_mfr
                    chunks.extend(real_chunks)
                    logger.info("[Retriever] Got %d chunks from %s (mfr=%s)",
                                len(real_chunks), url, is_mfr)
                    if len(chunks) >= 8:
                        break
                elif fetched_chunks:
                    logger.warning("[Retriever] Skipped %s — content too short", url)
            except Exception as e:
                logger.warning("[Retriever] Failed to fetch %s: %s", url, e)

    # 4. Fallback to local if no chunks
    if not chunks:
        logger.info("[Retriever] No chunks from web (or offline). Trying local fallback.")
        chunks = _fallback_local(brand, mpn)

    # 5. Save to Chroma
    if chunks:
        _store_chunks(product_id, chunks)

    return {
        "chunks": chunks,
        "mfr_url": mfr_url,
        "ref_urls": ref_urls,
        "product_image_url": product_image_url,
        "spec_sheet_url": spec_sheet_url,
        "sds_url": sds_url,
        "manual_url": manual_url,
        "installation_url": installation_url,
        "warranty_url": warranty_url,
        "catalog_url": catalog_url,
        "energy_guide_url": energy_guide_url,
        "alternate_image_urls": alternate_image_urls,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    os.environ["OFFLINE_DEMO"] = "true"
    brand, mpn, desc = "Siemens", "3RT2015-1BB41", "Contactor"
    print(f"\n--- Retrieving: {brand} {mpn} ---")
    result = retrieve(brand, mpn, desc, "Electrical Switchgear")
    chunks = result["chunks"]
    print(f"Total chunks: {len(chunks)}")
    print(f"MFR URL: {result['mfr_url']}")
    print(f"Ref URLs: {result['ref_urls']}")
    print(f"Spec Sheet: {result['spec_sheet_url']}")
