import os
import json
from pathlib import Path

# Base Directory
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

# File Paths
CANDIDATE_LIST_PATH = DATA_DIR / "candidate_list.csv"
LOGIN_CONFIG_PATH = BASE_DIR / "login.json"

# Load Credentials
def load_config():
    if not LOGIN_CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuration file not found: {LOGIN_CONFIG_PATH}")
    
    with open(LOGIN_CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

CONFIG = {}
try:
    CONFIG = load_config()
except Exception as e:
    print(f"Warning: Could not load config: {e}")

# Parameters
GAP_THRESHOLD = 0.01  # 1%
P_LOC_THRESHOLD = 0.5
MIN_VOLUME_SHEETS = 500
MIN_AMOUNT_TWD = 10_000_000  # 10 Million

# Pre-process Parameters
BIAS_WINDOW = 60
BIAS_PERCENTILE = 0.60  # Bottom 60%
