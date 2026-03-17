import os
import sys
import requests
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup

# --- Configuration ---
CSV_FILE = 'spotify_india_history.csv' 
def get_anonymous_token():
    """
    Hacks the system by requesting a temporary anonymous token 
    used by the Spotify Web Player. No developer account needed.
    """
    print("Fetching anonymous Web Player token...")
    url = "https://open.spotify.com/get_access_token?reason=transport&productType=web_player"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        token_data = response.json()
        return token_data['accessToken']
    except Exception as e:
        print(f"Error extracting anonymous token: {e}")
        sys.exit(1)

def scrape_top_50_ids():
    """Scrapes Kworb for the current Track IDs."""
    url = "https://kworb.net/spotify/country/in_daily.html"
    print(f"Scraping Top 50 IDs from {url}...")
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        track_ids = []
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link['href']
            if '/track/' in href:
                parts = href.split('/track/')
                if len(parts) > 1:
                    clean_id = parts[1].replace('.html', '').strip()
                    if clean_id not in track_ids:
                        track_ids.append(clean_id)
            if len(track_ids) >= 50:
                break
                
        if not track_ids:
            raise Exception("Kworb scraping failed. No track IDs found.")
            
        print(f"Successfully scraped {len(track_ids)} track IDs.")
        return track_ids
        
    except Exception as e:
        print(f"Error scraping Kworb: {e}")
        sys.exit(1)

def get_tracks_metadata(token, track_ids):
    """Fetches metadata using the anonymous token."""
    ids_string = ",".join(track_ids[:50])
    url = f"https://api.spotify.com/v1/tracks?ids={ids_string}"
    
    headers = {
        'Authorization': f'Bearer {token}',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()['tracks']
    except Exception as e:
        print(f"Error fetching track details: {e}")
        sys.exit(1)

def process_data():
    # 1. Scrape IDs
    track_ids = scrape_top_50_ids()

    # 2. Get Anonymous Token (Bypass Developer Auth)
    token = get_anonymous_token()
    
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

    # Clean the Date format
    new_df['Release_Date'] = pd.to_datetime(new_df['Release_Date'], format='mixed', errors='coerce')
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
