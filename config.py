import json
import os
from pathlib import Path


MAIN_DIR = Path(__file__).resolve().parent
CONFIG_OVERRIDES_PATH = MAIN_DIR / "system_config.json"


def _load_overrides() -> dict:
    if not CONFIG_OVERRIDES_PATH.exists():
        return {}

    try:
        with CONFIG_OVERRIDES_PATH.open("r", encoding="utf-8") as config_file:
            data = json.load(config_file)
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


CONFIG_OVERRIDES = _load_overrides()


def setting(name: str, default: str) -> str:
    return os.getenv(name, str(CONFIG_OVERRIDES.get(name, default)))


def int_setting(name: str, default: int) -> int:
    try:
        return int(setting(name, str(default)))
    except ValueError:
        return default


# Nafezly login and scraping settings
Username = setting("NAFEZLY_USERNAME", "")
Password = setting("NAFEZLY_PASSWORD", "")
JOBS_CSV_PATH = setting(
    "JOBS_CSV_PATH",
    str(MAIN_DIR / "data" / "jobs.csv"),
)

HOME_URL = setting("HOME_URL", "https://nafezly.com/")
LOGIN_URL = setting("LOGIN_URL", "https://nafezly.com/login")
PROJECTS_URL = setting("PROJECTS_URL", "https://nafezly.com/projects")
CHROME_USER_DATA = setting(
    "CHROME_USER_DATA",
    "",
)
CHROME_PROFILE = setting("CHROME_PROFILE", "Default")

# Job monitoring settings
RECENT_JOB_MAX_AGE_MINUTES = int_setting("RECENT_JOB_MAX_AGE_MINUTES", 5)
JOB_POLL_INTERVAL_MINUTES = int_setting("JOB_POLL_INTERVAL_MINUTES", 15)
JOB_LIST_PAGES_PER_CYCLE = int_setting("JOB_LIST_PAGES_PER_CYCLE", 5)

# Groq proposal generation settings
GROQ_API_KEY = setting("GROQ_API_KEY", "")
GROQ_BASE_URL = setting("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
PROPOSAL_MODEL = setting("GROQ_PROPOSAL_MODEL", "llama-3.3-70b-versatile")
GROQ_CALL_INTERVAL_SECONDS = int_setting("GROQ_CALL_INTERVAL_SECONDS", 2)

# Proposal submission defaults
DEFAULT_PROPOSAL_PERIOD_DAYS = int_setting("DEFAULT_PROPOSAL_PERIOD_DAYS", 3)
DEFAULT_PROPOSAL_COST_USD = int_setting("DEFAULT_PROPOSAL_COST_USD", 25)
