# System Monitoring Agent

A conversational system-monitoring agent powered by Google ADK, MCP, and Gemini. It features a continuous Streamlit-based web UI to seamlessly trace and query your computer's health (CPU, RAM, Disk formatting to Markdown) while securely keeping track of the chat context using a locally hosted PostgreSQL database.

## Prerequisites
- Python 3.9+
- PostgreSQL server instance running locally

## Quick Start Setup

### 1. Environment Variables
You must securely configure your keys before running. We have provided an example template:
```bash
cp .env.example .env
```
Open `.env`, fill in your Google and Gemini API keys, and replace `<YOUR_POSTGRES_PASSWORD>` with your local PostgreSQL password.

### 2. Installations
Initialize your virtual environment and install the required dependencies (now explicitly tracked in `requirements.txt`):
```bash
python -m venv venv
venv\Scripts\activate      # For Windows
# source venv/bin/activate # For Mac/Linux

pip install -r requirements.txt
```

### 3. PostgreSQL Database Initialization
Before the agent can store memories, it needs a database and tables.
1. **Create the Base Database**:
   *(Make sure to temporarily add your postgres password inside the placeholder inside `create_db.py` before running this!).*
   ```bash
   python create_db.py
   ```
2. **Initialize Tables (Events / Sessions)**:
   ```bash
   python init_db.py
   ```

## Testing & Verifying the Application

### 1. The Streamlit Web UI
To talk to the Google ADK + MCP monitoring agent, spin up the server:
```bash
python -m streamlit run ui.py
```
This triggers your browser at `http://localhost:8501`. 
**Verification**: Try typing prompts like `"what are top 10 processes"` followed by `"ram usage?"`. The database and logic loop are perfectly linked, giving accurate formatted responses without crashing.

### 2. The Context / State Tracker
We built an exclusive python script `check_db.py` to directly audit PostgreSQL without needing SQL GUIs. It cleanly dumps your Session variables and Chat Context stored by the ADK. 

Run it in your terminal while the Streamlit server is either running or offline:
```bash
python check_db.py
```
**Verification**: It prints your active Streamlit sessions sequentially and shows the raw conversational context the Agent remembers.
