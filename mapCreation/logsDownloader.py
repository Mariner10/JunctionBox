import os
import pysftp
from stat import S_IMODE, S_ISDIR, S_ISREG
import click
import calendar
from .mapStats import *
import csv
from dotenv import load_dotenv
load_dotenv()

def do_the_map_thing(deviceName):


    remote_logs_directory = os.getenv("ILOGGER_REMOTE_LOGS_DIRECTORY") +f"/{deviceName}/"


    main_path = str(os.path.join(os.path.dirname(os.path.abspath(__file__))))
    localLogPath = f"{main_path}/logs/{deviceName}/"



    def findDay(date):
        year,month,day = (int(i) for i in date.split(' '))    
        dayNumber = calendar.weekday(year, month, day)
        
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday","Sunday"]
        
        return days[dayNumber]



    def downloadFiles(remotedir):
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None    
        sftp=pysftp.Connection(os.getenv("ILOGGER_SERVER_HOSTNAME"),port=int(os.getenv("ILOGGER_SERVER_PORT")) ,username=os.getenv("ILOGGER_SERVER_USERNAME"),cnopts=cnopts)
        print("DOWNLOAD REQUESTED!")
        serverFiles = sftp.listdir(remotedir)
        try:
            clientFiles = os.listdir(localLogPath)
        except FileNotFoundError:
            os.mkdir(localLogPath)
            clientFiles = os.listdir(localLogPath)

        toDownload = []
        final_log = None
        print("\n")
        
        for file in serverFiles:
            if ".csv" in file:
                if file not in clientFiles:
                    toDownload.append(file)
                final_log = file
        
        if len(toDownload) > 1:
            for entry in toDownload:
                try:
                    sftp.get(os.path.join(remotedir, entry), os.path.join(localLogPath, entry), preserve_mtime=False)
                    print(f"Successfully downloaded [ {entry} ]")
                except Exception as e:
                    print(remotedir, entry, e)
                    pass
            return True
        else:
            try:
                sftp.get(os.path.join(remotedir, final_log), os.path.join(localLogPath, final_log), preserve_mtime=False)
                print(f"Successfully downloaded last known file [ {final_log} ]")
                return False
            except Exception as e:
                print(remotedir, final_log, e)

    def aggregate_data(devicepath,devicename):
        csv_Files = []
        new_File = f"{main_path}/map/compiled/{devicename}.csv"
        logPath = f"{devicepath}"
        
        try:
            print("Deleting " + new_File + "...")
            os.remove(new_File)
            print("Done!")
        except FileNotFoundError:
            print("we good")

        isExist = os.path.exists(new_File)

        if isExist == False:
            filename = new_File

            try:
                file = open(filename, 'w')
            except FileNotFoundError:
                print("NEW File : ", filename)
                os.mkdir( f"{main_path}/map/compiled" )
                file = open(filename, 'w')

            file.close()

            fields = ["Date", "Time", "Latitude", "Longitude", "Weekday", "Battery", "inTransit", "Speed", "timeAtLocation","locationType" ,"accuracy"]
            with open(filename, 'w') as csvfile:
                csvwriter = csv.writer(csvfile)
                csvwriter.writerow(fields)
                csvfile.close()
            csvfile.close()


            for path, subdirs, files in os.walk(logPath):
                for name in files:
                    
                    if ".csv" in name:
                        csv_Files.append(str(os.path.join(logPath,name)))
                        

                    else:
                        pass

            print("READING")
            for user_File in csv_Files:
                with open(user_File, 'r') as csvfile:
                    filename = str(user_File).split("/20")
                    filename = "20" + filename[1]
                    filename = filename.split("_")
                    dateFromFilename = filename[0]

                    heading = next(csvfile)
                    csvreader = csv.reader(csvfile)

                    for row in csvreader:

                        

                        latitude = row[1]
                        longitude = row[2]

                        timeElement = row[0]
                        
                        time = str(datetime.fromtimestamp(float(timeElement)).strftime('%I:%M:%S %p'))
                        battery = row[6]
        
                        inTransit = row[5]
                        if "class" in inTransit:
                            inTransit == "False"

                        speed = row[3]
                        timeAtLocation = row[4]
                        locationType = row[7]
                        accuracy = row[9]
                        weekday = findDay(dateFromFilename.replace("-"," "))
                        
                        data = [dateFromFilename, time, latitude, longitude, weekday, battery, inTransit, speed, timeAtLocation,locationType ,accuracy]

                        with open(new_File, 'a') as file:
                                    writer = csv.writer(file)
                                    row = data
                                    
                                    writer.writerow(row)

                        file.close
                    csvfile.close

            print("Wrote all Lines to " + new_File + "...")

        
        else:
            print("I do not know how you managed this... I did at one point though ¯\_(ツ)_/¯")

    def mapCreation(name):
        try:
            print("Map Creation Module Loaded!\nCreating HTML for...\n")
            compiledFilename = f"{main_path}/map/compiled/{name}.csv"
            outputHTML = f"{main_path}/map/{name}/"
            #timeSpentAtHeatmap(compiledFilename,outputHTML,10)
            print("LocationTypeMap!")
            locationTypeMap(compiledFilename,outputHTML)
            print("Done!\nNext is dailyMarkers!")
            dailyMarkers(compiledFilename,outputHTML)
            print("Done!\nNext is heatmap!")
            heatmap(compiledFilename,outputHTML)
            print("Done!\nNext is frequentMarkers!")
            frequentMarkers(compiledFilename,outputHTML,3)
            print("Done!\nNext is timestamp geoJson!!")
            timestampGeoJson(compiledFilename,outputHTML)
            print("All maps created!")

        except Exception as e:
            print(f"An error occured, {e}")
            pass

    def theSauce(device_name):
        isExist = os.path.exists(f"{main_path}/map/{device_name}")
        if not isExist:
            os.mkdir(f"{main_path}/map/{device_name}")

        downloadFiles(remote_logs_directory)
        aggregate_data(localLogPath,device_name)
        mapCreation(device_name)

    theSauce(deviceName)


