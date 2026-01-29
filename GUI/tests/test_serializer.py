
import sys
import os
import unittest
import json
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPointF

# Setup Path
sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from core.model_registry import ModelRegistry
from ui.canvas import GraphScene, BlockItem, PortItem, ConnectionItem
from utils.serializer import GraphSerializer

app = QApplication(sys.argv)

class TestSerializer(unittest.TestCase):
    def test_save_load(self):
        registry = ModelRegistry()
        scene = GraphScene()
        
        # Setup Scene
        vehicle_def = registry.get_block("Vehicle")
        tank_def = registry.get_block("Tank")
        
        vehicle = BlockItem(vehicle_def, "Vehicle_1", QPointF(10, 20))
        tank = BlockItem(tank_def, "Tank_1", QPointF(100, 200))
        
        # Modify parameters
        tank.parameters["mass"] = 555.0
        
        scene.addItem(vehicle)
        scene.addItem(tank)
        
        # No connections for simple test (Connection saved tested implicitly if logic matches)
        # Or add connection
        # Need output port on Vehicle? No. 
        # Add simpler blocks if needed. 
        # But let's assume Tank flow_out -> Vehicle (doesn't have inputs).
        # Let's add Mass.
        mass_def = registry.get_block("Mass")
        mass = BlockItem(mass_def, "Mass_1", QPointF(300, 300))
        scene.addItem(mass)
        
        # Connect Mass input (force_in) to... nothing (no output matching).
        # Ah, Tank has flow_out. Mass has Force_in. Not compatible visually?
        # Canvas check: Port types matching not strict in MVP connection logic yet.
        # Let's connect Tank flow_out to Mass force_in just for serialization test.
        
        out_port = tank.outputs[0]
        in_port = mass.inputs[0]
        
        conn = ConnectionItem(out_port, in_port)
        out_port.connections.append(conn)
        in_port.connections.append(conn)
        scene.addItem(conn)
        
        # Save
        serializer = GraphSerializer(registry)
        serializer.save(scene, "test_save.dsf")
        
        # Verify File
        with open("test_save.dsf", "r") as f:
            data = json.load(f)
            
        self.assertEqual(len(data["blocks"]), 3)
        self.assertEqual(len(data["connections"]), 1)
        
        tank_data = next(b for b in data["blocks"] if b["id"] == "Tank_1")
        self.assertEqual(tank_data["parameters"]["mass"], 555.0)
        self.assertEqual(tank_data["x"], 100)
        
        # Load
        new_scene = GraphScene()
        serializer.load(new_scene, "test_save.dsf")
        
        items = list(new_scene.items())
        blocks = [i for i in items if isinstance(i, BlockItem)]
        self.assertEqual(len(blocks), 3)
        
        loaded_tank = next(b for b in blocks if b.instance_id == "Tank_1")
        self.assertEqual(loaded_tank.parameters["mass"], 555.0)
        self.assertEqual(loaded_tank.scenePos().x(), 100)
        
        # Verify connection
        conns = [i for i in items if isinstance(i, ConnectionItem)]
        self.assertEqual(len(conns), 1)
        
        # Cleanup
        os.remove("test_save.dsf")

if __name__ == '__main__':
    unittest.main()
