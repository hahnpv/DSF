from ui.canvas import BlockItem
from typing import List, Dict
import xml.etree.ElementTree as ET
from xml.dom import minidom

class XMLGenerator:
    def __init__(self, scene):
        self.scene = scene

    def generate(self) -> str:
        # Preamble
        # In DSF, the root is usually <sim>.
        # And it contains <vehicle>.
        
        sim_root = ET.Element("sim")
        # Global sim attributes (hardcoded for MVP or extracted from Scene properties)
        sim_root.set("dt", "0.1")
        sim_root.set("tmax", "100.0")
        
        # Find Vehicle blocks and others
        items = [i for i in self.scene.items() if isinstance(i, BlockItem)]
        
        # Hierarchy strategy for MVP:
        # If "Vehicle" block exists, it is the parent of all other blocks.
        # Otherwise, everything is flat under <sim> (DSF might accept this? block.configure reads children?)
        # Actually in dynamic.py we create sim_root (a Block) and add children.
        # The XML structure should mirror the desired Block hierarchy.
        
        vehicle_block = next((b for b in items if b.block_def.type_id == "Vehicle"), None)
        other_blocks = [b for b in items if b != vehicle_block]
        
        # Process connections to update properties
        # Map connections to properties: e.g. Port "fuel" connected to "Tank1" -> property "fuel_id" = "Tank1"
        for block in items:
            self._resolve_connections(block)

        if vehicle_block:
            vehicle_node = self._create_node(vehicle_block)
            sim_root.append(vehicle_node)
            parent_node = vehicle_node
        else:
            parent_node = sim_root # Fallback
            
        for block in other_blocks:
            node = self._create_node(block)
            parent_node.append(node)

        # Pretty print
        rough_string = ET.tostring(sim_root, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")

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
        # Create element name = type_id (or class name?)
        # DSF XML: <type_id id="instance_id" attr="val">
        # wait, <tank id="S2_Fuel" class="Tank">
        # Tag name is usually arbitrary? Or matched to factory?
        # dsf::xml checks `model = n.attrAsString("class")`.
        # tag name doesn't matter for factory, but might matter for parent logic sometimes.
        # But commonly used tag names are lowercase class names.
        
        tag_name = block.block_def.type_id.lower()
        node = ET.Element(tag_name)
        node.set("id", block.instance_id)
        node.set("class", block.block_def.type_id)
        
        # Set properties
        # Merge default defaults with instance values
        # For now using defaults since BlockItem doesn't store edtis yet (Inspector was readonly)
        # But connections should modify it.
        
        # We need to access the block's current properties.
        # Let's assume BlockItem has a `parameters` dict. I need to add it.
        params = getattr(block, "parameters", {})
        
        # Also check connections mappings
        for port in block.inputs:
            if port.connections:
                conn = port.connections[0]
                other = conn.start_port.parentItem() if conn.end_port == port else conn.end_port.parentItem()
                # Heuristic: port name "fuel_tank" -> param "fuel_tank_id"
                # Check if param exists
                tgt = f"{port.name}_id"
                # Update params
                params[tgt] = other.instance_id

        # Write params from block definition
        for prop in block.block_def.properties:
            val = params.get(prop.name, prop.default)
            if isinstance(val, list):
                s_val = ",".join(map(str, val))
            else:
                s_val = str(val)
            node.set(prop.name, s_val)
            
        # Write connection params (which might not be in definition)
        for port in block.inputs:
            if port.connections:
                conn = port.connections[0] # Single input support for now
                other = conn.start_port.parentItem() if conn.end_port == port else conn.end_port.parentItem()
                prop_name = f"{port.name}_id"
                if prop_name not in node.attrib: # Avoid duplicate if it was reachable via block_def
                    node.set(prop_name, other.instance_id)

        return node
