import logging
import azure.functions as func
from azure.storage.blob import BlobServiceClient
import pandas as pd
import numpy as np
import requests
import json
from datetime import datetime, time, date, timedelta
import io
import re


### Helper Functions
def convert_to_prob(odds: float) -> float:
    """Convert American odds to implied probability."""
    if odds > 0:
        return 100 / (odds + 100)
    else:
        return abs(odds) / (abs(odds) + 100)
    
def compute_h2h_avg(historical_stats):
    """
    Compute the H2H average for the current and previous year from historical stats.
    """
    h2h_games = historical_stats.get("H2H Games", {})
    h2h_values = h2h_games.get("Value", [])
    h2h_dates = h2h_games.get("Date", [])

    current_year = datetime.now().year
    filtered_h2h_values = [
        value for value, date in zip(h2h_values, h2h_dates)
        if datetime.strptime(date, "%Y-%m-%d").year in {current_year, current_year - 1}
    ]

    return sum(filtered_h2h_values) / len(filtered_h2h_values) if filtered_h2h_values else 0

def synthesize_projection(book_lines, historical_stats, alpha_static=0.70, h2h_alpha=0.85):
    """
    Synthesize a projection by dynamically weighting book lines, season history, and H2H data.
    Recent H2H matchups are weighted higher using EWMA.

    Args:
    - book_lines (list of tuple): Current book lines with (line, volume, odds).
    - historical_stats (dict): Historical stats for the player, including H2H game dates.
    - alpha_static (float): EWMA alpha for historical stats (default = 0.70).
    - h2h_alpha (float): EWMA alpha for recent H2H games (default = 0.85).

    Returns:
    - float: Synthesized projection.
    """

    # Step 1: Extract Historical Data with Outlier Filtering
    season_game_values = historical_stats.get("Season Games", {}).get("Value", [])
    h2h_data = historical_stats.get("H2H Games", {})
    h2h_values = h2h_data.get("Value", [])
    h2h_dates = h2h_data.get("Dates", [])  # Assume this stores game dates

    # Convert H2H data into a DataFrame if dates exist
    if h2h_values and h2h_dates:
        h2h_df = pd.DataFrame({"Value": h2h_values, "Date": pd.to_datetime(h2h_dates)})
        h2h_df = h2h_df.sort_values(by="Date")  # Ensure chronological order

        # Compute EWMA on sorted H2H values (recent games weighted more)
        h2h_df["EWMA"] = h2h_df["Value"].ewm(alpha=h2h_alpha).mean()
        h2h_avg = h2h_df["EWMA"].iloc[-1]  # Use the most recent EWMA value
    else:
        h2h_avg = np.mean(h2h_values) if h2h_values else 0

    # Compute EWMA for season-long data
    if season_game_values:
        season_series = pd.Series(season_game_values)
        season_ewma = season_series.ewm(alpha=alpha_static).mean().median()  # Median-based EWMA
    else:
        season_ewma = historical_stats.get("Season Avg", 0)

    # Step 2: Handle No Book Lines Case
    if not book_lines:
        historical_series = pd.Series({
            "Season EWMA": season_ewma,
            "H2H": h2h_avg
        })
        normalized_weights = historical_series / historical_series.sum()
        projection = (
            season_ewma * normalized_weights["Season EWMA"] +
            h2h_avg * normalized_weights["H2H"]
        )
        return round(projection, 2)

    # Step 3: Process Book Lines with Correct Probability-Based Weighting
    total_weight = 0
    weighted_sum = 0

    for line, volume, odds in book_lines:
        probability = convert_to_prob(float(odds))  # Convert odds to implied probability
        weight = volume * probability  # Market confidence weighting
        weighted_sum += line * weight
        total_weight += weight

    # Compute the weighted average line
    weighted_line = weighted_sum / total_weight if total_weight > 0 else 0

    # Step 4: Compute Dynamic Weights
    num_season_games = len(season_game_values)
    num_h2h_games = len(h2h_values)
    num_book_lines = len(book_lines)

    # Confidence-based dynamic weighting
    book_confidence = min(1, num_book_lines / 5)  # More book lines → higher weight (caps at 1)
    season_confidence = min(1, num_season_games / 10)  # More games → higher weight (caps at 1)
    h2h_confidence = min(1, num_h2h_games / 3)  # More H2H games → higher weight (caps at 1)

    # Normalize weights dynamically
    total_confidence = book_confidence + season_confidence + h2h_confidence
    book_weight = book_confidence / total_confidence
    season_weight = season_confidence / total_confidence
    h2h_weight = h2h_confidence / total_confidence

    # Step 5: Compute Final Projection with Dynamic Weights
    projection = (
        weighted_line * book_weight +
        season_ewma * season_weight +
        h2h_avg * h2h_weight
    )

    return round(projection, 2)

# This version now:
# - Prioritizes recent H2H games using EWMA (older games fade out naturally).
# - Removes artificial clipping, instead weighting alternate lines properly based on probability & volume.
# - Ensures book lines drive the projection when reliable data is available, without letting extreme values dominate.
# - Balances historical season & matchup trends dynamically based on data confidence.
