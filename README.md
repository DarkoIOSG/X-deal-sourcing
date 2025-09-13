# X-deal-sourcing

A Python application that analyzes Twitter/X user relationships to identify common follows and potential deal sources using the TweetScout API.

## Overview

This application helps identify accounts that are commonly followed by a curated list of users, which can be useful for deal sourcing and network analysis. It tracks accounts that are followed by at least 20% of the monitored users and provides notifications through Telegram. At the end there is Notion Dahsboard that shows list of all common follows accounts ordered by number of accounts from our watchlist follow them.

## Features

- Fetches follower data for a list of Twitter/X accounts
- Identifies accounts followed by at least 20% of monitored users
- Tracks new accounts that meet the threshold
- Sends notifications via Telegram for new discoveries
- Maintains historical data in CSV files
- Compares results with previous runs to identify new common follows

## Prerequisites

- Python 3.x
- TweetScout API key
- Telegram Bot Token

## Environment Variables

Create a `.env` file in the project root with the following variables:

```
TweetScout_API_key=your_api_key_here
TG_bot_token=your_telegram_bot_token_here
```

## Installation

1. Clone the repository:
```bash
git clone https://github.com/DarkoIOSG/X-deal-sourcing.git
cd X-deal-sourcing
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

## Usage

Run the script:
```bash
python TweetScout_API.py
```

The script will:
1. Fetch follower data for all configured accounts
2. Identify common follows (accounts followed by ≥20% of users)
3. Compare with previous results
4. Send notifications via Telegram for new discoveries
5. Save results to CSV files:
   - `common_follows.csv`: All tracked accounts
   - `new_tracking_{date}.csv`: New accounts to track

## Output Files

- `common_follows.csv`: Contains all tracked accounts with their details
- `new_tracking_{date}.csv`: Contains new accounts that meet the tracking threshold

## Telegram Notifications

The script sends notifications to a configured Telegram channel for:
- New common follows discovered
- New accounts that meet the tracking threshold
- First run notifications

## Contributing

Feel free to submit issues and enhancement requests.
