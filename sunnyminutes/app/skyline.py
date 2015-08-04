# skyline module

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge, Circle
from matplotlib.collections import PatchCollection

# class to store the geometry of a rooftop on the skyline
class Roof:
    def __init__(self, tup=(-1, 1, -1)):
        self.phi1 = tup[0]
        self.phi2 = tup[1]
        self.theta = tup[2]
    
    def show(self):
        print "(phi1=" + str(self.phi1) + ", phi2=" + str(self.phi2) + ", theta=" + str(self.theta) +")"   



# class to store the geometry of the steps between consecutive rooftops on the skyline
class Cliff:
    def __init__(self, phi=None, theta_L=None, theta_R=None ):
        self.phi = phi
        self.theta_L = theta_L
        self.theta_R = theta_R
    
    def show(self):
        print "(phi=" + str(self.phi) + ", theta_L=" + str(self.theta_L) + ", theta_R=" + str(self.theta_R) +")"   
    


# class to store the skyline
class Silhouette:
    
    def __init__(self):
        self.cliffs = [] # list of cliffs ordered by phi
        # add the two extreme points
        self.cliffs.append(Cliff(-np.pi -1, 0,0))
        self.cliffs.append(Cliff(np.pi + 1, 0,0))
    
    def add_roof(self, roof):
        # find the cliffs that are between the roof's phi1 and phi2
        cliffs_inside = []
        insert_index_1 = 0
        insert_index_2 = 0

        i = 0
        while self.cliffs[i].phi < roof.phi1:
            insert_index_1 += 1
            insert_index_2 += 1
            i += 1
        while self.cliffs[i].phi < roof.phi2:
            insert_index_2 += 1
            i += 1
            
        # in case the entire roof falls between too cliffs
        if not self.cliffs[insert_index_1 : insert_index_2]:
            # get the silhouette's height from previous cliff
            theta = self.cliffs[insert_index_1 -1].theta_R
            # add only if it's higher
            if theta < roof.theta:
                cliff1 = Cliff(roof.phi1, theta, roof.theta)
                cliff2 = Cliff(roof.phi2, roof.theta, theta)
                self.cliffs.insert(insert_index_1, cliff1)
                insert_index_2 += 1 # the first insertion shift the index
                self.cliffs.insert(insert_index_2, cliff2)
                
        # in case the roof spans over at least one cliff
        else:
            
            # process the cliffs between the roof endpoints
            cliffs_to_delete = []
            for i in range(insert_index_1, insert_index_2):
                L = self.cliffs[i].theta_L
                R = self.cliffs[i].theta_R
                H = roof.theta
                
                # if the cliff is under the roof, delete it
                if L < H and R < H:
                    cliffs_to_delete.insert(0,i)
                
                # if the cliff crosses the roof downwards, update it
                elif L > H and R < H:
                    self.cliffs[i].theta_R = roof.theta
                
                # if the cliff crosses the roof upwards, update it
                elif L < H and R > H:
                    self.cliffs[i].theta_L = roof.theta
                
                # if the cliff is above the roof, it shouldn't change
            
            # process the endpoints of the roof
            theta1 = self.cliffs[insert_index_1 -1].theta_R
            theta2 = self.cliffs[insert_index_2].theta_L
            
            # add phi2 first
            if theta2 < roof.theta:
                cliff2 = Cliff(roof.phi2, roof.theta, theta2)
                self.cliffs.insert(insert_index_2, cliff2)
            
            # delete cliffs under the roof
            for index in cliffs_to_delete:
                self.cliffs.pop(index)
            
            # add phi1 last
            if theta1 < roof.theta:
                cliff1 = Cliff(roof.phi1, theta1, roof.theta)
                self.cliffs.insert(insert_index_1, cliff1)
 
    def calculate_sky_visibility(self):
        deltaphi_list = []
        theta_list = []

        for i in range(0, len(self.cliffs)-1, 1):
            deltaphi_list.append(self.cliffs[i+1].phi - self.cliffs[i].phi)
            theta_list.append(self.cliffs[i].theta_R)

        deltaphi_arr = np.array(deltaphi_list)
        theta_arr = np.array(theta_list)

        full_sky = 2*np.pi
        covered_sky = sum(deltaphi_arr * np.sin(theta_arr))
        visible_sky = (full_sky - covered_sky) / full_sky
        return visible_sky

    def draw(self, ax, color='k'):
            
        # colelect (phi, theta) from cliffs
        phi_list = []
        theta_list = []
        for cliff in self.cliffs:
            phi_list.append(cliff.phi * 180 / np.pi )
            theta_list.append(cliff.theta_L * 180 / np.pi)
            phi_list.append(cliff.phi * 180 / np.pi )
            theta_list.append(cliff.theta_R * 180 / np.pi)

        ax.fill_between(phi_list, 0, theta_list, color=color, facecolor=color)

        # plot East, South and West markers as vertical lines
        gray_color = '#909090'
        ax.plot([-90, -90], [0, 90], color=gray_color)
        ax.plot([0, 0], [0, 90], color=gray_color)
        ax.plot([90, 90], [0, 90], color=gray_color)

        plt.text(-179, 1, 'N', color=gray_color)
        plt.text(-89, 1, 'E', color=gray_color)
        plt.text(1, 1, 'S', color=gray_color)
        plt.text(91, 1, 'W', color=gray_color)
        plt.text(175, 1, 'N', color=gray_color)
        


    def draw_inverted_polar(self, ax, color='k', plot_size=1.85):
        gray_color = '#909090'

        # plot horizon
        p = PatchCollection([Circle((0,0), np.pi/2+0.02)], color=gray_color)
        ax.add_collection(p)

        # plot sky
        p = PatchCollection([Circle((0,0), np.pi/2)], color='#bed6ff')
        ax.add_collection(p)

        # get (phi, theta) coordinates from cliffs
        phis = []
        thetas = []
        for cliff in self.cliffs:
            phis.append(cliff.phi)
            thetas.append(cliff.theta_L) 
            phis.append(cliff.phi)
            thetas.append(cliff.theta_R) 
        phis = np.array(phis)
        thetas = np.array(thetas)
        
        # get rid of points out of bounds
        phi_deg = phis * 180/np.pi
        for i in range(0, len(phi_deg)):
            if phi_deg[i] < -180:
                phi_deg[i] = -180
            if phi_deg[i] > 180:
                phi_deg[i] = 180

        # declare wedges, corresponding to the buildings
        wedge_list = []
        for i in range(0, len(phi_deg)-1):
            wedge_list.append(
                Wedge(
                    (0,0),
                    np.pi/2,
                    90+phi_deg[i],
                    90+phi_deg[i+1],
                    width=thetas[i]
                )
            )
        p = PatchCollection(wedge_list, facecolor=color, edgecolor=gray_color)
        ax.add_collection(p)

        # declare wedges, corresponding to the sky above each roof
        # wedge_list = []
        # for i in range(0, len(phi_deg)-1):
        #     wedge_list.append(
        #         Wedge(\
        #             (0,0), \
        #             np.pi/2 - thetas[i], \
        #             90+phi_deg[i], \
        #             90+phi_deg[i+1]
        #         ) \
        #     )
        # p = PatchCollection(wedge_list, color='#bed6ff')
        # ax.add_collection(p)


        
        
        # geographic directions and their names
        L = plot_size
        gray_color = '#909090'
        fontsize = 'large'
        outer_radius = np.pi/2 + 0.03
        ax.plot([0,0], [0.7*L,L], color=gray_color, zorder=10)
        ax.plot([0,0], [-0.7*L,-L], color=gray_color, zorder=10)
        ax.plot([-L,-0.7*L], [0,0], color=gray_color, zorder=10)
        ax.plot([L,0.7*L], [0,0], color=gray_color, zorder=10)
        ax.text(0, -outer_radius, 'North', 
            verticalalignment=u'top', 
            horizontalalignment=u'center',
            size=fontsize)
        ax.text(0, outer_radius, 'South', 
            verticalalignment=u'bottom', 
            horizontalalignment=u'center',
            size=fontsize)
        ax.text(-outer_radius, 0, 'West', 
            verticalalignment=u'bottom', 
            horizontalalignment=u'right',
            size=fontsize)
        ax.text(outer_radius, 0, 'East', 
            verticalalignment=u'bottom', 
            horizontalalignment=u'left',
            size=fontsize)

        # axes
        ax.set_ylim([-L, L])
        ax.set_xlim([-L, L])
        ax.xaxis.set_visible(False)
        ax.yaxis.set_visible(False)
        ax.set_aspect('equal')


