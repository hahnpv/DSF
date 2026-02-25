import json
from dsf.gui.ui.canvas import BlockItem, ConnectionItem
from PyQt6.QtCore import QPointF

class GraphSerializer:
    def __init__(self, registry):
        self.registry = registry

    def save(self, scene, filepath, metadata=None):
        data = {
            "blocks": [],
            "connections": [],
            "metadata": metadata or {}
        }
        
        # Save Blocks
        for item in scene.items():
            if isinstance(item, BlockItem):
                block_data = {
                    "id": item.instance_id,
                    "type": item.block_def.type_id,
                    "tag": getattr(item, "xml_tag", ""),
                    "parent_id": item.parent_block.instance_id if item.parent_block else None,
                    "x": item.scenePos().x(),
                    "y": item.scenePos().y(),
                    "parameters": item.parameters,
                    "raw_params": getattr(item, "raw_params", {}),
                    "ports": {
                        "inputs": [{"name": p.name, "type": p.port_type} for p in item.inputs],
                        "outputs": [{"name": p.name, "type": p.port_type} for p in item.outputs]
                    }
                }
                data["blocks"].append(block_data)
        
        # Save Connections
        for item in scene.items():
            if isinstance(item, BlockItem):
                for port in item.inputs:
                    if port.connections:
                        conn = port.connections[0]
                        other = conn.start_port.parentItem() if conn.end_port == port else conn.end_port.parentItem()
                        if not other or not isinstance(other, BlockItem):
                            continue
                            
                        other_port = conn.start_port if conn.end_port == port else conn.end_port
                        
                        conn_data = {
                            "from_block": other.instance_id,
                            "from_port": other_port.name,
                            "to_block": item.instance_id,
                            "to_port": port.name
                        }
                        data["connections"].append(conn_data)
                        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)

    def load_from_file(self, filepath):
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading JSON: {e}")
            return None

    def load(self, scene, filepath):
        """Wrapper for MainWindow/main.py compatibility."""
        data = self.load_from_file(filepath)
        if data:
            return self.reconstruct(scene, data)
        return None

    def reconstruct(self, scene, data):
        scene.clear()
        
        # Load Blocks
        block_map = {}
        for b_data in data.get("blocks", []):
            b_def = self.registry.get_block(b_data["type"])
            if not b_def:
                # Create dummy for missing lib
                from dsf.gui.core.model_registry import BlockDefinition
                b_def = BlockDefinition(b_data["type"], "Imported", "", [], [])
            
            pos = QPointF(b_data["x"], b_data["y"])
            block = BlockItem(b_def, b_data["id"], pos)
            block.xml_tag = b_data.get("tag", block.xml_tag)
            block.parameters = b_data.get("parameters", block.parameters)
            block.raw_params = b_data.get("raw_params", {})
            
            # Restore Ports (Dynamic + Definitions)
            if "ports" in b_data:
                for p_data in b_data["ports"].get("inputs", []):
                    block.add_input_port(p_data["name"], p_data["type"])
                for p_data in b_data["ports"].get("outputs", []):
                    block.add_output_port(p_data["name"], p_data["type"])
            
            scene.addItem(block)
            block_map[b_data["id"]] = block
        
        # Load Connections
        for c_data in data.get("connections", []):
            from_block = block_map.get(c_data["from_block"])
            to_block = block_map.get(c_data["to_block"])
            
            if from_block and to_block:
                from_port = next((p for p in from_block.outputs if p.name == c_data["from_port"]), None)
                to_port = next((p for p in to_block.inputs if p.name == c_data["to_port"]), None)
                
                if from_port and to_port:
                    from dsf.gui.ui.canvas import ConnectionItem
                    conn = ConnectionItem(from_port, to_port)
                    from_port.connections.append(conn)
                    to_port.connections.append(conn)
                    scene.addItem(conn)
                    conn.update_geometry()
        
        # Build Hierarchy
        print(f"Reconstructing hierarchy for {len(block_map)} blocks...")
        for b_data in data.get("blocks", []):
            parent_id = b_data.get("parent_id")
            if parent_id and parent_id in block_map:
                block = block_map[b_data["id"]]
                parent = block_map[parent_id]
                block.parent_block = parent
                if block not in parent.child_blocks:
                    parent.child_blocks.append(block)
                print(f"  Parent: {parent_id} -> Child: {b_data['id']}")
        
        return data.get("metadata", {})
