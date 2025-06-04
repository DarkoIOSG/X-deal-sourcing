import pandas as pd
import ast

def process_users_tweets_analysis(file_path: str, output_path: str):
    # Load CSV
    df = pd.read_csv(file_path)

    # Prepare empty columns
    descriptions = []
    entities_list = []

    for index, row in df.iterrows():
        raw_value = row.get("users_tweets_analysis", "")
        try:
            # Safely evaluate the dictionary string
            parsed = ast.literal_eval(raw_value)

            # Get description text
            description = parsed.get("description", "").strip()
            descriptions.append(description)

            # Extract just the names from mentioned_entities
            mentioned_entities = parsed.get("mentioned_entities", [])
            entity_names = [entity.get("name", "") for entity in mentioned_entities]
            entities_list.append(entity_names)
        except (ValueError, SyntaxError):
            # Handle malformed data
            descriptions.append("")
            entities_list.append([])

    # Assign new columns
    df["account_description_based_on_last_20_tweets"] = descriptions
    df["mentioned_entities"] = entities_list

    # Drop old column
    df.drop(columns=["users_tweets_analysis"], inplace=True)

    # Remove surrounding double quotes if they exist
    df["account_description_based_on_last_20_tweets"] = df["account_description_based_on_last_20_tweets"].apply(
        lambda x: x.strip('"') if isinstance(x, str) else x
    )
    df["mentioned_entities"] = df["mentioned_entities"].apply(
        lambda x: str(x).strip('"') if isinstance(x, str) else x
    )

    # Save to new CSV
    df.to_csv(output_path, index=False)

process_users_tweets_analysis(
    file_path="merged_tracking_following_2025-06-03_with_analysis.csv",
    output_path="cleaned_tracking_following.csv"
)