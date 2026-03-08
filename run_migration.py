import asyncio
import asyncpg
import sys

async def main():
    if len(sys.argv) < 2:
        print("Usage: python run_migration.py <db_url>")
        return
    db_url = sys.argv[1]
    with open("migrations/001_init.sql", "r", encoding="utf-8") as f:
        sql = f.read()

    print(f"Connecting to {db_url}...")
    conn = await asyncpg.connect(db_url)
    try:
        print("Running migrations...")
        await conn.execute(sql)
        print("Migrations complete.")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
