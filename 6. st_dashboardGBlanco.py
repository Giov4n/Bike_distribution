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

################################## Defining Session Onboarding Functions##############################
# Defining function to start session
def new_session():
    if st.query_params.get('onboarding') == 'done':
        st.session_state['onboarding_complete'] = True
        
    defaults = {
        'onboarding_complete': False,
        'onboarding_step': 0,
        'show_help': True}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

new_session()

ONBOARDING_STEPS = [{'title': 'Welcome! 👋', 'description': "This dashboard helps you explore CitiBike's trip data with key metrics designed to capture insights and suggest strategic operational changes. The insights shown on the charts are based on an 8% representative sample of the full dataset to balance performance and accuracy. The patterns, trends and directional changes reflect the overall population, but exact totals are only shown on the sidebar and chart annotations. Chart figures that appear upon hovering can be multiplied by 12.5 to derive the complete dataset figure."},
                    {'title': 'Navigation', 'description': "👈 Use the sidebar to filter data and switch views. The **Section Selector** dropdown menu on the left will take you to the analysis details of each aspect starting at Overview."},
                    {'title': 'Interacting with Charts', 'description': "Hover over charts to see details. You can also zoom on the data by selecting directly on the chart the part you would like to view in more detail. Keep in mind charts and tables are designed for exploratory analysis that preserves meaningful patterns."},
                    {'title': "Ready to enjoy?", 'description': "All Visuals update automatically. You can now explore the dashboard on your own."}]

def main():
    st.title('CitiBike Operational Analysis Dashboard')

    #blocking dashboard until unboarding is complete
    if not st.session_state.onboarding_complete:
        with st.expander('How to read this dashboard', expanded=True):
            step = st.session_state.onboarding_step
            step_data = ONBOARDING_STEPS[step]
            st.subheader(step_data['title'])
            st.write(step_data['description'])

            col1, col2, = st.columns(2)

            with col1:
                if step > 0:
                    if st.button('Back'):
                        st.session_state.onboarding_step -= 1
                        st.rerun()

            with col2:
                if step < len(ONBOARDING_STEPS) - 1:
                    if st.button('Next'):
                        st.session_state.onboarding_step += 1
                        st.rerun()
                else:
                    if st.button('Finish Onboarding'):
                        st.session_state.onboarding_complete = True
                        st.query_params['onboarding'] = 'done'
                        st.rerun()

    if st.sidebar.button('Restart Onboarding'):
        st.session_state.onboarding_complete = False
        st.session_state.onboarding_step = 0
        st.query_params.clear()
        st.rerun()

if __name__ == '__main__':
        main()

################################## Configuring the Dashboard Page ##############################
st.set_page_config(page_title = 'CitiBike 2022 Strategy Dashboard', layout='wide')

st.sidebar.info('Choose an option from this sidebar to update the dashboard.')
st.sidebar.title('Section Selector')
page = st.sidebar.selectbox('Select to View a Dashboard Section',
                           ['Overview', 'Daily Weather vs Rides', 'Stations & Routes', 'Trip Duration', 'Actionable Insights', 'Recommendations'], help='Select one to switch views.')

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
#                "Water_Stations.csv",
#                "CitiBike_Trip_Routes_Map.html"]
#
# results = uploader.upload_files(
# base_folder="./data",
# file_list=TARGET_FILES,
# user_id=user_id,
# parallel=True,
# max_workers=4,
#compress=True)

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
    st.markdown('#### This dashboard analyzes real CitiBike trip data to suggest strategic operational changes that enhance net income and address logistical issues with bike availability voiced by customers.')
    st.markdown("""**The analysis is separated into 5 sections that examines how each aspect contributes to availability issues:**

    - Daily rides correlation to weather temperatures
    - Geographic routes and stations
    - Trip duration
    - Actionable Insights
    - Recommendations""")

    st.markdown("""**Please note this analysis uses pre-processed data sourced from the CitiBike's website and NOAA's API for NY weather data, which included bike type; start station name, ID, lattitude and longitude; end station name, ID, lattitude and longitude; trip start and end times; user type and average temperature.**""")


    stationimage = Image.open(io.BytesIO(CB_photo))
    st.image(stationimage, use_container_width=True)

############################################ Weather vs Rides Charts #######################################
elif page == 'Daily Weather vs Rides':
    st.subheader('Identifying 🌦️ weather related trip patterns and seasonal surges 🚲.')

    # Creating side-bar filter
    with st.sidebar:
        season_filter = st.multiselect(label='Select the Season', options=bikeTrips['season'].unique(), default=bikeTrips['season'].unique(), help='Select Winter to filter for December to February, Spring for March to May, Summer for June to August and Fall for September to November.')
        tripSeasons = bikeTrips.query('season == @season_filter')
        total_rides = float(tripSeasons['daily_rides'].count()*12.5)
        st.metric(label = 'Total Bike Rides', value=numerize(total_rides), help='This number reflects the full dataset ride count figure, while the chart is a reduced representation that can be multiplied by 12.5 to derive the complete dataset figure.')

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

    # Calculating Pearson's correlation coefficient
    correlation = tripSeasons['daily_rides'].corr(tripSeasons['avgTemp'])
    
    # Calculating median values for easier interpretation
    member_median = tripSeasons[tripSeasons['member_casual'] == 'member']['avgTemp'].median()
    casual_median = tripSeasons[tripSeasons['member_casual'] == 'casual']['avgTemp'].median()

    fig_DAline.add_annotation(text=f'Exhibiting a {"Strong Positive" if correlation > 0.7 else "Moderate Positive" if correlation > 0.4 else "Weak"} Correlation of {correlation:.3f}', xref='paper', yref='paper', x=0.001, y=1.01, showarrow=False, font=dict(size=16, color='indigo'))

    # Creating Average Temperature per User Type Box Plot
    userTemp_box = go.Figure()

    for ride_type in tripSeasons['rideable_type'].unique():
        userTemp_box.add_trace(go.Box(x=tripSeasons[tripSeasons['rideable_type'] == ride_type]['member_casual'], y=tripSeasons[tripSeasons['rideable_type'] == ride_type]['avgTemp'], name=ride_type, boxmean=True))

    userTemp_box.update_layout(title=dict(text='Riding Temperature per User', x=0.5, xanchor= 'center', font=dict(size=15, color='navy', family='bree, sans-serif')),
                             legend=dict(yanchor='auto', y=0.00, xanchor='auto', x=.51, bgcolor='rgba(255,255,255,0.5)'),
                             boxmode='group',
                             plot_bgcolor='lightsteelblue',
                             paper_bgcolor='white',
                             height=600)

    userTemp_box.add_annotation(text=f'Members ride at: {member_median:.1f}°C<br> Casual users do at: {casual_median:.1f}°C.', xref='paper', yref='paper', x=0.5, y=1.07, xanchor='center', showarrow=False, font=dict(size=14, color='indigo'))
    
    with st.container():
        with col1:
            st.plotly_chart(fig_DAline, use_container_width=True)
        with col2:
            st.plotly_chart(userTemp_box, use_container_width=True)
    
        st.markdown("""*The analysis started by understanding trip patterns by correlating daily rides with weather temperatures. These showed a strong positive correlation of 0.814 suggesting trips increase at similar levels as temperatures, but decline slightly when temperatures exceed the 30°C. The trip spikes between May and November seem to indicate the availability issues may be prevalent during the warm to cool temperature months.*""")
        st.markdown("""*The box plot lower whiskers confirms members are more resilient to low temperatures, while the interquartile range boxes confirm that most trips take place during warm to cool weather temperatures with members riding bikes at a median of 17.8°C and casual users prefering warmer temperatures with a median of about 20.5°C. The presence of docked bikes for casual users suggests bikes used for recreational purposes remain locked mostly during high season months.*""")

######################################## Stations & Routes Map ####################################
elif page == 'Stations & Routes':
    st.subheader('Unveiling high-traffic bike stations, typical routes and zones favored by users 🏙️.')

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
        st.markdown(f':green[The Top 4 stations account for {Top4_proportion:.2%} of the all trips recorded in 2022.]')

        st.markdown("""*Let's now look at station and route activity. The origin-destination pairs connected by the map arcs ⋒ reveal that Hoboken City is the busiest zone with the most intra-zonal flows. The most popular start stations, located near the Hudson River, are also part of the most popular routes:
        - Grove St. PATH to Montgomery St. covering a distance of 6 blocks (895 trips)
        - South Waterfront Walkway – Sinatra Dr. & 1st St to Bloomfield St. & 15th St covering a distance of 18 blocks (with 977 trips)
        - Hoboken Terminal on River St & Hudson Pl. to Church Sq. Park on 5 St & Park Ave. covering a distance of 11 blocks (968 trips)
        - Hoboken Terminal on Hudson St. & Hudson Place to Columbus Park on Clinton St. & 9 St. covering a short distance of 15 blocks (with 977 trips).*""")
        st.markdown("""*These 4 Stations account for almost approximately 15.66% of the total bike rental trips. Their strategic location near the water combined with the city's transit network gateway offered by the Hoboken Terminal make the small-town charm of Hoboken City an atractive zone. New Jersey City is the second busiest zone and interestingly the least connected zone is New York City, which accounts for most inactive end stations suggesting a bridge crossing difficulty.*""")

############################################ Trip Duration Charts #########################################
elif page == 'Trip Duration':
    
    st.subheader('Revealing initial clues on availability issues based on weekly ridership duration ⌛.')

    # Creating side-bar filter
    with st.sidebar:
        season_filter = st.multiselect(label='Select the Season', options=bikeTrips['season'].unique(), default=bikeTrips['season'].unique(), help='Select Winter to filter for December to February, Spring for March to May, Summer for June to August and Fall for September to November.')
        tripSeasons = bikeTrips.query('season == @season_filter')
        total_rides = float(tripSeasons['daily_rides'].count()*12.5)
        st.metric(label = 'Total Bike Rides', value=numerize(total_rides), help='This number reflects the full dataset ride count figure, while the chart is a reduced representation that can be multiplied by 12.5 to derive the complete dataset figure.')

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
    end_point = (max(filtered['trip_duration'])//60 + 1) * 60 if not filtered.empty else 60
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

    # Calculating number of trips exceeding 24 hours.
    Below1hr = (filtered['trip_duration'] < 3_600).sum()
    From1to24hrs = filtered['trip_duration'].between(3_600, 86_400).sum()
    Over24hrs = (filtered['trip_duration'] > 86_400).sum()
    
    duration_line.add_annotation(text=f'Total trips between 1 - 24 hours: {From1to24hrs*12.5:,.0f}<br>over 24 hours: {Over24hrs*12.5:,.0f}', xref='paper', yref='paper', x=0.001, y=1.02, showarrow=False, font=dict(size=14, color='black'))
    
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

    col1, col2 = st.columns([3, 1])

    with st.container():
        with col1:
            st.plotly_chart(duration_line, use_container_width=True)
        with col2:
            st.plotly_chart(user_box, use_container_width=True)
        st.markdown("""*The operational dynamic is better understood when considering the duration of trips each day. Trips have a short average duration of about 15 minutes, except on Saturdays and Sundays when the average increases to 18 and 22 minutes respectively, suggesting longer commutes or recreations. The line-bar chart suggests there is a high flow of bike usage during weekdays, especially Wednesdays, when bike volume is high and trip duration is low. When analyzed from a user perspective; however, members take an average of about 12 minutes per trip while casual users take an average of 27 minutes on classic bikes and 22 minutes on electric bikes, suggesting depletion at popular start stations. Moreover, the trip count increase from Wednesday to Saturday indicates that demand is affected by immediate availability and bike station restocking on these 4 days highlighting the need for active rebalancing, especially in start stations near touristic sites.*""")
        st.markdown("""*There also exists many extremely long rentals that alter total trip durations such as the 18,788 trips lasting from 1 hours to almost 24 hours. The CitiBikes Day Pass is also likely causing the 1,775 trips that exceed the 24 hour duration.*""")
        st.markdown("""**🤔 The effect of CitiBike's 30-minute policy on spatial patterns remains unclear due to the lack of data on customer complaints and bike stocking at station.**""")

######################################## Actionable Insights ####################################
elif page == 'Actionable Insights':
    st.markdown('### Reducing costs by scaling back between November and April.')

    st.markdown("""While analyzing monthly demand it was evident significant fluctuations existed as shown by the average daily rides shown below. In sight of this, we suggest transitioning to a dynamic month-by-month scaling strategy that reduces operational costs. The below table outlines a strategic monthly fleet reduction based on daily ride demand for each bike type indexed against the August high, with a safe margin to accommodate service level variations. Since both bike types follow similar seasonal patterns, expanding in December and contracting in April with further decreases afterwards, we can safely maintain November service levels with approximately 74% of the fleet size. This intentional reduction creates a maintenance and bike substitution window that does not compromise the user experience.""")

    st.dataframe(fleetPlan)
    st.markdown("""The above also confirms that our fleet is currently operating with significant seasonal inefficiency across CitiBike stations, with waterfront stations experiencing the highest concentration of activity, suggesting suboptimal resource allocation. It's thus advisable to relocate certain water stations along the waterfront.""")

    st.markdown('### Enhancing resilience to seasonal fluctuations by adding more stations along the water.')
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
        st.markdown("""Currently, there are 21 waterfront stations located within 300 meters of the water, which represent approximately 6.56% of the total operating stations. However, these stations account for over 1/3 of all trips, indicating that each waterfront station received approximately 5.6 more trips than the average station. Based on this information, the number of stations that could be relocated to the waterfront while maintaining the total number of stations at 320 was calculated using a load multiplier that safely reduces the existing 5.6x load to a maximum of 3x. To operate effectively at 3x load, we would need a total of 40 waterfront stations. Since we already have 21, this means we need to relocate 19 additional stations along the water. Start a targeted pilot plan that relocates 19 of the existing spatially close non-water stations that are experiencing low activity and increase it to 98 progressively so as to not affect other non-waterfront station operations.""")

########################################### Recommendations #######################################
else:
    st.markdown('### Determining the optimal timeframe for fleet health to recover lost revenue from stockouts:')

    day_order = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    time_order = ['Morning', 'Afternoon', 'Evening', 'Night']
    dayProb = bikeTrips.groupby(['day_name', 'time_period'], observed=False)['member_casual'].apply(lambda x: (x=='member').mean()).reset_index(name='P(MemberperDay)')
    day_prob = go.Figure(data=go.Heatmap(z=dayProb['P(MemberperDay)'], x=dayProb['day_name'], y=dayProb['time_period'], hoverongaps=False, text=(dayProb['P(MemberperDay)']*100).values, texttemplate='%{text:.2f}%', textfont={'size':13}))

    day_prob.update_layout(title=dict(text='Member Probability of Riding per Day (2022)', x=0.5, xanchor= 'center', font=dict(size=18, color='navy', family='bree, sans-serif')),
                         xaxis = dict(tickfont=dict(size=15, family='bree, sans-serif', color='midnightblue'), categoryorder='array', categoryarray=day_order),
                         yaxis = dict(tickfont=dict(size=15, family='bree, sans-serif', color='midnightblue'), categoryorder='array', categoryarray=time_order, autorange='reversed'),
                         height=400)

    st.markdown("""
    - The Member Probability heatmap helps us identify the optimal window for fleet health. It shows late-night activity has the lowest member ridership probability. We can also see member users have a preference (probability) to ride bikes during mid-week mornings (Tuesday to Friday), which when combined with the cool weather and short trip preference previously observed suggests a commuter usage suggesting the need for rapid rebalancing at transit stations. While casual users seem to rent bike for leisure purposes given their warm weather, longer trips, and night riding preference especially on the weekend.""")
    
    st.plotly_chart(day_prob, use_container_width=True)
    
    st.markdown("""Furthermore, our model's stability depends on 3 high-density hubs that require close monitoring to ensure they remain stocked before and throughout the business day: Grove St. PATH (42,556 average daily starts), South Waterfront Walkway (34,245) and Hoboken Terminal at River St. & Hudson Pl. (33,020). These stations experience a very high demand that will require overnight and early morning re-stocking to prevent depletion. Additionally, Hamilton Park and Marin Light Rail show a demand time compression of 36.5% and 35.8% respectively. This indicates that these stations deplete faster than the operations team can handle. We can overcome these issues with the below advanced predictive stocking that help these nodes circumvent system wide availability failures and lost revenue.""")

    st.dataframe(restockingPlan)
    st.subheader('**Additional Strategy Recommendations: CitiBike should focus on the following objectives moving forward to counter distribution inefficiencies.**')

    st.markdown("""
    - Improve the model's adaption to seasonal volatility by correlating bike ride trends with weather forecasts to plan short-term logistics, especially during peak usage months from June to October.
    - Prioritize dock usage in residential areas and transit hubs during winter and in leisure areas starting in May when temperatures cross the 15°C threshold to manage the rapid surge in demand.
    - Consider having dedicated crews in charge of adjusting bike fleet size during early mornings at 6 a.m. to avoid depletion at start stations, especially from Wednesdays to Saturdays.
    - Counter availability issues with flexible dock usage combined with planned maintenance periods during night windows and frequent electric bikes rotation during the extreme cold identified in February.
    - Implement user alerts to guide riders towards nearby stations with available docks during peak traffic times.
    - Consider redistributing other station resources from low usage areas in New York City to other high demand zones near residential areas and transit hubs.
    - Overstock stations near other touristic attractions and incentivize riders to return bikes to low-stock stations with ride credits or discounts, special packages and special events at unpopular stations that encourage a balanced bike use.""")