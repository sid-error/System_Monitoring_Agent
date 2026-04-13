# System Monitoring Agent

A conversational system-monitoring agent powered by Google ADK, MCP, and Gemini. It features a Streamlit-based web UI to seamlessly trace and query your computer's health (CPU, RAM, Disk formatting to Markdown) while securely keeping track of the chat context using a locally hosted PostgreSQL database.

## Requirements
- Python 3.9+
- PostgreSQL server instance running locally

## Setup Instructions

### 1. Configure the Environment
Ensure your `.env` file is properly configured. A template `.env.example` has been provided for reference:
```bash
cp .env.example .env
```
Inside `.env`, populate your Google/Gemini API keys, and update `<YOUR_POSTGRES_PASSWORD>` in the `DATABASE_URL`.

### 2. Install Dependencies
Initialize your virtual environment and install dependencies:
```bash
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
```
*(If you don't have a requirements.txt yet, install the foundational MCP, google-adk, Streamlit, and asyncpg packages.)*

### 3. Initialize the Database
Ensure your PostgreSQL daemon is running. We have provided two initialization scripts:
1. **Create Database**: Run this once to construct the `health_db` (you may need to modify the password placeholder in the script before doing so):
   ```bash
   python create_db.py
   ```
2. **Seed Tabular Schema**: Once `health_db` is created, populate it with ADK tracking tables (`sessions`, `events`):
   ```bash
   python init_db.py
   ```

### 4. Run the Streamlit Interface
We built the asynchronous interactions directly onto Streamlit efficiently utilizing a caching layer to avoid any `asyncio` Event Loop disconnects. 
Run the web application to talk to the Gemeni agent smoothly:
```bash
python -m streamlit run ui.py
```
This will open `http://localhost:8501` automatically.

## Checking DB State (Debugging)
To view raw JSON payloads spanning your conversations cached by Google ADK:
```bash
python check_db.py
```
