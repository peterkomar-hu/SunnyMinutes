
# modules for the web app
from flask import Flask
from flask import render_template, request, make_response
from app import app
import StringIO
import matplotlib
matplotlib.use('Agg')
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib import pylab as plt

# modules for the processing
# import re
# import csv
# import pandas as pd
# import matplotlib.pyplot as plt
# import matplotlib.cm as cm
# import numpy as np
# import datetime as dt
import pymysql as mdb

# my modules
from buildingmapping import *
from skyline import *
from sun import *
from observer import *


# colors
COLOR_BROWN = '#2d1b00'
COLOR_LIGHTBROWN = '#ffc469'

DEFAULT_DAY = '7/31'
DEFAULT_ADDRESS = 'Columbus Circle'
DEFAULT_FLOOR = '0'
ZOOM_SIZE = 200
ZOOM_SIZE_PX = 350
SUN_STEPSIZE = 5


#  declare global instances
obs = Observer()
sil = Silhouette()
summary = SunSummary()
buildings = {}
building_keys_at_address = []
x_grid = None
y_grid = None
address_placeholder = 'e.g. One Times Square'
floor_placeholder = DEFAULT_FLOOR

con = mdb.connect('localhost', 'root', '123', 'Manhattan_buildings')

obs.load_basic_geography(con)
(x_grid, y_grid) = load_grid_data(con)



@app.after_request
def add_header(response):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also to cache the rendered page for 10 minutes.
    """
    response.headers['X-UA-Compatible'] = 'IE=Edge,chrome=1'
    response.headers['Cache-Control'] = 'public, max-age=0'
    return response


@app.route('/')
@app.route('/index')
def start():
    exec 'address_placeholder = "e.g. One Times Square"' in globals()

    return render_template('start.html', 
        address_placeholder=address_placeholder)

@app.route('/about_page')
def go_to_about_page():
    return render_template('about.html')

@app.route('/contact_page')
def go_to_contact_page():
    return render_template('contact.html')


@app.route('/zoom')
def zoom():

    con = mdb.connect('localhost', 'root', '123', 'Manhattan_buildings')

    address = request.args.get('Address')
    
    if address:
        address = address + ', Manhattan'
    else: 
        address = DEFAULT_ADDRESS

    exec 'address_placeholder = "' + address + '"' in globals()

    obs.get_geocoordinates(address, floor=DEFAULT_FLOOR)
    obs.convert_to_cartesian()
    obs.find_my_block(x_grid, y_grid)

    # get all buildings within the 9 blocks around the observer
    buildings.clear()
    (x_id_list, y_id_list) = obs.get_neighboring_block_ids()

    # add buildings on the block
    buildings_in_observers_block = append_buildings_in_block(con, x_id_list[0], y_id_list[0])
    if buildings_in_observers_block:
        buildings.update(buildings_in_observers_block)
    # block is empty, fall back to default address
    else:
        obs.get_geocoordinates(DEFAULT_ADDRESS, floor=DEFAULT_FLOOR)
        obs.convert_to_cartesian()
        obs.find_my_block(x_grid, y_grid)
        buildings.clear()
        (x_id_list, y_id_list) = obs.get_neighboring_block_ids()
        buildings.update(append_buildings_in_block(con, x_id_list[0], y_id_list[0]))

    # find the buildings the observer is sitting in
    del building_keys_at_address[:]
    building_keys_at_address.extend(obs.get_my_buildings(buildings))

    # find windows
    obs.clear_windows()
    for key in building_keys_at_address:
        obs.get_windows(buildings[key])

    # add buildings in neighboring blocks
    for i in range(1, len(x_id_list)):
        buildings.update(\
            append_buildings_in_block(con, x_id_list[i], y_id_list[i])\
        )

    return render_template('zoom_to_address.html', 
        address_placeholder=address_placeholder)

@app.route('/zoom_adjust')
def zoom_after_click():
    click_x = float(request.args.get('zoom.x'))
    click_y = float(request.args.get('zoom.y'))
    dx = (click_x / ZOOM_SIZE_PX - 0.5) * ZOOM_SIZE
    dy = -(click_y / ZOOM_SIZE_PX - 0.5) * ZOOM_SIZE
    obs.x = obs.x + dx
    obs.y = obs.y + dy
    obs.clear_windows()
    obs.convert_to_geographical()

    exec 'floor_placeholder = "'+ str(int(round(obs.z / 3))) + '"' in globals()

    # find the buildings the observer is sitting in
    del building_keys_at_address[:]
    building_keys_at_address.extend(obs.get_my_buildings(buildings))

    # find windows
    obs.clear_windows()
    for key in building_keys_at_address:
        obs.get_windows(buildings[key])

    return render_template('show_calculate_button.html', 
        address_placeholder=address_placeholder, 
        floor_placeholder=floor_placeholder)

@app.route('/results')
def show_results():
    floor = request.args.get('Floor')

    if not obs.get_altitude(floor):
        floor = DEFAULT_FLOOR
    exec 'floor_placeholder = "'+ str(int(round(obs.z / 3))) + '"' in globals()

    # clear skyline
    sil.cliffs = Silhouette().cliffs
    
    # add the roof blocking the view towards the back of the window
    if obs.closest_window:
        phi_window = obs.closest_window.phi
        if phi_window < -np.pi/2:
            sil.add_roof(
                Roof((
                    phi_window + np.pi/2, 
                    phi_window - np.pi/2 + 2*np.pi, 
                    np.pi/2
                ))
            )
        elif phi_window > np.pi/2:
            sil.add_roof(
                Roof((
                    phi_window + np.pi/2 -2*np.pi, 
                    phi_window - np.pi/2, 
                    np.pi/2
                ))
            )
        else:
            sil.add_roof(
                Roof((
                    -np.pi, 
                    phi_window - np.pi/2, 
                    np.pi/2
                ))
            )
            sil.add_roof(
                Roof((
                    phi_window + np.pi/2, 
                    np.pi, 
                    np.pi/2
                ))
            )

    # add roofs of the buildings to sil
    for key in buildings:
        if (buildings[key].z > obs.z) and (key not in building_keys_at_address):
            if obs.windows:
                x = obs.closest_window.x
                y = obs.closest_window.y
            else:
                x = obs.x
                y = obs.y
            z = obs.z
            roofs = buildings[key].get_roofs(x, y, z)
            for tup in roofs:
                sil.add_roof( Roof(tup) )
    
    summary.clear()
    summary.collect_summary(sil, obs, SUN_STEPSIZE)

    # calculate sun score
    minutes_in_2h = 2*60
    minutes_in_12h = 12*60
    minutes_of_total_visible_sun = sum(summary.morning_sun)
    minutes_of_total_visible_sun += sum(summary.afternoon_sun)
    minutes_of_total_visible_sun /= len(summary.dates)
    #minutes_of_waking_sun = sum(summary.wakinghours_sun)
    #minutes_of_waking_sun /= len(summary.dates)
    #wakeup_score = 100.0 * minutes_of_waking_sun / minutes_in_2h
    day_score = 5.0 * minutes_of_total_visible_sun / minutes_in_12h
    #sun_score = 0.5 * wakeup_score + 0.5 * day_score
    #wakeup_score = round(wakeup_score, 1)
    day_score = round(day_score, 1)
    sun_score = day_score
    #sun_score = round(sun_score, 1)
    sun_icon_file = './static/' + str(round(2 * sun_score, 0) * 0.5) + '_sun.svg'
    
    # calculate sky score
    sky_visibility = sil.calculate_sky_visibility()
    sky_score = 5.0 * sky_visibility
    sky_score = round(sky_score, 1)
    sky_icon_file = './static/' + str(round(2 * sky_score, 0) * 0.5) + '_sky.svg'

    return render_template("results.html", lat=obs.lat, lon=obs.lon, 
        address_placeholder=address_placeholder, 
        floor_placeholder=floor_placeholder,
        sun_score=sun_score,
        sky_score=sky_score,
        sun_icon_file=sun_icon_file,
        sky_icon_file=sky_icon_file)


@app.route('/building_zoom')
def draw_building_zoom():
    plt.cla()   # Clear axis
    plt.clf()   # Clear figure
    plt.close() # Close a figure window

    fig = plt.figure()
    ax = fig.add_axes([0,0,1,1])
    radius = ZOOM_SIZE/2 * 1.5
    for key in buildings:
        if obs.distance_from_building(buildings[key]) < radius:
            if key not in building_keys_at_address:
                buildings[key].plot_footprint(ax, color='k')
            else:
                buildings[key].plot_footprint(ax, color=COLOR_LIGHTBROWN)
    obs.plot_observers_location(ax, color='r')
    L = ZOOM_SIZE/2     # half size of the plotted area in meters
    ax.set_xlim([obs.x-L, obs.x+L])
    ax.set_ylim([obs.y-L, obs.y+L])    
    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)
    ax.axis('off')
    ax.set_aspect('equal')

    fig.patch.set_facecolor('#d4c3a8')
    fig.set_size_inches(5, 5)

    # post-process for html
    canvas = FigureCanvas(fig)
    png_output = StringIO.StringIO()
    canvas.print_png(png_output)
    response = make_response(png_output.getvalue())
    response.headers['Content-Type'] = 'image/png'

    plt.cla()   # Clear axis
    plt.clf()   # Clear figure
    plt.close() # Close a figure window
    return response 



@app.route('/light_plot')
def draw_light_plot():
    plt.cla()   # Clear axis
    plt.clf()   # Clear figure
    plt.close() # Close a figure window
    
    # create light summary plot
    fig = plt.figure()
    ax = fig.add_subplot(111)
    summary.plot_light(ax)
    fig.patch.set_facecolor('#fff9f0')
    fig.set_size_inches(8, 8)

    # post-process for html
    canvas = FigureCanvas(fig)
    png_output = StringIO.StringIO()
    canvas.print_png(png_output)
    response = make_response(png_output.getvalue())
    response.headers['Content-Type'] = 'image/png'
        
    plt.cla()   # Clear axis
    plt.clf()   # Clear figure
    plt.close() # Close a figure window
    return response 


@app.route('/inverted_polar_plot')
def draw_inverted_polar_plot():
    plt.cla()   # Clear axis
    plt.clf()   # Clear figure
    plt.close() # Close a figure window

    fig = plt.figure()
    ax = fig.add_axes([0,0,1,1])
    sil.draw_inverted_polar(ax, color='k')
    this_year = dt.datetime.today().year
    dates_to_plot = [
        dt.datetime(this_year, 6, 21), 
        dt.datetime.today(),
        dt.datetime(this_year, 12, 22)
    ]
    morning_colors = ['#ffc469', '#fd8181', '#ffc469']
    afternoon_colors = ['#f98536', 'r', '#f98536']
    labels = ['Jun 21', 'today', 'Dec 22']
    text_colors = ['#f98536', 'r', '#f98536']
    for i in range(0, len(dates_to_plot)):
        d = dates_to_plot[i]
        cm = morning_colors[i]
        ca = afternoon_colors[i]
        ct = text_colors[i]
        l = labels[i]
        sun = SunPath(
            stepsize=SUN_STEPSIZE, 
            lat=obs.lat, 
            lon=obs.lon, 
            date=d)
        sun.calculate_path()
        sun.calculate_visibility(sil)
        sun.draw_inverted_polar(ax, morning_color=cm, afternoon_color=ca, text_color=ct, label=l)  
    
    ax.axis('off')
    ax.set_aspect('equal')
    fig.patch.set_facecolor('#fff9f0')
    fig.set_size_inches(8, 8)

    # post-process for html
    canvas = FigureCanvas(fig)
    png_output = StringIO.StringIO()
    canvas.print_png(png_output)
    response = make_response(png_output.getvalue())
    response.headers['Content-Type'] = 'image/png'
        
    plt.cla()   # Clear axis
    plt.clf()   # Clear figure
    plt.close() # Close a figure window
    return response 


