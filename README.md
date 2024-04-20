
This API will not serve much purpose for many, beyond that of viewing what I have created. But there are some interesting quirks it has I'll explain here.
 
### Instructions
You will need to create your `.env` file, these are the fields it requires:
```python
# SERVER SIDE:

# Authentication
USERNAME = ""

FULL_NAME = ""

EMAIL = ""

SECRET_KEY= ""

CLI_KEY = ""

API_KEY = ""

# Directory Locations
SSL_KEYFILE = ""

SSL_CERT = ""

# Strings
NTFY_MESSAGES = ""

NTFY_ALERTS = ""

  
# CLIENT SIDE:

API_URL = 'http://localhost:8000'

API_USER_PASS = ''
```

Make sure `API_KEY` is a hashed version of `API_USER_PASS` (generated using `connection.get_password_hash(os.getenv(API_USER_PASS))`)

You will need an `HTML/` directory to place your HTML landing page in, as I will not be including my own.

If you plan on using any of the `zone_endpoint` urls you need to make sure you actually have declared zones in the `JSON/Zones.json` file. You can do this at [the GeoJson website](https://geojson.io/#map=2/0/20). 

You also will need to create a `userFiles/` and the `ZipFiles/` directories, the `userFiles/` directory acts as a workspace and the `ZipFiles/` a storage place for the assembled zip files.

### Usage
Start the server with `uvicorn main:app --reload --log-level debug` then go to http://127.0.0.1:8000/docs#/ to see the usage and information about the endpoints you can call.
