import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional

class XMLParser:
    def __init__(self, registry):
        self.registry = registry

    def parse_file(self, file_path: str) -> List[Dict[str, Any]]:
        tree = ET.parse(file_path)
        root = tree.getroot()
        return self.parse_root(root)

    def parse_string(self, xml_string: str) -> List[Dict[str, Any]]:
        root = ET.fromstring(xml_string)
        return self.parse_root(root)

    def parse_root(self, root: ET.Element) -> Dict[str, Any]:
        """Returns a dict with 'blocks' list and 'sim_metadata' dict."""
        blocks = []
        metadata = {}
        
        # Capture global <sim> attributes
        if root.tag == "sim":
            for k, v in root.attrib.items():
                try:
                    metadata[k] = float(v)
                except ValueError:
                    metadata[k] = v

        # Check if root itself is a block (e.g. <vehicle>)
        root_block = self._parse_element(root)
        if root_block:
            blocks.append(root_block)
        else:
            # If not, loop through children (e.g. <sim>)
            for child in root:
                block_data = self._parse_element(child)
                if block_data:
                    blocks.append(block_data)
        
        return {"blocks": blocks, "sim_metadata": metadata}

    def _parse_element(self, element: ET.Element) -> Optional[Dict[str, Any]]:
        # Check if it's a block (should have 'class' or 'id')
        block_class = element.get("class")
        block_id = element.get("id")
        
        # In DSF, if no class, maybe tag name is the class? 
        # But usually 'class' is required for factory.
        # If it's something like <gravity class="FlatGravity">
        if not block_class and not block_id:
            # Might be a container or metadata? e.g. <sim dt="0.1">
            return None

        if not block_class:
            # Heuristic: tag name could be class if class is missing
            block_class = element.tag.capitalize() # Simple mapping
            
        data = {
            "type": block_class,
            "id": block_id or f"{block_class}_{id(element)}",
            "tag": element.tag,
            "params": {},
            "connections": [] # Extracted from ID attributes
        }
        
        # Parse attributes as params
        for key, value in element.attrib.items():
            if key in ("class", "id"):
                continue
            
            # Check if it looks like a connection (ends with _id)
            if key.endswith("_id"):
                data["connections"].append({
                    "port": key[:-3], # e.g. "fuel_tank"
                    "target": value
                })
            
            # Keep in params as well as a fail-safe
            # Try to parse numeric values
            try:
                if "," in value:
                    # Vec3
                    data["params"][key] = [float(p.strip()) for p in value.split(",")]
                else:
                    data["params"][key] = float(value)
            except ValueError:
                # String or bool
                if value.lower() in ("true", "false", "yes", "no"):
                    data["params"][key] = value.lower() in ("true", "yes")
                else:
                    data["params"][key] = value
        
        # Children are sub-blocks or raw params
        for child in element:
            child_data = self._parse_element(child)
            if child_data:
                if "sub_blocks" not in data:
                    data["sub_blocks"] = []
                data["sub_blocks"].append(child_data)
            elif child.text and child.text.strip():
                # Text-only child (like <position>6378237, 0, 0</position>)
                if "raw_params" not in data:
                    data["raw_params"] = {}
                data["raw_params"][child.tag] = child.text.strip()
                
        return data
