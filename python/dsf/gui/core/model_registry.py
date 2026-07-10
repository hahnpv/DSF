from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class PortDefinition:
    name: str
    type: str  # "signal", "mass", "frame"
    direction: str  # "input", "output"

@dataclass
class PropertyDefinition:
    name: str
    type: str  # "float", "string", "vec3", "bool"
    default: Any
    description: str = ""
    options: List[str] = field(default_factory=list) # For enums/dropdowns

@dataclass
class BlockDefinition:
    type_id: str
    category: str
    description: str
    properties: List[PropertyDefinition]
    ports: List[PortDefinition]

class ModelRegistry:
    def __init__(self):
        self._blocks: Dict[str, BlockDefinition] = {}
        self._register_defaults()

    def get_block(self, type_id: str) -> Optional[BlockDefinition]:
        return self._blocks.get(type_id)

    def add_block(self, block_def: BlockDefinition):
        self._blocks[block_def.type_id] = block_def

    def get_all_block_names(self) -> List[str]:
        return list(self._blocks.keys())


    def get_categories(self) -> List[str]:
        return sorted(list(set(b.category for b in self._blocks.values())))

    def get_blocks_by_category(self, category: str) -> List[BlockDefinition]:
        return [b for b in self._blocks.values() if b.category == category]

    def _register_defaults(self):
        # Mass
        self._blocks["Mass"] = BlockDefinition(
            type_id="Mass",
            category="Dynamics",
            description="Simple point mass with inertia",
            properties=[
                PropertyDefinition("mass", "float", 100.0),
                PropertyDefinition("area", "float", 1.0),
                PropertyDefinition("station", "float", 0.0),
                PropertyDefinition("position", "vec3", [0.0, 0.0, 0.0]),
                PropertyDefinition("MOI", "vec3", [1.0, 1.0, 1.0]), # Simplified diagonal for MVP? Or vector string
            ],
            ports=[
                PortDefinition("force_in", "signal", "input"),
            ]
        )

        # Tank
        self._blocks["Tank"] = BlockDefinition(
            type_id="Tank",
            category="Propulsion",
            description="Fuel/Oxidizer Tank",
            properties=[
                PropertyDefinition("mass", "float", 1000.0),
                PropertyDefinition("station", "float", 0.0),
                PropertyDefinition("position", "vec3", [0.0, 0.0, 0.0]),
                PropertyDefinition("MOI", "vec3", [1.0, 1.0, 1.0]),
                PropertyDefinition("geometry", "string", "cylinder", options=["cylinder", "sphere", "point_mass"]),
                PropertyDefinition("radius", "float", 1.0),
                PropertyDefinition("length", "float", 5.0),
                PropertyDefinition("density", "float", 1000.0),
            ],
            ports=[
                PortDefinition("flow_out", "flow", "output"),
            ]
        )
        
        # RocketProp
        self._blocks["RocketProp"] = BlockDefinition(
            type_id="RocketProp",
            category="Propulsion",
            description="Rocket Engine",
            properties=[
                PropertyDefinition("max_thrust", "float", 10000.0),
                PropertyDefinition("Isp", "float", 300.0),
                PropertyDefinition("fuel_tank_id", "string", ""),
                PropertyDefinition("ox_tank_id", "string", ""),
            ],
            ports=[
                PortDefinition("throttle", "signal", "input"),
                PortDefinition("force_out", "signal", "output"),
            ]
        )

        # 6DOF / Vehicle
        self._blocks["Vehicle"] = BlockDefinition(
            type_id="Vehicle",
            category="System",
            description="Root vehicle container",
            properties=[
                PropertyDefinition("name", "string", "Vehicle"),
            ],
            ports=[]
        )
