import pandas as pd
import requests
from typing import Dict, Optional

def get_user_info(user_id: str) -> Optional[Dict]:
    """
    Fetch user information from TweetScout API using user ID
    """
    url = "https://api.tweetscout.io/v2/follows"
    headers = {
        "Accept": "application/json",
        "ApiKey": "16a5a7f9-f612-4e3d-8310-d6c836efe920"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Find the user with matching ID
        for user in data:
            if user['id'] == user_id:
                return user
    except Exception as e:
        print(f"Error fetching data for user {user_id}: {str(e)}")
    
    return None

def add_links_to_csv(input_file: str, output_file: str) -> None:
    """
    Add Twitter profile links to the CSV file
    """
    # Read the CSV file
    df = pd.read_csv(input_file)
    
    # Add new 'link' column
    df['link'] = df['id'].apply(lambda x: f"https://x.com/i/user/{x}")
    
    # Save the updated CSV
    df.to_csv(output_file, index=False)
    print(f"Updated CSV saved to {output_file}")

if __name__ == "__main__":
    input_file = "new_tracking_2025-05-19.csv"
    output_file = "new_tracking_2025-05-19_with_links.csv"
    add_links_to_csv(input_file, output_file) 