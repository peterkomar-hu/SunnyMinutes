# sun modul

import numpy as np
import datetime as dt
from dateutil.parser import parse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

DURATION_OF_SUNRISE_SUNSET = 15 # minutes


class SunPath:
    
    def __init__(self, stepsize=1, lat=None, lon=None, date=dt.datetime.today()):
        self.positions = []  # list of tuples (phi, theta)
        self.visible = []
        self.stepsize = stepsize
        self.lat = lat
        self.lon = lon
        self.date = date

    def get_date(self, date_str):
        # extract month and day from string such as "4/13"
        try:
            self.date = parse(date_str)
        except:
            print "Warning: input date cannot be parsed, using default: today()"


    def get_sun_vector(self):
        # convert to datetime
        start_date = dt.datetime(2000,1,1)

        # the number of days from 1 Jan 2000
        n = (self.date - start_date).days

        # mean longitude of the Sun
        L_deg = (280.460 + 0.9856474 * n) % 360

        # mean anomaly of the Sun
        g_deg = (357.528 + 0.9856003 * n) % 360
        g_rad = g_deg * np.pi/180

        # ecliptic longitude
        lambda_deg = L_deg + 1.915 * np.sin(g_rad) + 0.020 * np.sin(2*g_rad)
        lambda_rad = lambda_deg * np.pi/180

        # obliquity of the ecliptic
        eps_deg = 23.439 - 0.0000004 * n
        eps_rad = eps_deg * np.pi/180

        # Sun's unit vector (in equatorial coordinates) for this day
        u_sun = np.array([
                    np.cos(lambda_rad), \
                    np.cos(eps_rad) * np.sin(lambda_rad), \
                    np.sin(eps_rad) * np.sin(lambda_rad)\
                ])
        return u_sun

    # cities GPS coordinates
    def get_city_vectors(self, greenwich_time_minutes):

        minute2deg = 360.0/1440.0

        theta_city_deg = 90 - self.lat
        theta_city_rad = theta_city_deg * np.pi/180

        phi_city_deg = greenwich_time_minutes * minute2deg + self.lon
        phi_city_rad = phi_city_deg * np.pi/180

        # city's unit vector
        u_r = np.array([
                    np.sin(theta_city_rad) * np.cos(phi_city_rad),
                    np.sin(theta_city_rad) * np.sin(phi_city_rad),
                    np.cos(theta_city_rad)
                ])
        u_theta = np.array([
                    np.cos(theta_city_rad) * np.cos(phi_city_rad),
                    np.cos(theta_city_rad) * np.sin(phi_city_rad),
                    -np.sin(theta_city_rad)
                ])
        u_phi = np.array([
                    -np.sin(phi_city_rad),
                    np.cos(phi_city_rad),
                    0
                ])
        return (u_r, u_theta, u_phi)


    def calculate_path(self):
            
        u_sun = self.get_sun_vector()

        for time_minutes in range(0, 1440, self.stepsize):
            (u_r, u_theta, u_phi) = \
                self.get_city_vectors(time_minutes)

            # calculate height of the Sun on the sky
            theta_rad = np.pi/2 - np.arccos( np.dot(u_r, u_sun) )
            
            if theta_rad > 0:
                # calculate projected Sun vector
                u_sun_projected = u_sun - u_r * np.dot(u_r, u_sun)
                u_sun_projected = u_sun_projected / \
                    np.sqrt(np.dot(u_sun_projected, u_sun_projected))

                # calculate azimuth of Sun
                phi_rad = np.arccos( np.dot(u_sun_projected, u_theta) )
                if np.dot(u_sun_projected, u_phi) > 0:
                    phi_rad *= -1

                self.positions.append( (phi_rad, theta_rad) )
            
            self.positions.sort(key=lambda t:t[0])

    def calculate_visibility(self, sil):
        cliff_index = 0
        for p in self.positions:
            while sil.cliffs[cliff_index].phi < p[0]:
                cliff_index += 1
            vis = sil.cliffs[cliff_index].theta_L < p[1]
            self.visible.append( vis )
        # return (sum(self.visible), len(self.positions))
        
    # def draw(self, ax, color='#ffa700', deg=True, linewidth=3.0):
    #     if deg:
    #         phis = []
    #         thetas = []
    #         for p in self.positions:
    #             phis.append(p[0] * 180/np.pi)
    #             thetas.append(p[1] * 180/np.pi)
    #         ax.plot(phis, thetas, color=color, linewidth=linewidth)
    #     else:
    #         ax.plot(self.phi_list, self.theta_list, color=color, linewidth=linewidth)

# colors:
#   almost white: #ffedd2
#   pastel sun: #ffc469
#   sunset orange: #f98536
#   dark pastel sun: #cc9c54


    def draw_inverted_polar(self, ax, 
        solid_linewidth=6, 
        dashed_linewidth=1,
        morning_color='#ffc469',
        afternoon_color='#f98536'):

        path = self.positions
        vis = self.visible
        L = len(path)

        i = 0

        # morning sun
        while i < L/2:
            if not vis[i]:
                x_list = []
                y_list = []
                while not vis[i]:                
                    r = np.pi/2 - path[i][1]
                    x_list.append(-r * np.sin(path[i][0]))
                    y_list.append(r * np.cos(path[i][0]))
                    i += 1
                    if not i < L/2:
                        break
                ax.plot(x_list, y_list, color=morning_color, 
                    linewidth=dashed_linewidth, linestyle='--')
            else:
                x_list = []
                y_list = []
                while vis[i]:                
                    r = np.pi/2 - path[i][1]
                    x_list.append(-r * np.sin(path[i][0]))
                    y_list.append(r * np.cos(path[i][0]))
                    i += 1
                    if not i < L/2:
                        break
                ax.plot(x_list, y_list, color=morning_color, linewidth=solid_linewidth)
            i += 1

        # afternoon sun
        while i < L:
            if not vis[i]:
                x_list = []
                y_list = []
                while not vis[i]:                
                    r = np.pi/2 - path[i][1]
                    x_list.append(-r * np.sin(path[i][0]))
                    y_list.append(r * np.cos(path[i][0]))
                    i += 1
                    if not i < L:
                        break
                ax.plot(x_list, y_list, color=afternoon_color, 
                    linewidth=dashed_linewidth, linestyle='--')
            else:
                x_list = []
                y_list = []
                while vis[i]:                
                    r = np.pi/2 - path[i][1]
                    x_list.append(-r * np.sin(path[i][0]))
                    y_list.append(r * np.cos(path[i][0]))
                    i += 1
                    if not i < L:
                        break
                ax.plot(x_list, y_list, color=afternoon_color, linewidth=solid_linewidth)
            i += 1



        # # morning sun
        # for p in self.positions[0:L/2]:
        #     r = np.pi/2 - p[1]
        #     x_list.append(-r * np.sin(p[0]))
        #     y_list.append(r * np.cos(p[0]))
        # ax.plot(x_list, y_list, color='#cc9c54', linewidth=linewidth)

        # # afternoon sun
        # for p in self.positions[0:L/2]:
        #     r = np.pi/2 - p[1]
        #     x_list.append(-r * np.sin(p[0]))
        #     y_list.append(r * np.cos(p[0]))
        # ax.plot(x_list, y_list, color='#f98536', linewidth=linewidth)


class SunSummary:
    def __init__(self):
        self.dates = [] # list of datetimes pointing to the Mondays of the weeks
        self.total_sun = [] # list of floats (minutes)
        self.morning_sun = [] # list of floats (minutes)
        self.afternoon_sun = [] # list of floats (minutes)
        self.sunrise = [] # list of booleans
        self.sunset = [] # list of booleans
        
        # initialize weeks
        this_year = dt.datetime.today().year
        one_week = dt.timedelta(weeks=1)
        d = dt.datetime(this_year, 1, 1)
        while d.year == this_year:
            self.dates.append(d)
            d += one_week

    def clear(self):
        self.dates = [] # list of datetimes pointing to the Mondays of the weeks
        self.total_sun = [] # list of floats (minutes)
        self.morning_sun = [] # list of floats (minutes)
        self.afternoon_sun = [] # list of floats (minutes)
        self.sunrise = [] # list of booleans
        self.sunset = [] # list of booleans
        
        # initialize weeks
        this_year = dt.datetime.today().year
        one_week = dt.timedelta(weeks=1)
        d = dt.datetime(this_year, 1, 1)
        while d.year == this_year:
            self.dates.append(d)
            d += one_week


    def collect_summary(self, silhouette, observer, stepsize):
        for date in self.dates:
            this_sun = SunPath(lat=observer.lat, lon=observer.lon, date=date, stepsize=stepsize)
            this_sun.calculate_path()
            this_sun.calculate_visibility(silhouette)

            total_steps = len(this_sun.positions)
            self.total_sun.append(total_steps * this_sun.stepsize)
            self.morning_sun.append(sum(this_sun.visible[:total_steps/2])  * this_sun.stepsize)
            self.afternoon_sun.append(sum(this_sun.visible[total_steps/2:])  * this_sun.stepsize)
            sunset_limit_index = int(15 / this_sun.stepsize)
            self.sunrise.append(any(this_sun.visible[:sunset_limit_index]))
            self.sunset.append(any(this_sun.visible[-sunset_limit_index:]))

    def plot_light(self, ax):
        color_morning = '#ffc469'
        color_afternoon = '#f98536'
        dashed_style = ':'
        height_sunset_line = 500
        height_of_plot = 600
        dy_ticks = 100

        week_list = np.arange(1, len(self.dates)+1, 1)
        L = len(week_list)

        dates = self.dates
        total = np.array(self.total_sun)
        morning = np.array(self.morning_sun)
        afternoon = np.array(self.afternoon_sun)

        # plot curves for the minutes of sun
        ax.plot(week_list, total/2, color='k', linestyle=dashed_style)
        ax.plot(week_list , -total/2, color='k', linestyle=dashed_style)
        ax.fill_between(week_list , 0, - morning , color=color_morning)
        ax.fill_between(week_list , 0, afternoon, color=color_afternoon)
        ax.set_xlim([1, L])  

        # find the x positions of the first day of every week
        first_weeks = []
        d = dates[0]
        year = d.year
        one_day = dt.timedelta(days=1)
        current_month = 0
        i = 0
        while d.year == year :
            if d.month > current_month:
                first_weeks.append(1 + i / 7.0)
                current_month += 1
            d += dt.timedelta(days=1)
            i += 1

        # plot vertical lines to divide months
        for i in first_weeks:
            ax.plot([i,i], [height_of_plot, -height_of_plot], color='k', linewidth=0.5)

        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        for i in range(0, 12, 1):
            ax.text(first_weeks[i]+1.5, height_of_plot - 50, month_names[i])
            ax.text(first_weeks[i]+1.5, -height_of_plot + 30, month_names[i])

        # turn y labels into positive numbers
        y_ticks = range(-height_of_plot, +height_of_plot + dy_ticks, dy_ticks)
        y_labels = [str(np.abs(yt)) for yt in y_ticks]
        plt.yticks(y_ticks, y_labels)

        ax.xaxis.set_visible(False)
        ax.set_ylabel('minutes of morning/afternoon sun')
        







