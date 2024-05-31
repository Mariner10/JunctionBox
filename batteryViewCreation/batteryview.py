import pandas as pd
import glob
import plotly.express as px
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

def generateBatteryView(CSV_PATH, HTML_PATH, weekOf):
    csv_files = glob.glob(os.path.join(CSV_PATH, '*.csv'))

    # Initialize an empty DataFrame
    df = pd.DataFrame()

    # Read and concatenate all CSV files
    for file in csv_files:
        temp_df = pd.read_csv(file)
        df = pd.concat([df, temp_df], ignore_index=True)

    # Convert EPOCH time to datetime
    df['Time'] = pd.to_datetime(df['Time Object (EPOCH)'], unit='s')

    # Set the datetime as the index
    df.set_index('Time', inplace=True)

    # Filter data for the specified week
    start_date = datetime.strptime(weekOf, '%Y-%m-%d')
    end_date = start_date + timedelta(days=7)
    df_week = df[start_date:end_date]

    # Resample to minute-by-minute intervals, filling gaps with NaN
    df_resampled = df_week['Battery Level (%)'].resample('T').mean()

    # Create the plot
    fig = px.line(df_resampled, title=f'Battery Level Minute-by-Minute ({weekOf} to {end_date.strftime("%Y-%m-%d")})', labels={'index': 'Time', 'value': 'Battery Level (%)'})

    # Update layout to improve readability
    fig.update_layout(
        xaxis_title='Time',
        yaxis_title='Battery Level (%)',
        xaxis_rangeslider_visible=True
    )

    fig.write_html(HTML_PATH, include_plotlyjs='cdn')
