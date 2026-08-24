"""
pipeline/knowledge_store.py — SQLite-backed knowledge cache.

Stores learned mappings to avoid hardcoding and repeating expensive LLM calls:
  - brand_aliases: maps messy distributor/input strings to canonical OEM brands
  - brand_domains: maps canonical OEM brands to their official website domains
  - category_cache: maps leaf categories to their taxonomy classpath and required attributes
"""

import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

def _get_db_path() -> str:
    primary = Path(__file__).resolve().parent.parent / "knowledge_store.db"
    try:
        primary.parent.mkdir(parents=True, exist_ok=True)
        test_file = primary.parent / ".db_test_ks"
        test_file.touch(exist_ok=True)
        test_file.unlink(missing_ok=True)
        return str(primary)
    except Exception:
        return "/tmp/knowledge_store.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_get_db_path(), timeout=15.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create knowledge cache tables if they don't exist."""
    with _get_conn() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS brand_aliases (
                raw_name TEXT PRIMARY KEY,
                canonical_brand TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS brand_domains (
                brand TEXT PRIMARY KEY,
                domain TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS category_cache (
                subcategory TEXT PRIMARY KEY,
                classpath TEXT NOT NULL,
                unspsc TEXT NOT NULL,
                expected_fields_json TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS attribute_aliases (
                raw_value TEXT PRIMARY KEY,
                canonical_value TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                document_id TEXT PRIMARY KEY,
                url TEXT,
                manufacturer TEXT,
                sha256 TEXT UNIQUE,
                local_path TEXT,
                processed BOOLEAN DEFAULT 0
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS series_knowledge (
                manufacturer TEXT,
                series TEXT,
                attribute TEXT,
                value TEXT,
                scope TEXT,
                confidence REAL,
                source TEXT,
                PRIMARY KEY (manufacturer, series, attribute)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS human_reviews (
                product_id TEXT,
                attribute TEXT,
                proposed_value TEXT,
                final_value TEXT,
                decision TEXT,
                timestamp TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS scalability_metrics (
                metric_key TEXT PRIMARY KEY,
                metric_value INTEGER DEFAULT 0
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS desc_abbreviations (
                abbreviation TEXT PRIMARY KEY,
                canonical_value TEXT NOT NULL,
                field_name TEXT,
                approval_count INTEGER DEFAULT 1,
                last_seen TEXT
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS product_attributes (
                brand TEXT,
                mpn TEXT,
                attribute TEXT,
                value TEXT,
                confidence REAL,
                source TEXT,
                approved_by TEXT,
                timestamp TEXT,
                PRIMARY KEY (brand, mpn, attribute)
            )
        ''')
        conn.commit()
    logger.info("Knowledge store initialized at %s", _DB_PATH)


# --- Scalability Metrics ---

def increment_metric(metric_key: str, amount: int = 1) -> None:
    with _get_conn() as conn:
        conn.execute('''
            INSERT INTO scalability_metrics (metric_key, metric_value)
            VALUES (?, ?)
            ON CONFLICT(metric_key) DO UPDATE SET
                metric_value = metric_value + excluded.metric_value
        ''', (metric_key, amount))
        conn.commit()


def get_all_metrics() -> dict[str, int]:
    with _get_conn() as conn:
        rows = conn.execute("SELECT metric_key, metric_value FROM scalability_metrics").fetchall()
        metrics = {r["metric_key"]: r["metric_value"] for r in rows}
        
        docs_cached = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        series_cached = conn.execute("SELECT COUNT(DISTINCT series) FROM series_knowledge").fetchone()[0]
        aliases_cached = conn.execute("SELECT COUNT(*) FROM brand_aliases").fetchone()[0]
        reviews_count = conn.execute("SELECT COUNT(*) FROM human_reviews").fetchone()[0]
        
        return {
            "searches_avoided": metrics.get("searches_avoided", 0),
            "cache_hits": metrics.get("cache_hits", 0),
            "series_hits": metrics.get("series_hits", 0),
            "documents_reused": metrics.get("documents_reused", 0),
            "documents_cached": docs_cached,
            "unique_series_cached": series_cached,
            "brand_aliases_cached": aliases_cached,
            "human_reviews_logged": reviews_count,
        }


# --- Brand Aliases ---

def get_canonical_brand(raw_name: str) -> str | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT canonical_brand FROM brand_aliases WHERE lower(raw_name) = lower(?)", 
            (raw_name.strip(),)
        ).fetchone()
        return row["canonical_brand"] if row else None


def save_brand_alias(raw_name: str, canonical_brand: str) -> None:
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO brand_aliases (raw_name, canonical_brand) VALUES (?, ?)", 
            (raw_name.strip(), canonical_brand.strip())
        )
        conn.commit()


# --- Brand Domains ---

def get_brand_domain(brand: str) -> str | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT domain FROM brand_domains WHERE lower(brand) = lower(?)", 
            (brand.strip(),)
        ).fetchone()
        return row["domain"] if row else None


def save_brand_domain(brand: str, domain: str) -> None:
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO brand_domains (brand, domain) VALUES (?, ?)", 
            (brand.strip(), domain.strip())
        )
        conn.commit()


# --- Category / Taxonomy Cache ---

def get_category_cache(subcategory: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT classpath, unspsc, expected_fields_json FROM category_cache WHERE lower(subcategory) = lower(?)", 
            (subcategory.strip(),)
        ).fetchone()
        if row:
            return {
                "classpath": row["classpath"],
                "unspsc": row["unspsc"],
                "expected_fields": json.loads(row["expected_fields_json"])
            }
        return None


def save_category_cache(subcategory: str, classpath: str, unspsc: str, expected_fields: list[str]) -> None:
    with _get_conn() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO category_cache (subcategory, classpath, unspsc, expected_fields_json)
            VALUES (?, ?, ?, ?)
        ''', (subcategory.strip(), classpath.strip(), unspsc.strip(), json.dumps(expected_fields)))
        conn.commit()


# --- Documents ---

def get_document_by_hash(sha256: str) -> dict | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE sha256 = ?",
            (sha256,)
        ).fetchone()
        return dict(row) if row else None


def save_document_metadata(document_id: str, url: str, manufacturer: str, sha256: str, local_path: str, processed: bool = False) -> None:
    with _get_conn() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO documents (document_id, url, manufacturer, sha256, local_path, processed)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (document_id, url, manufacturer, sha256, local_path, int(processed)))
        conn.commit()


def mark_document_processed(sha256: str) -> None:
    with _get_conn() as conn:
        conn.execute("UPDATE documents SET processed = 1 WHERE sha256 = ?", (sha256,))
        conn.commit()


# --- Series Knowledge ---

def get_series_knowledge(manufacturer: str, series: str) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM series_knowledge WHERE lower(manufacturer) = lower(?) AND lower(series) = lower(?)",
            (manufacturer.strip(), series.strip())
        ).fetchall()
        return [dict(row) for row in rows]


def save_series_knowledge(manufacturer: str, series: str, attribute: str, value: str, scope: str, confidence: float, source: str) -> None:
    with _get_conn() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO series_knowledge (manufacturer, series, attribute, value, scope, confidence, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (manufacturer.strip(), series.strip(), attribute.strip(), str(value), scope, confidence, source))
        conn.commit()


# --- Human Reviews ---

def save_human_review(product_id: str, attribute: str, proposed_value: str, final_value: str, decision: str) -> None:
    from datetime import datetime, timezone
    with _get_conn() as conn:
        conn.execute('''
            INSERT INTO human_reviews (product_id, attribute, proposed_value, final_value, decision, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (product_id, attribute, str(proposed_value), str(final_value), decision, datetime.now(timezone.utc).isoformat()))
        conn.commit()


# --- Attribute Aliases (Normalization Loop) ---

def get_canonical_attribute_value(raw_value: str) -> str | None:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT canonical_value FROM attribute_aliases WHERE lower(raw_value) = lower(?)",
            (raw_value.strip(),)
        ).fetchone()
        return row["canonical_value"] if row else None


def save_attribute_alias(raw_value: str, canonical_value: str) -> None:
    if not raw_value or not canonical_value:
        return
    # Avoid trivial self-aliases or duplicates
    if raw_value.strip().lower() == canonical_value.strip().lower():
        return
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO attribute_aliases (raw_value, canonical_value) VALUES (?, ?)",
            (raw_value.strip(), canonical_value.strip())
        )
        conn.commit()


# --- Description Abbreviations ---

def save_desc_abbreviation(abbreviation: str, canonical_value: str, field_name: str = "") -> None:
    """Save or increment a crowd-sourced abbreviation → canonical value mapping."""
    from datetime import datetime, timezone
    if not abbreviation or not canonical_value:
        return
    if abbreviation.strip().lower() == canonical_value.strip().lower():
        return
    with _get_conn() as conn:
        conn.execute('''
            INSERT INTO desc_abbreviations (abbreviation, canonical_value, field_name, approval_count, last_seen)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(abbreviation) DO UPDATE SET
                canonical_value = excluded.canonical_value,
                field_name = excluded.field_name,
                approval_count = approval_count + 1,
                last_seen = excluded.last_seen
        ''', (abbreviation.strip(), canonical_value.strip(), field_name.strip(),
              datetime.now(timezone.utc).isoformat()))
        conn.commit()


def get_desc_abbreviations() -> dict[str, dict]:
    """Return all DB-learned abbreviations as {abbreviation: {canonical_value, field_name}} dict."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT abbreviation, canonical_value, field_name, approval_count FROM desc_abbreviations"
        ).fetchall()
        return {
            r["abbreviation"]: {
                "canonical_value": r["canonical_value"],
                "field_name": r["field_name"] or "",
                "approval_count": r["approval_count"],
            }
            for r in rows
        }


# --- Product Attributes (non-series unique facts) ---

def save_product_attribute(
    brand: str, mpn: str, attribute: str, value: str,
    confidence: float, source: str, approved_by: str
) -> None:
    """Upsert a product-unique attribute fact to the product_attributes table."""
    from datetime import datetime, timezone
    with _get_conn() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO product_attributes
                (brand, mpn, attribute, value, confidence, source, approved_by, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (brand.strip(), mpn.strip(), attribute.strip(), str(value),
              confidence, source, approved_by,
              datetime.now(timezone.utc).isoformat()))
        conn.commit()


def boost_series_attribute_confidence(
    manufacturer: str, series: str, attribute: str, value: str
) -> None:
    """Set confidence to 1.0 and source to human_verified for a series knowledge entry."""
    with _get_conn() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO series_knowledge
                (manufacturer, series, attribute, value, scope, confidence, source)
            VALUES (?, ?, ?, ?, 'series', 1.0, 'human_verified')
        ''', (manufacturer.strip(), series.strip(), attribute.strip(), str(value)))
        conn.commit()
