import asyncio
import asyncpg
import os
from dotenv import load_dotenv
import json

load_dotenv()

async def check_db():
    print("Connecting to PostgreSQL health_db...")
    # asyncpg expects 'postgres://' or 'postgresql://' instead of 'postgresql+asyncpg://'
    db_url = os.getenv("DATABASE_URL")
    if getattr(db_url, "startswith", None) and db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgres://")
        
    try:
        conn = await asyncpg.connect(db_url)
        
        print("\n================== SESSIONS ==================")
        sessions = await conn.fetch("SELECT * FROM sessions")
        if not sessions:
            print("No sessions found.")
        for s in sessions:
            print(f"App: {s.get('app_name')} | User: {s.get('user_id')} | Session ID: {s.get('session_id')}")
            
        print("\n=================== EVENTS ===================")
        print("This is the chat history/context stored by the Agent.")
        events = await conn.fetch("SELECT * FROM events")
        if not events:
            print("No events/history found.")
        
        for e in events:
            session_ref = e.get('session_id')
            # Events structure might vary based on ADK, but usually stores raw JSON representations:
            model_info = e.get('model')
            timestamp = e.get('created_at')
            print(f"\n[{timestamp}] Session UUID: {session_ref}")
            if model_info:
                print(f"Model: {model_info}")
                
            # Content is typically a JSON serialized list or dict
            # We'll just print it cleanly:
            content = e.get('content')
            print(f"Content: {content}")
            
        await conn.close()
        print("\n==============================================")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_db())
