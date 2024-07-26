import os
import glob
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

def generateBatteryDayView(CSV_PATH, HTML_PATH, dayOf):

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

    start_date = datetime.strptime(dayOf, "%Y-%m-%d")
    end_date = start_date + timedelta(days=1)

    nearest_start = df.index.asof(start_date)
    nearest_end = df.index.asof(end_date)

    if pd.isna(nearest_start) or pd.isna(nearest_end):
        print(f"No data available for the specified day {start_date}.")
        return "<p>No data available for the specified day.</p>"

    df_day = df.loc[nearest_start:nearest_end]

    if df_day.empty:
        print("No data available for the specified day.")
        return "<p>No data available for the specified day.</p>"

    df_resampled = df_day['Battery Level (%)'].resample('T').mean()

    fig = px.line(df_resampled, title=f'Battery Level Minute-by-Minute ({dayOf})',
                labels={'index': 'Time', 'value': 'Battery Level (%)'})

    fig.update_layout(
        xaxis_title='Time',
        yaxis_title='Battery Level (%)',
        xaxis_rangeslider_visible=True
    )

    fig.write_html(HTML_PATH,include_plotlyjs='cdn')

