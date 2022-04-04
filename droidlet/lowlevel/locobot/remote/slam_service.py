import os
import sys
import time
import numpy as np
import Pyro4
import select
import cv2
from PIL import Image
from slam_pkg.utils.map_builder import MapBuilder as mb
from slam_pkg.utils import depth_util as du
from skimage.morphology import disk, binary_dilation
from constants import coco_categories, color_palette

Pyro4.config.SERIALIZER = "pickle"
Pyro4.config.SERIALIZERS_ACCEPTED.add("pickle")
Pyro4.config.PICKLE_PROTOCOL_VERSION = 4


@Pyro4.expose
class SLAM(object):
    def __init__(
        self,
        robot,
        map_size=4000,
        resolution=5,
        robot_rad=30,
        agent_min_z=5,
        agent_max_z=70,
    ):
        self.robot = robot
        self.robot_rad = robot_rad
        self.map_resolution = resolution
        self.map_builder = mb(
            map_size_cm=map_size,
            resolution=resolution,
            agent_min_z=agent_min_z,
            agent_max_z=agent_max_z,
            num_semantic_categories=len(coco_categories)
        )
        self.map_size = map_size
        # if the map is a previous map loaded from disk, and
        # if the robot looks around and registers itself at a
        # non-origin location in the map just as it is coming up,
        # then the robot's reported origin (from get_base_state) is
        # not the map's origin. In such cases, `self.init_state`
        # is useful, as it is used to handle all co-ordinate transforms
        # correctly.
        # Currently, self.init_state is kinda useless and not utilized
        # in any meaningful way
        self.init_state = (0.0, 0.0, 0.0)
        self.prev_bot_state = (0.0, 0.0, 0.0)

        self.update_map()
        assert self.traversable is not None

    def get_traversable_map(self):
        return self.traversable

    def real2map(self, real):
        return self.map_builder.real2map(real)

    def map2real(self, map_loc):
        return self.map_builder.map2real(map_loc)

    def robot2map(self, robot_loc):
        # TODO: re-enable this code when init_state can be non-zero
        # robot_location = du.get_relative_state(
        #     robot_loc,
        #     self.init_state)
        return self.real2map(robot_loc)

    def map2robot(self, map_loc):
        return self.map2real(map_loc)
        # TODO: re-enable and test this code when init_state can be non-zero
        # real_loc = self.map2real(map_loc)
        # loc = du.get_relative_state(real_loc, (0.0, 0.0, -self.init_state[2]))

        # # 2) add the offset
        # loc = list(loc)
        # loc[0] += self.init_state[0]
        # loc[1] += self.init_state[1]
        # return tuple(loc)

    def add_obstacle(self, location, in_map=False):
        """
        add an obstacle at the given location.
        if in_map=False, then location is given in real co-ordinates
        if in_map=True, then location is given in map co-ordinates
        """
        if not in_map:
            location = self.real2map(location)
        self.map_builder.add_obstacle(location)

    def update_map(self):
        pcd = self.robot.get_current_pcd()[0]
        semantics = self.robot.get_rgb_depth_segm()[2]
        semantic_channels = self.preprocess_habitat_semantics(semantics) 
        semantic_channels = semantic_channels.reshape(-1, semantic_channels.shape[2])
        self.map_builder.update_map(pcd)
        self.map_builder.update_semantic_map(pcd, semantic_channels)
        self.visualize_sem_map()

        # explore the map by robot shape
        obstacle = self.map_builder.map[:, :, 1] >= 1.0
        selem = disk(self.robot_rad / self.map_builder.resolution)
        traversable = binary_dilation(obstacle, selem) != True
        self.traversable = traversable

    def preprocess_habitat_semantics(self, gt_semantics):
        num_semantic_cats = len(coco_categories)
        category_instance_lists = self.robot.get_category_instance_lists()
        semantic = gt_semantics.astype(np.float32)
        semantic_channels = np.zeros((semantic.shape[0],
                                    semantic.shape[1],
                                    num_semantic_cats+1))

        def add_cat_channel(cat_id):
            mask = np.zeros((semantic.shape), dtype=bool)
            if cat_id in category_instance_lists:
                instance_list = category_instance_lists[cat_id]
                for inst_id in instance_list:
                    mask = np.logical_or(mask, semantic == inst_id)
                semantic[mask] = -(cat_id + 1)
            return mask*1

        for i in range(num_semantic_cats):
            semantic_channels[:,:,i+1] = add_cat_channel(i)

        return semantic_channels

    def visualize_sem_map(self):
        sem_map = self.map_builder.semantic_map
        sem_map[-1,:,:] = 1e-5
        sem_map = sem_map.argmax(0)
        sem_map_vis = Image.new("P", (sem_map.shape[1],
                                      sem_map.shape[0]))
        color_pal = [int(x * 255.) for x in color_palette]                        
        sem_map_vis.putpalette(color_pal)
        sem_map_vis.putdata(sem_map.flatten().astype(np.uint8))
        sem_map_vis = sem_map_vis.convert("RGB")
        sem_map_vis = np.flipud(sem_map_vis)

        sem_map_vis = sem_map_vis[:, :, [2, 1, 0]]
        cv2.imwrite("sem_map.png", sem_map_vis)
                

    def get_map_resolution(self):
        return self.map_resolution

    def get_map(self):
        """returns the location of obstacles created by slam only for the obstacles,"""
        # get the index correspnding to obstacles
        indices = np.where(self.map_builder.map[:, :, 1] >= 1.0)
        # convert them into robot frame
        real_world_locations = [
            self.map2real([indice[0], indice[1]]).tolist()
            for indice in zip(indices[0], indices[1])
        ]
        return real_world_locations

    def reset_map(self):
        self.map_builder.reset_map(self.map_size)


robot_ip = os.getenv("LOCOBOT_IP")
ip = os.getenv("LOCAL_IP")
robot_name = "remotelocobot"
if len(sys.argv) > 1:
    robot_name = sys.argv[1]
with Pyro4.Daemon(ip) as daemon:
    robot = Pyro4.Proxy("PYRONAME:" + robot_name + "@" + robot_ip)
    obj = SLAM(robot)
    obj_uri = daemon.register(obj)
    with Pyro4.locateNS(robot_ip) as ns:
        ns.register("slam", obj_uri)

    print("SLAM Server is started...")

    def refresh():
        obj.update_map()
        # print("In refresh: ", time.asctime())
        return True

    daemon.requestLoop(refresh)

    # visit this later
    # try:
    #     while True:
    #         print(time.asctime(), "Waiting for requests...")

    #         sockets = daemon.sockets
    #         ready_socks = select.select(sockets, [], [], 0)
    #         events = []
    #         for s in ready_socks:
    #             events.append(s)
    #         daemon.events(events)
    # except KeyboardInterrupt:
    #     pass
