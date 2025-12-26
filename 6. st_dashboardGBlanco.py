##################################CITIBIKES DASHBOARD########################################
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from keplergl import KeplerGl
from streamlit_keplergl import keplergl_static
from datetime import datetime as dt
from numerize.numerize import numerize
from PIL import Image
from database_utils import SecureGridFSHandler, get_mongo_config
import streamlit.components.v1 as components

################################## Configuring the Dashboard Page ##############################
st.set_page_config(page_title = 'CitiBike 2022 Strategy Dashboard', layout='wide')

################################Initializing Custom Defined Handler#############################
@st.cache_resource
def get_handler():
    return SecureGridFSHandler()

handler = get_handler()
config = get_mongo_config()
user_id = config['default_user_id']

# Loaded data into MongoDB using:
# topStart = handler.save_csv_from_file(user_id, r"D:\Data_Analysis\05-12-2025_Bike_Dashboard\02.Data\Prepared Data\Top_Start.csv", 'Top_Start')
# bikeTrips = handler.save_csv_from_file(user_id, r"D:\Data_Analysis\05-12-2025_Bike_Dashboard\02.Data\Prepared Data\Reduced_Trips.csv", 'Reduced_Trips')
# arcsMap = handler.save_html_from_file(user_id, r"D:\Data_Analysis\05-12-2025_Bike_Dashboard\02.Data\CitiBike_Trip_Routes_Map.html", "CitiBike_Trip_Routes_Map")

# Fetching previously loaded csv files
@st.cache_data
def load_dataset(dataset_name):
    return handler.load_dataframe(user_id, dataset_name)

###########################################Importing Data#######################################
# Loading above MongoDB dataset into memory
topStart = load_dataset('Top_Start')
bikeTrips = load_dataset('Reduced_Trips')

# Message to display if data frames are not loaded
if topStart is None or bikeTrips is None:
    st.error('ONE OR MORE REQUIRED DATASETS WERE NOT FOUND IN MONGODB')
    st.stop

# Fetching previously loaded HTML file
@st.cache_data
def load_html(map_name):
    return handler.load_map_html(user_id, map_name)

# Loading HTML map into memory
arcsMap = load_html('CitiBike_Trip_Routes_Map')

#################################Initial Settings for Dashboard##############################

st.title('CitiBike Operational Analysis Dashboard')
st.markdown('#### This dashboard analyzes real CitiBike trip data to suggest strategic operational changes aimed at circumventing bike availability issues voiced by Customers.')
st.markdown("""**The following charts show how distribution inefficiencies are contributing to the availability issues.**

Note: This pages uses pre-processed files of data sourced from the CitiBike website and La Guardia, NY NOAA API weather data.""")

############################################Bar Chart#########################################

st.markdown('### Which are the most popular stations users go to rent bikes?')

fig_top20 = go.Figure(go.Bar(x=topStart['start_station'], y=topStart['total_trips'], marker={'color':topStart['total_trips'], 'colorscale':'Blues'}))
fig_top20.update_layout(title=dict(text='Most Popular CitiBike Stations in New York', x=0.35, font=dict(size=18, color='navy', family='bree, sans-serif')),
                 xaxis_title = 'Start Stations',
                 xaxis = dict(color='navy', title=dict(font=dict(size=16))),
                 yaxis_title = 'Sum of Trips',
                 yaxis = dict(gridcolor='rgba(0,0,0,0.1)', zerolinecolor='rgba(0,0,0,0.1)', color='navy', title=dict(font=dict(size=16))),
                 plot_bgcolor='lightsteelblue',
                 paper_bgcolor='white',
                 width = 800, height=500)
fig_top20.show()

# Calculating trip percentage of total 20 station trips captured by the top 5 stations.
Top4_proportion = (topStart['total_trips'].head(4).sum()) / \
    (topStart['total_trips'].sum())
with st.container():
    st.plotly_chart(fig_top20, use_container_width=True)
    st.caption(f'The Top 4 stations account for {Top4_proportion:.2%} of the top 20 station trips.')
    
    st.markdown("""*The Grove St, South Waterfront Walkway, and Hoboken Terminal Stations account for almost about 1/3 of the total bike rental trips. The first four rank among the most preferred start stations. The interactive map will help us understand this aspect that can be accessed below.*""")

############################################Line Chart#######################################

st.markdown('### Can any availability issues be inferred from weather temperatures vs ridership patterns?')

# Using Graph Objects to plot dual axis line chart
fig_DAline = make_subplots(specs = [[{'secondary_y':True}]])
fig_DAline.add_trace(go.Scatter(x=bikeTrips['date'], y=bikeTrips['daily_rides'], name='Daily Rides', marker={'color':bikeTrips['daily_rides'], 'color':'navy'}),
               secondary_y=False)
fig_DAline.add_trace(go.Scatter(x=bikeTrips['date'], y=bikeTrips['avgTemp'], name='Daily Average Temperatures', marker={'color':bikeTrips['avgTemp'], 'color':'violet'}),
               secondary_y=True)

# Updating layout and Axes
fig_DAline.update_layout(title=dict(text='CitiBike Daily Rides and Average Temperature (2022)', x=0.3, font=dict(size=18, color='navy', family='bree, sans-serif')),
                 plot_bgcolor='lightsteelblue',
                 paper_bgcolor='white',
                 width=1200, height=600)
fig_DAline.update_yaxes(title_text='Sum of Daily Rides', secondary_y=False, color='navy', title=dict(font=dict(size=16)))
fig_DAline.update_yaxes(title_text='Daily Average Temperature', secondary_y=True, color='violet', title=dict(font=dict(size=16)))
fig_DAline.show()

# Calculating Pearson's correlation coefficient
correlation = bikeTrips['daily_rides'].corr(bikeTrips['avgTemp'])
with st.container():
    st.plotly_chart(fig_DAline, use_container_width=True)
    st.caption(f'Daily Rides and Daily Average Temperature have a '
               f'{"Strong Positive" if correlation > 0.7 else "Moderate Positive" if correlation > 0.4 else "Weak"} Correlation of {correlation:.3f}')
    
    st.markdown("""*The ride patterns and weather temperatures reflected have a strong positive correlation of 0.814, which suggests trips increase at similar levels as temperatures, but decline slightly when temperatures exceed the 30°C. The trip spikes between September and November seem to indicate the availability issues may be prevalent during the warm to cool temperature months*""")

########################################Displaying Kepler HTML Map####################################

st.markdown('### Which are the most popular bike stations pairs and common routes per the Interactive Map?')
components.html(arcsMap, height=700, scrolling=True)

st.markdown("""*The origin-destination pairs reflected in the map reveal that Hoboken City is the busiest zone with the most intra-zonal flows. The most popular start stations, located near the Hudson River, are also part of the most popular trips: Marshall St. & 2nd St. to City Hall – Washington St. & 1 St. covering a short distance of 14 blocks (with 999 trips), and South Waterfront Walkway – Sinatra Dr. & 1st St to Bloomfield St. & 15th St (with 977 trips) and Columbus Park on to Hoboken Terminal (with 977 trips). Their strategic location near the Pier A Park combined with the city's transit network gateway offered by the Hoboken Terminal make the small-town charm of Hoboken City an atractive zone. New Jersey City is the second busiest zone and interestingly the least popular zone is New York City, which accounts for most inactive end stations, maybe due to the bridge crossing difficulty.*""")