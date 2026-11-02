
from dotenv import load_dotenv
import os
import requests

load_dotenv(dotenv_path=r'c:\Trabajos\scrapingcines\.env')
TMDB_API_KEY = os.getenv("TMDB_API_KEY")

def search_movie(query, year=None):
    if not TMDB_API_KEY:
        print("Error: TMDB_API_KEY not found.")
        return

    url = "https://api.themoviedb.org/3/search/movie"
    headers = {
        "Authorization": f"Bearer {TMDB_API_KEY}",
        "Content-Type": "application/json;charset=utf-8"
    }
    params = {
        "query": query,
        "language": "es"
    }
    if year:
        params["year"] = year
        
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        results = response.json().get("results", [])
        print(f"\n--- Results for '{query}' (Year: {year}) ---")
        for movie in results[:5]:
            print(f"ID: {movie['id']}, Title: {movie['title']}, Original: {movie['original_title']}, Year: {movie.get('release_date', '')[:4]}, Director: {get_director(movie['id'])}")
    else:
        print(f"Error: {response.status_code} - {response.text}")

def get_director(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}/credits"
    headers = {
        "Authorization": f"Bearer {TMDB_API_KEY}",
        "Content-Type": "application/json;charset=utf-8"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        crew = response.json().get("crew", [])
        directors = [m['name'] for m in crew if m['job'] == 'Director']
        return ", ".join(directors)
    return "Unknown"

if __name__ == "__main__":
    search_movie("Alpha")
    search_movie("Drácula")
