import asyncio
import asyncpg
import sys

async def main():
    db_url = "postgresql://postgres:mpzdd03mym0im4xyjyib21o2gajtq08q@crossover.proxy.rlwy.net:36205/railway"
    print(f"Connecting to {db_url}...")
    conn = await asyncpg.connect(db_url)
    try:
        print("Dropping tables to free space...")
        await conn.execute("DROP TABLE IF EXISTS messages CASCADE;")
        await conn.execute("DROP TABLE IF EXISTS conversations CASCADE;")
        await conn.execute("DROP TABLE IF EXISTS sections CASCADE;")
        await conn.execute("DROP TABLE IF EXISTS laws CASCADE;")
        print("Tables dropped. Space should be freed.")
        
        with open("migrations/001_init.sql", "r", encoding="utf-8") as f:
            sql = f.read()
        print("Recreating tables...")
        await conn.execute(sql)
        print("Schema recreated successfully.")
    except Exception as e:
        print("ERROR:", e)
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
