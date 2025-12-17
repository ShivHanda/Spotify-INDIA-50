import os
import sys
import requests
import pandas as pd
from datetime import datetime
import base64
from bs4 import BeautifulSoup

# --- Configuration ---
CLIENT_ID = os.environ.get('SPOTIPY_CLIENT_ID')
CLIENT_SECRET = os.environ.get('SPOTIPY_CLIENT_SECRET')
CSV_FILE = 'spotify_india_history.csv'

def get_access_token():
    """Spotify Auth (Client Credentials)."""
    auth_url = 'https://accounts.spotify.com/api/token'
    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()
    
    headers = {
        'Authorization': f'Basic {b64_auth_str}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {'grant_type': 'client_credentials'}
    
    try:
        response = requests.post(auth_url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()['access_token']
    except Exception as e:
        print(f"Error extracting token: {e}")
        sys.exit(1)

def scrape_top_50_ids():
    """
    Fail-Safe Scraper: Looks for ANY link containing '/track/' 
    instead of relying on a specific table structure.
    """
    url = "https://kworb.net/spotify/country/in_daily.html"
    print(f"Scraping Top 50 IDs from {url}...")
    
    try:
        # User-Agent header is often required to avoid 403 blocks
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        track_ids = []
        
        # Robust Strategy: Find ALL links that look like a Spotify track
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link['href']
            # Kworb links usually look like: ../track/12345ID.html
            if '/track/' in href:
                # Extract the ID part
                # Example: ../track/4Dvkj6JhhA12EX05fT7y2e.html -> 4Dvkj6JhhA12EX05fT7y2e
                parts = href.split('/track/')
                if len(parts) > 1:
                    clean_id = parts[1].replace('.html', '').strip()
                    if clean_id not in track_ids: # Avoid duplicates
                        track_ids.append(clean_id)
            
            if len(track_ids) >= 50:
                break
        
        if not track_ids:
            # Fallback debug
            print("Debug: No links found with '/track/'. Page content preview:")
            print(soup.prettify()[:500])
            raise Exception("Kworb scraping failed. No track IDs found.")
            
        print(f"Successfully scraped {len(track_ids)} track IDs.")
        return track_ids
        
    except Exception as e:
        print(f"Error scraping Kworb: {e}")
        sys.exit(1)

def get_tracks_metadata(token, track_ids):
    """Fetch metadata from Spotify API."""
    # Spotify allows max 50 IDs per request
    ids_string = ",".join(track_ids[:50])
    url = f"https://api.spotify.com/v1/tracks?ids={ids_string}" # Use official endpoint
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()['tracks']
    except Exception as e:
        print(f"Error fetching track details: {e}")
        sys.exit(1)

def process_data():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("Error: Secrets missing. Github Settings check karein.")
        sys.exit(1)

    # 1. Scrape IDs
    track_ids = scrape_top_50_ids()

    # 2. Login
    print("Authenticating with Spotify...")
    token = get_access_token()
    
    # 3. Get Details
    print("Fetching metadata for tracks...")
    tracks_data = get_tracks_metadata(token, track_ids)
    
    today_date = datetime.now().strftime('%Y-%m-%d')
    extracted_data = []

    for idx, track in enumerate(tracks_data):
        if not track:
            continue
            
        artists = ", ".join([artist['name'] for artist in track.get('artists', [])])
        album_images = track.get('album', {}).get('images', [])
        cover_url = album_images[0]['url'] if album_images else None

        row = {
            'Date': today_date,
            'Position': idx + 1,
            'Song': track.get('name'),
            'Artist': artists,
            'Popularity': track.get('popularity'),
            'Duration_MS': track.get('duration_ms'),
            'Album_Type': track.get('album', {}).get('album_type'),
            'Total_Tracks': track.get('album', {}).get('total_tracks'),
            'Release_Date': track.get('album', {}).get('release_date'),
            'Is_Explicit': track.get('explicit'),
            'Album_Cover_URL': cover_url
        }
        extracted_data.append(row)

    new_df = pd.DataFrame(extracted_data)
    new_df['Release_Date'] = pd.to_datetime(new_df['Release_Date'], format='mixed')
    new_df['Release_Date'] = new_df['Release_Date'].dt.strftime('%Y-%m-%d')

    # 4. Save Logic
    if os.path.exists(CSV_FILE):
        try:
            existing_df = pd.read_csv(CSV_FILE)
            if today_date in existing_df['Date'].values:
                print(f"Aaj ({today_date}) ka data pehle se hai.")
                sys.exit(0)
            
            updated_df = pd.concat([existing_df, new_df], ignore_index=True)
            updated_df.to_csv(CSV_FILE, index=False)
            print(f"Data appended for {today_date}.")
        except pd.errors.EmptyDataError:
            new_df.to_csv(CSV_FILE, index=False)
            print("File khali thi, naya data dala.")
    else:
        new_df.to_csv(CSV_FILE, index=False)
        print(f"Nayi file banayi: {CSV_FILE}")

if __name__ == "__main__":
    process_data()
