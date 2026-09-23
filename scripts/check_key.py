import os
import requests
import json

key = os.environ.get("GROQ_API_KEY")
resp = requests.get(
    "https://api.groq.com/openai/v1/models",
    headers={"Authorization": f"Bearer {key}"},
)
data = resp.json()
for m in data["data"]:
    print(m["id"])