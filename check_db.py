import asyncio
import os
import sys
from dotenv import load_dotenv
from google.adk.sessions.database_session_service import DatabaseSessionService

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv()

async def check_db():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("[Error] DATABASE_URL not found in .env")
        return
        
    print(f"Connecting to database via DatabaseSessionService to verify logs...\n")
    session_service = DatabaseSessionService(db_url)
    
    app_name = "system_health_app"
    user_id = "admin"
    
    target_sessions = ["cli_session", "prefab_interactive_session", "streamlit_session"]
    
    for session_id in target_sessions:
        try:
            session = await session_service.get_session(
                app_name=app_name, 
                user_id=user_id, 
                session_id=session_id
            )
            
            if session:
                print(f"--- [FOUND] Session ID: {session_id} ---")
                history_len = len(session.events) if hasattr(session, 'events') and session.events else 0
                print(f"Records stored: {history_len} messages")
                
                if history_len > 0:
                    last_msg = session.events[-1]
                    author = last_msg.author
                    text = "".join(p.text for p in last_msg.content.parts if p.text)
                    print(f"Last Event ({author}): {text[:150]}...")
                print()
            else:
                print(f"--- [EMPTY] Session ID: {session_id} ---")
                print("No history recorded for this session yet.\n")
                
        except Exception as e:
            print(f"Error checking session {session_id}: {e}")

if __name__ == "__main__":
    asyncio.run(check_db())
