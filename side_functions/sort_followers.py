import pandas as pd

# Read the CSV file
df = pd.read_csv('new_tracking.csv')

# Sort by followers_count in descending order
df_sorted = df.sort_values('followers_count', ascending=False)

# Save the sorted data to a new CSV file
df_sorted.to_csv('new_tracking_sorted.csv', index=False)

print("Sorted data has been saved to 'new_tracking_sorted.csv'") 