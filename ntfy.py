from requests import post

def send(Title: str, Message: str, address: str, priority: str = "urgent"):
    
    post(f"https://ntfy.sh/{address}", data=Message,headers={
                        "Title": Title,
                        "Priority": priority
                    })


