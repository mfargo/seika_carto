import bpy, bmesh, os, sys, csv, json, urllib.request, ssl, math


# 本当はpyprojのようなモジュールを使いたいが、ブレンダーのパイソンを素のままで使えるように、簡単なプロジェクション。
def mercator(lat, lon):
    r_major = 6378137.000
    x = r_major * lon / 180 * math.pi
    scale = x/lon
    y = 180.0/math.pi * math.log(math.tan(math.pi/4.0 + lat * (math.pi/180.0)/2.0)) * scale
    return (x, y)


min = (34.8116, 135.6269)
max = (35.1064, 135.9661)
center = mercator((min[0]+max[0])/2, (min[1]+max[1])/2)


class Reporter:

    def __init__(self, filename):
        filename = os.path.join(os.path.dirname(bpy.data.filepath), filename)
        with open(filename,'r') as data_file:
            data = json.load(data_file)
        for snap in data["snapshots"]:
            location = snap["location"]
            lat = float(location["latitude"])
            lon = float(location["longitude"])



class KyotoMap:

    def __init__(self):


        self.data = self.loadTopoFromCache()
        size = 80
        segments_lat = len(self.data["elevations"])
        segments_lon = len(self.data["elevations"][0]["points"])
        print("SEGs:", segments_lat, segments_lon)
        map_scale = 0.001
        height_multiplier = 2
        scene_root = self.clear_scene()
        self.plane = self.create_plane(segments_lat, segments_lon, size)
        self.plane.parent = scene_root

        # for i in range(segments_lat + 2):
        #     print(i, self.plane.data.vertices[i].co)

        for y, row in enumerate(self.data["elevations"]):
            for x, point in enumerate(row["points"]):
                vertex = self.plane.data.vertices[(segments_lat - 1 - y) * segments_lon + x]
                projected = mercator(point["lat"], point["lon"])
                vertex.co.x = (projected[0] - center[0]) * map_scale
                vertex.co.y = (projected[1] - center[1]) * map_scale
                vertex.co.z = point["elevation"] * map_scale * height_multiplier

        self.plane.data.polygons.foreach_set('use_smooth',  [True] * len(bpy.context.object.data.polygons))

        # テクスチャーを貼る
        mat = bpy.data.materials.new(name="Material")
        self.plane.data.materials.append(mat)
        imgpath = os.path.join(os.path.dirname(bpy.data.filepath), 'Kyoto.png')
        img = bpy.data.images.load(imgpath)

        mat.use_nodes=True

        material_output = mat.node_tree.nodes.get('Material Output')
        principled_BSDF = mat.node_tree.nodes.get('Principled BSDF')

        tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex_node.image = img

        tex_mapping = mat.node_tree.nodes.new("ShaderNodeMapping")
        tex_coordinate = mat.node_tree.nodes.new("ShaderNodeTexCoord")
        mat.node_tree.links.new(tex_coordinate.outputs["UV"], tex_mapping.inputs["Vector"])
        mat.node_tree.links.new(tex_mapping.outputs["Vector"], tex_node.inputs["Vector"])
        tex_mapping.inputs["Rotation"].default_value = (0, 0, math.pi/2)

        mat.node_tree.links.new(tex_node.outputs[0], principled_BSDF.inputs[0])
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.flip_normals()
        bpy.ops.object.mode_set()

        # 簡単な太陽光
        light_data = bpy.data.lights.new(name="sun", type='SUN')
        light_data.energy = 2
        light_object = bpy.data.objects.new(name="main-sun", object_data=light_data)
        bpy.context.collection.objects.link(light_object)
        light_object.location = (50, 50, 20)

    def loadTopoFromCache(self):
        filename = os.path.join(os.path.dirname(bpy.data.filepath), "elevations_1600.json")
        with open(filename) as data_file:
            data = json.load(data_file)
        print("LOADED", len(data["elevations"]))
        return data



    # 高度データをCSVから読みこむ
    def loadTopoFromCSV(self):
        filename = os.path.join(os.path.dirname(bpy.data.filepath), "ritti.csv")
        c = 0
        with open(filename,'r') as data_file:
            for line in data_file:
                data = line.split(',')
                vertex = self.plane.data.vertices[c]
                vertex.co.x = float(data[0])
                vertex.co.y = float(data[1])
                vertex.co.z = float(data[2].replace('\n', ''))
                c += 1

    def clear_scene(self, root_name = "scene_root"):
        for bpy_data_iter in (bpy.data.objects, bpy.data.meshes, bpy.data.cameras):
            for id_data in bpy_data_iter:
                bpy_data_iter.remove(id_data)
        scene_root = bpy.data.objects.new(name=root_name, object_data=None)
        bpy.context.collection.objects.link(scene_root)

    def create_plane(self, segments_lat, segments_lon, size):
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=segments_lon-1, y_subdivisions=segments_lat-1, size=size)
        plane = bpy.context.object
        return plane


# Reporterのデータを読み込んで、地図に貼る。
reporter = Reporter('reporter-export.json')


map = KyotoMap()





# サービスとしてviewport shadeをつけておく
area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
space = next(space for space in area.spaces if space.type == 'VIEW_3D')
space.shading.type = 'RENDERED'  # set the viewport shading


