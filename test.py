# import requests
# import json

# response = requests.post(
#     "http://localhost:11434/api/generate",
#     json={
#         "model": "mistral",
#         "prompt": "Explain Kubernetes in one sentence."
#     },
#     stream=True
# )

# for chunk in response.iter_lines():
#     if chunk:
#         data = json.loads(chunk.decode())
#         print(data.get("response", ""), end="")

import requests

API_KEY = "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"

url = "https://openrouter.ai/api/v1/chat/completions"
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

data = {
    "model": "mistralai/mistral-7b-instruct",
    "messages": [
        {"role": "system", "content": "Respond in one short sentence."},
        {"role": "user", "content": "Explain Kubernetes in one sentence."}
    ]
}

response = requests.post(url, headers=headers, json=data)

print("Status:", response.status_code)
print("Response:", response.text)
