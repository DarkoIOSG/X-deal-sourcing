import os
from dotenv import load_dotenv

load_dotenv()

SORSA_API_KEY = os.getenv("TweetScout_API_key")
OPENAI_API_KEY = os.getenv("OPENAI_API_key")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

SORSA_BASE_URL = "https://api.sorsa.io/v3"
WATCHLIST_FILE = "followed_accounts.txt"
DB_PATH = "state.db"
MIN_WATCHERS = 1  # minimum watchlist members that must follow an account to surface it
