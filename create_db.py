import asyncio
import asyncpg
import os
import sys
from dotenv import load_dotenv

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

async def create_db():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("[Error] DATABASE_URL not found in .env")
        return
        
    print(f"Extracted DATABASE_URL: {db_url}")
    # Convert 'postgresql+asyncpg://...' to 'postgresql://...'
    base_url = db_url.replace("postgresql+asyncpg", "postgresql")
    
    parts = base_url.rsplit("/", 1)
    if len(parts) == 2:
        sys_db = parts[0] + "/postgres"
        target_db = parts[1]
        
        print(f"Connecting to default system db to create '{target_db}'...")
        try:
            conn = await asyncpg.connect(sys_db)
            await conn.execute(f"CREATE DATABASE {target_db}")
            print(f"Database {target_db} created successfully.")
            await conn.close()
        except asyncpg.exceptions.DuplicateDatabaseError:
            print(f"Database {target_db} already exists.")
        except Exception as e:
            print(f"Error creating DB: {e}")

if __name__ == "__main__":
    asyncio.run(create_db())
