import dsf
import sys

print("VerifyBlock module loaded")

class VerifyBlock(dsf.Block):
    def configure(self, xml):
        print("VerifyBlock configured")
        # Test xmlnode bindings
        try:
            rpt = xml.attrAsDouble("rpt")
            print(f"RPT from XML via binding: {rpt}")
        except Exception as e:
            print(f"Error accessing xmlnode: {e}")

    def init(self):
        print("VerifyBlock init called")
        try:
            print(f"Time at init: {self.t()}")
            print(f"dt at init: {self.dt()}")
        except Exception as e:
            print(f"Error accessing simulation time in init: {e}")

    def update(self):
        pass

    def rpt(self):
        try:
            t = self.t()
            print(f"VerifyBlock rpt: t={t}")
            if t > 0.2:
                print("Simulation checks passed, stopping.")
                self.end()
        except Exception as e:
            print(f"Error in rpt: {e}")

    def finalize(self):
        print("VerifyBlock finalize called")
