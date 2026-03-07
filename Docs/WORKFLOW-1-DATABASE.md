# WORKFLOW-1-DATABASE.md — Database & ETL Ingestion

> **Owner:** Person 1
> **Dependencies:** None (first to start)
> **Delivers to:** Person 2 (backend needs populated DB), Person 3 (needs /api/laws and /api/sections data)

## Your Job

You own the data layer. By the end of Friday evening, the other three teammates should be able to connect to a running PostgreSQL instance with real Canadian law data in it.

## Prerequisites

- Docker Desktop installed
- Python 3.12+
- Git
- ~2GB disk space for the laws-lois-xml repo

## Timeline

### Friday Evening (4-5 hours)

#### Hour 1: Database Setup

1. Create `docker-compose.yml` in project root:

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: statutelens
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

2. Start it: `docker compose up -d db`

3. Create `migrations/001_init.sql` with the full schema from CLAUDE.md. Run it:
```bash
psql postgresql://dev:dev@localhost:5432/statutelens -f migrations/001_init.sql
```

4. Verify: `psql` in, run `\dt` to see tables, `\dx` to confirm `vector` extension.

**Checkpoint:** Tables exist, pgvector enabled. Share the connection string with team.

#### Hours 2-4: ETL Pipeline

Clone the data:
```bash
git clone https://github.com/justicecanada/laws-lois-xml.git
```

Build these files:

**`etl/__main__.py`** — CLI entry point:
```python
"""Usage: python -m etl.ingest [--repo-path PATH] [--db-url URL] [--reset] [--small|--start|--full]"""
import argparse
import asyncio
from etl.ingest import run_ingestion

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-path", default="./laws-lois-xml")
    parser.add_argument("--db-url", default="postgresql://dev:dev@localhost:5432/statutelens")
    parser.add_argument("--reset", action="store_true", help="Wipe and reload all data")
    parser.add_argument("--small", action="store_true", help="1 act + 1 regulation")
    parser.add_argument("--start", action="store_true", help="5-10 key acts")
    parser.add_argument("--full", action="store_true", help="All acts (eng only)")
    parser.add_argument("--lang", default="en", choices=["en", "fr"])
    args = parser.parse_args()
    asyncio.run(run_ingestion(args))

if __name__ == "__main__":
    main()
```

**`etl/ingest.py`** — Orchestrator:
```python
import asyncpg
from pathlib import Path
from etl.xml_parser import parse_law_file
from etl.embedder import BatchEmbedder
from tqdm import tqdm

# Which acts to ingest for --start flag
START_ACTS = ["A-1", "C-46", "I-5", "L-2", "I-2.5"]
# --small flag
SMALL_ACTS = ["A-1"]
SMALL_REGS = ["SOR-97-175"]

async def run_ingestion(args):
    pool = await asyncpg.create_pool(args.db_url, min_size=2, max_size=5)
    embedder = BatchEmbedder()

    if args.reset:
        await pool.execute("TRUNCATE laws, sections CASCADE")
        print("Reset: all data cleared.")

    # Determine which files to process
    lang_folder = "eng" if args.lang == "en" else "fra"
    acts_dir = Path(args.repo_path) / lang_folder / "acts"
    regs_dir = Path(args.repo_path) / lang_folder / "regulations"

    act_files = sorted(acts_dir.glob("*.xml")) if acts_dir.exists() else []
    reg_files = sorted(regs_dir.glob("*.xml")) if regs_dir.exists() else []

    if args.small:
        act_files = [f for f in act_files if f.stem in SMALL_ACTS]
        reg_files = [f for f in reg_files if _reg_matches(f, SMALL_REGS)]
    elif args.start:
        act_files = [f for f in act_files if f.stem in START_ACTS]
        reg_files = []  # Skip regs for --start to save time
    # --full: use all files as-is

    all_files = [(f, "act") for f in act_files] + [(f, "regulation") for f in reg_files]
    print(f"Processing {len(all_files)} files...")

    for xml_path, law_type in tqdm(all_files, desc="Ingesting"):
        try:
            law_data, sections = parse_law_file(xml_path, law_type, args.lang)
        except Exception as e:
            print(f"SKIP {xml_path.name}: {e}")
            continue

        # Upsert law
        law_id = await pool.fetchval("""
            INSERT INTO laws (code, type, short_title_en, long_title_en,
                            in_force, pit_date, last_amended, enabling_act_code, xml_path)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (code) DO UPDATE SET
                short_title_en = EXCLUDED.short_title_en,
                last_amended = EXCLUDED.last_amended,
                ingested_at = NOW()
            RETURNING id
        """, law_data["code"], law_type, law_data["short_title_en"],
            law_data.get("long_title_en"), law_data.get("in_force", True),
            law_data.get("pit_date"), law_data.get("last_amended"),
            law_data.get("enabling_act_code"), str(xml_path))

        # Batch embed all sections
        texts = [s["content_text"] for s in sections]
        embeddings = embedder.encode_batch(texts)

        # Upsert sections
        for section, emb in zip(sections, embeddings):
            await pool.execute("""
                INSERT INTO sections (law_id, lims_id, label, marginal_note,
                    heading, part_label, part_title, content_text, content_xml,
                    chunk_type, definitions, cross_refs, embedding, language, token_count)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
                ON CONFLICT (lims_id, language) DO UPDATE SET
                    content_text = EXCLUDED.content_text,
                    embedding = EXCLUDED.embedding,
                    ingested_at = NOW()
            """, law_id, section["lims_id"], section["label"],
                section.get("marginal_note"), section.get("heading"),
                section.get("part_label"), section.get("part_title"),
                section["content_text"], section.get("content_xml"),
                section.get("chunk_type", "section"),
                json.dumps(section.get("definitions", [])),
                json.dumps(section.get("cross_refs", [])),
                emb.tolist(), args.lang,
                section.get("token_count"))

    # Print stats
    law_count = await pool.fetchval("SELECT COUNT(*) FROM laws")
    sec_count = await pool.fetchval("SELECT COUNT(*) FROM sections")
    print(f"Done. {law_count} laws, {sec_count} sections in database.")
    await pool.close()
```

**`etl/xml_parser.py`** — The core parser:
```python
from lxml import etree
from etl.text_extractor import extract_section_text
import json

LIMS_NS = "http://justice.gc.ca/lims"

def _lims(attr):
    """Helper: get lims-namespaced attribute."""
    return f"{{{LIMS_NS}}}{attr}"

def parse_law_file(xml_path, law_type, language):
    """Parse one XML file into a law dict + list of section dicts."""
    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    # Parse <Identification>
    ident = root.find("Identification")
    law_data = {
        "code": _get_code(ident, law_type),
        "short_title_en": ident.findtext("ShortTitle") or ident.findtext("LongTitle") or xml_path.stem,
        "long_title_en": ident.findtext("LongTitle"),
        "in_force": root.get("in-force", "yes") == "yes",
        "pit_date": root.get(_lims("pit-date")),
        "last_amended": root.get(_lims("lastAmendedDate")),
        "enabling_act_code": _get_enabling_act(ident),
    }

    # Parse <Body> → walk for Sections
    sections = []
    body = root.find("Body")
    if body is not None:
        _walk_body(body, sections, language)

    # Parse <Schedule> sections
    for schedule in root.iter("Schedule"):
        _walk_schedule(schedule, sections, language)

    return law_data, sections


def _get_code(ident, law_type):
    """Extract the law code (e.g., 'A-1', 'SOR-97-175')."""
    if law_type == "act":
        chapter = ident.find(".//ConsolidatedNumber")
        if chapter is not None:
            return chapter.text.strip()
    # Regulations use InstrumentNumber
    inst = ident.findtext("InstrumentNumber")
    if inst:
        return inst.strip().replace(",", "").replace(" ", "")
    return None


def _get_enabling_act(ident):
    """For regulations: extract the enabling act code from XRefExternal."""
    ea = ident.find("EnablingAuthority")
    if ea is not None:
        xref = ea.find("XRefExternal")
        if xref is not None:
            return xref.get("link")
    return None


def _walk_body(body, sections, language):
    """Walk the Body tree, tracking Heading context, extracting Sections."""
    current_heading = None
    current_part_label = None
    current_part_title = None

    for el in body:
        if el.tag == "Heading":
            level = el.get("level", "1")
            title = el.findtext("TitleText", "")
            label = el.findtext("Label", "")
            if level == "1":
                current_part_label = label
                current_part_title = title
            current_heading = title

        elif el.tag == "Section":
            section = _parse_section(el, language)
            section["heading"] = current_heading
            section["part_label"] = current_part_label
            section["part_title"] = current_part_title
            sections.append(section)

        # Recurse into Part, Division, etc.
        elif el.tag in ("Part", "Division", "Subdivision"):
            _walk_body(el, sections, language)


def _parse_section(section_el, language):
    """Parse a single <Section> node into a dict."""
    lims_id = section_el.get(_lims("id"))
    label = section_el.findtext("Label", "")
    marginal_note = section_el.findtext("MarginalNote", "")

    content_text = extract_section_text(section_el)
    content_xml = etree.tostring(section_el, encoding="unicode", pretty_print=True)

    # Extract definitions
    definitions = []
    for defn in section_el.iter("Definition"):
        term_en = defn.findtext(".//DefinedTermEn")
        term_fr = defn.findtext(".//DefinedTermFr")
        if term_en or term_fr:
            definitions.append({"term_en": term_en, "term_fr": term_fr})

    # Extract cross-references
    cross_refs = []
    for xref in section_el.iter("XRefExternal"):
        cross_refs.append({
            "link": xref.get("link"),
            "type": xref.get("reference-type"),
            "text": xref.text or "",
        })

    # Determine chunk type
    chunk_type = "definition" if definitions else "section"

    # Rough token count (words / 0.75)
    token_count = int(len(content_text.split()) / 0.75)

    return {
        "lims_id": lims_id,
        "label": label,
        "marginal_note": marginal_note,
        "content_text": content_text,
        "content_xml": content_xml,
        "chunk_type": chunk_type,
        "definitions": definitions,
        "cross_refs": cross_refs,
        "token_count": token_count,
    }


def _walk_schedule(schedule_el, sections, language):
    """Extract sections from Schedule nodes."""
    for section_el in schedule_el.iter("Section"):
        section = _parse_section(section_el, language)
        section["chunk_type"] = "schedule"
        section["heading"] = schedule_el.findtext(".//ScheduleFormHeading/Label", "Schedule")
        sections.append(section)
```

**`etl/text_extractor.py`**:
```python
def extract_section_text(section_el):
    """Flatten a Section element into readable text with label hierarchy."""
    parts = []

    mn = section_el.findtext("MarginalNote")
    if mn:
        parts.append(mn)

    label = section_el.findtext("Label", "")

    # Direct text children
    for text_el in section_el.findall("Text"):
        parts.append(f"{label} {_get_all_text(text_el)}")

    # Definitions at section level
    for defn in section_el.findall("Definition"):
        text_el = defn.find("Text")
        if text_el is not None:
            parts.append(_get_all_text(text_el))

    # Subsections
    for sub in section_el.findall("Subsection"):
        sub_label = sub.findtext("Label", "")
        sub_mn = sub.findtext("MarginalNote")
        if sub_mn:
            parts.append(sub_mn)
        for text_el in sub.findall("Text"):
            parts.append(f"{sub_label} {_get_all_text(text_el)}")
        # Paragraphs within subsection
        for para in sub.findall("Paragraph"):
            _extract_paragraph(para, parts, indent=1)

    return "\n".join(parts)


def _extract_paragraph(para_el, parts, indent=1):
    """Recursively extract paragraphs and subparagraphs."""
    prefix = "  " * indent
    label = para_el.findtext("Label", "")
    for text_el in para_el.findall("Text"):
        parts.append(f"{prefix}{label} {_get_all_text(text_el)}")
    for subpara in para_el.findall("Subparagraph"):
        _extract_paragraph(subpara, parts, indent=indent + 1)


def _get_all_text(el):
    """Get all text from element and children (handles XRefExternal, DefinedTermEn, etc.)."""
    return "".join(el.itertext()).strip()
```

**`etl/embedder.py`**:
```python
from sentence_transformers import SentenceTransformer
import numpy as np

class BatchEmbedder:
    def __init__(self, model_name="all-MiniLM-L6-v2"):
        print(f"Loading embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        print("Model loaded.")

    def encode_batch(self, texts: list[str], batch_size=64) -> list[np.ndarray]:
        """Encode a list of texts, returns list of numpy arrays."""
        if not texts:
            return []
        embeddings = self.model.encode(texts, batch_size=batch_size, show_progress_bar=False)
        return list(embeddings)
```

#### Hour 5: Verify & Share

Run ingestion:
```bash
python -m etl.ingest --repo-path ./laws-lois-xml --small
```

Verify:
```sql
SELECT l.code, l.short_title_en, COUNT(s.id) as sections
FROM laws l LEFT JOIN sections s ON s.law_id = l.id
GROUP BY l.code, l.short_title_en;
```

Then run with `--start` for the 5 demo acts.

**Checkpoint:** Database has 5 laws with hundreds of sections, all with embeddings. Share the connection string and stats with the team.

### Saturday Morning: Support & Polish

- Run `--start` if not done Friday
- Fix any parsing edge cases the team discovers
- Add any missing indexes
- Help Person 2 test hybrid search queries
- Build the `/api/graph/{code}` data by querying cross_refs JSONB

### Sunday: Help with integration testing

- Verify retrieval quality with golden test queries
- Fix any data issues found during demo prep

## Files You Own

```
etl/
  __main__.py
  ingest.py
  xml_parser.py
  text_extractor.py
  embedder.py
migrations/
  001_init.sql
docker-compose.yml
tests/
  test_xml_parser.py
  test_retrieval.py    (with Person 2)
  golden_queries.json
```

## Definition of Done

- [ ] `docker compose up db` works, pgvector enabled
- [ ] `python -m etl.ingest --small` succeeds in < 2 minutes
- [ ] `python -m etl.ingest --start` populates 5 acts with 500+ sections
- [ ] All sections have non-null embeddings (384-dim)
- [ ] `content_xml` column has valid XML for each section
- [ ] Cross-references extracted into `cross_refs` JSONB
- [ ] Definitions extracted into `definitions` JSONB
- [ ] Idempotent: running twice doesn't duplicate data
- [ ] Connection string shared with all teammates
