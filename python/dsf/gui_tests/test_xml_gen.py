
import sys
import os
import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPointF

# Setup Path
sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from core.model_registry import ModelRegistry
from ui.canvas import GraphScene, BlockItem, PortItem, ConnectionItem
from utils.xml_generator import XMLGenerator

app = QApplication(sys.argv)

class TestXMLGen(unittest.TestCase):
    def test_generation(self):
        registry = ModelRegistry()
        scene = GraphScene()
        
        # Create Blocks
        vehicle_def = registry.get_block("Vehicle")
        tank_def = registry.get_block("Tank")
        prop_def = registry.get_block("RocketProp")
        
        vehicle = BlockItem(vehicle_def, "Vehicle_1", QPointF(0, 0))
        tank = BlockItem(tank_def, "Tank_1", QPointF(200, 0))
        prop = BlockItem(prop_def, "Prop_1", QPointF(400, 0))
        
        scene.addItem(vehicle)
        scene.addItem(tank)
        scene.addItem(prop)
        
        # Create Connection: Tank (flow_out) -> Prop (throttle? No wait, prop doesn't have fuel input in registry defaults?)
        # Let's check registry defaults I wrote.
        # RocketProp: ports=[throttle(in), force_out(out)]. Props: fuel_tank_id
        # Wait, if there is no explicit port for "fuel_tank", how do I connect it?
        # My registry definition for RocketProp in previous step only had "throttle" and "force_out".
        # So I cannot connect Tank to RocketProp in the current registry!
        # I need to update Registry to include a "fuel_tank" input port (type="flow" or "ref") if I want visual connection.
        # Or I just rely on manual property editing for MVP.
        # But FR-2.2 says "Connect model outputs to inputs".
        # Let's assume for this test I connect "force_out" of Prop to "force_in" of Mass (if Mass has it).
        
        mass_def = registry.get_block("Mass")
        mass = BlockItem(mass_def, "Mass_1", QPointF(600, 0))
        scene.addItem(mass)
        
        # Connect Prop.force_out -> Mass.force_in
        out_port = prop.outputs[0] # force_out
        in_port = mass.inputs[0] # force_in
        
        conn = ConnectionItem(out_port, in_port)
        # Manually wire internal lists since Scene.mouseRelease does it
        out_port.connections.append(conn)
        in_port.connections.append(conn)
        scene.addItem(conn)
        
        # Generate XML
        generator = XMLGenerator(scene)
        xml_out = generator.generate()
        
        print("Generated XML:\n", xml_out)
        
        # Verify
        self.assertIn('<sim', xml_out)
        self.assertIn('<vehicle id="Vehicle_1"', xml_out)
        self.assertIn('<tank id="Tank_1"', xml_out)
        self.assertIn('<rocketprop id="Prop_1"', xml_out)
        self.assertIn('<mass id="Mass_1"', xml_out)
        
        # Verify connection mapping (Prop -> Mass)
        # Mass has "force_in". Prop has "force_out".
        # XML Generator logic: iter inputs. Mass has "force_in". Connected to Prop.
        # Generated param: "force_in_id" = "Prop_1"
        self.assertIn('force_in_id="Prop_1"', xml_out)

if __name__ == '__main__':
    unittest.main()
