import json
from ui.canvas import BlockItem, ConnectionItem
from PyQt6.QtCore import QPointF

class GraphSerializer:
    def __init__(self, registry):
        self.registry = registry

    def save(self, scene, filepath):
        data = {
            "blocks": [],
            "connections": []
        }
        
        # Save Blocks
        for item in scene.items():
            if isinstance(item, BlockItem):
                block_data = {
                    "id": item.instance_id,
                    "type": item.block_def.type_id,
                    "x": item.scenePos().x(),
                    "y": item.scenePos().y(),
                    "parameters": item.parameters
                }
                data["blocks"].append(block_data)
        
        # Save Connections
        # Connections are stored on PortItems. To avoid duplicates, iterate blocks -> inputs -> connection
        for item in scene.items():
            if isinstance(item, BlockItem):
                for port in item.inputs:
                    if port.connections:
                        conn = port.connections[0]
                        other = conn.start_port.parentItem() if conn.end_port == port else conn.end_port.parentItem()
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

    def load(self, scene, filepath):
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        scene.clear()
        
        # Load Blocks
        block_map = {}
        for b_data in data["blocks"]:
            b_def = self.registry.get_block(b_data["type"])
            if b_def:
                pos = QPointF(b_data["x"], b_data["y"])
                block = BlockItem(b_def, b_data["id"], pos)
                block.parameters = b_data.get("parameters", block.parameters)
                scene.addItem(block)
                block_map[b_data["id"]] = block
        
        # Load Connections
        for c_data in data["connections"]:
            from_block = block_map.get(c_data["from_block"])
            to_block = block_map.get(c_data["to_block"])
            
            if from_block and to_block:
                # Find ports
                from_port = next((p for p in from_block.outputs if p.name == c_data["from_port"]), None)
                to_port = next((p for p in to_block.inputs if p.name == c_data["to_port"]), None)
                
                if from_port and to_port:
                    conn = ConnectionItem(from_port, to_port)
                    from_port.connections.append(conn)
                    to_port.connections.append(conn)
                    scene.addItem(conn)
