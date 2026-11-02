
from dotenv import load_dotenv
import os
import sys

try:
    load_dotenv(dotenv_path=r'c:\Trabajos\scrapingcines\.env')
    key = os.getenv("TMDB_API_KEY")
    if key:
        print(f"Key found: {key[:10]}...{key[-10:]}")
    else:
        print("Key NOT found")
except Exception as e:
    print(f"Error: {e}")
