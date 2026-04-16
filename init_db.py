import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from google.adk.sessions.database_session_service import BaseV0
import os
from dotenv import load_dotenv

load_dotenv()

async def init_db():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("[Error] DATABASE_URL not found in .env")
        return
    
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(BaseV0.metadata.create_all)
    
    print("Session tables (sessions, events) created in health_db")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_db())
