import pandas as pd
import glob
import plotly.express as px
import os
from dotenv import load_dotenv
load_dotenv()

def generateBatteryView(CSV_PATH,HTML_PATH):

    csv_files = glob.glob(os.path.join(CSV_PATH,'*.csv'))

    df = pd.DataFrame()

    for file in csv_files:
        temp_df = pd.read_csv(file)
        df = pd.concat([df, temp_df], ignore_index=True)


    df['Time'] = pd.to_datetime(df['Time Object (EPOCH)'], unit='s')


    df.set_index('Time', inplace=True)

    df_resampled = df['Battery Level (%)'].resample('T').mean()

    fig = px.line(df_resampled, title='Battery Level Minute-by-Minute', labels={'index': 'Time', 'value': 'Battery Level (%)'})

    fig.update_layout(
        xaxis_title='Time',
        yaxis_title='Battery Level (%)',
        xaxis_rangeslider_visible=True
    )

    
    fig.write_html(HTML_PATH)
