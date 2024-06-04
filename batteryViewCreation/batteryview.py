import os
import glob
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

def generateBatteryView(CSV_PATH, HTML_PATH, weekOf):

    csv_files = glob.glob(os.path.join(CSV_PATH, '*.csv'))

    data_frames = []

    for file in csv_files:
        temp_df = pd.read_csv(file)
        data_frames.append(temp_df)

    df = pd.concat(data_frames, ignore_index=True)

    df['Time'] = pd.to_datetime(df['Time Object (EPOCH)'], unit='s')

    df.set_index('Time', inplace=True)
    df.sort_index(inplace=True)
    df = df[~df.index.duplicated(keep='first')]

    start_date = datetime.strptime(weekOf, "%m-%d-%Y")
    end_date = start_date + timedelta(days=7)

    nearest_start = df.index.asof(start_date)
    nearest_end = df.index.asof(end_date)

    if pd.isna(nearest_start) or pd.isna(nearest_end):
        print(f"No data available for the specified week {start_date} to {end_date}.")
        return

    df_week = df.loc[nearest_start:nearest_end]


    if df_week.empty:
        print("No data available for the specified week.")
        return

    df_resampled = df_week['Battery Level (%)'].resample('T').mean()

    fig = px.line(df_resampled, title=f'Battery Level Minute-by-Minute ({weekOf} to {end_date.strftime("%m-%d-%Y")})',
                  labels={'index': 'Time', 'value': 'Battery Level (%)'})


    fig.update_layout(
        xaxis_title='Time',
        yaxis_title='Battery Level (%)',
        xaxis_rangeslider_visible=True
    )

    fig.write_html(HTML_PATH, include_plotlyjs='cdn')
