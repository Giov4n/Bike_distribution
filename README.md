# **Bike Distribution Analysis Dashboard**

## Introduction:
This project delves into the usage patterns, station logistics and weather temperatures that influence the New York Citi Bike sharing system to uncover distribution inefficiencies on bike rentals with the aim of circumventing availability issues. By examining the existing January to December 2022 bike trip and weather data, I used pandas, Matplotlib, and Seaborn to analyze:
* Weather temperature impact on demand,
* Trip duration,
* Station activity, 
* User profiles,
* Weekday vs weekend activity, 

With it, the relevant logistic issues were presented in the interactive charts using Plotly and Kepler.gl and designed with Streamlit on the final dashboard.

## Analysis Objective:
Uncover distribution inefficiencies based on rental patterns to circumvent availability issues.

## Data Sources:
1. [Citi Bike Trip Data]( https://s3.amazonaws.com/tripdata/index.html)
 
2. [La Guardia, NY API Data ](https://www.ncdc.noaa.gov/cdo-web/api/v2/data?datasetid=GHCND&datatypeid=TAVG&limit=1000&stationid=GHCND:USW00014732&startdate=2022-01-01&enddate=2022-12-31)

## Insights:
Key findings that will contribute to a more efficient distribution of resources include:
* The use short-term logistic forecasting based on weather patterns to address availability issues.
* Resource redistribution according to station proximity to residential areas, waterfront zones, and transit hub stations.
* Bike maintenance and fleet replacement periods based on weather patterns and riding probabilities
* Crew coordination oriented to avoid depletion while accommodating user bike riding preferences.
