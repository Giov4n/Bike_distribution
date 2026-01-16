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
                           ['Overview', 'Daily Weather vs Rides', 'Stations & Routes', 'Trip Duration', 'Actionable Insights', 'Recommendations'])

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
#                "CB-Community.jpg",
#                "Fleet_Plan.csv",
#                "Restocking_Plan.csv",
#                "Water_Stations.csv"]
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
datafiles = load_data(['Reduced_Trips', 'Fleet_Plan', 'Restocking_Plan', 'Water_Stations', 'CitiBike_Trip_Routes_Map', 'CB-Community.jpg'])

bikeTrips = datafiles['Reduced_Trips']
fleetPlan = datafiles['Fleet_Plan']
restockingPlan = datafiles['Restocking_Plan']
waterStations = datafiles['Water_Stations']
arcsMap = datafiles['CitiBike_Trip_Routes_Map']
CB_photo = datafiles.get('CB-Community.jpg')

# Message to display if data is not loaded
NotLoaded = [name for name, value in datafiles.items()
            if value is None and name in {'Reduced_Trips', 'Fleet_Plan', 'Restocking_Plan', 'Water_Stations', 'CitiBike_Trip_Routes_Map'}]

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
    st.markdown("""**This analysis is separated into 5 sections that analyze how each aspect contributes to availability issues:**

    - Daily rides correlation to weather temperatures
    - Trip duration
    - Geographic routes and stations
    - Actionable Insights
    - Conclusions and Recommendations""")

    st.markdown("""**👈 The Section Selector dropdown menu on the left will take you to the analysis details of each aspect. Please note this analysis uses pre-processed data sourced from the CitiBike's website and NOAA API for La Guardia (NY) Weather, which included bike type; start station name, ID, lattitude and longitude; end station name, ID, lattitude and longitude; trip start and end times; user type and average temperature.**""")


    stationimage = Image.open(io.BytesIO(CB_photo))
    st.image(stationimage, use_container_width=True)

############################################ Weather vs Rides Charts #######################################
elif page == 'Daily Weather vs Rides':
    st.subheader('Can any user preference be inferred from daily 🚲 rides vs weather temperatures 🌦️?')

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
    fig_DAline.update_layout(title=dict(text='CitiBike Daily Rides Vs Average Temperature (2022)', x=0.25, font=dict(size=15, color='navy', family='bree, sans-serif')),
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

    userTemp_box.update_layout(title=dict(text='Riding Temperature per User', x=0.5, xanchor= 'center', font=dict(size=15, color='navy', family='bree, sans-serif')),
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
                   f'and box plot suggests members ride at: {member_median:.1f}°C\nwhile casual users ride at: {casual_median:.1f}°C.')
    
        st.markdown("""*The daily rides and weather temperatures strong positive correlation of 0.814 suggests trips increase at similar levels as temperatures, but decline slightly when temperatures exceed the 30°C. The trip spikes between May and November seem to indicate the availability issues may be prevalent during the warm to cool temperature months.*""")
        st.markdown("""*The box plot lower whiskers confirms members are more resilient to low temperatures, while the interquartile range boxes confirm that most trips take place during warm to cool weather temperatures with members riding bikes at a median of 17.8°C and casual users prefering warmer temperatures with a median of about 20.5°C. The presence of docked bikes for casual users suggests bikes used for recreational purposes remain locked mostly during high season months.*""")

######################################## Stations & Routes Map ####################################
elif page == 'Stations & Routes':
    st.subheader('Which are the most popular bike stations pairs and common routes 🏙️?')

    topStart = pd.DataFrame(bikeTrips['start_station_name'].value_counts().head(20)).reset_index()
    topStart.rename(columns={'start_station_name':'start_station', 'count':'total_trips'}, inplace=True)
    fig_top20 = go.Figure(go.Bar(y=topStart['start_station'], x=topStart['total_trips'], orientation='h', marker={'color':topStart['total_trips'], 'colorscale':'Bluyl'}))
    fig_top20.update_layout(title=dict(text='Most Popular Stations', x=0.25, font=dict(size=15, color='navy', family='bree, sans-serif')),
                         yaxis_title = 'Start Stations',
                         yaxis = dict(categoryorder='total ascending', title=dict(font=dict(size=16, color='midnightblue'))),
                         xaxis_title = 'Total Trips',
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

        st.markdown("""*The origin-destination pairs connected by the map arcs ⋒ reveal that Hoboken City is the busiest zone with the most intra-zonal flows. The most popular start stations, located near the Hudson River, are also part of the most popular routes: Grove St. PATH to Montgomery St. covering a distance of 6 blocks (895 trips), South Waterfront Walkway – Sinatra Dr. & 1st St to Bloomfield St. & 15th St covering a distance of 18 blocks (with 977 trips), Hoboken Terminal on River St City & Hudson Pl. to Church Sq. Park on 5 St & Park Ave. covering a distance of 11 blocks (968 trips), City Hall on Washington St. & 1 St. to Columbus Park on Clinton St. and 9 St. covering a short distance of 13 blocks (with 923 trips).*""")
        st.markdown("""*Grove St, South Waterfront Walkway, and Hoboken Terminal Stations account for almost about 15.66% of the total bike rental trips. Their strategic location near the water combined with the city's transit network gateway offered by the Hoboken Terminal make the small-town charm of Hoboken City an atractive zone. New Jersey City is the second busiest zone and interestingly the least connected zone is New York City, which accounts for most inactive end stations suggesting a bridge crossing difficulty.*""")

############################################ Trip Duration Charts #########################################
elif page == 'Trip Duration':
    
    st.subheader('What usage patterns can be uncovered from trip duration ⌛?')

    # Creating side-bar filter
    with st.sidebar:
        season_filter = st.multiselect(label='Select the Season', options=bikeTrips['season'].unique(), default=bikeTrips['season'].unique())
        tripSeasons = bikeTrips.query('season == @season_filter')
        total_rides = float(tripSeasons['daily_rides'].count())
        st.metric(label = 'Total Bike Rides', value=numerize(total_rides))

    filtered = tripSeasons[tripSeasons['rideable_type'].isin(['classic_bike', 'electric_bike'])]

    weekday_order = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    
    # Using Graph Objects to plot Trip Duration line chart
    durline = filtered.groupby('day_name')['trip_duration'].mean().reset_index(name='trip_duration')
    durline['day_name'] = pd.Categorical(durline['day_name'], categories=weekday_order, ordered=True)
    durline = durline.sort_values('day_name').reset_index(drop=True)
    
    duration_line = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02)
    duration_line.add_trace(go.Scatter(x=durline['day_name'], y=durline['trip_duration'], name='Trip Duration', marker={'color':durline['day_name'], 'color':'navy'}), row=1, col=1)
    duration_line.add_trace(go.Histogram(histfunc='count', x=filtered['day_name'], name='Total Trips'), row=2, col=1)

    # Find the max and round up to nearest minute mark
    end_point = (max(filtered['trip_duration'])//60 + 1) * 60
    tick_loc = np.arange(0, end_point + 1, 180)
    tick_labels = [f'{int(s // 60):02d}:{int(s % 60):02d}' for s in tick_loc]

    # Updating layout and Axes
    duration_line.update_layout(title=dict(text='Trip Duration per Day of the Week', x=0.5, xanchor= 'center', font=dict(size=15, color='navy', family='bree, sans-serif')),
                 yaxis_title = 'Trip Duration (Minutes)',
                 yaxis = dict(tickmode='array', tickvals=tick_loc, ticktext=tick_labels, range=[0, 2_160], title=dict(font=dict(size=14, color='midnightblue'))),
                 legend=dict(yanchor='auto', y=0.99, xanchor='auto', x=0.99, bgcolor='rgba(255,255,255,0.5)'),
                 plot_bgcolor='lightsteelblue',
                 paper_bgcolor='white',
                 height=600)

    # Creating Trip Duration per User Type Box Plot
    user_box = go.Figure()

    for ride_type in filtered['rideable_type'].unique():
        user_box.add_trace(go.Box(x=filtered[filtered['rideable_type'] == ride_type]['member_casual'], y=filtered[filtered['rideable_type'] == ride_type]['trip_duration'], name=ride_type, boxmean=True))

    user_box.update_layout(title=dict(text='Trip Duration per User', x=0.5, xanchor= 'center', font=dict(size=15, color='navy', family='bree, sans-serif')),
                 yaxis_title = 'Trip Duration (Minutes)',
                 yaxis = dict(tickmode='array', tickvals=tick_loc, ticktext=tick_labels, range=[0, 7_020], title=dict(font=dict(size=14, color='midnightblue'))),
                             legend=dict(yanchor='auto', y=0.8, xanchor='auto', x=0.3, bgcolor='rgba(255,255,255,0.5)'),
                             boxmode='group',
                             plot_bgcolor='lightsteelblue',
                             paper_bgcolor='white',
                             height=600)
    user_box.update_yaxes(title_text='Trip Duration', title=dict(font=dict(size=16, color='midnightblue')))

    # Calculating number of trips exceeding 24 hours.
    Below1hr = filtered[filtered['trip_duration'] < 3_600].shape[0]
    From1to24hrs = filtered.loc[filtered['trip_duration'].between(3_600, 86_400)].shape[0]
    Over24hrs = filtered[filtered['trip_duration'] > 86_400].shape[0]

    col1, col2 = st.columns([3, 1])

    with st.container():
        with col1:
            st.plotly_chart(duration_line, use_container_width=True)
        with col2:
            st.plotly_chart(user_box, use_container_width=True)
        st.caption(f'Total trips below 1 hour sum-up to {Below1hr*12.5:,.0f}, between 1 - 24 hours sum up to {From1to24hrs*12.5:,.0f}, and over 24 hours sum up to {Over24hrs*12.5:,.0f}.')
        st.markdown("""*Trips have a short average duration of about 15 minutes, except on Saturdays and Sundays when the average increases to 18 and 22 minutes respectively, suggesting longer commutes or recreations. The line-bar chart suggests there is a high flow of bike usage during weekdays, especially Wednesdays, when bike volume is high and trip duration is low. When analyzed from a user perspective; however, members take an average of about 12 minutes per trip while casual users take an average of 27 minutes on classic bikes and 22 minutes on electric bikes, suggesting depletion at popular start stations. The trip count increase from Thursday to Saturday indicates that demand is affected by immediate availability and bike station restocking on these 4 days highlighting the need for active rebalancing, especially in start stations near touristic sites.*""")
        st.markdown("""*There also exists many extremely long rentals that alter total trip durations such as the 18,788 trips lasting from 1 hours to almost 24 hours. The CitiBikes Day Pass is also likely causing the 1,775 trips that exceed the 24 hour duration.*""")
        st.markdown("""**🤔 The effect of CitiBike's 30-minute policy on spatial patterns remains unclear due to the lack of data on customer complaints and bike stocking at station.**""")

######################################## Actionable Insights ####################################
elif page == 'Actionable Insights':
    st.markdown('### How much to scale back between November and April?')

    st.markdown("""Given the significant fluctuations of Citibike's monthly demand, we suggest transitioning to a dynamic month-by-month scaling strategy. The below table outlines a strategic monthly fleet reduction based on daily ride demand for each bike type indexed against the August high, with a safe margin to accommodate service level variations. Since both bike types follow similar seasonal patterns, expanding in December and contracting in April with further decreases afterwards, we can safely maintain November service levels with approximately 74% of the fleet size. This intentional reduction creates a maintenance and bike substitution window that does not compromise the user experience.""")

    st.dataframe(fleetPlan)
    st.markdown("""The above also confirms that our fleet is currently operating with significant seasonal inefficiency across CitiBike stations, with waterfront stations experiencing the highest concentration of activity, suggesting suboptimal resource allocation. It's thus advisable to relocate water stations along the waterfront.""")

    st.markdown('### How many more stations to add along the water?')
    summary_df = waterStations[waterStations['section']=='summary']
    waterStations_df = waterStations[waterStations['section']=='scenario_options']

    col1, col2, col3, col4 = st.columns(4)
    with st.container():
        with col1:
            st.metric(label='Total Stations', value=f"{summary_df.loc[summary_df.metric == 'Total Stations', 'value'].iloc[0]}")
        with col2:
            st.metric(label='Existing Water Stations', value=f"{summary_df.loc[summary_df.metric == 'Existing Water Stations', 'value'].iloc[0]}")
        with col3:
            st.metric(label='Share of Total Stations', value=f"{summary_df.loc[summary_df.metric == 'Existing Water Stations Share of Total Stations', 'value'].iloc[0]}")
        with col4:
            st.metric(label='Trip Share of Existing Water Stations', value=f"{summary_df.loc[summary_df.metric == 'Trip Share of Existing Water Stations', 'value'].iloc[0]}")
        st.dataframe(waterStations_df[['Load Multiplier', 'Required Water Stations', 'Additional Water Stations']].set_index('Load Multiplier'))
        st.markdown("""Currently, there are 21 waterfront stations located within 300 meters of the water, which represent approximately 6.56% of the total operating stations. However, these stations account for over 1/3 of all trips, indicating that each waterfront station received approximately 5.6 more trips than the average station. Based on this information, I calculated the number of stations that could be relocated to the waterfront while maintaining the total number of stations at 320 using a load multiplier that safely reduces the existing 5.6x load to a maximum of 3x. To operate effectively at 3x load, we would need a total of 40 waterfront stations. Since we already have 21, this means we need to relocate 19 additional stations along the water. Start with this as the targeted pilot plan that relocates 19 of the existing spatially close non-water stations that are experiencing low activity and increase it to 98 progressively so as to not affect other non-waterfront station operations.""")

########################################### Recommendations #######################################
else:
    st.markdown('### Stations Recommendations:')

    day_order = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    time_order = ['Morning', 'Afternoon', 'Evening', 'Night']
    dayProb = bikeTrips.groupby(['day_name', 'time_period'], observed=False)['member_casual'].apply(lambda x: (x=='member').mean()).reset_index(name='P(MemberperDay)')
    day_prob = go.Figure(data=go.Heatmap(z=dayProb['P(MemberperDay)'], x=dayProb['day_name'], y=dayProb['time_period'], hoverongaps=False, text=(dayProb['P(MemberperDay)']*100).values, texttemplate='%{text:.2f}%', textfont={'size':13}))

    day_prob.update_layout(title=dict(text='Member Probability of Riding per Day (2022)', x=0.5, xanchor= 'center', font=dict(size=18, color='navy', family='bree, sans-serif')),
                         xaxis = dict(tickfont=dict(size=15, family='bree, sans-serif', color='midnightblue'), categoryorder='array', categoryarray=day_order),
                         yaxis = dict(tickfont=dict(size=15, family='bree, sans-serif', color='midnightblue'), categoryorder='array', categoryarray=time_order, autorange='reversed'),
                         height=400)

    st.markdown("""
    - The below heatmap confirms member users have a preference (probability) to ride bikes during mid-week mornings (Tuesday to Friday), which when combined with the cool weather and short trip preference previously observed suggests a commuter usage. While casual users seem to rent bike for leisure purposes given their warm weather, longer trips, and night riding preference especially on the weekend.""")
    
    st.plotly_chart(day_prob, use_container_width=True)
    
    st.markdown("""Our model's stability depends on 3 high-density hubs that require close monitoring to ensure they remain stocked before and throughout the business day: Grove St. PATH (42,550 average daily starts), South Waterfront Walkway (34,200) and Hoboken Terminal (33,000). These stations experience a very high demand that will require overnight and early morning re-stocking to prevent depletion. Additionally, Hamilton Park and Marin Light Rail show a demand time compression of 36.5% and 35.8% respectively. This indicates that these stations deplete faster than the operations team can handle. Failure to implement advanced predictive stocking at these nodes will result in system wide availability failures and lost revenue.""")

    st.dataframe(restockingPlan)
    st.subheader('**Additional Strategy Recommendations: CitiBike should focus on the following objectives moving forward to counter distribution inefficiencies.**')

    st.markdown("""
    - Improve the model's adaption to seasonal volatility by correlating bike ride trends with weather forecasts to plan short-term logistics, especially during peak usage months from June to October and for newly relocated waterfront stations.
    - Prioritize dock usage in residential areas and transit hubs during winter and in leisure areas starting in May when temperatures cross the 15°C threshold to manage the rapid surge in demand.
    - Consider having dedicated crews in charge of adjusting bike fleet size during early mornings at 6 a.m. to avoid depletion at start stations, especially from Wednesdays to Saturdays.
    - Counter availability issues with flexible dock usage combined with planned maintenance periods during night windows and frequent electric bikes rotation during the extreme cold identified in February.
    - Implement user alerts to guide riders towards nearby stations with available docks during peak traffic times.
    - Consider redistributing other station resources from low usage areas in New York City to other high demand zones near residential areas and transit hubs.
    - Overstock stations near other touristic attractions and incentivize riders to return bikes to low-stock stations with ride credits or discounts, special packages and special events at unpopular stations that encourage a balance bike use.""")