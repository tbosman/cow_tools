from sqlalchemy import create_engine
import json

with open("cow_tools/config/apikeys.json", "r") as f:
    apikeys = json.load(f)

def get_postgres_engine():
   return create_engine(apikeys['postgres_uri'])

