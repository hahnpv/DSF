import json
import os
import tempfile
import xml.etree.ElementTree as ET
from xml.dom import minidom

def _resolve_connection_pointers(port_name, params):
    """
    Helps infer the corresponding XML attribute name from a GUI port connection mapping.
    
    In GUI JSON `connections`, it might say from_port: "state", to_port: "prop".
    In XML this needs to be represented as `<child_block prop_id="instance_id" />`.
    """
    # These pointer ports are read by the C++ models under their BARE names
    # (e.g. PointMassEOM reads attrAsString("guidance"), Seeker reads "target").
    # Emitting "guidance_id" here would leave the connection silently unwired.
    known_pointers = {"nav", "control", "guidance", "prop", "parent", "target"}
    if port_name in known_pointers:
        return port_name

    # Generic fallback for other ports.
    if not port_name.endswith("_id"):
         return f"{port_name}_id"
    return port_name


def _dict_to_xml(json_data):
    """
    Translates a `.dsf` project dictionary natively into a `<sim>` ElementTree structure.
    """
    metadata = json_data.get("metadata", {})
    tmax = metadata.get("tmax", 100.0)
    dt = metadata.get("dt", 0.1)
    library = metadata.get("library") or metadata.get("lib_path", "")
    
    sim_root = ET.Element("sim")
    sim_root.set("dt", str(dt))
    sim_root.set("tmax", str(tmax))
    if library:
        sim_root.set("library", library)
    file_rate = metadata.get("file")
    if file_rate is not None:
        sim_root.set("file", str(file_rate))

    blocks = json_data.get("blocks", [])
    connections = json_data.get("connections", [])
    
    # Index blocks by ID for hierarchy and connection resolution
    block_map = {b["id"]: b for b in blocks}
    
    # Track Element instances for parent-child assignments
    et_map = {}
    
    for b_data in blocks:
        tag_name = b_data.get("tag", b_data["type"].lower())
        node = ET.Element(tag_name)
        node.set("id", b_data["id"])
        node.set("class", b_data["type"])
        
        # Add basic parameters
        params = b_data.get("parameters", {})
        for key, val in params.items():
            if isinstance(val, bool):
                # C++ attrAsBool accepts only "true"/"1"; Python's str(True)
                # is "True", which C++ reads as false.
                s_val = "true" if val else "false"
            elif isinstance(val, list):
                s_val = ",".join(map(str, val))
            else:
                s_val = str(val)
            node.set(key, s_val)
            
        # Add raw parameters (nested XML text elements like <position>1, 0, 0</position>)
        raw_params = b_data.get("raw_params", {})
        for tag, text in raw_params.items():
            child_node = ET.SubElement(node, tag)
            child_node.text = text
            
        et_map[b_data["id"]] = node

    # Resolve Connections and add them as *_id reference attributes
    for c_data in connections:
        # We need to map `to_port` to `<node target_id="from_block" />`
        # Connections always describe an output linking to an input.
        # So the `to_block` receives the pointer to the `from_block`.
        to_node = et_map.get(c_data["to_block"])
        if to_node is not None:
             to_port = c_data["to_port"]
             target_id = c_data["from_block"]
             
             # Fetch the original params to determine if port_name is explicit
             # In a generic situation we can just use _resolve_connection_pointers
             # to format it perfectly for the C++ factory.
             attr_name = _resolve_connection_pointers(to_port, {})
             to_node.set(attr_name, target_id)

    # Establish Hierarchy
    roots = []
    for b_data in blocks:
        node = et_map[b_data["id"]]
        parent_id = b_data.get("parent_id")
        
        if parent_id and parent_id in et_map:
            # Append as a child in the XML ElementTree
            parent_node = et_map[parent_id]
            parent_node.append(node)
        else:
            roots.append(node)
            
    for root_node in roots:
        sim_root.append(root_node)
        
    # Return formatted XML string
    rough_string = ET.tostring(sim_root, encoding='utf-8')
    if not rough_string:
         return ""
         
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def convert_dsf_to_xml(json_filepath):
    """
    Reads a DSF JSON project file and returns the path to a newly generated temporary XML file.
    The caller is responsible for deleting the temporary file.
    """
    with open(json_filepath, 'r') as f:
         data = json.load(f)

    # Validate the project before converting/running. Fails loudly by default on
    # structural errors (bad dt/tmax, duplicate ids, dangling connections) and
    # registry-known attribute mistakes, instead of letting the C++ layer
    # silently substitute zeros. DSF_VALIDATE=warn downgrades to warnings.
    from dsf.utils.validate_config import enforce_config
    enforce_config(data)

    xml_content = _dict_to_xml(data)
    
    # Create temp file
    fd, temp_path = tempfile.mkstemp(suffix=".xml", prefix="dsf_run_")
    with os.fdopen(fd, 'w') as f:
         f.write(xml_content)
         
    return temp_path
