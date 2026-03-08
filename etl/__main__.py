"""Usage: python -m etl.ingest [--repo-path PATH] [--db-url URL] [--reset] [--small|--start|--full]"""
import argparse
import asyncio
from etl.ingest import run_ingestion


def main():
    parser = argparse.ArgumentParser(description="SpecterBot ETL: ingest Canadian laws XML into PostgreSQL")
    parser.add_argument("--repo-path", default="./laws-lois-xml")
    parser.add_argument("--db-url", default="postgresql://dev:dev@localhost:5433/statutelens")
    parser.add_argument("--reset", action="store_true", help="Wipe and reload all data")
    parser.add_argument("--small", action="store_true", help="1 act + 1 regulation")
    parser.add_argument("--start", action="store_true", help="5-10 key acts")
    parser.add_argument("--full", action="store_true", help="All acts (eng only)")
    parser.add_argument("--lang", default="en", choices=["en", "fr"])
    args = parser.parse_args()
    asyncio.run(run_ingestion(args))


if __name__ == "__main__":
    main()
