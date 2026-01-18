# **Bike Distribution Analysis Dashboard**

## Introduction:

CitiBike has experienced significant growth since 2013, thanks in part to effective marketing focused on sustainability. This growth was further accelerated by increased demand during the pandemic; however, the surge in usage also strained its operational model. At the time of this analysis, the system has been facing challenges with logistical imbalances, such as empty or overcrowded stations, which has led to an increase in customer complaints.

This project delves into the usage patterns, station logistics, and weather variables that influence the New York CitiBike sharing system to uncover distribution inefficiencies on bike rentals with the aim of circumventing availability issues. By examining the existing January to December 2022 bike trip and weather data, I used pandas, Matplotlib, and Seaborn to analyze:

* Weather temperature impact on demand
* Trip duration
* Station activity
* User profiles
* Weekday vs time of day activity

The key insights can be found in the Streamlit interactive dashboard created with Plotly and Kepler.gl.

## Analysis Objective:

To uncover distribution inefficiencies based on rental patterns that circumvent availability issues.

## Data Sources:

1. [Citi Bike Trip Data](https://s3.amazonaws.com/tripdata/index.html)
2. [La Guardia, NY API Data ](https://www.ncdc.noaa.gov/cdo-web/api/v2/data?datasetid=GHCND&datatypeid=TAVG&limit=1000&stationid=GHCND:USW00014732&startdate=2022-01-01&enddate=2022-12-31)

## Insights:

Key findings that will contribute to a more efficient distribution of resources include:

* The use of short-term logistic forecasting based on weather patterns to adapt to seasonal surges.
* Bike maintenance and fleet replacement periods based on weather patterns and riding probabilities.
* Crew coordination oriented to avoid depletion while accommodating user bike riding preferences.
* Implementation of flexible dock usage and user alerts to guide riders towards nearby stations with available docks during peak traffic times.
* Fleet scaling and bike stocking plans to improve resource utilization.
* Resource redistribution according to station proximity to residential areas, waterfront zones, and transit hub stations.
* The promotion of low-density stations near other tourist attractions and traffic gateways through discounts, special packages, and special events that encourage a more balanced bike use.

## Analysis Deliverables:
1. [Reduced and aggregated datasets](https://github.com/Giov4n/Bike_distribution/tree/159eec9b5de076675470ea8a9cac487d6a14b96b/data) hosted in MongoDB to ensure fast dashboard performance.
2. The 5 numbered notebooks that were used to clean and analyze the data.
3. [The requirements text file](https://github.com/Giov4n/Bike_distribution/blob/159eec9b5de076675470ea8a9cac487d6a14b96b/requirements.txt) with the packages used to run the app.
4. [database_utils.py](https://github.com/Giov4n/Bike_distribution/blob/159eec9b5de076675470ea8a9cac487d6a14b96b/database_utils.py) used to securely connect to MongoDB Atlas using GridFS for the storing and retrieval of the files included in the "Reduced and aggregated datasets".
5. [6. st_dashboardGBlanco.py](https://github.com/Giov4n/Bike_distribution/blob/159eec9b5de076675470ea8a9cac487d6a14b96b/6.%20st_dashboardGBlanco.py) as the final dashboard script.
6. [Live Streamlit Dashboard](https://citibike-operational-analysis-dashboard.streamlit.app/) with the main visualizations used for the final reporting.
