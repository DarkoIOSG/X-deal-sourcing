import pandas as pd
import glob
from datetime import datetime
import os
import requests
import time
from urllib.parse import urlparse

def get_user_id_from_link(link):
    """Extract user ID from Twitter link"""
    # Remove any @ symbol if present
    link = link.strip('@')
    # Extract the ID from the URL
    return link.split('/')[-1]

def check_user_follows(project_id, user_handle=None, user_id=None, project_handle=None, api_key=None):
    """
    Check if a user follows a specific Twitter handle (project).
    
    Args:
        project_handle (str): The handle of the project account (e.g., "tweetscout_io").
        user_handle (str, optional): The handle of the user to check (e.g., "elonmusk").
        user_id (str, optional): The Twitter user ID (e.g., "44196397").
        project_id (str, optional): The project ID (e.g., "940691529697554432").
        api_key (str): Your API key for authentication.

    Returns:
        dict: Dictionary with keys 'follow' (bool) and 'user_protected' (bool), or an error message.
    """
    url = "https://api.tweetscout.io/v2/check-follow"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "ApiKey": api_key
    }

    payload = {
        "project_id": project_id
    }

    if user_handle:
        payload["user_handle"] = user_handle
    if user_id:
        payload["user_id"] = user_id
    if project_id:
        payload["project_id"] = project_id

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def load_followed_accounts():
    """Load and process followed accounts from file"""
    with open('followed_accounts.txt', 'r') as f:
        accounts = [line.strip() for line in f if line.strip()]
    return [get_handle_from_url(url) for url in accounts]

def get_handle_from_url(url):
    """Extract handle from Twitter URL"""
    path = urlparse(url).path
    return path.strip('/')

def merge_tracking_files():
    # Load followed accounts
    followed_accounts = load_followed_accounts()
    
    # Find all tracking CSV files
    tracking_files = glob.glob('new_tracking_*.csv')
    
    # Initialize empty list to store all dataframes
    dfs = []
    
    # Read each file and append to list
    for file in tracking_files:
        try:
            df = pd.read_csv(file)
            dfs.append(df)
        except Exception as e:
            print(f"Error reading {file}: {e}")
    
    if not dfs:
        print("No tracking files found!")
        return
    
    # Concatenate all dataframes
    merged_df = pd.concat(dfs, ignore_index=True)
    
    # Convert register_date to datetime
    merged_df['register_date'] = pd.to_datetime(merged_df['register_date'])
    
    # Group by id and get the latest record for each account
    latest_records = merged_df.sort_values('register_date').groupby('id').last()
    print("latest_records", latest_records)
    
    # Process each account to get current followers and following
    processed_records = []
    
    for idx, row in latest_records.iterrows():
        print(f"Processing account: {row['name']}")
        
        # Check which accounts from followed_accounts.txt are following this user
        followers = []
        for followed_handle in followed_accounts:
            result = check_user_follows(
                project_id=str(idx),  # Use the id from the index
                user_handle=followed_handle,
                api_key=os.getenv("TweetScout_API_key")
            )
            if result.get('follow', False):
                followers.append(followed_handle)
            time.sleep(1)  # Rate limiting
        
        processed_records.append({
            'name': row['name'],
            'followers_count': len(followers),  # Number of accounts from our list that follow this user
            'followed_by': ', '.join(followers),  # List of accounts from our list that follow this user
            'register_date': row['register_date'],
            'link': row['link']
        })
    
    # Create new dataframe with processed records
    result_df = pd.DataFrame(processed_records)
    
    # Sort by followers_count in descending order
    result_df = result_df.sort_values('followers_count', ascending=False)
    
    # Generate output filename with current date
    current_date = datetime.now().strftime('%Y-%m-%d')
    output_file = f'merged_tracking_{current_date}.csv'
    
    # Save to CSV
    result_df.to_csv(output_file, index=False)
    print(f"Successfully created {output_file}")

if __name__ == "__main__":
    merge_tracking_files()
