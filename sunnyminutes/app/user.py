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


def get_next_user_id():
    f = open('users.stat', 'r')
    match = re.search(r'total number of users = (\d+)', f.read())
    if match:
        next_user_id = int(match.group(1))
    else:
        next_user_id = 0
    f.close()
    return next_user_id

def put_next_user_id(next_id):
    f = open('users.stat', 'w')
    f.write('total number of users = ' + str(next_id))
    f.close()