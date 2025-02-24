# Sports Performance Projection Algorithm

## Overview
This repository contains the function **`synthesize_projection`**, which generates a dynamic performance projection for a player using:

- **Sportsbook betting lines** (weighted by volume and probability)
- **Season-long historical statistics** (processed with EWMA)
- **Head-to-head (H2H) matchup data** (recent matchups weighted higher)

The function intelligently **blends these sources** based on available data, ensuring that:
- **Recent matchups are emphasized** via an **Exponentially Weighted Moving Average (EWMA)**
- **Betting market confidence is incorporated** using implied probability weighting
- **The projection dynamically adapts** to sample sizes for each data source

## Features
- **Market-informed projections** using sportsbook data  
- **Prioritizes recent performance** using EWMA for season and H2H stats  
- **Handles missing data cases gracefully**  
- **Prevents extreme values from dominating projections**  

## Installation
Clone this repository to your local machine:
```sh
git clone https://github.com/your-username/sports-projection.git
cd sports-projection
```
## Smaller part of a stat projection tool used by a startup
