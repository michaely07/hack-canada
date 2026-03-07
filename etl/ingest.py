import json
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


def _reg_matches(filepath, codes):
    """Check if a regulation file matches any of the given codes."""
    stem = filepath.stem
    for code in codes:
        # Normalize: SOR-97-175 -> SOR-97-175 (stem should match)
        if stem == code or stem.replace(",", "").replace(" ", "") == code:
            return True
    return False


async def run_ingestion(args):
    pool = await asyncpg.create_pool(args.db_url, min_size=2, max_size=5)
    embedder = BatchEmbedder()

    if args.reset:
        async with pool.acquire() as conn:
            await conn.execute("TRUNCATE laws, sections CASCADE")
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

        if not law_data.get("code"):
            print(f"SKIP {xml_path.name}: could not determine law code")
            continue

        if not sections:
            print(f"WARN {xml_path.name}: no sections found, skipping")
            continue

        async with pool.acquire() as conn:
            # Upsert law
            law_id = await conn.fetchval("""
                INSERT INTO laws (code, type, short_title_en, long_title_en,
                                in_force, pit_date, last_amended, enabling_act_code, xml_path)
                VALUES ($1, $2, $3, $4, $5, $6::date, $7::date, $8, $9)
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
                # Skip sections with no lims_id (can't upsert without it)
                if not section.get("lims_id"):
                    continue
                try:
                    await conn.execute("""
                        INSERT INTO sections (law_id, lims_id, label, marginal_note,
                            heading, part_label, part_title, content_text, content_xml,
                            chunk_type, definitions, cross_refs, embedding, language, token_count)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13::vector,$14,$15)
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
                        str(emb.tolist()), args.lang,
                        section.get("token_count"))
                except Exception as e:
                    print(f"  WARN section {section.get('lims_id')}: {e}")

    # Print stats
    async with pool.acquire() as conn:
        law_count = await conn.fetchval("SELECT COUNT(*) FROM laws")
        sec_count = await conn.fetchval("SELECT COUNT(*) FROM sections")
    print(f"Done. {law_count} laws, {sec_count} sections in database.")
    await pool.close()
