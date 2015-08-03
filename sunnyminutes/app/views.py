
# modules for the web app
from flask import Flask
from flask import render_template, request, make_response, session, redirect, url_for
from app import app
import StringIO
import matplotlib
matplotlib.use('Agg')
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure

from matplotlib import pylab as plt
import pymysql as mdb
import datetime as dt

# my modules
from buildingmapping import *
from skyline import *
from sun import *
from observer import *
from user import *


# colors
COLOR_BROWN = '#2d1b00'
COLOR_LIGHTBROWN = '#ffc469'

DEFAULT_DAY = '7/31'
DEFAULT_ADDRESS = 'Columbus Circle'
DEFAULT_FLOOR = '0'
ZOOM_SIZE = 200
ZOOM_SIZE_PX = 350
SUN_STEPSIZE = 5

SESSION_LIFETIME_IN_SECONDS = 2 * 60
MAX_NUMBER_OF_ACTIVE_USERS = 100


write_to_log('Restarting flask server')
next_user_id = get_next_user_id()
users = {}





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
    # check existing users for activity, delete inactive users
    inactive_users = []
    now = dt.datetime.today()
    for uid in users:
        if (now - users[uid].last_activity_time).seconds > SESSION_LIFETIME_IN_SECONDS:
            inactive_users.append(uid)
    for uid in inactive_users:
        write_to_log(
            'Deactivating user: uid= ' + str(uid) 
            )
        del users[uid]


    if len(users) >= MAX_NUMBER_OF_ACTIVE_USERS:
        return redirect(url_for('about_page'))

    if 'userid' in session:
        uid = session['userid']
        if uid not in users:
            write_to_log(
                'Reactivating returning user: uid= ' + str(uid)
                + ', IP: ' + str(request.remote_addr))
    else:
        uid = get_next_user_id()
        exec 'next_user_id += 1' in globals()
        put_next_user_id(next_user_id)
        write_to_log(
            'Adding new user: uid= ' + str(uid)
            + ', IP: ' + str(request.remote_addr))
        session['userid'] = uid

    
    users[uid] = User()

    

    write_to_log(
        'Users'
        + ' active: ' + str(len(users))
        + ', total: ' +  str(next_user_id))

    

    return render_template('start.html', 
        address_placeholder=users[uid].address_placeholder)

@app.route('/about_page')
def go_to_about_page():
    if 'userid' in session:
        uid = session['userid']
        if uid in users:
            users[uid].record_as_active()
    return render_template('about.html')
    
@app.route('/contact_page')
def go_to_contact_page():
    if 'userid' in session:
        uid = session['userid']
        if uid in users:
            users[uid].record_as_active()
    return render_template('contact.html')


@app.route('/zoom')
def zoom():
    if 'userid' not in session:
        return redirect(url_for('index'))
    uid = session['userid']
    if uid not in users:
        return redirect(url_for('index'))
    users[uid].record_as_active()    

    con = mdb.connect('localhost', 'root', '123', 'Manhattan_buildings')

    # load basic information about Manhattan
    users[uid].obs.load_basic_geography(con)
    (users[uid].x_grid, users[uid].y_grid) = load_grid_data(con)

    address = request.args.get('Address')
    
    if address:
        address = address + ', Manhattan'
    else: 
        address = DEFAULT_ADDRESS

    users[uid].address_placeholder = address

    users[uid].obs.get_geocoordinates(address, floor=DEFAULT_FLOOR)
    users[uid].obs.convert_to_cartesian()
    users[uid].obs.find_my_block(users[uid].x_grid, users[uid].y_grid)

    # get all buildings within the 9 blocks around the observer
    users[uid].buildings.clear()
    (x_id_list, y_id_list) = users[uid].obs.get_neighboring_block_ids()

    # add buildings on the block
    buildings_in_observers_block = append_buildings_in_block(con, x_id_list[0], y_id_list[0])
    if buildings_in_observers_block:
        users[uid].buildings.update(buildings_in_observers_block)
    # block is empty, fall back to default address
    else:
        users[uid].obs.get_geocoordinates(DEFAULT_ADDRESS, floor=DEFAULT_FLOOR)
        users[uid].obs.convert_to_cartesian()
        users[uid].obs.find_my_block(x_grid, y_grid)
        users[uid].buildings.clear()
        (x_id_list, y_id_list) = users[uid].obs.get_neighboring_block_ids()
        users[uid].buildings.update(append_buildings_in_block(con, x_id_list[0], y_id_list[0]))

    # find the buildings the observer is sitting in
    del users[uid].building_keys_at_address[:]
    users[uid].building_keys_at_address.extend(users[uid].obs.get_my_buildings(users[uid].buildings))

    # find windows
    users[uid].obs.clear_windows()
    for key in users[uid].building_keys_at_address:
        users[uid].obs.get_windows(users[uid].buildings[key])

    # add buildings in neighboring blocks
    for i in range(1, len(x_id_list)):
        users[uid].buildings.update(
            append_buildings_in_block(con, x_id_list[i], y_id_list[i])\
        )

    return render_template('zoom_to_address.html', 
        address_placeholder=users[uid].address_placeholder)

@app.route('/zoom_adjust')
def zoom_after_click():
    if 'userid' not in session:
        return redirect(url_for('index'))
    uid = session['userid']
    if uid not in users:
        return redirect(url_for('index'))
    users[uid].record_as_active()    
    
    click_x = float(request.args.get('zoom.x'))
    click_y = float(request.args.get('zoom.y'))
    dx = (click_x / ZOOM_SIZE_PX - 0.5) * ZOOM_SIZE
    dy = -(click_y / ZOOM_SIZE_PX - 0.5) * ZOOM_SIZE
    users[uid].obs.x = users[uid].obs.x + dx
    users[uid].obs.y = users[uid].obs.y + dy
    users[uid].obs.clear_windows()
    users[uid].obs.convert_to_geographical()

    users[uid].floor_placeholder = str(int(round(users[uid].obs.z / 3)))

    # find the buildings the observer is sitting in
    del users[uid].building_keys_at_address[:]
    users[uid].building_keys_at_address.extend(users[uid].obs.get_my_buildings(users[uid].buildings))

    # find windows
    users[uid].obs.clear_windows()
    for key in users[uid].building_keys_at_address:
        users[uid].obs.get_windows(users[uid].buildings[key])

    return render_template('show_calculate_button.html', 
        address_placeholder=users[uid].address_placeholder, 
        floor_placeholder=users[uid].floor_placeholder)

@app.route('/results')
def show_results():
    if 'userid' not in session:
        return redirect(url_for('index'))
    uid = session['userid']
    if uid not in users:
        return redirect(url_for('index'))
    users[uid].record_as_active()    


    floor = request.args.get('Floor')

    if not users[uid].obs.get_altitude(floor):
        floor = DEFAULT_FLOOR
    users[uid].floor_placeholder = str(int(round(users[uid].obs.z / 3)))

    # clear skyline
    users[uid].sil.cliffs = Silhouette().cliffs
    
    # add the roof blocking the view towards the back of the window
    if users[uid].obs.closest_window:
        phi_window = users[uid].obs.closest_window.phi
        if phi_window < -np.pi/2:
            users[uid].sil.add_roof(
                Roof((
                    phi_window + np.pi/2, 
                    phi_window - np.pi/2 + 2*np.pi, 
                    np.pi/2
                ))
            )
        elif phi_window > np.pi/2:
            users[uid].sil.add_roof(
                Roof((
                    phi_window + np.pi/2 -2*np.pi, 
                    phi_window - np.pi/2, 
                    np.pi/2
                ))
            )
        else:
            users[uid].sil.add_roof(
                Roof((
                    -np.pi, 
                    phi_window - np.pi/2, 
                    np.pi/2
                ))
            )
            users[uid].sil.add_roof(
                Roof((
                    phi_window + np.pi/2, 
                    np.pi, 
                    np.pi/2
                ))
            )

    # add roofs of the buildings to sil
    for key in users[uid].buildings:
        if (users[uid].buildings[key].z > users[uid].obs.z) and (key not in users[uid].building_keys_at_address):
            if users[uid].obs.windows:
                x = users[uid].obs.closest_window.x
                y = users[uid].obs.closest_window.y
            else:
                x = users[uid].obs.x
                y = users[uid].obs.y
            z = users[uid].obs.z
            roofs = users[uid].buildings[key].get_roofs(x, y, z)
            for tup in roofs:
                users[uid].sil.add_roof( Roof(tup) )
    
    users[uid].summary.clear()
    users[uid].summary.collect_summary(users[uid].sil, users[uid].obs, SUN_STEPSIZE)

    # calculate sun score
    minutes_in_2h = 2*60
    minutes_in_12h = 12*60
    minutes_of_total_visible_sun = sum(users[uid].summary.morning_sun)
    minutes_of_total_visible_sun += sum(users[uid].summary.afternoon_sun)
    minutes_of_total_visible_sun /= len(users[uid].summary.dates)
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
    sky_visibility = users[uid].sil.calculate_sky_visibility()
    sky_score = 5.0 * sky_visibility
    sky_score = round(sky_score, 1)
    sky_icon_file = './static/' + str(round(2 * sky_score, 0) * 0.5) + '_sky.svg'


    if users[uid].obs.closest_window:
        write_to_log(
            'Report: user (uid=' + str(uid) + ') calculates at '
            + '(' + str(users[uid].obs.lat)
            + ', '+ str(users[uid].obs.lon)
            + ', '+ str(users[uid].obs.z) + ') '
            + 'facing ' + str(users[uid].obs.closest_window.phi * 180/np.pi) + ' from south, '
            + 'and gets scores: '
            + '(' + str(sun_score) + ', ' + str(sky_score) + ')'
            )
    else:
        write_to_log(
            'Report: user (uid=' + str(uid) + ') calculates at '
            + '(' + str(users[uid].obs.lat)
            + ', '+ str(users[uid].obs.lon)
            + ', '+ str(users[uid].obs.z) + ') '
            + 'outside, '
            + 'and gets scores: '
            + '(' + str(sun_score) + ', ' + str(sky_score) + ')'
            )

    return render_template("results.html", lat=users[uid].obs.lat, lon=users[uid].obs.lon, 
        address_placeholder=users[uid].address_placeholder, 
        floor_placeholder=users[uid].floor_placeholder,
        sun_score=sun_score,
        sky_score=sky_score,
        sun_icon_file=sun_icon_file,
        sky_icon_file=sky_icon_file)


@app.route('/building_zoom')
def draw_building_zoom():
    if 'userid' not in session:
        return redirect(url_for('index'))
    uid = session['userid']
    if uid not in users:
        return redirect(url_for('index'))
    users[uid].record_as_active()    

    plt.cla()   # Clear axis
    plt.clf()   # Clear figure
    plt.close() # Close a figure window

    fig = plt.figure()
    ax = fig.add_axes([0,0,1,1])
    radius = ZOOM_SIZE/2 * 1.5
    for key in users[uid].buildings:
        if users[uid].obs.distance_from_building(users[uid].buildings[key]) < radius:
            if key not in users[uid].building_keys_at_address:
                users[uid].buildings[key].plot_footprint(ax, color='k')
            else:
                users[uid].buildings[key].plot_footprint(ax, color=COLOR_LIGHTBROWN)
    users[uid].obs.plot_observers_location(ax, color='r')
    L = ZOOM_SIZE/2     # half size of the plotted area in meters
    ax.set_xlim([users[uid].obs.x-L, users[uid].obs.x+L])
    ax.set_ylim([users[uid].obs.y-L, users[uid].obs.y+L])    
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
    if 'userid' not in session:
        return redirect(url_for('index'))
    uid = session['userid']
    if uid not in users:
        return redirect(url_for('index'))
    users[uid].record_as_active()    

    plt.cla()   # Clear axis
    plt.clf()   # Clear figure
    plt.close() # Close a figure window
    
    # create light summary plot
    fig = plt.figure()
    ax = fig.add_subplot(111)
    users[uid].summary.plot_light(ax)
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
    if 'userid' not in session:
        return redirect(url_for('index'))
    uid = session['userid']
    if uid not in users:
        return redirect(url_for('index'))
    users[uid].record_as_active()    

    plt.cla()   # Clear axis
    plt.clf()   # Clear figure
    plt.close() # Close a figure window

    fig = plt.figure()
    ax = fig.add_axes([0,0,1,1])
    users[uid].sil.draw_inverted_polar(ax, color='k')
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
            lat=users[uid].obs.lat, 
            lon=users[uid].obs.lon, 
            date=d)
        sun.calculate_path()
        sun.calculate_visibility(users[uid].sil)
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


