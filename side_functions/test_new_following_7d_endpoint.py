import requests
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from collections import defaultdict

API_KEY = os.getenv("TweetScout_API_key")
TG_bot_token = os.getenv("TG_bot_token")

def get_followers_data(link):
    url = "https://api.tweetscout.io/v2/new-following-7d"
    
    querystring = {"link": link}
    
    headers = {
        "Accept": "application/json",
        "ApiKey": API_KEY
    }
    
    response = requests.get(url, headers=headers, params=querystring)
    data = response.json()
    print(data)
    # Extract id and name from each user in the response
    users_data = []
    for user in data:
        # Only add if both id and name are not empty
        if user.get('id') and user.get('name'):
            users_data.append({
                'id': user['id'],
                'name': user['name'],
                'register_date': user['registerDate']
            })
    
    # Create DataFrame
    df = pd.DataFrame(users_data)
    return df

print(get_followers_data('https://x.com/DarkoB1995'))