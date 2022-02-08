from typing import List
import overpy
import json
from copy import deepcopy
#Send request to get map data from OSM
def query_osmdata(radius:float, lat:float, lon:float):
  api = overpy.Overpass()
  result = api.query (f'way(around:{radius},{lat},{lon})["highway"=""];(._;>;);out body;')
  return (result)


#Retrieve inteterested street information from the requested OSM data
def transform_osmdata(raw_osmdata: List[dict]):
  street_data_list=[]
  for way in raw_osmdata.ways:
    nodes_list=[] 
    for node in way.nodes:
      node_record={"id":node.id,"lat":str(node.lat),"lon":str(node.lon)}
      if node_record not in nodes_list:
        nodes_list.append(node_record)
        way_record={"street_name":way.tags.get("name","n/a"),"street_type":way.tags.get("highway","n/a"),"surface":way.tags.get("surface","n/a"),"oneway":way.tags.get("oneway","n/a"),"sidewalk":way.tags.get("sidewalk","n/a"),"nodes":nodes_list} 
        street_data_list.append(way_record)
        #Remove duplicate objects if any
        cleaned_street_data_list=[]
        for obj in street_data_list:
          if obj not in cleaned_street_data_list:
            cleaned_street_data_list.append(obj)              
  return (cleaned_street_data_list)


#Group all street information on street name (to achieve street by street record)
def merge_street_by_name(transformed_osmdata: List[dict]):
  response=transformed_osmdata
  output={}
  for obj in response:
    str_name=obj["street_name"]
    if str_name not in output:
      assert obj["nodes"] is not None
      record={"street_name":obj["street_name"],"street_type":obj["street_type"],"surface":obj["surface"], "sidewalk":obj["sidewalk"],"oneway":obj["oneway"],"nodes": obj["nodes"]} 
      output[str_name]= record
    else:
      existing_record = output[str_name]
      existing_nodes = existing_record["nodes"]
      assert existing_nodes is not None
      new_node = obj["nodes"]
      assert new_node is not None
      merged_node = existing_nodes + new_node
      existing_record["nodes"] = merged_node
      output[str_name] = existing_record
      merged_street = list(output.values())
  return(merged_street)


#Compare two streets for possible intersection
def extract_intersection(list1, list2):
  computed_intersection = [x for x in list1 if x in list2]  
  return(computed_intersection)


#The function uses loop to extract sets of points (nodes) for any two streets and send out for possible intersection and so on
def extract_nodes_list(result):
  intersection_sets = []
  for i in range(len(result)):
    for j in range(i + 1, len(result)):
      list1 = (result[i]["nodes"])
      list2 = (result[j]["nodes"])
      intersection = extract_intersection(list1,list2)
      if len(intersection):
        #str_record={"street_name":result[i]["street_name"],"street_type":result[i]["street_type"],"surface":result[i]["surface"], "sidewalk":result[i]["sidewalk"],"oneway":result[i]["oneway"],"intersection_sets":intersection} 
        #intersection_sets.append(str_record)
        #str_record={"street_name":result[j]["street_name"],"street_type":result[j]["street_type"],"surface":result[j]["surface"], "sidewalk":result[j]["sidewalk"],"oneway":result[j]["oneway"],"intersection_sets":intersection} 
        intersection_sets.append(intersection)
  return(intersection_sets)

def create_new_intersection_sets(result):
  #Create a new single list of intersection objects [{},{},{}...]
  modified_intersection_sets=[]
  for intersect_list in result:
    for obj in intersect_list:
      modified_intersection_sets.append(obj)
      
  return(modified_intersection_sets)

def my_final_data_structure(merged_street, modified_intersection_set):
  str_records = []
  for obj in range (len(merged_street)):
    nodes= merged_street[obj]["nodes"]
    for i in range (len(nodes)):
      if nodes[i] not in modified_intersection_set:
        alist=[]
        node = nodes[i]
        node["inter_link"] = "nil"
        alist.append(node)
        str_info={"street_name":merged_street[obj]["street_name"],"street_type":merged_street[obj]["street_type"],"surface":merged_street[obj]["surface"], "sidewalk":merged_street[obj]["sidewalk"],"oneway":merged_street[obj]["oneway"],"nodes":alist} 
        str_records.append(str_info)
      else:
        alist=[]
        node = nodes[i]
        node["inter_link"] = "intersected"
        alist.append(node)
        str_info = {"street_name":merged_street[obj]["street_name"],"street_type":merged_street[obj]["street_type"],"surface":merged_street[obj]["surface"], "sidewalk":merged_street[obj]["sidewalk"],"oneway":merged_street[obj]["oneway"],"nodes":alist} 
        str_records.append(str_info)
  return(str_records)

def merge_street_points_by_name(my_response):
  output={}
  for obj in my_response:
    str_name=obj["street_name"]
    if str_name not in output:
      assert obj["nodes"] is not None
      record={"street_name":obj["street_name"],"street_type":obj["street_type"],"surface":obj["surface"], "sidewalk":obj["sidewalk"],"oneway":obj["oneway"],"nodes": obj["nodes"]} 
      output[str_name]= record
    else:
      existing_record = output[str_name]
      existing_node = existing_record["nodes"]
      assert existing_node is not None
      new_node = obj["nodes"]
      assert new_node is not None
      merged_node = existing_node + new_node
      existing_record["nodes"] = merged_node
      output[str_name] = existing_record
      merged_node = list(output.values())

      #remove duplicate objects if any
      #cleaned_node_data_list=[]
      #for obj in merged_node:
      #  if obj not in cleaned_node_data_list:
         # cleaned_node_data_list.append(obj)
         # merged_data_structure=cleaned_node_data_list
  return(merged_node)