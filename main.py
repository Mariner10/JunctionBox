from datetime import datetime, timedelta, timezone
from typing import Union, List
import lib.ntfy as ntfy
from fastapi import Depends, FastAPI, HTTPException, status, File, UploadFile, Form, Response
from starlette.requests import Request as apiRequest
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from typing_extensions import Annotated
import zipfile
import pyzipper
import sys
from geojson import Polygon, Feature, FeatureCollection
import asyncio
import json
import csv
import os 
import shutil
import json
import base64
import ssl
import re
import glob
import pandas as pd
from turfpy import measurement as turfpyMeasure, transformation as turfpyTransform
from mapCreation.map_toolkit import map_toolkit
from lib.requestview import drawRequestView
from lib.barcodeProcessor import add_code, get_code, get_all_codes
from batteryViewCreation.batteryview import generateBatteryDayView
from dotenv import load_dotenv

load_dotenv()


# openssl rand -hex 32
SECRET_KEY = os.getenv('SECRET_KEY')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

MAIN_PATH = str(os.path.join(os.path.dirname(os.path.abspath(__file__))))
HTML_PATH = os.path.join( MAIN_PATH, 'HTML')
JSON_PATH = os.path.join(MAIN_PATH, 'JSON')
LOGS_PATH = os.path.join(MAIN_PATH,"mapCreation","logs")

from userdatabase import users_db

CLI_users_db = {
    os.getenv("USERNAME"): {
        "username": os.getenv("USERNAME"),
        "full_name": os.getenv("FULL_NAME"),
        "email": os.getenv("EMAIL"),
        "password": os.getenv("CLI_KEY")
    }
}


class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Union[str, None] = None

class User(BaseModel):
    username: str
    email: Union[str, None] = None
    full_name: Union[str, None] = None
    disabled: Union[bool, None] = None

class DeviceLocation(BaseModel):
    name: str 
    deviceType: str
    latitude: float  
    longitude: float
    batteryLevel: float  
    positionType: str
    timestamp: float 

class circleZone(BaseModel):
    name: str
    latitude: float
    longitude: float
    radius: int

class image(BaseModel):
    img: str

class image(BaseModel):
    img: str

class flipSwitch(BaseModel):
    title: str
    state: int
    toggleTime: float

class UserInDB(User):
    hashed_password: str



pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

templates = Jinja2Templates(directory=os.path.join("HTML","templates"))

app = FastAPI(ssl_keyfile=os.getenv("SSL_KEYFILE"), ssl_certfile=os.getenv("SSL_CERT"),docs_url=None, redoc_url=None)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)

def authenticate_user(db, username: str, password: str):
    user = get_user(db, username)
    if not user:
        ntfy.send(f"Someone tried a username [ {username} ] on API!", f"If this was not you, take action! [ {username} , {password}]", os.getenv("NTFY_ALERTS"))
        return False
    if not verify_password(password, user.hashed_password):
        ntfy.send("Someone tried to authenticate API!", f"User, [ {username} ]: If this was not you, take action!", os.getenv("NTFY_ALERTS"))
        return False
    return user

def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def logRequest(request: apiRequest, send = True):

    with open("JSON/requests.json", "r") as requestFile:
        requestDict = dict(json.load(requestFile))

    headers = request.headers

    now = datetime.now()
    client_host = headers.get("x-forwarded-for")
    language = headers.get("accept-language")
    user_agent = headers.get("user-agent")
    scheme = request.url

    try:
        hits = int(requestDict[client_host]["HITS"]) + 1
    except Exception:
        hits = 0
    
    if send:
        ntfy.send(f"{client_host} accessed API.", f"{user_agent} accessed {scheme}, lifetime connections: {hits}.", os.getenv("NTFY_ALERTS"),"min")

    new_entry = {
        "HOST": client_host,
        "HITS": hits,
        "AGENT": str(user_agent),
        "METHOD": str(scheme),
        "LANGUAGE": str(language),
        "LAST_TIMESTAMP": now.strftime("%m/%d/%Y, %H:%M:%S")
    }
    


    requestDict[client_host] = new_entry

    update_json_file(requestDict,"requests")


def generate_feature_id(features):
    if not features:
        return 0
    max_id = max(feature['id'] for feature in features)
    return max_id + 1

def update_json_file(stateDict,filename):
    with open(f"JSON/{filename}.json", "w") as file:
        json.dump(stateDict, file)

def current_zone(lat,lon):
    filename = 'JSON/Zones.json'
    listObj = {}
    
    if not os.path.isfile(filename):
        return [{"Status": "Failed", "Info": "JSON file not found!"}]
    
    with open(filename) as fp:
        listObj = json.load(fp).get("features", [])

    for name in listObj:
        boolean = turfpyMeasure.boolean_point_in_polygon([lon, lat], name)
        if boolean:
            return [{"Status": "Success", "Data": name}]
    
    return [{"Status": "Failed", "Data": False}]

def cleanup_zipFiles(name: str = None):
    with open("JSON/zipFiles.json", "r") as zipFiles:
        zipDict = dict(json.load(zipFiles))

    for filename in zipDict:
        expireTime = zipDict[filename]["Lifespan"]
        uploader = zipDict[filename]["Uploader"]
        uploadDate = zipDict[filename]["Timestamp"]
        expireTimeDT = datetime.strptime(expireTime,"%m/%d/%Y, %H:%M:%S")
        if datetime.now() >= expireTimeDT:
            try:
                os.remove(f"ZipFiles/{filename}")
                zipDict.pop(filename)
                update_json_file(zipDict,"zipFiles")
                return True
            except Exception:
                ntfy.send(f"Couldn't delete {filename}!", f"It was originally uploaded by {uploader} on {uploadDate}", os.getenv("NTFY_ALERTS"))
                return False

    if  name != None:
        for key in zipDict:
            if key == f"{name}.zip":
                try:
                    os.remove(f"ZipFiles/{filename}")
                    zipDict.pop(key)
                    update_json_file(zipDict,"zipFiles")
                    return True
                except Exception:
                    ntfy.send(f"Couldn't delete {filename}!", f"It was originally uploaded by {uploader} on {uploadDate}", os.getenv("NTFY_ALERTS"))
                    return False

def fileHasBeenUsed(name: str):
    with open("JSON/zipFiles.json", "r") as zipFiles:
        zipDict = dict(json.load(zipFiles))

    for key in zipDict:
        if key == f"{name}.zip":
            isItOneUse = bool(zipDict[key]["One-Time-Use"])
            if isItOneUse:
                now = datetime.now()
                zipDict[key]["Lifespan"] = now.strftime("%m/%d/%Y, %H:%M:%S")
                update_json_file(zipDict,"zipFiles")

def get_weeks(deviceName):
    csv_files = glob.glob(os.path.join(LOGS_PATH, deviceName, '*.csv'))
    df = pd.DataFrame()

    for file in csv_files:
        temp_df = pd.read_csv(file)
        df = pd.concat([df, temp_df], ignore_index=True)

    df['Time'] = pd.to_datetime(df['Time Object (EPOCH)'], unit='s')
    start_date = df['Time'].min()
    end_date = df['Time'].max()

    # Adjust start_date to the previous Sunday
    start_date -= timedelta(days=start_date.weekday() + 1 if start_date.weekday() != 6 else 0)
    
    # Adjust end_date to the next Saturday
    end_date += timedelta(days=(5 - end_date.weekday() + 1) if end_date.weekday() != 5 else 0)

    weeks = []
    current_week = start_date
    while current_week <= end_date:
        weeks.append(current_week.strftime('%m-%d-%Y'))
        current_week += timedelta(weeks=1)

    return weeks


@app.get("/map", response_class=HTMLResponse)
async def root(request: apiRequest, current_user: Annotated[User, Depends(get_current_active_user)]):
    logRequest(request)
    with open('HTML/ZoneMap.html', 'r') as file:  # r to open file in READ mode
        html_as_string = file.read()

    return html_as_string

@app.get("/",response_class=HTMLResponse)
async def get_login(request: apiRequest):
    logRequest(request,send = 0)
    
    with open("HTML/login.html", "r") as file:  # Assuming your HTML file is named 'login.html'

        return HTMLResponse(content=file.read(), status_code=200)
    
@app.get("/protected", response_class=HTMLResponse)
async def get_protected_page(request: apiRequest):
    logRequest(request)
    headers = request.headers
    authorization: str = headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        ntfy.send("SOMEBODY TRIED TO ACCESS PROTECTED!", f"See: {headers.get('x-forwarded-for')} and {headers.get('user-agent')}", os.getenv("NTFY_ALERTS"))
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    token = authorization.split(" ")[1]


    if (token):
        try:
            with open("HTML/endpoints.html", "r") as file:
                return HTMLResponse(content=file.read(), status_code=200)
        except FileNotFoundError:
            raise HTTPException(status_code=500, detail="HTML file not found")
    else:
        with open("HTML/denied.html", "r") as file:
            return HTMLResponse(content=file.read(), status_code=401)




@app.get("/heartbeat")
async def heatbeat(request: apiRequest):
    logRequest(request)
    return {"Status": "Success", "Time": f"{datetime.strftime(datetime.now(), '%m/%d/%Y, %H:%M:%S')}"}
'''
@app.get("/twoFA_enact")
async def twoFA_enact(request: apiRequest,current_user: Annotated[User, Depends(get_current_active_user)]):
    logRequest(request)
    headers = request.headers
    authorization: str = headers.get("Authorization")
    if not authorization or not authorization.startswith("Bearer "):
        ntfy.send("SOMEBODY TRIED TO ACCESS twoFA_enact!", f"See: {headers.get('x-forwarded-for')} and {headers.get('user-agent')}", os.getenv("NTFY_ALERTS"))
        raise HTTPException(status_code=401, detail="Invalid or missing token")
    


    return {"Status": "Success", "Time": f"{datetime.strftime(datetime.now(), '%m/%d/%Y, %H:%M:%S')}"}

@app.get("/twoFA")
async def twoFA(request: apiRequest):
    logRequest(request)
    ntfy.twoFactor("goonCave2FAAUTH","Auth Test",
          [{
              "action": "http",
              "label": "Auth",
              "url": "https://carterbeaudoin2.ddns.net/twoFA_enact",
              "method": "GET",
              "headers": {
                'username': "",
                'password': os.getenv("API_USER_PASS")
              },
              "body": "{\"action\": \"close\"}"
            }
            ])
    # Sit here and make new fuction that waits 15 seconds for a 2FA file to change or something?
    ntfy.send("Authenticating!!", f"YAYYYYYY", os.getenv("NTFY_ALERTS"))
    return {"Status": "Success", "Time": f"{datetime.strftime(datetime.now(), '%m/%d/%Y, %H:%M:%S')}"}
'''
@app.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], request: apiRequest
) -> Token:
    logRequest(request)
    user = authenticate_user(users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")


@app.get("/users/me/", response_model=User)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    return current_user

@app.get("/users/me/deviceName")
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)]
):
    username = current_user.model_dump()['username']
    deviceName = users_db[username]["device_name"]

    return {"deviceName": deviceName}


most_recent_phone_data = {}
@app.post("/iLogger/publish_data/")
async def input_current_whereabouts(item: DeviceLocation):
    global most_recent_phone_data

    current_datetime = datetime.now()
    devicetimestamp = item.timestamp
    datetime_from_unix = datetime.fromtimestamp(devicetimestamp)
    time_difference = current_datetime - datetime_from_unix

    # Convert time difference to seconds
    time_difference_seconds = str(time_difference.total_seconds())

    most_recent_phone_data["Name"] = item.name
    most_recent_phone_data["DeviceType"] = item.deviceType
    most_recent_phone_data["Latitude"] = item.latitude
    most_recent_phone_data["Longitude"] = item.longitude
    most_recent_phone_data["BatteryLevel"] = item.batteryLevel  
    most_recent_phone_data["PositionType"] = item.positionType
    most_recent_phone_data["Timestamp"] = item.timestamp

    print(f"Saved phone data: {most_recent_phone_data}")
 
    savedLocalesFilename = 'JSON/Zones.json'
    LocalesDic = {}
    

    response = current_zone(item.latitude, item.longitude)

    for zoneInfo in response:
        if zoneInfo["Status"] == "Success":
            data = zoneInfo["Data"]
            properties = data.get("properties", {})

            if properties:
                name = properties.get("Name")

                if os.path.isfile(savedLocalesFilename):
                    with open(savedLocalesFilename) as fn:
                        LocalesDic = json.load(fn)

                    for place in LocalesDic:
                        if name == place:
                            LocalesDic[place]["Number"] += 1
                            LocalesDic[place]["Timestamps"].append(item.timestamp)

                            with open(savedLocalesFilename, 'w') as instances_file:
                                json.dump(LocalesDic, instances_file, indent=4, separators=(',', ': '))
        else:
            print("Not in zone. Ignoring.")
            pass


            

    return [{"Status": "Success", "Latency": f"{time_difference_seconds}s"}]

@app.get("/iLogger/return_data/")
async def output_current_whereabouts(current_user: Annotated[User, Depends(get_current_active_user)],request: apiRequest):
    global most_recent_phone_data
    

    if most_recent_phone_data == {}:
        print(f"No phone data found!")
        return [{"Status": "Failed", "Info": "No phone data available."}]
    else:   
        print(f"Returned phone data: {most_recent_phone_data}")
        return [{"Status": "Success", "Data": most_recent_phone_data}]

@app.post("/iLogger/create_zone/")
async def create_zone(current_user: Annotated[User, Depends(get_current_active_user)], zoneinfo: circleZone):
    filename = 'JSON/Zones.json'

    # Check if file exists
    if not os.path.isfile(filename):
        return {"Status": "Failed", "Info": "JSON file not found!"}
    
    # Read JSON file
    with open(filename, 'r') as fp:
        zones_data = json.load(fp)
    
    # Generate ID for the new feature
    new_id = generate_feature_id(zones_data['features'])
    polygon = turfpyTransform.circle([zoneinfo.longitude, zoneinfo.latitude], zoneinfo.radius, units="m")

    # Create Feature with ID
    new_feature = {
        "type": "Feature",
        "properties": {
            "Name": zoneinfo.name,
            "Count": []
        },
        "geometry": polygon["geometry"],
        "id": new_id
    }

    # Append new feature to existing features
    zones_data['features'].append(new_feature)

    # Write updated JSON file
    with open(filename, 'w') as json_file:
        json.dump(zones_data, json_file, indent=4)

    return {"Status": f"Successfully added {zoneinfo.name}", "Data": polygon, "id": new_id}

@app.get("/iLogger/get_zones/")
async def get_zones(current_user: Annotated[User, Depends(get_current_active_user)]):

    filename = 'JSON/Zones.json' 
    listObj = {}
    
    # Check if file exists
    if os.path.isfile(filename) is False:
        return [{"Status": "Failed", "Info": "JSON file not found!"}]
    
    # Read JSON file
    with open(filename) as fp:
        listObj = dict(json.load(fp))
    
    \
    return listObj

@app.get("/iLogger/current_zone/")
async def output_current_zone(current_user: Annotated[User, Depends(get_current_active_user)]):
    global most_recent_phone_data
    try: 
        lat = most_recent_phone_data["Latitude"]
        lon = most_recent_phone_data["Longitude"]
    except Exception as e:
        return [{"Status": "Failed", "Info": e}]

    return current_zone(lat,lon)
    
'''@app.get("/command/{item}")
def read_cmd(item: str, request: Request):
    print(item)
    client_host = request.client.host
    port = request.client.port
    return {"client_host": client_host,"client_port": port, "command": item}

@app.post('/roomCamera/takePicture/')
async def roomCamera(current_user: Annotated[User, Depends(get_current_active_user)], image: image):
    imageJSON = image.img

    return {"Image": imageJSON}'''

@app.post('/flipswitch/')
async def switch(current_user: Annotated[User, Depends(get_current_active_user)], flipSwitch: flipSwitch):
    # Load initial state from file if it exists
    if os.path.exists("JSON/flipSwitches.json"):
        with open("JSON/flipSwitches.json", "r") as file:
            stateDict = json.load(file)
    else:
        stateDict = {}

    if flipSwitch.state == 5:
        return stateDict

    async def background_task(title, time):
        nonlocal stateDict
        stateDict[title]['state'] = not stateDict[title]['state']
        await asyncio.sleep(time)
        stateDict[title]['state'] = not stateDict[title]['state']
        update_json_file(stateDict,"flipSwitches")

    title = flipSwitch.title
    if title not in stateDict:
        stateDict[title] = {'state': False}

    flipSwitch_state = stateDict[title]['state']
    toggleTime = float(flipSwitch.toggleTime)

    match int(flipSwitch.state):
        case 0:
            flipSwitch_state = False
        case 1:
            flipSwitch_state = True
        case 2:
            flipSwitch_state = not flipSwitch_state
        case 3:
            if toggleTime != 0:
                asyncio.create_task(background_task(title, toggleTime))
            else:
                return {"Status": 406, "Issue": "toggleTime cannot be 0"}
        case 4:
            return stateDict[title]
        case 6:
            stateDict.pop(title, None)
            update_json_file(stateDict,"flipSwitches")
            return stateDict

    stateDict[title]['state'] = flipSwitch_state
    update_json_file(stateDict,"flipSwitches")

    return {"State": flipSwitch_state}


@app.get('/flipswitch/polling/{switchName}/{truthState}')
async def switchPoll(switchName,truthState):
    try:
        stateDict = {}

        if truthState == "0":
            truthState = False
        else:
            truthState = True
            
        if os.path.exists("JSON/flipSwitches.json"):
            with open("JSON/flipSwitches.json", "r") as file:
                stateDict = json.load(file)

            while bool(stateDict[switchName]["state"]) != truthState:
                with open("JSON/flipSwitches.json", "r") as file:
                    stateDict = json.load(file)
                await asyncio.sleep(1)
            
            return stateDict[switchName]
    except Exception as e:

        return {"Error": f"Timeout - {e}"}
   
@app.post("/file-storage/upload/{linkName}")
def uploadFile(request: apiRequest,current_user: Annotated[User, Depends(get_current_active_user)],linkName,files: List[UploadFile] = File(...)):

    passHeader = request.headers.get('filePassword')
    for file in files:
        try:
            contents = file.file.read()
            subdirectory = f"userFiles/{linkName}"
            os.makedirs(subdirectory, exist_ok=True)
            with open(f"userFiles/{linkName}/{file.filename}", 'wb') as f:
                f.write(contents)
        except Exception:
            return {"message": "There was an error uploading the file(s)"}
        finally:
            file.file.close()
    

    ntfy.send("File Upload Complete",f"Uploaded: {[file.filename for file in files]} to {linkName}",os.getenv("NTFY_MESSAGES")) # Send notification
    return {"message": f"Successfuly uploaded {[file.filename for file in files]} to {linkName}"}    

@app.post("/CLI/file-storage/upload/{linkName}")
async def CLIuploadFile(request: apiRequest, linkName, file: UploadFile = File(...)):
    passHeader = request.headers.get('filepassword')  # string to set the zip password to
    uploaderHeader = request.headers.get('uploader')  # uploader username
    passwordHeader = request.headers.get('uploaderPassword')  # uploader password
    oneTimeUse = False
    try:
        persistanceHeader = int(request.headers.get('persistance')) # minutes till I auto delete it
    except Exception:
        persistanceHeader = None

    if persistanceHeader == None or persistanceHeader < 1:

        if persistanceHeader == 0:
            oneTimeUse = True
            persistanceHeader = 10080
        else:
            persistanceHeader = 720 # 12 hours

    if os.path.exists("JSON/zipFiles.json"):
        with open("JSON/zipFiles.json", "r") as zipFile:
            zipDict = json.load(zipFile)
    else:
        ntfy.send("A JSON File is doing something funky!", f"zipFiles.json VANISHED!?!?!: HOW!?!?!?", os.getenv("NTFY_ALERTS"))
 
    linkName = str(linkName).split(".")[0]

    zip_filename = f"ZipFiles/{linkName}.zip"

    if uploaderHeader not in CLI_users_db:
        return [{"Status": "Failed", "Info": "Username not found."}]

    if uploaderHeader in CLI_users_db and CLI_users_db[uploaderHeader]["password"] == passwordHeader:
        now = datetime.now()
                
        try:
            contents = await file.read()  # Read file asynchronously
            subdirectory = f"userFiles/{linkName}"
            os.makedirs(subdirectory, exist_ok=True)
            with open(f"{subdirectory}/{file.filename}", 'wb') as f:
                f.write(contents)

            zipDict[f"{linkName}.zip"] = {"Uploader": uploaderHeader,"File": file.filename,"Timestamp": now.strftime("%m/%d/%Y, %H:%M:%S"),"Lifespan": (now + timedelta(minutes=persistanceHeader)).strftime("%m/%d/%Y, %H:%M:%S"),"One-Time-Use":oneTimeUse}
        except Exception as e:
            return {"message": f"There was an error uploading the file(s): {str(e)}"}


        zip_filename = f"ZipFiles/{linkName}.zip"
        
        def zip_folderPyzipper(folder_path, output_path):
            """Zip the contents of an entire folder (with that folder included
            in the archive). Empty subfolders will be included in the archive
            as well.
            """
            parent_folder = os.path.dirname(folder_path)
            # Retrieve the paths of the folder contents.
            contents = os.walk(folder_path)
            
            try:
                zip_file = pyzipper.ZipFile(f"{output_path}",'w',compression=pyzipper.ZIP_DEFLATED,compresslevel=9)
                if passHeader != None:
                    zip_file = pyzipper.AESZipFile(f"{output_path}",'w',compression=pyzipper.ZIP_DEFLATED,compresslevel=9,encryption=pyzipper.WZ_AES)
                    zip_file.pwd=passHeader.encode(encoding='utf-8')

                for root, folders, files in contents:
                    # Include all subfolders, including empty ones.
                    for folder_name in folders:
                        absolute_path = os.path.join(root, folder_name)
                        relative_path = absolute_path.replace(parent_folder + '\\',
                                                            '')
                        zip_file.write(absolute_path, relative_path)
                    for file_name in files:
                        absolute_path = os.path.join(root, file_name)
                        relative_path = absolute_path.replace(parent_folder + '\\',
                                                            '')
                        zip_file.write(absolute_path, relative_path)


            except IOError as message:
                print (message)
                sys.exit(1)
            except OSError as message:
                print(message)
                sys.exit(1)
            except zipfile.BadZipfile as message:
                print (message)
                sys.exit(1)
            finally:
                zip_file.close()
        
        try:
            zip_folderPyzipper(subdirectory,f"{zip_filename}")
            shutil.rmtree(subdirectory)
        except Exception:
            return [{"Status": "Failed", "Info": "Error zipping up File?"}]

        try:
            update_json_file(zipDict,"zipFiles")
        except Exception as grr:
            ntfy.send("A JSON File is doing something funky!", f"zipFiles.json failed to update to: {str(zipDict)}", os.getenv("NTFY_ALERTS"))

        try:
            cleanup_zipFiles()
            ntfy.send("CLI File Upload Complete", f"Uploaded: {file.filename} to {linkName}", os.getenv("NTFY_MESSAGES"))
            return {"message": f"Successfully uploaded {file.filename} to {linkName}"}
        except Exception as oi:
            ntfy.send("CLI File Upload Complete", f"It was a janky name but we uploaded it to {linkName}", os.getenv("NTFY_MESSAGES"))
            return {"message": f"Successfully uploaded {file.filename} to {linkName}... But for some reason couldn't call NTFY correctly soo..?"}

    else:
        return [{"Status": "Failed", "Info": "Incorrect password."}]

@app.get("/file-storage/delete/{linkName}") #TODO
async def deleteFile(current_user: Annotated[User, Depends(get_current_active_user)],linkName):

    result = cleanup_zipFiles(linkName)

    if result == True:
        ntfy.send("File Deletion Complete",f"Deleted: {linkName}",os.getenv("NTFY_MESSAGES")) # Send notification
        return {"Status": "Success", "Data": f"Successfuly deleted file [ {linkName}.zip ] from server."}
    else:
        return {"Status": "Failed", "Data": f"Could not delete file [ {linkName}.zip ] from server."}

@app.get("/file-storage/download/{linkName}",response_class=FileResponse)
async def sendFile(linkName,request: apiRequest):
    logRequest(request)
    linkName = str(linkName).split(".")[0]
    cleanup_zipFiles()
    fileHasBeenUsed(linkName)

    zip_filename = f"ZipFiles/{linkName}.zip"

     
    try:
        ntfy.send("File Downloaded!",f"Sent: {linkName}.zip",os.getenv("NTFY_MESSAGES")) # Send notification
        return FileResponse(f"{zip_filename}", media_type="application/zip")
    except Exception as e:
        return {"Status": "Failed", "Data": f"Could not delete file [ {linkName}.zip ] from server: {e}"}
        
@app.get("/dataview/iLogger/{mapModelName}/{redownload}",response_class=HTMLResponse)
async def mapCreation(mapModelName,redownload,current_user: Annotated[User, Depends(get_current_active_user)],request: apiRequest):
    logRequest(request)

    username = current_user.model_dump()['username']
    deviceName = users_db[username]["device_name"]

    if bool(int(redownload)):
        mpToolkit = map_toolkit(deviceName)
        mpToolkit.theSauce()
    else:
        pass
    try:
        with open(f'mapCreation/map/{deviceName}/{mapModelName}.html', 'r') as file: 
            html_as_string = file.read()
    except Exception as e:
        ntfy.send("DEBUG ERROR!", f"Exception: {e}", os.getenv("NTFY_ALERTS"))
        with open(f'HTML/denied.html', 'r') as file:
            html_as_string = file.read()
    return html_as_string

@app.get("/personal/view/today",response_class=HTMLResponse)
async def todayView(current_user: Annotated[User, Depends(get_current_active_user)],request: apiRequest):
    logRequest(request)
    username = current_user.model_dump()['username']
    deviceName = users_db[username]["device_name"]

    iLogger = map_toolkit(deviceName)

    iLogger.createTodayPath(os.path.join(LOGS_PATH,deviceName),os.path.join(HTML_PATH,"today_path.html"))

    try:
        with open(f'{os.path.join(HTML_PATH,"today_path.html")}', 'r') as file:  
            html_as_string = file.read()

    except Exception as e:
        ntfy.send("DEBUG ERROR!", f"Exception: {e}", os.getenv("NTFY_ALERTS"))
        with open(f'HTML/denied.html', 'r') as file:  # r to open file in READ mode
            html_as_string = file.read()
    return html_as_string

@app.get("/personal/view/requests",response_class=HTMLResponse)
async def requestsView(current_user: Annotated[User, Depends(get_current_active_user)],request: apiRequest):
    logRequest(request)

    drawRequestView()

    try:
        with open(f'{os.path.join(HTML_PATH,"requests.html")}', 'r') as file:  
            html_as_string = file.read()

    except Exception as e:
        ntfy.send("DEBUG ERROR!", f"Exception: {e}", os.getenv("NTFY_ALERTS"))
        with open(f'HTML/denied.html', 'r') as file:  # r to open file in READ mode
            html_as_string = file.read()
    return html_as_string

@app.get("/personal/view/flipswitch",response_class=HTMLResponse)
async def flipswitchView(current_user: Annotated[User, Depends(get_current_active_user)],request: apiRequest):
    logRequest(request)
    
    
    try:
        with open(f'{os.path.join(HTML_PATH,"flipswitches.html")}', 'r') as file:  
            html_as_string = file.read()

    except Exception as e:
        ntfy.send("DEBUG ERROR!", f"Exception: {e}", os.getenv("NTFY_ALERTS"))
        with open(f'HTML/denied.html', 'r') as file:  # r to open file in READ mode
            html_as_string = file.read()
    return html_as_string

@app.get("/personal/view/batteryTimeline/{day}", response_class=HTMLResponse)
async def batteryView(day,current_user: Annotated[User, Depends(get_current_active_user)],request: apiRequest):
    logRequest(request)

    username = current_user.model_dump()['username']
    deviceName = users_db[username]["device_name"]

    generateBatteryDayView(os.path.join(LOGS_PATH,deviceName), os.path.join("batteryViewCreation/HTML", f"battery_level_{day}.html"), day)

    try:
        with open(os.path.join("batteryViewCreation/HTML", f"battery_level_{day}.html"), 'r') as file:  
            html_as_string = file.read()
    except Exception as e:
        html_as_string = f"Error generating the graph: {e}"

    return HTMLResponse(content=html_as_string)

@app.get("/personal/view/locationTimeline/{day}", response_class=HTMLResponse)
async def locationDayView(day,current_user: Annotated[User, Depends(get_current_active_user)],request: apiRequest):
    logRequest(request)

    username = current_user.model_dump()['username']
    deviceName = users_db[username]["device_name"]
    iLogger = map_toolkit(deviceName)

    os.makedirs(os.path.join("mapCreation","map","days"),exist_ok=True)
    iLogger.createDayPath(os.path.join(LOGS_PATH,deviceName), os.path.join("mapCreation","map","days", f"day_timeline_{day}.html"), day)

    try:
        with open(os.path.join("mapCreation","map","days", f"day_timeline_{day}.html"), 'r') as file:  
            html_as_string = file.read()
    except Exception as e:
        html_as_string = f"Error generating the graph: {e}"

    return HTMLResponse(content=html_as_string)

@app.get("/personal/view/timestampedDayPath/{day}", response_class=HTMLResponse)
async def locationDayView(day,current_user: Annotated[User, Depends(get_current_active_user)],request: apiRequest):
    logRequest(request)

    username = current_user.model_dump()['username']
    deviceName = users_db[username]["device_name"]
    iLogger = map_toolkit(deviceName)

    os.makedirs(os.path.join("mapCreation","map","days"),exist_ok=True)
    iLogger.timestampedDayPath(os.path.join(LOGS_PATH,deviceName), os.path.join("mapCreation","map","days", f"day_timeline_{day}.html"), day)

    try:
        with open(os.path.join("mapCreation","map","days", f"day_timeline_{day}.html"), 'r') as file:  
            html_as_string = file.read()
    except Exception as e:
        html_as_string = f"Error generating the graph: {e}"

    return HTMLResponse(content=html_as_string)

@app.get("/personal/view/batteryTimeline", response_class= HTMLResponse)
async def batteryChooserView(current_user: Annotated[User, Depends(get_current_active_user)],request: apiRequest):
    logRequest(request)
    headers = request.headers
    authorization: str = headers.get("Authorization")
    
    token = authorization.split(" ")[1]


    if (token):
        try:
            with open("HTML/battery_level_week_chooser.html", "r") as file:
                return HTMLResponse(content=file.read(), status_code=200)
        except FileNotFoundError:
            raise HTTPException(status_code=500, detail="HTML file not found")
    else:
        with open("HTML/denied.html", "r") as file:
            return HTMLResponse(content=file.read(), status_code=401)

@app.get("/function/deviceControl/update")
async def deviceControlUpdate(current_user: Annotated[User, Depends(get_current_active_user)],request: apiRequest):
    logRequest(request,0)
    try:
        if os.path.exists("JSON/deviceUpdate.json"):
            with open("JSON/deviceUpdate.json", "r") as file:
                stateDict = json.load(file)

            while bool(stateDict["update"]) != True:
                with open("JSON/deviceUpdate.json", "r") as file:
                    stateDict = json.load(file)
                await asyncio.sleep(1)
            
            return stateDict["command"]
        
    except Exception as e:

        return {"Error": f"Timeout - {e}"}

@app.get("/function/deviceControl/command/{commandType}/{commandNumber}")
async def deviceControlUpdate(current_user: Annotated[User, Depends(get_current_active_user)],commandType,commandNumber,request: apiRequest):
    logRequest(request,False)
    if os.path.exists("JSON/deviceControl.json"):
        with open("JSON/deviceControl.json", "r") as file:
            stateDict = json.load(file)

        command = stateDict[commandType][int(commandNumber)]

        
        update_json_file({"update": True, "command": command},"deviceUpdate")
        await asyncio.sleep(3)
        update_json_file({"update": False, "command": "libactivator.system.nothing"},"deviceUpdate")

        return command
            
@app.get("/personal/view/deviceControl", response_class= HTMLResponse)
async def batteryChooserView(current_user: Annotated[User, Depends(get_current_active_user)],request: apiRequest):
    logRequest(request)

    
    try:
        with open(f'{os.path.join(HTML_PATH,"iosControl.html")}', 'r') as file:  
            html_as_string = file.read()

    except Exception as e:
        ntfy.send("DEBUG ERROR!", f"Exception: {e}", os.getenv("NTFY_ALERTS"))
        with open(f'HTML/denied.html', 'r') as file:  # r to open file in READ mode
            html_as_string = file.read()
    return html_as_string
    

@app.get("/personal/view/timemachine", response_class= HTMLResponse)
async def timemachine(current_user: Annotated[User, Depends(get_current_active_user)], request: apiRequest):
    # Path to the directory containing the files
    username = current_user.model_dump()['username']
    deviceName = users_db[username]["device_name"]
    iLogger = map_toolkit(deviceName)
    
    iLogger.downloadFiles(os.path.join(os.getenv("ILOGGER_REMOTE_LOGS_DIRECTORY"),deviceName))
    directory_path = 'mapCreation/logs/Yeeter'

    # List to hold the dates
    dates = []

    # Regex pattern to match the date part of the filename
    pattern = re.compile(r'(\d{4}-\d{2}-\d{2})')

    # Loop through all files in the directory
    for filename in os.listdir(directory_path):
        match = pattern.match(filename)
        if match:
            date_str = match.group(1)
            dates.append(date_str)

    # Sort the dates for better user experience
    dates.sort()

    return templates.TemplateResponse("timemachine.html", {"request": request, "dates": dates})




# GROCERY ERA

@app.get("/upc/add/{upc_code}")
async def upload_upc_code(upc_code, request: apiRequest):
    logRequest(request,send=False)
    result = add_code(upc_code)

    match result:
        case 2:
            return {"message": "API request limit hit. Item added to queue."}
        case 0:
            return {"message": "Error occurred gathering data, content was NoneType."}
        case 1:
            return {"message": "Success, new item added to entries."}
        case -1:
            return {"message": "Success, but we already had this item, just increased it's counter"}


@app.get("/upc/get/{upc_code}")
async def get_upc_code(upc_code, request: apiRequest):
    logRequest(request,send=False)
    result = get_code(upc_code)
    return result

@app.get("/upc/getall")
async def get_all_upc_codes(request: apiRequest):
    logRequest(request,send=False)
    result = get_all_codes()
    return result
