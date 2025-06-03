import requests
import os
import pandas as pd
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from openai import OpenAI

API_KEY = os.getenv("TweetScout_API_key")
OPENAI_API_KEY = os.getenv("OPENAI_API_key")

def get_user_tweets(user_id: str, max_tweets: int = 20) -> list:
    """
    Fetch tweets from a specified X user account.
    
    Args:
        user_id (str): The X user ID to fetch tweets from
        max_tweets (int): Maximum number of tweets to fetch (default: 20)
    
    Returns:
        list: List of tweet texts
    """
    url = "https://api.tweetscout.io/v2/user-tweets"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "ApiKey": API_KEY
    }
    
    all_tweets = []
    cursor = None
    
    while len(all_tweets) < max_tweets:
        payload = {
            "user_id": user_id
        }
        
        if cursor:
            payload["cursor"] = cursor
            
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            tweets = data.get("tweets", [])
            if not tweets:
                break
                
            # Extract only the full_text from each tweet
            tweet_texts = [tweet.get("full_text", "") for tweet in tweets]
            all_tweets.extend(tweet_texts)
            
            cursor = data.get("next_cursor")
            if not cursor:
                break
                
        except requests.exceptions.RequestException as e:
            print(f"Error fetching tweets: {e}")
            break
    
    return all_tweets[:max_tweets]

def get_last_tweet_date(user_id: str) -> str:
    """
    Get the date of the most recent tweet from a specified X user account.
    
    Args:
        user_id (str): The X user ID to fetch the last tweet date from
    
    Returns:
        str: The date in format 'YYYY-MM-DD' of the most recent tweet, or None if no tweets found
    """
    url = "https://api.tweetscout.io/v2/user-tweets"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "ApiKey": API_KEY
    }
    
    payload = {
        "user_id": user_id
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        tweets = data.get("tweets", [])
        if tweets:
            # Parse the date string and format it as YYYY-MM-DD
            date_str = tweets[0].get("created_at")
            if date_str:
                date_obj = datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
                return date_obj.strftime("%Y-%m-%d")
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching last tweet date: {e}")
        return None

def summarize_account_tweets(user_id: str) -> tuple[str, list]:
    """
    Analyze user's tweets to provide a description of their interests and extract mentioned entities.
    
    Args:
        user_id (str): The X user ID to analyze tweets from
    
    Returns:
        tuple: A tuple containing:
            - str: Description of user's interests based on their tweets
            - list: List of dictionaries containing mentioned entities with their types
    """
    # Get the tweets
    tweets = get_user_tweets(user_id)
    if not tweets:
        return "No tweets found to analyze.", []
    
    # Combine tweets into a single text
    tweets_text = "\n".join(tweets)
    
    # Initialize OpenAI client
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    try:
        # Create the prompt for the LLM
        prompt = f"""Analyze these tweets and provide:
1. A brief description of the user's main interests and focus areas
2. A list of specific entities mentioned (projects, tokens, VCs, companies, people)

Format the response as:
DESCRIPTION:
[Your analysis of user's interests]

ENTITIES:
- Entity1 (type)
- Entity2 (type)
- Entity3 (type)

Tweets to analyze:
{tweets_text}"""
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert at analyzing social media content and extracting meaningful insights about user interests and mentioned entities."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7
        )
        
        # Parse the response
        content = response.choices[0].message.content.strip()
        
        # Split the response into description and entities
        parts = content.split("ENTITIES:")
        description = parts[0].replace("DESCRIPTION:", "").strip()
        
        # Extract entities into a list of dictionaries
        mentioned_entities = []
        if len(parts) > 1:
            entities_text = parts[1].strip()
            for line in entities_text.split("\n"):
                if line.strip().startswith("-"):
                    entity_parts = line.strip("- ").split("(")
                    if len(entity_parts) == 2:
                        name = entity_parts[0].strip()
                        entity_type = entity_parts[1].strip(")")
                        mentioned_entities.append({
                            "name": name,
                            "type": entity_type
                        })
        
        return description, mentioned_entities
        
    except Exception as e:
        return f"Error generating summary: {str(e)}", []

# Example usage
if __name__ == "__main__":
    user_id = "1395628622417825795"
    print("Last 20 tweets:")
    print(get_user_tweets(user_id))
    print("\nLast tweet date:")
    print(get_last_tweet_date(user_id))
    print("\nAccount analysis:")
    description, entities = summarize_account_tweets(user_id)
    print("\nDescription:")
    print(description)
    print("\nMentioned Entities:")
    for entity in entities:
        print(f"- {entity['name']} ({entity['type']})")