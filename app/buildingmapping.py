# buildingmapping module

import numpy as np

# class to store a single node of a building
class Node:
    def __init__(self, input_x=0, input_y=0):
        self.x = input_x
        self.y = input_y
    
    def show(self):
        print '[x=' + str(self.x) + ', y=' + str(self.y) + ']'

    # function to determine if a node lies outside a boundary piece
    def is_outside(self, boundary_node_1, boundary_node_2):
        ux = self.x - boundary_node_1.x
        uy = self.y - boundary_node_1.y
        vx = boundary_node_2.x - boundary_node_1.x
        vy = boundary_node_2.y - boundary_node_1.y
        
        if ((vx*uy) > (vy*ux)):
            return True
        else:
            return False




# class to store geometries of a single building
class Building:
    def __init__(self):
        self.nodes = []   # list of Nodes
        self.center = Node()
        self.z = None        # height
        
    def show(self):
        print 'Nodes:'
        for node in self.nodes:
            node.show()
        print 'Center:\n' + 'x_center=' + str(self.center.x) + ', ' \
              + 'y_center=' + str(self.center.y)
        print 'Height:\n' + 'z=' + str(self.z)
        
    def plot_footprint(self, ax, color='k'):
        x_list = []
        y_list = []
        for node in self.nodes:
            x_list.append(node.x)
            y_list.append(node.y)
        ax.plot(x_list,y_list, color=color)
        
    def calculate_center(self):
        x_array = []
        y_array = []
        for node in self.nodes:
            x_array.append(node.x)
            y_array.append(node.y)
        self.center.x = np.mean(x_array)
        self.center.y = np.mean(y_array)


    # function to assign a building to a block, using its center coordinates
    def assign_to_block(self, building_id, x_grid, y_grid, blocks):
        
        # find x_index of the block
        block_x_index = -1
        for x in x_grid:
            if self.center.x > x:
                block_x_index += 1
            else:
                break
        
        # find y_index of the block
        block_y_index = -1
        for y in y_grid:
            if self.center.y > y:
                block_y_index += 1
            else:
                break
                
        # compile key (as string)
        block_key = str(block_x_index) + ':' + str(block_y_index)
        
        # add the building id to the selected block
        blocks[block_key].building_ids.append(building_id)
                    

    # distills a list of roofs from nodes of a building, given the observer's location
    def get_roofs(self, obs_x, obs_y, obs_z, blur_epsilon=0.01):
        
        roofs = []
        
        # gather node coordinates
        dx_list = []
        dy_list = []
        for node in self.nodes:
            dx_list.append(node.x)
            dy_list.append(node.y)
        
        # calculate relative location with respect to the observer
        dx_list = np.array(dx_list) - obs_x
        dy_list = np.array(dy_list) - obs_y
        dz = self.z - obs_z
        
        # calclate distances from the observer
        dist_list = np.sqrt(dx_list**2 + dy_list**2)
     
        # calculate viewing angles
        theta_list = np.arctan( np.true_divide(dz, dist_list) )
        phi_list = -np.arctan2(dx_list, -dy_list)
        

        for i in range(0, len(dx_list)-1):
            # order the two endpoints in ascending order
            phi1 = min(phi_list[i], phi_list[i+1])
            phi2 = max(phi_list[i], phi_list[i+1])

            # get visible height of the building
            theta = np.mean(theta_list[i:i+2])
            
            # check if the building crosses the North line
            if dy_list[i] > 0 and dy_list[i+1] > 0 and dx_list[i] * dx_list[i+1] < 0:
                # if so, make two separate roof objects, on the two edges of the silhouette
                roof1 = (-np.pi - blur_epsilon, phi1 + blur_epsilon, theta)
                roof2 = (phi2 - blur_epsilon, np.pi + blur_epsilon, theta)
                roofs.append(roof1)
                roofs.append(roof2)
                
            # if not, make a single roof object
            else:
                roof = (phi1 - blur_epsilon, phi2 + blur_epsilon, theta)
                roofs.append(roof)
        
        return roofs




# class for a block, haviing buildigns assigned to it
class Block:
    def __init__(self):
        self.vertices = []  # list of nodes
        self.building_ids = []  # list of building_ids
        self.max_z = 0  # maximum height of the buildings in it
    
    def __init__(self, node1, node2, node3, node4):
        self.vertices = [node1, node2, node3, node4]  # list of nodes
        self.building_ids = []  # list of building_ids
        self.max_z = 0  # maximum height of the buildings in it
    
    def calculate_max_z(self, buildings):
        current_max_z = 0
        for key in self.building_ids:
            this_z = buildings[key].z
            if this_z > current_max_z:
                current_max_z = this_z
        self.max_z = current_max_z
    
    def plot_on_map(self, ax):
        x_list = []
        y_list = []
        for node in self.vertices:
            x_list.append(node.x)
            y_list.append(node.y)
        ax.plot(x_list, y_list)


def append_buildings_in_block(db_connection, block_xid, block_yid):
    with db_connection: 
        cur = db_connection.cursor()
        # get block_id
        cur.execute("SELECT \
            Id\
            FROM Blocks\
            WHERE X_id = " + str(block_xid) + "\
                AND Y_id = " + str(block_yid) + "\
        ")
        result = cur.fetchall()
        
    # load nodes in the block into dict
    buildings = {}
    if result:
        block_id = result[0][0]
        
        with db_connection: 
            cur = db_connection.cursor()
            cur.execute("SELECT \
                X,\
                Y,\
                Z, \
                Order_in_building,\
                Number_of_nodes_in_building,\
                Building_id \
                FROM Nodes \
                WHERE Block_id = " + str(block_id) + " \
                    AND Z > 0 \
                ORDER BY Building_id, Order_in_building\
            ")
            rows = cur.fetchall()
        
        i = 0
        while i < len(rows):
            
            # find the first "1" in the Order_in_building column
            if rows[i][3] == 1:
                
                building_id = rows[i][5]
                building = Building()
                
                number_of_nodes = rows[i][4]
                
                # loop through the consecutive nodes
                for j in range(0, number_of_nodes):
                    i_cursor = i + j
                    x = rows[i_cursor][0]
                    y = rows[i_cursor][1]
                    building.nodes.append(Node(x,y))
                
                z = rows[i_cursor][2]
                building.z = z
                building.calculate_center()
                
                buildings[building_id] = building
                
                i += number_of_nodes
            else:
                i += 1

    return buildings
