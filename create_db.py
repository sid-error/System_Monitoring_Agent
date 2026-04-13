import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(
        user='postgres',
        password='<YOUR_POSTGRES_PASSWORD>', # Replace with your password if running again
        database='postgres',
        host='localhost',
        port=5432
    )
    await conn.execute('CREATE DATABASE health_db')
    await conn.close()
    print("Database 'health_db' created successfully.")

asyncio.run(main())