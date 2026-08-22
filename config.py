from os import getenv
from dotenv import load_dotenv

load_dotenv()

def load_ids(value: str) -> list[int]:
    if value is None:
        return []
    
    if value.find(",") == -1:
        return int(value)
    
    values = value.replace(", ", ",").split(",")
    
    return map(int, values)

class Config:
    BOT_TOKEN = getenv("BOT_TOKEN")
    ADMINS_IDS = load_ids(getenv("ADMINS_IDS"))