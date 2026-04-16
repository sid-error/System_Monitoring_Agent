# System Monitoring Agent

A deterministic AI agent powered by Google ADK + FastMCP to monitor your system health with interactive charts and tables natively. 

## Features
- **Interactive Interfaces**: Choose between a generative UI dashboard powered by **Prefab UI** or a clean, metric-focused **Streamlit Dashboard**.
- **Instant Diagnostics**: Ask natural questions or click quick-action buttons to query CPU, RAM, Disk, and Running Processes.
- **Process Lookup**: Zero-in on specific processes using PID or Name-based fuzzy search.
- **Backend-Driven**: All system telemetry visualization logic securely resides strictly in MCP tools.
- **Persistence**: Chat history is stored seamlessly in a PostgreSQL database layout.

## Prerequisites
- **Python 3.10+**
- **PostgreSQL**: Running locally or accessible via URI.
- **Google Gemini API Key**: Set in `.env`.

## Setup
1. **Clone the repo** and navigate to the directory.
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure environment**:
   Make sure you have a `.env` file configured:
   ```text
   GEMINI_API_KEY=your_key_here
   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/health_db
   ```
4. **Initialize Database** (If using Prefab/PostgreSQL persistence):
   ```bash
   python create_db.py
   python init_db.py
   ```

## Usage

### Option 1: Streamlit Dashboard (Recommended)
This is a sleek, multi-column dashboard with integrated process filtering and quick-diagnostics rendering.

```bash
streamlit run streamlit_app.py
```
*Note: This will automatically launch an interface in your default web browser.*

### Option 2: Prefab UI 
Launch the agent as an interactive AI chat interface using `prefab`.

**PowerShell (Windows):**
```powershell
$env:PYTHONIOENCODING="utf-8" ; prefab serve prefab_app.py
```

**Command Prompt (cmd):**
```cmd
set PYTHONIOENCODING=utf-8 && prefab serve prefab_app.py
```

Once running, open `http://127.0.0.1:5175` in your browser.

## Project Structure
- `streamlit_app.py`: The robust Streamlit dashboard front-end.
- `prefab_app.py`: The Generative AI front-end (FastMCP + Prefab UI).
- `health_agent.py`: The deterministic ADK agent router and session controller.
- `health_server.py`: The MCP standard server extracting active system telemetry.
- `check_db.py`: Utility to audit stored chat context in PostgreSQL.
