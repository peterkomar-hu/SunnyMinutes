__author__ = 'Peter Komar'

# modules for the web app
from flask import Flask
from flask import render_template, request, make_response
import StringIO
import matplotlib
matplotlib.use('Agg')
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure

app = Flask(__name__)


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

    # add buildings in neighboring blocks
    for i in range(1, len(x_id_list)):
        buildings.update(\
            append_buildings_in_block(con, x_id_list[i], y_id_list[i])\
        )

    # create plot for building zoom
    fig = plt.figure()
    ax = fig.add_axes([0,0,1,1])
    radius = ZOOM_SIZE/2 * 1.5
    for key in buildings:
        if obs.distance_from_building(buildings[key]) < radius:
            buildings[key].plot_footprint(ax, color='k')
    obs.plot_observers_location(ax)
    L = ZOOM_SIZE/2     # half size of the plotted area in meters
    ax.set_xlim([obs.x-L, obs.x+L])
    ax.set_ylim([obs.y-L, obs.y+L])    
    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)    
    ax.set_aspect('equal')
    fig.set_size_inches(5, 5)
    plt.savefig('./static/building_zoom.png', bbox_inches='tight')
    fig.clf()

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
    obs.convert_to_geographical()

    exec 'floor_placeholder = "'+ str(int(round(obs.z / 3))) + '"' in globals()

    # create plot for building zoom
    fig = plt.figure()
    ax = fig.add_axes([0,0,1,1])
    radius = ZOOM_SIZE/2 * 1.5
    for key in buildings:
        if obs.distance_from_building(buildings[key]) < radius:
            buildings[key].plot_footprint(ax, color='k')
    obs.plot_observers_location(ax)
    L = ZOOM_SIZE/2     # half size of the plotted area in meters
    ax.set_xlim([obs.x-L, obs.x+L])
    ax.set_ylim([obs.y-L, obs.y+L])    
    ax.xaxis.set_visible(False)
    ax.yaxis.set_visible(False)    
    ax.set_aspect('equal')
    fig.set_size_inches(5, 5)
    plt.savefig('./static/building_zoom.png', bbox_inches='tight')
    fig.clf()

    return render_template('show_calculate_button.html', 
        address_placeholder=address_placeholder, 
        floor_placeholder=floor_placeholder)

@app.route('/results')
def show_results():
    floor = request.args.get('Floor')

    # if not obs.get_altitude(floor):
    #     floor = DEFAULT_FLOOR
    exec 'floor_placeholder = "'+ str(int(round(obs.z / 3))) + '"' in globals()


    # add roofs of the buildigns to sil
    sil.cliffs = Silhouette().cliffs
    for key in buildings:
        if buildings[key].z > obs.z:
            roofs = buildings[key].get_roofs(obs.x, obs.y, obs.z)
            for tup in roofs:
                sil.add_roof( Roof(tup) )
    
    summary.clear()
    summary.collect_summary(sil, obs, SUN_STEPSIZE)

    # create light summary plot
    fig = plt.figure()
    ax = fig.add_subplot(111)
    #ax = fig.add_axes([0,0,1,1])
    summary.plot_light(ax)
    fig.set_size_inches(8, 8)
    plt.savefig('./static/light_plot.png', bbox_inches='tight')    
    fig.clf()

    # create fisheye plot
    fig = plt.figure()
    ax = fig.add_axes([0,0,1,1])
    sil.draw_inverted_polar(ax, color='k')
    this_year = dt.datetime.today().year
    dates_to_plot = [
        dt.datetime(this_year, 3, 20), 
        dt.datetime(this_year, 6, 21), 
        dt.datetime(this_year, 12, 22)
    ]
    for d in dates_to_plot:
        sun = SunPath(
            stepsize=SUN_STEPSIZE, 
            lat=obs.lat, 
            lon=obs.lon, 
            date=d)
        sun.calculate_path()
        sun.calculate_visibility(sil)
        sun.draw_inverted_polar(ax)  
    fig.set_size_inches(8, 8)
    plt.savefig('./static/inverted_polar_plot.png', bbox_inches='tight')
    fig.clf()

    return render_template("results.html", lat=obs.lat, lon=obs.lon, 
        address_placeholder=address_placeholder, 
        floor_placeholder=floor_placeholder)


# @app.route('/building_zoom')
# def draw_building_zoom():
#     fig = plt.figure()
#     ax = fig.add_axes([0,0,1,1])

#     radius = ZOOM_SIZE/2 * 1.5
#     for key in buildings:
#         if obs.distance_from_building(buildings[key]) < radius:
#             buildings[key].plot_footprint(ax, color='k')
#     obs.plot_observers_location(ax)

#     L = ZOOM_SIZE/2     # half size of the plotted area in meters
#     ax.set_xlim([obs.x-L, obs.x+L])
#     ax.set_ylim([obs.y-L, obs.y+L])    
#     ax.xaxis.set_visible(False)
#     ax.yaxis.set_visible(False)    

#     ax.set_aspect('equal')
#     fig.set_size_inches(5, 5)

#     # post-process for html
#     canvas = FigureCanvas(fig)
#     png_output = StringIO.StringIO()
#     canvas.print_png(png_output)
#     response = make_response(png_output.getvalue())
#     response.headers['Content-Type'] = 'image/png'

#     fig.clf()
#     return response 



# @app.route('/light_plot')
# def draw_light_plot():
#     fig = plt.figure()
#     ax = fig.add_subplot(111)
#     #ax = fig.add_axes([0,0,1,1])

#     summary.plot_light(ax)

#     fig.set_size_inches(8, 8)


#     # post-process for html
#     canvas = FigureCanvas(fig)
#     png_output = StringIO.StringIO()
#     canvas.print_png(png_output)
#     response = make_response(png_output.getvalue())
#     response.headers['Content-Type'] = 'image/png'
        
#     fig.clf()
#     return response 


# @app.route('/inverted_polar_plot')
# def draw_inverted_polar_plot():
#     fig = plt.figure()
#     ax = fig.add_axes([0,0,1,1])

#     sil.draw_inverted_polar(ax, color='k')
    

#     this_year = dt.datetime.today().year
#     dates_to_plot = [
#         dt.datetime(this_year, 3, 20), 
#         dt.datetime(this_year, 6, 21), 
#         dt.datetime(this_year, 12, 22)
#     ]
#     for d in dates_to_plot:
#         sun = SunPath(
#             stepsize=SUN_STEPSIZE, 
#             lat=obs.lat, 
#             lon=obs.lon, 
#             date=d)
#         sun.calculate_path()
#         sun.calculate_visibility(sil)
#         sun.draw_inverted_polar(ax)
    
#     fig.set_size_inches(8, 8)

#     # post-process for html
#     canvas = FigureCanvas(fig)
#     png_output = StringIO.StringIO()
#     canvas.print_png(png_output)
#     response = make_response(png_output.getvalue())
#     response.headers['Content-Type'] = 'image/png'
        
#     fig.clf()
#     return response 


# @app.route('/block_map')
# def draw_block():
#     fig = plt.figure()
#     # ax = fig.add_subplot(111)
#     ax = fig.add_axes([0,0,1,1])
#     for key in buildings:
#         if buildings[key].z > obs.z:    # plot only if building is taller than observer
#             if buildings[key].z < 20:
#                 color = 'k'
#             elif buildings[key].z < 50:
#                 color = 'b'
#             elif buildings[key].z < 100:
#                 color = 'g'
#             elif buildings[key].z < 200:
#                 color = 'r'
#             else:
#                 color = 'y'
            
#             buildings[key].plot_footprint(ax, color='k') 

#     obs.plot_observers_location(ax, color='k')
    
#     L = 500
#     ax.set_xlim([obs.x-L, obs.x+L])
#     ax.set_ylim([obs.y-L, obs.y+L])    
#     ax.xaxis.set_visible(False)
#     ax.yaxis.set_visible(False)    
    
#     ax.set_aspect('equal')
#     fig.set_size_inches(8, 8)

#     # post-process for html
#     canvas = FigureCanvas(fig)
#     png_output = StringIO.StringIO()
#     canvas.print_png(png_output)
#     response = make_response(png_output.getvalue())
#     response.headers['Content-Type'] = 'image/png'
#     return response 


# @app.route('/silhouette')
# def draw_silhouette():
#     fig = plt.figure()
#     ax = fig.add_subplot(111)

#     sun.draw(ax)       
#     sil.draw(ax)

#     ax.set_ylim([0, 90])
#     ax.set_xlim([-180, 180])

#     ax.set_aspect('equal', adjustable='box')
#     fig.set_size_inches(10, 2.5)

#     # post-process for html
#     canvas = FigureCanvas(fig)
#     png_output = StringIO.StringIO()
#     canvas.print_png(png_output)
#     response = make_response(png_output.getvalue())
#     response.headers['Content-Type'] = 'image/png'
#     return response 







# @app.route('/input')
# def input():
#     address = request.args.get('Address')
#     floor = request.args.get('Floor')
#     day_of_year = request.args.get('Day')
    
#     if address:
#         address = address + ' New York City'
#     else:
#         address = 'Columbus Circle, New York City'

#     obs.get_geocoordinates(address, floor)
#     obs.convert_to_cartesian()
#     obs.find_my_block(x_grid, y_grid)

#     sun.get_date(day_of_year)
#     sun.lat = obs.lat
#     sun.lon = obs.lon

#     # get all buildings within the 9 blocks around the observer
#     buildings.clear()
#     (x_id_list, y_id_list) = obs.get_neighboring_block_ids()
    
#     # # add buildings on the block
#     # buildings.update(append_buildings_in_block(con, x_id_list[0], y_id_list[0]))

#     # # select the buildings the observer is sitting in, and delete them
#     # building_at_address_keys = obs.get_my_buildings(buildings)
#     # if building_at_address_keys:
#     #     for key in building_at_address_keys:
#     #         del buildings[key]

#     # add buildings in neighboring blocks
#     for i in range(0, len(x_id_list)):
#         buildings.update(\
#             append_buildings_in_block(con, x_id_list[i], y_id_list[i])\
#         )


#     # # add roofs of the buildigns to sil
#     # sil.cliffs = Silhouette().cliffs
#     # for key in buildings:
#     #     if buildings[key].z > obs.z:
#     #         roofs = buildings[key].get_roofs(obs.x, obs.y, obs.z)
#     #         for tup in roofs:
#     #             sil.add_roof( Roof(tup) )
    
#     # sun.positions = []
#     # sun.calculate_path()

#     # sun.visible = []
#     # v = sun.calculate_visibility(sil)
#     # # message = str(v[0]) + ' min sunny / ' + str(v[1]) + ' min total'

#     return render_template("input.html")
    
if __name__ == "__main__":
   app.run(host='0.0.0.0', port=5000, debug=True)

