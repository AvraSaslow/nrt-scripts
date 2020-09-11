## GMAO AQ Forcast Dataset Near Real-time Script
This file describes the near real-time script that retrieves and processes the [GMAO AQ Forcast dataset]()for display on Resource Watch as the following datasets:

-[Air Quality: Mexico City Ozone (O₃) Forecast](https://resourcewatch.org/data/explore/00d6bae1-e105-4165-8230-ee73a8128538)

This dataset was provided by the source as a JSON file. A unique ID for each air quality forecast was created using forecast date and station number. This was stored in a new column called 'uid'. The JSON was transformed into a table and the resulting table was then uploaded to Carto. 

Please see the [Python script](https://github.com/resource-watch/nrt-scripts/blob/master/cit_004_city_aq/contents/src/__init__.py) for more details on this processing.

**Schedule**

This script is run daily. The exact time that the script is run to update the dataset can be found in the the `time.cron` file. This time is in Coordinated Universal Time (UTC), expressed in cron format.

###### Note: This script was originally written by [Taufiq Rashid](https://www.wri.org/profile/taufiq-rashid), and is currently maintained by [Amelia Snyder](https://www.wri.org/profile/amelia-snyder).