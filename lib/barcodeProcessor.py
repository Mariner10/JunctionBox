import requests
from bs4 import BeautifulSoup
import random
import time
import os
import json
from datetime import datetime

file_path = "JSON/barcode_data.json"
waiting_file_path = "JSON/barcode_waitingroom.json"

user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.77 Mobile Safari/537.36"
]


def fetch_content(upc_code):
    product_title = None
    product_description = None
    product_ingredients = None
    product_image = None
    time.sleep(random.uniform(0.2, 3))
    url = f"https://go-upc.com/search?q={upc_code}"
    
    headers = {
        "User-Agent": random.choice(user_agents),
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/"
    }
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        content = BeautifulSoup(response.content, "html.parser")

        try:
            product_title = content.find("h1", class_="product-name").get_text(strip=True)
        except AttributeError:
            product_title = "N/A"

        try:
            h2_elements = content.find_all("h2")
            for h2_element in h2_elements:
                if h2_element and h2_element.get_text(strip=True) == "Description":
                    # Find the next sibling <span> element
                    span_element = h2_element.find_next_sibling("span")
                    if span_element:
                        # Get the text content of the <span> element
                        product_description = span_element.get_text(strip=True)
                    else:
                        print("No <span> element found after the <h2> element.")


                if h2_element and h2_element.get_text(strip=True) == "Ingredients":
                    # Find the next sibling <span> element
                    span_element = h2_element.find_next_sibling("span")
                    if span_element:
                        # Get the text content of the <span> element
                        product_ingredients = span_element.get_text(strip=True)
                    else:
                        print("No <span> element found after the <h2> element.")
        except Exception as e:
            print(f"An error occurred aquiring description and/or ingredients: {e}")

        try:
            product_image = content.find("figure", class_="product-image non-mobile").find('img')['src']
        except Exception as e:
            print(f"An error occurred aquiring image source URL: {e}")
            

        return product_title, product_description, product_ingredients, product_image

    elif response.status_code == 429:
        print("Too many requests. Please try again later.")
        return 429

    else:
        print(f"Failed to retrieve content, status code: {response.status_code}")
        return None


def add_code(key):
    '''
    2  -> API request limit hit. Item added to queue.\n
    0  -> Error occurred gathering data, content was NoneType.\n
    1  -> Success, new item added to entries.\n
    -1 -> Succes, but we already had this item, just increased it's count.
    '''
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}

    if os.path.exists(waiting_file_path):
        with open(waiting_file_path, 'r') as file:
            try:
                waitingdata = json.load(file)
            except json.JSONDecodeError:
                waitingdata = {}
    else:
        waitingdata = {}


    keydata = data.get(key)
    if keydata == None:
        data[key] = {}
        data[key]["timestamp"] = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
        data[key]["count"] = 1


    if not data[key].get("title"):
        waitingkeydata = waitingdata.get(key)
        if waitingkeydata == None:
            content = fetch_content(key)
        
            if content == 429:
                print("We ran out of requests. Last key: ",key)
                
                waitingdata[key] = {}
                waitingdata[key]["timestamp"] = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
                waitingdata[key]["count"] = 1
        


                with open(waiting_file_path, 'w') as waitingfile:
                    json.dump(waitingdata, waitingfile, indent=4)

                return 2

            
            if content != None:
                product_title, product_description, product_ingredients, product_image = content
                data[key]["title"] = product_title
                data[key]["description"] = product_description
                data[key]["ingredients"] = product_ingredients
                data[key]["image"] = product_image

            else:
                print("Content was Nonetype")
                return 0

        else:
            print(key, "is already waiting to be processed.")
            try:
                waitingdata[key]["count"] += 1
            except KeyError:
                waitingdata[key].setdefault("count",1)

            with open(waiting_file_path, 'w') as waitingfile:
                json.dump(waitingdata, waitingfile, indent=4)
    
    else:
        print("We already have", data[key]["title"])
        try:
            data[key]["count"] += 1
        except KeyError:
            data[key].setdefault("count",0)
        return -1
        

    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)

    return 1

def edit_code(code,key,value):
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}

    keydata = data.get(code)
    if keydata != None:
        if key == "count":
            keydata[key] = int(value)
        keydata[key] = value
        with open(file_path, 'w') as file:
            json.dump(data, file, indent=4)
        return 1
    else:
        return None

def get_code(code):
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}

    if os.path.exists(waiting_file_path):
        with open(waiting_file_path, 'r') as file:
            try:
                waitingdata = json.load(file)
            except json.JSONDecodeError:
                waitingdata = {}
    else:
        waitingdata = {}

    codeData = data.get(code)
    if codeData == None:
        codeData = waitingdata.get(code)
        if codeData == None:
            return None
        
        
    return codeData

def get_all_codes():
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}

    return data

def sync_codes():
    '''
    Syncs the codes from the waiting file to the main file.\n
    NoneType, NoneType -> No data waiting to be synced.\n
    remaining_codes, codes -> The codes that are still waiting to sync, and the codes that did sync.
    '''
    if os.path.exists(waiting_file_path):
        with open(waiting_file_path, 'r') as file:
            try:
                waitingdata = json.load(file)
            except json.JSONDecodeError:
                waitingdata = {}
                with open(waiting_file_path, 'w') as file:
                    json.dump(waitingdata, file, indent=4)
                return None, None
    else:
        waitingdata = {}
        with open(waiting_file_path, 'w') as file:
            json.dump(waitingdata, file, indent=4)
        return None, None

    codes = []
    for key in waitingdata:
        result = add_code(key)
        if result == 1:
            codes.append(key)
        elif result == 0 or result == -1:
            pass
        elif result == 2:
            break

    keysList = list(waitingdata.keys())
    remaining_codes = [x for x in keysList if x not in codes]

    return remaining_codes, codes


