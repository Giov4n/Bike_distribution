################################## CITIBIKES DASHBOARD ########################################
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
import streamlit as st
from keplergl import KeplerGl
from streamlit_keplergl import keplergl_static
from datetime import datetime as dt
from numerize.numerize import numerize
from PIL import Image
import io
from pathlib import Path
from database_utils import SecureGridFSHandler, SecureBulkUploader, get_mongo_config
import streamlit.components.v1 as components
from typing import Iterable, Dict, Union

################################## Configuring the Dashboard Page ##############################
st.set_page_config(page_title = 'CitiBike 2022 Strategy Dashboard', layout='wide')

st.title('CitiBike Operational Analysis Dashboard')
st.sidebar.title('Section Selector')
page = st.sidebar.selectbox('Select to View a Dashboard Section',
                           ['Overview', 'Daily Weather vs Rides', 'Trip Duration', 'Stations & Routes', 'Recommendations'])

################################ Initializing Custom Defined Handler ##############################
# Defining a project root for local files
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT/'data'
Files = Union[pd.DataFrame, str]

# Using Mongo handler and config
@st.cache_resource(show_spinner=False)
def get_handler():
    try:
        return SecureGridFSHandler()
    except Exception as e:
        st.warning('MongoDB Handler Unavailable: Falling back to local files.')
        return None

handler = get_handler()
try:
    config = get_mongo_config()
    user_id = config['default_user_id']
except Exception:
    user_id = None

# Loaded data into MongoDB using:
# uploader = SecureBulkUploader()
# config = get_mongo_config()
# user_id = config['default_user_id']
#
# TARGET_FILES = ["Top_Start.csv",
#                "Reduced_Trips.csv",
#                 "CB-Community.jpg"]
#
# results = uploader.upload_files(
# base_folder="./data",
# file_list=TARGET_FILES,
# user_id=user_id,
# parallel=True,
# max_workers=4,
# compress=True
#    )

########################################### Importing Data #######################################

# Custom Function to fetch previously loaded csv files from MongoDB
@st.cache_data(show_spinner=False)
def load_data(dataset_names):
    results = {}

    for dataset_name in dataset_names:
        loaded=False
        
        if handler is not None and user_id is not None:
            try:
                df = handler.load_dataframe(user_id, dataset_name)
                if df is not None:
                    results[dataset_name] = df
                    loaded=True
                    continue
            except Exception:
                pass

            try:
                html = handler.load_map_html(user_id, dataset_name)
                
                if html is not None:
                    if isinstance(html, bytes):
                        html = html.decode('utf-8', errors='replace')
                    
                    if isinstance(html, str) and html.strip():
                        results[dataset_name] = html
                    loaded=True
                    continue
            except Exception:
                pass

            try:
                image_data = handler.load_image(user_id, dataset_name)

                if image_data is not None:
                    results[dataset_name] = image_data
                    loaded=True
                    continue
            except Exception:
                pass

# Falling back to local files if MongoDB does not have them
        csv_path = DATA_DIR / f'{dataset_name}.csv'
        if csv_path.exists():
            results[dataset_name] = pd.read_csv(csv_path)
            continue

        html_path = DATA_DIR / f'{dataset_name}.html'
        if html_path.exists():
            results[dataset_name] = html_path.read_text(encoding='utf-8')
            continue

        image_extensions = ['.jpg' '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp', '.ico']
        for ext in image_extensions:
            image_path = DATA_DIR / f'{dataset_name}{ext}'
            if image_path.exists():
                with open(image_path, 'rb') as f:
                    results[dataset_name] = f.read()
                break
        else:
            results[dataset_name] = None

    return results

# Loading data into memory
datafiles = load_data(['Reduced_Trips', 'CitiBike_Trip_Routes_Map', 'CB-Community.jpg'])

bikeTrips = datafiles['Reduced_Trips']
arcsMap = datafiles['CitiBike_Trip_Routes_Map']
CB_photo = datafiles.get('CB-Community.jpg')

# Message to display if data is not loaded
NotLoaded = [name for name, value in datafiles.items()
            if value is None and name in {'Reduced_Trips', 'CitiBike_Trip_Routes_Map'}]

if NotLoaded:
    st.error(f'ONE OR MORE REQUIRED DATASETS WERE NOT FOUND: {", ".join(NotLoaded)}')
    st.stop()

################################################ Creating Custom Theme #############################################
pio.templates['Dashboard_Theme'] = go.layout.Template(
    layout=go.Layout(colorway= ['darkslateblue', 'steelblue', 'darkslategray', 'darkgoldenrod']))

pio.templates.default = 'Dashboard_Theme'
################################################ Overview Page #############################################
if page == 'Overview':
    st.markdown('#### This dashboard analyzes real CitiBike trip data to suggest strategic operational changes aimed at circumventing bike availability issues voiced by customers.')
    st.markdown("""**This analysis is separated into 4 sections that analyze how each aspect contributes to availability issues:**

    - Daily Rides correlation to weather temperatures
    - Trip duration
    - Geographic routes and stations
    - Conclusions and Recommendations""")

    st.markdown("""**The Section Selector dropdown menu on the left will take you to the analysis details of each aspect. Please note this analysis uses pre-processed data sourced from the CitiBike's website and NOAA API for La Guardia (NY) Weather.**""")


    stationimage = Image.open(io.BytesIO(CB_photo))
    st.image(stationimage, use_container_width=True)

############################################ Weather vs Rides Charts #######################################
elif page == 'Daily Weather vs Rides':
    st.subheader('Can any availability issues be inferred from weather temperatures vs ridership patterns?')

    # Creating side-bar filter
    with st.sidebar:
        season_filter = st.multiselect(label='Select the Season', options=bikeTrips['season'].unique(), default=bikeTrips['season'].unique())
        tripSeasons = bikeTrips.query('season == @season_filter')
        total_rides = float(tripSeasons['daily_rides'].count())
        st.metric(label = 'Total Bike Rides', value=numerize(total_rides))

    col1, col2 = st.columns([3, 1])

    # Using Graph Objects to plot dual axis line chart
    fig_DAline = make_subplots(specs = [[{'secondary_y':True}]])
    fig_DAline.add_trace(go.Scatter(x=tripSeasons['date'], y=tripSeasons['daily_rides'], name='Daily Rides', marker={'color':tripSeasons['daily_rides'], 'color':'navy'}),
                       secondary_y=False)
    fig_DAline.add_trace(go.Scatter(x=tripSeasons['date'], y=tripSeasons['avgTemp'], name='Daily Average Temperatures', marker={'color':tripSeasons['avgTemp'], 'color':'violet'}),
                       secondary_y=True)

    # Updating layout and Axes
    fig_DAline.update_layout(title=dict(text='CitiBike Daily Rides and Average Temperature (2022)', x=0.25, font=dict(size=18, color='navy', family='bree, sans-serif')),
                             legend=dict(yanchor='bottom', y=0.01, xanchor='center', x=0.5, bgcolor='rgba(255,255,255,0.5)'),
                             plot_bgcolor='lightsteelblue',
                             paper_bgcolor='white',
                             height=600)
    fig_DAline.update_yaxes(title_text='Sum of Daily Rides', secondary_y=False, color='navy', title=dict(font=dict(size=16, color='midnightblue')))
    fig_DAline.update_yaxes(title_text='Daily Average Temperature', secondary_y=True, color='violet', title=dict(font=dict(size=16, color='midnightblue')))

    # Creating Average Temperature per User Type Box Plot
    userTemp_box = go.Figure()

    for ride_type in tripSeasons['rideable_type'].unique():
        userTemp_box.add_trace(go.Box(x=tripSeasons[tripSeasons['rideable_type'] == ride_type]['member_casual'], y=tripSeasons[tripSeasons['rideable_type'] == ride_type]['avgTemp'], name=ride_type, boxmean=True))

    userTemp_box.update_layout(title=dict(text='Average Temperature per User', x=0.04, font=dict(size=18, color='navy', family='bree, sans-serif')),
                             legend=dict(yanchor='auto', y=0.4, xanchor='auto', x=0.26, bgcolor='rgba(255,255,255,0.5)'),
                             boxmode='group',
                             plot_bgcolor='lightsteelblue',
                             paper_bgcolor='white',
                             height=600)

    # Calculating Pearson's correlation coefficient
    correlation = tripSeasons['daily_rides'].corr(tripSeasons['avgTemp'])
    
    # Calculating median values for easier interpretation
    member_median = tripSeasons[tripSeasons['member_casual'] == 'member']['avgTemp'].median()
    casual_median = tripSeasons[tripSeasons['member_casual'] == 'casual']['avgTemp'].median()
    
    with st.container():
        with col1:
            st.plotly_chart(fig_DAline, use_container_width=True)
        with col2:
            st.plotly_chart(userTemp_box, use_container_width=True)
        st.caption(f'Daily Rides and Daily Average Temperature have a '
                   f'{"Strong Positive" if correlation > 0.7 else "Moderate Positive" if correlation > 0.4 else "Weak"} Correlation of {correlation:.3f} '
                   f'suggesting members ride at: {member_median:.1f}°C\nand casual users ride at: {casual_median:.1f}°C.')
    
        st.markdown("""*The ride patterns and weather temperatures reflect a strong positive correlation of 0.814, which suggests trips increase at similar levels as temperatures, but decline slightly when temperatures exceed the 30°C. The trip spikes between June and November seem to indicate the availability issues may be prevalent during the warm to cool temperature months.*""")
        st.markdown("""*The box plot confirms that most trips take place during cool to warm weather temperatures with members riding bikes during the cool temperatures with a median of 17.8°C while casual users do at warmer temperatures of about 20.5°C. The  higher concentrated distribution within the interquartile range (13°C to 25°C) indicates casual users have a clear preference for warmer temperatures with a few exceptions reflected as dots at the bottom of low temperature days.*""")

############################################ Trip Duration Charts #########################################
elif page == 'Trip Duration':
    
    st.subheader('What usage patterns can be uncovered from trip duration and riding preferences?')

    # Creating side-bar filter
    with st.sidebar:
        season_filter = st.multiselect(label='Select the Season', options=bikeTrips['season'].unique(), default=bikeTrips['season'].unique())
        tripSeasons = bikeTrips.query('season == @season_filter')
        total_rides = float(tripSeasons['daily_rides'].count())
        st.metric(label = 'Total Bike Rides', value=numerize(total_rides))

    filtered = tripSeasons[tripSeasons['rideable_type'].isin(['classic_bike', 'electric_bike'])]

    # Using Graph Objects to plot Trip Duration line chart
    durline = filtered.groupby('day_name')['trip_duration'].mean().reset_index(name='trip_duration')
    
    duration_line = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02)
    duration_line.add_trace(go.Scatter(x=durline['day_name'], y=durline['trip_duration'], name='Trip Duration', marker={'color':durline['day_name'], 'color':'navy'}), row=1, col=1)
    duration_line.add_trace(go.Histogram(histfunc='count', x=filtered['day_name'], name='Total Trips'), row=2, col=1)

    # Find the max and round up to nearest minute mark
    end_point = (max(filtered['trip_duration'])//60 + 1) * 60
    tick_loc = np.arange(0, end_point + 1, 180)
    tick_labels = [f'{int(s // 60):02d}:{int(s % 60):02d}' for s in tick_loc]

    # Updating layout and Axes
    duration_line.update_layout(title=dict(text='CitiBike Trip Duration per Day of the Week', x=0.25, font=dict(size=18, color='navy', family='bree, sans-serif')),
                 yaxis_title = 'Trip Duration (Minutes)',
                 yaxis = dict(tickmode='array', tickvals=tick_loc, ticktext=tick_labels, range=[0, 2160], title=dict(font=dict(size=14, color='midnightblue'))),
                 legend=dict(yanchor='auto', y=0.99, xanchor='auto', x=0.99, bgcolor='rgba(255,255,255,0.5)'),
                 plot_bgcolor='lightsteelblue',
                 paper_bgcolor='white',
                 height=600)

    # Creating Trip Duration per User Type Box Plot
    user_box = go.Figure()

    for ride_type in filtered['rideable_type'].unique():
        user_box.add_trace(go.Box(x=filtered[filtered['rideable_type'] == ride_type]['member_casual'], y=filtered[filtered['rideable_type'] == ride_type]['trip_duration'], name=ride_type, boxmean=True))

    user_box.update_layout(title=dict(text='Trip Duration per User', x=0.25, font=dict(size=18, color='navy', family='bree, sans-serif')),
                 yaxis_title = 'Trip Duration (Minutes)',
                 yaxis = dict(tickmode='array', tickvals=tick_loc, ticktext=tick_labels, range=[0, 7020], title=dict(font=dict(size=14, color='midnightblue'))),
                             legend=dict(yanchor='auto', y=0.8, xanchor='auto', x=0.3, bgcolor='rgba(255,255,255,0.5)'),
                             boxmode='group',
                             plot_bgcolor='lightsteelblue',
                             paper_bgcolor='white',
                             height=600)
    user_box.update_yaxes(title_text='Trip Duration', title=dict(font=dict(size=16, color='midnightblue')))

    # Calculating number of trips exceeding 24 hours.
    Below1hr = filtered[filtered['trip_duration'] < 10800].shape[0]
    From3to24hrs = filtered.loc[filtered['trip_duration'].between(10800, 86400)].shape[0]
    Over24hrs = filtered[filtered['trip_duration'] > 86400].shape[0]

    col1, col2 = st.columns([3, 1])

    with st.container():
        with col1:
            st.plotly_chart(duration_line, use_container_width=True)
        with col2:
            st.plotly_chart(user_box, use_container_width=True)
        st.caption(f'Total trips below 1 hour sum-up to {Below1hr:,}, between 3 - 24 hours sum up to {From3to24hrs:,}, and over 24 hours sum up to {Over24hrs:,}.')
        st.markdown("""*The line chart suggests that the average trip per day has a short average duration ranging from of 14 to 18 minutes, except on Saturdays and Sundays when the average increases to 20 and 24 minutes respectively suggesting longer commutes or recreations. Since trip counts increase from Thursday to Saturday, this indicates that demand is affected by immediate availability and bike station restocking on these 4 days.*""")
        st.markdown("""*When analyzed from a user perspective; however, members take an average of about 12 minutes per trip while casual users take an average of 27 minutes on classic bikes and 22 minutes on electric bikes which suggesting a clear difference in duration preference. However, there also exists many extremely long rentals that alter total trip durations such as the 259 trips lasting from 3 hours to almost 24 hours. Moreover, CitiBikes Day Pass is likely causing the 142 trips that exceed the 24 hour duration. These data points reveal existing operation issues.*""")
        st.markdown("""**It is important to note that CitiBike's policy indicates that any continuous use over 30 minutes incurs additional fees; however, the lack of data on how bikes are stocked at each station can only suggest there are likely recording issues contributing to the spatial distribution of those points.**""")

######################################## Stations & Routes Map ####################################
elif page == 'Stations & Routes':
    st.subheader('Which are the most popular bike stations pairs and common routes?')

    topStart = pd.DataFrame(bikeTrips['start_station_name'].value_counts().head(20)).reset_index()
    topStart.rename(columns={'start_station_name':'start_station', 'count':'total_trips'}, inplace=True)
    fig_top20 = go.Figure(go.Bar(y=topStart['start_station'], x=topStart['total_trips'], orientation='h', marker={'color':topStart['total_trips'], 'colorscale':'Bluyl'}))
    fig_top20.update_layout(title=dict(text='Most Popular CitiBike Stations', x=0.05, font=dict(size=18, color='navy', family='bree, sans-serif')),
                         yaxis_title = 'Start Stations',
                         yaxis = dict(categoryorder='total ascending', title=dict(font=dict(size=16, color='midnightblue'))),
                         xaxis_title = 'Sum of Trips',
                         xaxis = dict(title=dict(font=dict(size=16, color='midnightblue'))),
                         plot_bgcolor='lightsteelblue',
                         paper_bgcolor='white',
                         height=700)

# Calculating trip percentage of total 20 station trips captured by the top 5 stations.
    Top4_proportion = (topStart['total_trips'].head(4).sum()) / \
                    (bikeTrips['daily_rides'].count())

    col1, col2 = st.columns([3, 1])

    with st.container():
        with col1:
            st.components.v1.html(arcsMap, height=700, scrolling=True)
        with col2:
            st.plotly_chart(fig_top20, use_container_width=True)
        st.caption(f'The Top 4 stations account for {Top4_proportion:.2%} of the all trips recorded in 2022.')

        st.markdown("""*The origin-destination pairs reflected in the map reveal that Hoboken City is the busiest zone with the most intra-zonal flows. The most popular start stations, located near the Hudson River, are also part of the most popular routes: Grove St. PATH to Montgomery St. covering a distance of 6 blocks (895 trips), South Waterfront Walkway – Sinatra Dr. & 1st St to Bloomfield St. & 15th St (with 977 trips), Hoboken Terminal on River St City & Hudson Pl. to Church Sq. Park on 5 St & Park Ave. covering a distance of 11 blocks (968 trips), City Hall on Washington St. & 1 St. to Columbus Park on Clinton St. and 9 St. covering a short distance of 13 blocks (with 923 trips).*""")
        st.markdown("""*Grove St, South Waterfront Walkway, and Hoboken Terminal Stations account for almost about 15.66% of the total bike rental trips. Their strategic location near the Pier A Park combined with the city's transit network gateway offered by the Hoboken Terminal make the small-town charm of Hoboken City an atractive zone. New Jersey City is the second busiest zone and interestingly the least popular zone is New York City, which accounts for most inactive end stations, maybe due to the bridge crossing difficulty.*""")

####################################### Conclusions and Recommendations ###################################
else:
    st.markdown('### Conclusions:')

    day_order = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    time_order = ['Morning', 'Afternoon', 'Evening', 'Night']
    dayProb = bikeTrips.groupby(['day_name', 'time_period'], observed=False)['member_casual'].apply(lambda x: (x=='member').mean()).reset_index(name='P(MemberperDay)')
    day_prob = go.Figure(data=go.Heatmap(z=dayProb['P(MemberperDay)'], x=dayProb['day_name'], y=dayProb['time_period'], hoverongaps=False, text=(dayProb['P(MemberperDay)']*100).values, texttemplate='%{text:.2f}%', textfont={'size':13}))

    day_prob.update_layout(title=dict(text='Member Probability of Riding per Day (2022)', x=0.35, font=dict(size=18, color='navy', family='bree, sans-serif')),
                         xaxis = dict(tickfont=dict(size=15, family='bree, sans-serif', color='midnightblue'), categoryorder='array', categoryarray=day_order),
                         yaxis = dict(tickfont=dict(size=15, family='bree, sans-serif', color='midnightblue'), categoryorder='array', categoryarray=time_order, autorange='reversed'),
                         height=400)

    st.markdown("""
    - Member's preference of cool weather for short trips combined with their preference (probability) to ride bikes during mid-week mornings (Tuesday to Friday) suggests a commuter usage while casual users preference for warm weather for longer trips combined with a higher probability of riding at night time suggests leisure usage, especially on the weekend.
    - Weather correlation can be used to forecast short-term logistics, especially during peak usage months from June to September to circumvent availability issues.""")
    
    st.plotly_chart(day_prob, use_container_width=True)
    st.markdown('### Strategy Recommendations:')
    st.markdown('**CitiBike should focus on the following objectives moving forward to counter distribution inefficiencies**')
    st.markdown("""
    - Consider having dedicated crews in charge of adjusting bike fleet size during early mornings at 6 a.m. to avoid depletion at start stations, especially during warm seasons.
    - Counter availability issues with felxible dock usage and plan maintenance periods on Monday afternoon or evenings and bike fleet replacements during cold months.  
    - Consider redistributing bikes and station resources from low usage areas in New York City to high demand areas near residential areas, waterfront zones and transit hub stations of Hoboken and Jersey City.""")