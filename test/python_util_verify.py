import dsf
import sys

class UtilVerify(dsf.Block):
    def configure(self, xml):
        print("UtilVerify: Configuring...")
        
        # Constants
        print(f"PI: {dsf.PI}")
        print(f"RAD: {dsf.RAD}")

        # Vec3
        v1 = dsf.Vec3(1, 2, 3)
        v2 = dsf.Vec3(4, 5, 6)
        v3 = v1 + v2
        print(f"Vec3 Add: {v3}")
        print(f"Vec3 Mag: {v3.mag()}")
        v4 = v1 * 2.0
        print(f"Vec3 Scalar Mul: {v4}")
        v5 = 2.0 * v1
        print(f"Vec3 Scalar RMul: {v5}")

        # Mat3
        m1 = dsf.Mat3() # Identity? Or zero? Helper says constructors default.
        # Actually Mat3() {} leaves uninitialized? Or default?
        # Let's see bindings_util.cpp for Mat3() -> new Mat3().
        # C++ Mat3() {} does nothing. Elements undefined? 
        # Wait, if undefined, printing might show garbage.
        # Let's use constructor with values.
        m1 = dsf.Mat3(1,0,0, 0,1,0, 0,0,1)
        print(f"Mat3 Det: {m1.det()}")
        m2 = m1 * 2.0
        print(f"Mat3 Scalar Mul: {m2.det()}") # Should be 8 (2*2*2)
        
        # Mat3 * Vec3
        vr = m1 * v1
        print(f"Mat3 * Vec3: {vr}")

        # Quaternion
        q = dsf.Quaternion(0, 0, 0) # Euler 0,0,0
        print(f"Quat: x={q.x} w={q.w}")
        
        # Mat4
        m4 = dsf.Mat4()
        # Test operator()
        m4(1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1)
        print(f"Mat4 a00: {m4.a00}")
        
        # Table
        try:
            t1 = dsf.Table("table_1d.txt", "T1")
            val = t1(1.5)
            print(f"Table 1D interp(1.5): {val}") # Should be 15.0
        except Exception as e:
            print(f"Table 1D Error: {e}")

        # Table2d
        try:
            t2 = dsf.Table2d("table_2d.txt")
            val_v = t2.interp_vec(1.5)
            print(f"Table 2D interp_vec(1.5): {val_v}") # Should be [15.0, 150.0] roughly
            # val_i = t2.interp(1.5, 0)
            # print(f"Table 2D interp(1.5, 0): {val_i}")
        except Exception as e:
            print(f"Table 2D Error: {e}")
            
        # get_unique_file
        guf = dsf.get_unique_file("python_test_file.txt")
        print(f"Unique file: {guf.filename}")

    def init(self):
        print("UtilVerify: Init done, ending sim.")
        self.end()

    def update(self):
        pass
    def rpt(self):
        pass
    def finalize(self):
        pass
