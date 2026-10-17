import json
import urllib.request

WEBHOOK_URL = "https://discord.com/api/webhooks/1560829918642708490/EqFP2EeHzu2ygAACdhcHV1bPetR7GKJg5ltLSPkavrM5nPpw-omXanhaT7YgLMSvpLi2"

data = json.dumps({"content": "Webhook test: it works!"}).encode("utf-8")
request = urllib.request.Request(
    WEBHOOK_URL,
    data=data,
    headers={
        "Content-Type": "application/json",
        "User-Agent": "tfm-room-counter/1.0",
    },
)
urllib.request.urlopen(request, timeout=10).read()
print("Sent! Check your Discord channel.")
