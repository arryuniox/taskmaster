#  TaskMaster
Low-effort, AI-powered task manager that helps you keep track of and recommend different usage of your tasks. Complete with Google Calendar integration. Currently only a locally-hosted web-app.

## Overview
This project uses a combination of GROQ API for faster and smarter results when internet is available and self-hosted Ollama model qwen2.5:3b (approximately 2 GB of disk space required) when the internet is not available.

qwen2.5:3b was chosen as it can run reasonably fast and understand nuance when provided with 16 GB of RAM and a i5 Intel core. This makes it optimal for basic tasks such as sorting tasks by priority, etc. With an external GPU, it is possible to run stronger locally hosted models such as Mistral to enhance the application's ability to understand nuance.

**Key Features:**
- LLM-powered task prioritization
- Type/use voice-to-text (work in progress) to describe upcoming deadlines/new assigned work from a day
- Locally-hosted and can work in both the presence and absence of connection to the internet, prefect on public transit
- Only uses free APIs (GROQ API) or locally hosted LLM services (Ollama)

## Project Structure

```
.
├── frontend/         # Landing page
├── venv/             # should be set up if commands were run properly
├── __pycache__/      # Stored information
├── .env              # Enter your own GROQ API key
├── app.py            # RUN THIS THING
├── db.py             # Keeps track of all of your tasks
├── gcal.py           # Google Calendar Integration
├── llm_client.py     # GROQ API calls
├── ollama_client.py  # Locally hosted Ollama calls
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

## Installation

### Pre-requisites
- Python 3.8 or higher
- Ollama
    - qwen2.5:3b or better model
- GROQ API Key (optional)
- Google Calendar API credentials
- ThinkPad X1 or equivalent/better

### Set-up

```bash
# Clone or download the project files
cd taskmaster

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

And yeah that should be it. Easy peasy. There shouldn't be many more other difficult stuffs to do.

## Addendum: How to get API keys

### GROQ
1. Sign up for [GROQ](groq.com)
2. Pick a model (preferably something simpler so it doesn't overthink your text)
3. Create API key
4. Put in .env

### Google Calendar
1. Log into [Google Cloud](https://console.cloud.google.com/)
2. Create project
3. Create Google Calendar API for Desktop App
4. Download credentials as credentials.json and add it into the project directory

## Addendum: Ollama

### Installation
1. Go to [Ollama](https://ollama.com/download) and download the appropriate installer for your operating system
2. Follow the instructions given by the installer
3. In command prompt or an equivalent, run the command
```bash
ollama pull [model name]
```
(in this case either Mistral or qwen2.5:3b depending on your specs)

4. Before using the program, make sure that Ollama is running by running the command

```bash
ollama serve
```
