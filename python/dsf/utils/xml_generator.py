from dsf.gui.ui.canvas import BlockItem
from typing import List, Dict
import xml.etree.ElementTree as ET
from xml.dom import minidom

class XMLGenerator:
    def __init__(self, scene):
        self.scene = scene

    def generate(self, dt=0.1, tmax=100.0, library="") -> str:
        sim_root = ET.Element("sim")
        sim_root.set("dt", str(dt))
        sim_root.set("tmax", str(tmax))
        if library:
            sim_root.set("library", library)
        
        # Identify top-level blocks (those without a parent)
        items = [i for i in self.scene.items() if isinstance(i, BlockItem)]
        root_blocks = [b for b in items if b.parent_block is None]

        # Recursively build XML starting from root blocks
        for block in root_blocks:
            node = self._build_recursive_node(block)
            sim_root.append(node)

        # Pretty print
        rough_string = ET.tostring(sim_root, encoding='unicode')
        if not rough_string:
            return ""
        reparsed = minidom.parseString(rough_string.encode('utf-8'))
        return reparsed.toprettyxml(indent="  ")

    def _build_recursive_node(self, block: BlockItem) -> ET.Element:
        # Create node for current block
        node = self._create_node(block)
        
        # Recursively add children
        for child in block.child_blocks:
            child_node = self._build_recursive_node(child)
            node.append(child_node)
            
        return node

    def _resolve_connections(self, block: BlockItem):
        # Scan input ports
        for port in block.inputs:
            if port.connections:
                # Assuming 1 conn for input
                conn = port.connections[0]
                other_port = conn.start_port if conn.end_port == port else conn.end_port
                if other_port:
                    connected_block = other_port.parentItem()
                    if isinstance(connected_block, BlockItem):
                        # Heuristic: property name is port name + "_id" or just port name if mapped?
                        # For MVP checking if property exists
                        target_prop = f"{port.name}_id"
                        # Or match exactly port name to prop name?
                        # Let's say model_registry matches names.
                        
                        # In registry: RocketProp has 'fuel_tank_id', port could be 'fuel_tank'
                        # I'll update the block's internal property value map (need to store it on block)
                        
                        # BlockItem needs to store current parameter values!
                        # I didn't verify BlockItem storage. It has block_def. Not instances properties.
                        # I should add `self.properties = {}` to BlockItem init.
                        pass # Done in BlockItem update below

    def _create_node(self, block: BlockItem) -> ET.Element:
        # Use stored xml_tag if available, else fallback to class name lowercase
        tag_name = getattr(block, "xml_tag", block.block_def.type_id.lower())
        node = ET.Element(tag_name)
        
        node.set("id", block.instance_id)
        node.set("class", block.block_def.type_id)
        
        # 1. Export all parameters from the parameters dict
        params = getattr(block, "parameters", {})
        for key, val in params.items():
            if isinstance(val, list):
                s_val = ",".join(map(str, val))
            else:
                s_val = str(val)
            node.set(key, s_val)
            
        # 1.1 Export raw_params as child nodes
        raw_params = getattr(block, "raw_params", {})
        for tag, text in raw_params.items():
            child_node = ET.SubElement(node, tag)
            child_node.text = text
            
        # 2. Export all connections as *_id attributes
        # This overrides anything in parameters if there's a live connection
        for port in block.inputs:
            if port.connections:
                conn = port.connections[0]
                other = conn.start_port.parentItem() if conn.end_port == port else conn.end_port.parentItem()
                if isinstance(other, BlockItem):
                    # Heuristic: use port name as-is if it exists in parameters or is a known pointer
                    # Otherwise, use the portname_id convention
                    attr_name = port.name
                    known_pointers = ("nav", "control", "guidance", "prop", "parent", "target")
                    if port.name not in params and port.name not in block.block_def.properties and port.name not in known_pointers:
                         # Check if the _id version exists in parameters
                         if f"{port.name}_id" in params or f"{port.name}_id" in [p.name for p in block.block_def.properties]:
                             attr_name = f"{port.name}_id"
                         elif port.name.endswith("_id"):
                             attr_name = port.name # Already has it
                         else:
                             # Default fallback for dynamic ports that aren't known mission pointers
                             attr_name = f"{port.name}_id"

                    node.set(attr_name, other.instance_id)

        return node
