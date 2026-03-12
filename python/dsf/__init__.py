try:
    from .dsf_core import *
except ImportError as e:
    if "dsf_core" in str(e):
        # C++ extension not built — pure-Python submodules (e.g. MCP server) still work
        pass
    else:
        raise
