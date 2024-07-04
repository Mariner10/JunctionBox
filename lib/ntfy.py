from requests import post
import json

def send(Title: str, Message: str, address: str, priority: str = "urgent"):
    
    post(f"https://ntfy.sh/{address}", data=Message,headers={
                        "Title": Title,
                        "Priority": priority
                    })


def twoFactor(address: str,message: str,actions: list):
    '''Actions format
    "actions": [
            {
                "action": "view",
                "label": "Open portal",
                "url": "https://home.nest.com/",
                "clear": true
            },
            {
                "action": "http",
                "label": "Turn down",
                "url": "https://api.nest.com/",
                "body": "{\"temperature\": 65}"
            }
        ]'''
    post(f"https://carterbeaudoin2.ddns.net/ntfy/",
    data=json.dumps({
        "topic": address,
        "message": message,
        "actions": actions
    })
)

