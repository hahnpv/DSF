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
        from dsf.gui.ui.canvas import BlockItem
        
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
        from dsf.gui.ui.canvas import BlockItem
        
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

        for bid in self._detect_cycles(adj):
            errors.append(ValidationError(
                bid,
                "Part of a circular dependency (cycle detected).",
                "error"
            ))

        return errors

    @staticmethod
    def _detect_cycles(adj: Dict[str, List[str]]) -> Set[str]:
        """Return the set of nodes that participate in at least one cycle.

        Color-DFS with an explicit recursion stack that is always popped
        (unlike the previous version, which returned early on a cycle and left
        stale nodes in the path, poisoning later DFS roots and falsely flagging
        feeder blocks). Only nodes on the actual back-edge cycle are returned.
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {u: WHITE for u in adj}
        stack: List[str] = []
        cycled: Set[str] = set()

        def visit(u):
            color[u] = GRAY
            stack.append(u)
            for v in adj.get(u, []):
                if v not in color:
                    continue            # edge to a non-block target; ignore
                if color[v] == GRAY:
                    idx = stack.index(v)  # back edge → cycle is stack[idx:]
                    cycled.update(stack[idx:])
                elif color[v] == WHITE:
                    visit(v)
            stack.pop()
            color[u] = BLACK

        for u in adj:
            if color[u] == WHITE:
                visit(u)
        return cycled
