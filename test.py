import os
from dotenv import load_dotenv

load_dotenv()

print("GROQ KEY:", os.getenv("GROQ_API_KEY", "NOT FOUND"))