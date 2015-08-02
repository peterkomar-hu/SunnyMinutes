from buildingmapping import *
from skyline import *
from sun import *
from observer import *

import datetime as dt

class User:
    def __init__(self):
        self.last_activity_time = dt.datetime.today()
        self.obs = Observer()
        self.sil = Silhouette()
        self.summary = SunSummary()
        self.buildings = {}
        self.building_keys_at_address = []
        self.x_grid = None
        self.y_grid = None
        self.address_placeholder = 'e.g. One Times Square'
        self.floor_placeholder = '0'


    def record_as_active(self):
        self.last_activity_time = dt.datetime.today()

def write_to_log(message):
    f = open('sunnyminutes.log', 'a')
    f.write(str(dt.datetime.today()) + ' -- ' + message + '\n')
    f.close()

        
