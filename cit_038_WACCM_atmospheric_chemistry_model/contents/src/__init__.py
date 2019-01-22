from __future__ import unicode_literals

import os
import sys
import urllib
import datetime
import logging
import subprocess
import eeUtil
import urllib.request
import requests
from bs4 import BeautifulSoup
import urllib.request
import copy
import numpy as np


# Sources for nrt data
#h0 version is 3 hourly data
#h3 version is 6-hourly data for regional modelers to use as boundary conditions
VERSION = 'h0'
SOURCE_URL = 'https://www.acom.ucar.edu/waccm/DATA/f.e21.FWSD.f09_f09_mg17.forecast.001.cam.%s.{date}-00000.nc' %VERSION

VARS = ['NO2', 'CO', 'O3', 'SO2', 'PM25_SRF', 'bc_a1', 'bc_a4']
#most variables have 88 pressure levels; PM 2.5 only has one level (surface)
NUM_AVAILABLE_LEVELS = [88, 88, 88, 88, 1, 88, 88]
#need to specify which pressure level of data we was for each (level 1 being the lowest pressure)
#the highest level is the highest pressure (992.5 hPa), and therefore, closest to surface level
DESIRED_LEVELS = [88, 88, 88, 88, 1, 88, 88]

#h0 version is 3 hourly data
if VERSION == 'h0':
    TIME_HOURS = list(range(0, 24, 3))
# h3 version is 6-hourly data
elif VERSION == 'h3':
    TIME_HOURS = list(range(0, 24, 6))

SDS_NAME = 'NETCDF:"{fname}":{var}'
FILENAME = 'cit_038_WACCM_atmospheric_chemistry_model_{var}_{date}'
NODATA_VALUE = None

DATA_DIR = 'data'
COLLECTION = '/projects/resource-watch-gee/cit_038_WACCM_atmospheric_chemistry_model'
CLEAR_COLLECTION_FIRST = False
DELETE_LOCAL = True

#today plus 9 days forecast
MAX_DAYS = 10
MAX_ASSETS = len(TIME_HOURS) * MAX_DAYS
DATE_FORMAT_NETCDF = '%Y-%m-%d'
DATE_FORMAT = '%y-%m-%d_%H%M'
TIMESTEP = {'days': 1}

LOG_LEVEL = logging.INFO

DATASET_IDS = {
    'NO2': '',
    'CO': '',
    'O3': '',
    'SO2': '',
    'PM25_SRF': ''
}
apiToken = os.getenv('apiToken') or os.environ.get('rw_api_token') or os.environ.get('RW_API_KEY')

def lastUpdateDate(dataset, date):
   apiUrl = 'http://api.resourcewatch.org/v1/dataset/{0}'.format(dataset)
   headers = {
   'Content-Type': 'application/json',
   'Authorization': apiToken
   }
   body = {
       "dataLastUpdated": date.isoformat()
   }
   try:
       r = requests.patch(url = apiUrl, json = body, headers = headers)
       logging.info('[lastUpdated]: SUCCESS, '+ date.isoformat() +' status code '+str(r.status_code))
       return 0
   except Exception as e:
       logging.error('[lastUpdated]: '+str(e))

def getUrl(date):
    '''get source url from datestamp'''
    return SOURCE_URL.format(date=date)


def getAssetName(date):
    '''get asset name from datestamp'''# os.path.join('home', 'coming') = 'home/coming'
    return os.path.join(EE_COLLECTION, FILENAME.format(var=VAR, date=date))


def getFilename(date):
    '''get filename from datestamp CHECK FILE TYPE'''
    return os.path.join(DATA_DIR, '{}.nc'.format(
        FILENAME.format(var='all_vars', date=date)))

def getTiffname(file, hour, variable):
    '''get filename from datestamp CHECK FILE TYPE'''
    # get a string for that time
    if hour < 10:
        time_str = '0' + str(hour) + '00'
    else:
        time_str = str(hour) + '00'
    date = os.path.splitext(file)[0][-10:]
    name = os.path.join(DATA_DIR, FILENAME.format(var=variable, date=date)) + '_' + time_str
    return name

def getDateTime(filename):
    '''get last 8 chrs of filename CHECK THIS'''
    return os.path.splitext(os.path.basename(filename))[0][-13:]

def getDate_GEE(filename):
    '''get last 8 chrs of filename CHECK THIS'''
    return os.path.splitext(os.path.basename(filename))[0][-13:-5]

def getNewDates(exclude_dates):
    '''Get new dates excluding existing'''
    new_dates = []
    #forecasts are supposed to go 9 days into the future
    date = datetime.date.today() + datetime.timedelta(**{'days': 1})
    # if anything is in the collection, check back until last uploaded date
    if len(exclude_dates) > 0:
        while (date.strftime(DATE_FORMAT[0:8]) not in exclude_dates):
            datestr = date.strftime(DATE_FORMAT_NETCDF)
            new_dates.append(datestr)  #add to new dates
            date -= datetime.timedelta(**TIMESTEP)
    #if the collection is empty, make list of most recent 45 days to check
    else:
        #If collection is empty, pull three days because files are large (~7GB) and take
        # a long time to process (~30 mins per day)
        logging.info('Collection empty, checking for most recent 3 days')
        for i in range(3):
            datestr = date.strftime(DATE_FORMAT_NETCDF)
            new_dates.append(datestr)  #add to new dates
            date -= datetime.timedelta(**TIMESTEP)
    return new_dates

def getBands(var_num):
    # get specified pressure level for the current variable
    level = DESIRED_LEVELS[var_num]
    # the pressure and time dimensions are flattened into one dimension in the netcdfs
    # for the pressure level that we want, we want all the times available
    # we will make a list of the BANDS that have data for the desired level at all times available
    # h0 has 8 times
    if VERSION == 'h0':
        bands = [x * NUM_AVAILABLE_LEVELS[var_num] + level for x in
                 list(range(0, 8))]  # gives all times at specified pressure level
    # h3 has 4 times
    elif VERSION == 'h3':
        bands = [x * NUM_AVAILABLE_LEVELS[var_num] + level for x in
                 list(range(0, 4))]  # gives all times at specified pressure level
    return bands

def convert(files, var_num):
    '''convert netcdfs to tifs'''
    tifs = []
    for f in files:
        bands = getBands(var_num)
        logging.info('Converting {} to tiff'.format(f))
        for band in bands:
            # extract subdataset by name
            sds_path = SDS_NAME.format(fname=f, var=VAR)
            file_name_with_time = getTiffname(file=f, hour=TIME_HOURS[bands.index(band)], variable=VAR)
            tif = '{}.tif'.format(file_name_with_time) #naming tiffs
            tif_0_360 = '{}_0_360.tif'.format(file_name_with_time)
            #os.path.splitext gets rids of .nc because it makes a list of file name[0] and ext [1]
            #and only takes the file name (splits on last period)
            cmd = ['gdal_translate', '-b', str(band), '-q', '-a_nodata', str(NODATA_VALUE), '-a_srs', 'EPSG:4326', sds_path, tif_0_360] #'-q' means quiet so you don't see it
            subprocess.call(cmd) #using the gdal from command line from inside python
            cmd_warp = ['gdalwarp', '-t_srs', 'EPSG:4326', '-tr', '1.250000000000000', '-0.942408376963351', tif_0_360, tif, '-wo', 'SOURCE_EXTRA=1000', '--config', 'CENTER_LONG', '0']
            subprocess.call(cmd_warp) #using the gdal from command line from inside python
            tifs.append(tif)
    return tifs


def list_available_files(url, ext=''):
    page = requests.get(url).text
    soup = BeautifulSoup(page, 'html.parser')
    return [node.get('href') for node in soup.find_all('a') if type(node.get('href'))==str and node.get('href').endswith(ext)]

def fetch(new_dates):
	# 1. Set up authentication with the urllib.request library
	# not needed here
    # 2. Loop over the new dates, check if there is data available, and attempt to download the hdfs
    files = []
    for date in new_dates:
        # Setup the url of the folder to look for data, and the filename to download to if available
        url = getUrl(date)
        #starts as string, strptime changes to datetime object, strfttime reformats into string)
        f = getFilename(date)
        file_name = os.path.split(url)[1]
        file_list = list_available_files(os.path.split(url)[0], ext='.nc')
        if file_name in file_list:
            logging.info('Retrieving {}'.format(file_name))
            try:
                urllib.request.urlretrieve(url, f)
                files.append(f)
                logging.info('Successfully retrieved {}'.format(file_name))# gives us "Successully retrieved file name"
            except Exception as e:
                logging.error('Unable to retrieve data from {}'.format(url))
                logging.error(e)
                logging.debug(e)
        else:
            logging.info('{} not available yet'.format(file_name))

    return files

def processNewData(files, var_num):
    '''process, upload, and clean new data'''
    if files: #if files is empty list do nothing, if something in, convert netcdfs
        # Convert new files
        logging.info('Converting files')
        tifs = convert(files, var_num) # naming tiffs

        # Upload new files
        logging.info('Uploading files')
        dates = [getDateTime(tif) for tif in tifs] #finding date for naming tiffs, returns string
        datestamps = [datetime.datetime.strptime(date, DATE_FORMAT) #list comprehension/for loop
                      for date in dates] #returns list of datetime object
        assets = [getAssetName(date) for date in dates] #create asset nema (imagecollect +tiffname)
        eeUtil.uploadAssets(tifs, assets, GS_FOLDER, datestamps, timeout=3000) #puts on GEE

        # Delete local files
        if DELETE_LOCAL:
            logging.info('Cleaning local TIFF files')
            for tif in tifs:
                os.remove(tif)

        return assets
    return []


def checkCreateCollection(VARS):
    existing_dates = []
    existing_dates_by_var = []
    for VAR in VARS:
        # For one of the variables, get the date of the most recent data set
        # All variables come from the same file
        # If we have one for a particular data, we should have them all
        collection = EE_COLLECTION_GEN.format(var=VAR)
        if not eeUtil.exists(PARENT_FOLDER):
            logging.info('{} does not exist, creating'.format(PARENT_FOLDER))
            eeUtil.createFolder(PARENT_FOLDER)
        if eeUtil.exists(collection):
            existing_assets = eeUtil.ls(collection)
            dates = [getDate_GEE(a) for a in existing_assets]
            existing_dates_by_var.append(dates)
            for date in dates:
                if date not in existing_dates:
                    existing_dates.append(date)

        else:
            existing_dates_by_var.append([])
            logging.info('{} does not exist, creating'.format(collection))
            eeUtil.createFolder(collection, True)
    existing_dates_all_vars = copy.copy(existing_dates)
    for date in existing_dates:
        count = sum(x.count(date) for x in existing_dates_by_var)/len(TIME_HOURS)
        if count < len(VARS):
            existing_dates_all_vars.remove(date)
    return existing_dates_all_vars, existing_dates_by_var

def deleteExcessAssets(all_assets, max_assets):
    '''Delete assets if too many'''
    # oldest first
    if len(all_assets) > max_assets:
        for asset in all_assets[:-max_assets]:
            eeUtil.removeAsset(EE_COLLECTION +'/'+ asset)

def get_most_recent_date(all_assets):
    all_assets.sort()
    most_recent_date = datetime.datetime.strptime(all_assets[-1][-13:], DATE_FORMAT)
    return most_recent_date

def main():
    global VAR
    global EE_COLLECTION
    global EE_COLLECTION_GEN
    global PARENT_FOLDER
    global FILENAME
    global GS_FOLDER
    PARENT_FOLDER = COLLECTION
    EE_COLLECTION_GEN = COLLECTION + '/{var}'
    FILENAME = COLLECTION[29:] + '_{var}_{date}'
    '''Ingest new data into EE and delete old data'''
    logging.basicConfig(stream=sys.stderr, level=LOG_LEVEL)
    logging.info('STARTING')
    # Initialize eeUtil and clear collection in GEE if desired
    eeUtil.initJson()
    if CLEAR_COLLECTION_FIRST:
        for var_num in range(len(VARS)):
            VAR = VARS[var_num]
            EE_COLLECTION = EE_COLLECTION_GEN.format(var=VAR)
            if eeUtil.exists(EE_COLLECTION.format(var=VAR)):
                eeUtil.removeAsset(EE_COLLECTION, recursive=True)
    # 1. Check if collection exists and create
    existing_dates, existing_dates_by_var = checkCreateCollection(VARS)
    # Determine which files to fetch
    all_new_dates = getNewDates(existing_dates)
    #container only big enough to hold 3 files at once, so break into groups to process
    new_date_groups = [all_new_dates[x:x+3] for x in range(0, len(all_new_dates), 3)]
    for new_dates in new_date_groups:
        # Fetch new files
        logging.info('Fetching files for {}'.format(new_dates))
        files = fetch(new_dates) #get list of locations of netcdfs in docker container

        for var_num in range(len(VARS)):
            # get variable name
            VAR = VARS[var_num]
            # specify GEE collection name and Google Cloud Storage folder names
            EE_COLLECTION=EE_COLLECTION_GEN.format(var=VAR)
            GS_FOLDER=COLLECTION[1:]+'_'+VAR
            existing_assets = eeUtil.ls(EE_COLLECTION)
            # 2. Fetch, process, stage, ingest, clean
            new_assets = processNewData(files, var_num)
            new_dates = [getDateTime(a) for a in new_assets]
            # 3. Delete old assets
            all_dates = existing_dates_by_var[var_num] + new_dates
            all_assets = np.sort(np.unique(existing_assets + [os.path.split(asset)[1] for asset in new_assets]))
            logging.info('Existing assets for {}: {}, new: {}, max: {}'.format(
                VAR, len(all_dates), len(new_dates), MAX_ASSETS))
            deleteExcessAssets(all_assets, (MAX_ASSETS))
            # Get most recent update date
            most_recent_date = get_most_recent_date(all_assets)
            #lastUpdateDate(DATASET_IDS[VAR], most_recent_date)
            logging.info('SUCCESS for {}'.format(VAR))

        # Delete local netcdf files
        if DELETE_LOCAL:
            logging.info('Cleaning local NETCDF files')
            for f in files:
                os.remove(f)
