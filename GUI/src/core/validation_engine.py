from typing import List, Dict, Set, Any, Optional
from collections import deque

class ValidationError:
    def __init__(self, block_id: str, message: str, level: str = "error"):
        self.block_id = block_id
        self.message = message
        self.level = level # "warning" or "error"

class ValidationEngine:
    def __init__(self, scene):
        self.scene = scene

    def validate(self) -> List[ValidationError]:
        errors = []
        errors.extend(self.check_ports())
        errors.extend(self.check_cycles())
        return errors

    def check_ports(self) -> List[ValidationError]:
        errors = []
        from ui.canvas import BlockItem
        
        blocks = [i for i in self.scene.items() if isinstance(i, BlockItem)]
        for block in blocks:
            # Heuristic: mandatory ports? 
            # In DSF, most inputs are mandatory unless they have defaults in the C++ side.
            # For now, we flag any unconnected input as a warning.
            for port in block.inputs:
                if not port.connections:
                    errors.append(ValidationError(
                        block.instance_id,
                        f"Input port '{port.name}' is unconnected.",
                        "warning"
                    ))
        return errors

    def check_cycles(self) -> List[ValidationError]:
        errors = []
        from ui.canvas import BlockItem
        
        # Build adjacency list
        blocks = {i.instance_id: i for i in self.scene.items() if isinstance(i, BlockItem)}
        adj = {bid: [] for bid in blocks}
        
        for bid, block in blocks.items():
            for port in block.outputs:
                for conn in port.connections:
                    other_port = conn.start_port if conn.end_port == port else conn.end_port
                    if other_port:
                        target_block = other_port.parentItem()
                        if isinstance(target_block, BlockItem):
                            adj[bid].append(target_block.instance_id)

        # Standard DFS cycle detection
        visited = set()
        path = set()
        cycled_blocks = set()

        def visit(u):
            if u in path:
                return True
            if u in visited:
                return False
            
            visited.add(u)
            path.add(u)
            
            for v in adj.get(u, []):
                if visit(v):
                    cycled_blocks.add(u)
                    cycled_blocks.add(v)
                    return True
            
            path.remove(u)
            return False

        for bid in blocks:
            if bid not in visited:
                visit(bid)

        for bid in cycled_blocks:
            errors.append(ValidationError(
                bid,
                "Part of a circular dependency (cycle detected).",
                "error"
            ))

        return errors
