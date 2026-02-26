# MinutesLM

Local LLM Meeting Minutes Taker - record audio, transcribe with Whisper v3 Turbo, format with Ollama, store in PostgreSQL.

## Requirements

- Python 3.10+
- PostgreSQL
- [Ollama](https://ollama.ai) with a 7-8B model (e.g. `ollama pull llama3.1:8b`)
- Mac with Apple Silicon (M1/M2/M3) for Whisper v3 Turbo

## Quick Start

### 1. PostgreSQL

```bash
# macOS with Homebrew
brew install postgresql@16
brew services start postgresql@16
createdb minuteslm
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Copy env and edit if needed
cp ../.env.example .env

# Run
uvicorn app.main:app --reload --port 8000
```

### 3. Ollama

```bash
ollama pull llama3.1:8b
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## API

- `GET /meetings` - List meetings
- `POST /meetings` - Create meeting
- `GET /meetings/{id}` - Get meeting
- `POST /meetings/{id}/upload` - Upload audio (multipart)
- `GET /meetings/{id}/transcript` - Get transcript
- `GET /meetings/{id}/minutes` - Get formatted minutes
