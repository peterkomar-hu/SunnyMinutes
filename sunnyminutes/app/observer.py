# observer module

import re
import numpy as np
import datetime as dt
from dateutil.parser import parse
import geocoder

LATITUTE_DEFAULT = 40.7049687
LONGITUDE_DEFAULT = -74.0145948
ALTITUDE_DEFAULT = 0
    

class Observer:
    def __init__(self, \
            lon=LONGITUDE_DEFAULT, 
            lat=LATITUTE_DEFAULT,\
            alt=ALTITUDE_DEFAULT,\
            city_lon=-73.973351,\
            city_lat=40.771803,\
            planet_radius=6371009,\
        ):
        self.lon = lon
        self.lat = lat
        self.city_lon = city_lon
        self.city_lat = city_lat
        self.planet_radius = planet_radius
        self.x = None
        self.y = None
        self.z = alt
        self.block_xid = None
        self.block_yid = None


    def load_basic_geography(self, db_connection):
        with db_connection:
            cur = db_connection.cursor()
            cur.execute("SELECT \
                Planet_radius, \
                Mean_lon, \
                Mean_lat \
                FROM Cities \
                WHERE Name = 'New York Manhattan'\
            ")
            result = cur.fetchall()[0]
        self.planet_radius = result[0]
        self.city_lon = result[1]
        self.city_lat = result[2]

    def get_geocoordinates(self, address, floor):
        # if address:
        #     match = re.search(r'(-?\d+\.?\d*)\s*,?\s*(-?\d+\.?\d*)', address)
        #     if match:
        #         self.lat = float(match.group(1))
        #         self.lon = float(match.group(2))
        geocoordinates_from_address = geocoder.google(address).latlng
        if geocoordinates_from_address:
            self.lat = geocoordinates_from_address[0]
            self.lon = geocoordinates_from_address[1]

        if floor:
            match = re.search(r'(\d+)', floor)
            if match:
                self.z = float(floor) * 3   # 1 floor =approx= 3 meters

    def get_altitude(self, floor):
        if floor:
            match = re.search(r'(\d+)', floor)
            if match:
                self.z = float(floor) * 3   # 1 floor =approx= 3 meters
            return True
        else:
            return False


    # convert (lon,lat) to (x,y) on the local map
    def convert_to_cartesian(self):
        deg2rad = np.pi/180
        cos_mean_lat = np.cos(self.city_lat * deg2rad)
        self.x = self.planet_radius * cos_mean_lat * (self.lon - self.city_lon)* deg2rad
        self.y = self.planet_radius * (self.lat - self.city_lat)* deg2rad
    
    def convert_to_geographical(self):
        deg2rad = np.pi/180
        cos_mean_lat = np.cos(self.city_lat * deg2rad)
        self.lon = self.city_lon + self.x / self.planet_radius / cos_mean_lat / deg2rad
        self.lat = self.city_lat + self.y / self.planet_radius / deg2rad

    # finds the block the Node(x,y) coordinates are in
    # (blocks are indexed by (x_index, y_index), starting from (0,0) )
    def find_my_block(self, x_grid, y_grid):
        # find x_index of the block
        x_index = -1
        for x in x_grid:
            if self.x > x:
                x_index += 1
            else:
                break
        
        # find y_index of the block
        y_index = -1
        for y in y_grid:
            if self.y > y:
                y_index += 1
            else:
                break
        
        self.block_xid = x_index
        self.block_yid = y_index

    def distance_from_building(self, building):
        dx = self.x - building.center.x
        dy = self.y - building.center.y
        return np.sqrt(dx**2 + dy**2)

    def get_my_buildings(self, buildings):
        my_building_keys = []
        for key in buildings:
            poly = []
            for  node in buildings[key].nodes[:-1]:     # buildings repeat the first node as last
                poly.append((node.x, node.y))
            if self.is_inside(poly):
                my_building_keys.append(key)

        # z = 1e6
        # current_key = None
        # for key in my_building_keys:
        #     if buildings[key].z < z:
        #         z = buildings[key].z
        #         current_key = key

        return my_building_keys



    def is_inside(self, poly):
        x = self.x
        y = self.y
        n = len(poly)

        inside = False
        p1x,p1y = poly[0]
        for i in range(n+1):
            p2x,p2y = poly[i % n]
            if y > min(p1y,p2y):
                if y <= max(p1y,p2y):
                    if x <= max(p1x,p2x):
                        if p1y != p2y:
                            xints = (y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
                        if p1x == p2x or x <= xints:
                            inside = not inside
            p1x,p1y = p2x,p2y

        return inside

    def get_neighboring_block_ids(self):
        
        # relative integer coordinates of neighboring blocks (including the center block)
        deltax = [0,1,1,0,-1,-1,-1,0,1]
        deltay = [0,0,1,1,1,0,-1,-1,-1]

        xid_list = []
        yid_list = []
        for i in range(0, len(deltax)):
            xid_list.append(self.block_xid + deltax[i])
            yid_list.append(self.block_yid + deltay[i])
        
        return (xid_list, yid_list)


    def plot_observers_location(self, ax, color='k'):
        # center dot
        ax.plot([self.x], [self.y], color=color, marker='o', markersize=5)

        # cross
        L = 50
        ax.plot([self.x, self.x], [self.y - L, self.y + L], color=color)
        ax.plot([self.x - L, self.x + L], [self.y, self.y], color=color)


def load_grid_data(db_connection):
    with db_connection:
        cur = db_connection.cursor()
        cur.execute("SELECT \
            Xmin,\
            Xmax,\
            Xstep,\
            Ymin,\
            Ymax,\
            Ystep\
            FROM Grids \
            WHERE Id = 1"\
        )
        result = cur.fetchall()[0]

    x_min = result[0]
    x_max = result[1]
    x_step = result[2]
    y_min = result[3]
    y_max = result[4]
    y_step = result[5]

    x_grid = np.arange(x_min, x_max, x_step)
    y_grid = np.arange(y_min, y_max, y_step)

    return (x_grid, y_grid)