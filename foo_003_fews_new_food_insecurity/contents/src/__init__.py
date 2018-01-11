from __future__ import unicode_literals

import fiona
import os
import logging
import sys
import urllib
from datetime import datetime, timedelta
from collections import OrderedDict
import cartosql
import zipfile

# Constants
DATA_DIR = 'data'
SOURCE_URL = 'ftp://satepsanone.nesdis.noaa.gov/FIRE/HMS/GIS/hms_smoke{date}.zip'
FILENAME = 'hms_smoke{date}'
TIMESTEP = {'days': 1}
DATE_FORMAT = '%Y%m%d'
DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
CLEAR_TABLE_FIRST = False

# asserting table structure rather than reading from input
CARTO_TABLE = ''
CARTO_SCHEMA = OrderedDict([
    ('the_geom', 'geometry'),
    ('_UID', 'text'),
    ('date', 'timestamp'),
    ('Satellite', 'text'),
    ('_start', 'timestamp'),
    ('_end', 'timestamp'),
    ('duration', 'text'),
    ('Density', 'numeric')
])
UID_FIELD = '_UID'
TIME_FIELD = 'date'

LOG_LEVEL = logging.INFO
MAXROWS = 10000
MAXAGE = datetime.today() - timedelta(days=365*10)
MAXAGE_UPLOAD = datetime.today() - timedelta(days=10)


# Generate UID
def genUID(date, pos_in_shp):
    return str('{}_{}'.format(date, pos_in_shp))

def getDate(uid):
    '''first 8 chr of ID'''
    return uid.split('_')[0]

def findShp(zfile):
    with zipfile.ZipFile(zfile) as z:
        for f in z.namelist():
            if os.path.splitext(f)[1] == '.shp':
                return f
    return False

def getNewDates(exclude_dates):
    '''Get new dates excluding existing'''
    new_dates = []
    date = datetime.today()
    while date > MAXAGE_UPLOAD:
        date -= timedelta(**TIMESTEP)
        datestr = date.strftime(DATE_FORMAT)
        logging.debug(datestr)
        if datestr not in exclude_dates:
            new_dates.append(datestr)
        else:
            logging.debug(datestr + "already in table")
    return new_dates


def processNewData(exclude_ids):
    new_ids = []

    # get non-existing dates
    dates = set([getDate(uid) for uid in exclude_ids])
    new_dates = getNewDates(dates)
    for date in new_dates:
        # 1. Fetch data from source

        url = SOURCE_URL.format(date=date)
        tmpfile = '{}.zip'.format(os.path.join(DATA_DIR,
                                               FILENAME.format(date=date)))
        logging.info('Fetching {}'.format(date))
        try:
            urllib.request.urlretrieve(url, tmpfile)
        except Exception as e:
            logging.warning('Could not retrieve {}'.format(url))
            logging.error(e)
            continue

        # 2. Parse fetched data and generate unique ids
        logging.info('Parsing data')
        shpfile = '/{}'.format(findShp(tmpfile))
        zfile = 'zip://{}'.format(tmpfile)
        rows = []
        with fiona.open(shpfile, 'r', vfs=zfile) as shp:
            logging.debug(shp.schema)
            pos_in_shp = 0
            for obs in shp:

                uid = genUID(date, pos_in_shp)

                new_ids.append(uid)
                row = []
                for field in CARTO_SCHEMA.keys():
                    if field == 'the_geom':
                        row.append(obs['geometry'])
                    elif field == UID_FIELD:
                        row.append(uid)
                    elif field == TIME_FIELD:
                        row.append(date)
                    else:
                        row.append(obs['properties'][field])
                rows.append(row)
                pos_in_shp += 1
        # 3. Delete local files
        os.remove(tmpfile)

        # 4. Insert new observations
        new_count = len(rows)
        if new_count:
            logging.info('Pushing new rows')
            cartosql.insertRows(CARTO_TABLE, CARTO_SCHEMA.keys(),
                                CARTO_SCHEMA.values(), rows)
    num_new = len(new_ids)
    return num_new


##############################################################
# General logic for Carto
# should be the same for most tabular datasets
##############################################################

def createTableWithIndices(table, schema, idField, otherFields=[]):
    '''Get existing ids or create table'''
    cartosql.createTable(table, schema)
    cartosql.createIndex(table, idField, unique=True)
    for field in otherFields:
        if field != idField:
            cartosql.createIndex(table, field, unique=False)

def getFieldAsList(table, field, orderBy=''):
    assert isinstance(field, str), 'Field must be a single string'
    r = cartosql.getFields(field, table, order='{}'.format(orderBy),
                           f='csv')
    return(r.text.split('\r\n')[1:-1])

def deleteExcessRows(table, max_rows, time_field, max_age=''):
    '''Delete excess rows by age or count'''
    num_dropped = 0
    if isinstance(max_age, datetime):
        max_age = max_age.isoformat()

    # 1. delete by age
    if max_age:
        r = cartosql.deleteRows(table, "{} < '{}'".format(time_field, max_age))
        num_dropped = r.json()['total_rows']

    # 2. get sorted ids (old->new)
    ids = getFieldAsList(CARTO_TABLE, 'cartodb_id', orderBy=''.format(TIME_FIELD))

    # 3. delete excess
    if len(ids) > max_rows:
        r = cartosql.deleteRowsByIDs(table, ids[:-max_rows])
        num_dropped += r.json()['total_rows']
    if num_dropped:
        logging.info('Dropped {} old rows from {}'.format(num_dropped, table))


def main():
    logging.basicConfig(stream=sys.stderr, level=LOG_LEVEL)
    logging.info('STARTING')

    if CLEAR_TABLE_FIRST:
        logging.info("Clearing table")
        cartosql.dropTable(CARTO_TABLE)

    # 1. Check if table exists and create table
    existing_ids = []
    if cartosql.tableExists(CARTO_TABLE):
        existing_ids = getFieldAsList(CARTO_TABLE, UID_FIELD)
    else:
        createTableWithIndices(CARTO_TABLE, CARTO_SCHEMA, UID_FIELD, otherFields=[TIME_FIELD])

    # 2. Iterively fetch, parse and post new data
    num_new = processNewData(existing_ids)

    existing_count = num_new + len(existing_ids)
    logging.info('Total rows: {}, New: {}, Max: {}'.format(
        existing_count, num_new, MAXROWS))

    # 3. Remove old observations
    deleteExcessRows(CARTO_TABLE, MAXROWS, TIME_FIELD, MAXAGE)

    logging.info('SUCCESS')
