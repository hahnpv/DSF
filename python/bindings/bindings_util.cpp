#include "bindings.h"
#include <pybind11/stl.h> 
#include <pybind11/operators.h>

#include "util/xml/xml.h"
#include "util/xml/validate.h"
#include "util/math/vec3.h"
#include "util/math/mat3.h"
#include "util/math/mat4.h"
#include "util/math/quat.h"
#include "util/math/constants.h"
#include "util/tbl/tbl.h"
#include "util/tbl/tbl2d.h"
#include "util/file/get_unique_file.h"

using namespace dsf::xml;
using namespace dsf::util;

void init_util(py::module_ &m) {
    // Constants
    m.attr("C_DEG") = dsf::util::math::C_DEG;
    m.attr("RAD") = dsf::util::math::RAD;
    m.attr("PI") = dsf::util::math::PI;

    // Vec3
    py::class_<Vec3>(m, "Vec3")
        .def(py::init<double, double, double>())
        .def(py::init<>())
        .def_readwrite("x", &Vec3::x)
        .def_readwrite("y", &Vec3::y)
        .def_readwrite("z", &Vec3::z)
        .def("mag", &Vec3::mag)
        .def("__add__", &Vec3::operator+, py::is_operator())
        .def("__sub__", &Vec3::operator-, py::is_operator())
        .def("__mul__", &Vec3::operator*, py::is_operator()) // scalar
        .def("__rmul__", [](Vec3 &v, double d) { return v * d; }, py::is_operator())
        .def("__truediv__", &Vec3::operator/, py::is_operator())
        .def("__iadd__", &Vec3::operator+=, py::is_operator())
        .def("__isub__", &Vec3::operator-=, py::is_operator())
        .def("__call__", &Vec3::operator(), py::is_operator()) // set
        .def("__getitem__", [](Vec3 &v, int i) -> double { if(i<0||i>2) throw py::index_error(); return v[i]; })
        .def("__repr__", [](const Vec3 &v) {
            return "<dsf.Vec3 (" + std::to_string(v.x) + ", " + std::to_string(v.y) + ", " + std::to_string(v.z) + ")>";
        });

    // Quaternion
    py::class_<dsf::util::Quaternion>(m, "Quaternion")
        .def(py::init<>())
        .def(py::init<double, double, double>())       // from Euler (phi, theta, psi)
        .def(py::init<double, double, double, double>()) // from components (q0, q1, q2, q3)
        // Raw components (scalar-first: q0=scalar, q1/q2/q3=vector)
        .def_readwrite("q0", &dsf::util::Quaternion::q0)
        .def_readwrite("q1", &dsf::util::Quaternion::q1)
        .def_readwrite("q2", &dsf::util::Quaternion::q2)
        .def_readwrite("q3", &dsf::util::Quaternion::q3)
        // Standard named accessors (read-only)
        .def_property_readonly("w", &dsf::util::Quaternion::w)
        .def_property_readonly("x", &dsf::util::Quaternion::x)
        .def_property_readonly("y", &dsf::util::Quaternion::y)
        .def_property_readonly("z", &dsf::util::Quaternion::z)
        // Euler extraction
        .def("phi", &dsf::util::Quaternion::phi)
        .def("theta", &dsf::util::Quaternion::theta)
        .def("psi", &dsf::util::Quaternion::psi)
        // Rotation operations
        .def("dcm", &dsf::util::Quaternion::dcm)
        .def("Teb", &dsf::util::Quaternion::Teb)  // deprecated alias
        .def("quat_mult", &dsf::util::Quaternion::quat_mult)
        // Normalization
        .def("normalize", &dsf::util::Quaternion::normalize)
        .def("magnitude", &dsf::util::Quaternion::magnitude)
        // Operators
        .def("__mul__", &dsf::util::Quaternion::operator*, py::is_operator())
        .def("__add__", &dsf::util::Quaternion::operator+, py::is_operator())
        .def("__call__", &dsf::util::Quaternion::operator(), py::is_operator())
        .def("__repr__", [](const dsf::util::Quaternion &q) {
            return "<dsf.Quaternion (q0=" + std::to_string(q.q0) + ", q1=" + std::to_string(q.q1)
                 + ", q2=" + std::to_string(q.q2) + ", q3=" + std::to_string(q.q3) + ")>";
        })
        ;

    // Mat3
    py::class_<Mat3>(m, "Mat3")
        .def(py::init<>())
        .def(py::init<double, double, double, double, double, double, double, double, double>())
        .def(py::init<Vec3, Vec3, Vec3>())
        .def_readwrite("a0", &Mat3::a0)
        .def_readwrite("a1", &Mat3::a1)
        .def_readwrite("a2", &Mat3::a2)
        .def("det", &Mat3::det)
        .def("inv", &Mat3::inv)
        .def("transpose", &Mat3::transpose)
        .def("__add__", &Mat3::operator+, py::is_operator())
        .def("__sub__", &Mat3::operator-, py::is_operator())
        // Mat3 * Mat3
        .def("__mul__", (Mat3 (Mat3::*)(Mat3)) &Mat3::operator*, py::is_operator()) 
        // Mat3 * double
        .def("__mul__", (Mat3 (Mat3::*)(double)) &Mat3::operator*, py::is_operator())
        .def("__rmul__", [](Mat3 &m, double d) { return m * d; }, py::is_operator())
        // Mat3 * Vec3
        .def("__mul__", (Vec3 (Mat3::*)(Vec3)) &Mat3::operator*, py::is_operator())
        .def("__truediv__", &Mat3::operator/, py::is_operator())
        .def("__imul__", &Mat3::operator*=, py::is_operator())
        .def("__iadd__", &Mat3::operator+=, py::is_operator())
        .def("__call__", &Mat3::operator(), py::is_operator()) // Set values
        .def("__getitem__", [](Mat3 &m, int i) -> Vec3& { 
             if (i<0 || i>2) throw py::index_error();
             return m.operator[](i); 
        }, py::return_value_policy::reference)
        .def("__repr__", [](const Mat3 &m) {
            return "<dsf.Mat3>"; 
        });

    // Mat4
    py::class_<Mat4>(m, "Mat4")
        .def(py::init<>())
        .def(py::init<double, double, double, double,double, double, double, double,double, double, double, double,double, double, double, double>())
        .def_readwrite("a00", &Mat4::a00).def_readwrite("a01", &Mat4::a01).def_readwrite("a02", &Mat4::a02).def_readwrite("a03", &Mat4::a03)
        .def_readwrite("a10", &Mat4::a10).def_readwrite("a11", &Mat4::a11).def_readwrite("a12", &Mat4::a12).def_readwrite("a13", &Mat4::a13)
        .def_readwrite("a20", &Mat4::a20).def_readwrite("a21", &Mat4::a21).def_readwrite("a22", &Mat4::a22).def_readwrite("a23", &Mat4::a23)
        .def_readwrite("a30", &Mat4::a30).def_readwrite("a31", &Mat4::a31).def_readwrite("a32", &Mat4::a32).def_readwrite("a33", &Mat4::a33)
        .def("det", &Mat4::det)
        .def("inv", &Mat4::inv)
        .def("transpose", &Mat4::transpose)
        .def("__mul__", &Mat4::operator*, py::is_operator()) // * Quaternion
        .def("__call__", &Mat4::operator(), py::is_operator())
        ;

    // Table
    py::class_<Table>(m, "Table")
        .def(py::init<>())
        .def(py::init<std::string, std::string>())
        .def("interp", &Table::interp)
        .def("__call__", &Table::operator());

    // Table2d
    py::class_<Table2d>(m, "Table2d")
        .def(py::init<std::string>())
        .def("interp", (double (Table2d::*)(double, int)) &Table2d::interp)
        .def("interp_vec", (std::vector<double> (Table2d::*)(double)) &Table2d::interp);

    // get_unique_file
    py::class_<get_unique_file>(m, "get_unique_file")
        .def(py::init<std::string>())
        .def_readonly("filename", &get_unique_file::filename);

    // xmlnode
    py::class_<xmlnode>(m, "xmlnode")
        .def("check", &xmlnode::findAttr)
        .def("findAttr", &xmlnode::findAttr)
        .def("attrAsString", &xmlnode::attrAsString)
        .def("attrAsDouble", &xmlnode::attrAsDouble)
        .def("attrAsInt", [](xmlnode &n, std::string s){ return (int)n.attrAsDouble(s); })
        .def("attrAsBool", &xmlnode::attrAsBool)
        .def("attrAsVec3", &xmlnode::attrAsVec3)
        .def("attrAsMat3", &xmlnode::attrAsMat3)
        .def("child", &xmlnode::child, py::return_value_policy::reference)
        .def("parent", &xmlnode::parent, py::return_value_policy::reference)
        .def("numchild", &xmlnode::numchild)
        .def("search", &xmlnode::search, py::return_value_policy::reference)
        .def("children", &xmlnode::children)
        .def("name", &xmlnode::name);

    // xml
    py::class_<xml>(m, "xml")
        .def(py::init<std::string>())
        .def("parse", &xml::parse)
        .def_readonly("xmlRoot", &xml::xmlRoot, py::return_value_policy::reference);

    // Config validation (strict mode, H6). Call after the configure pass on
    // the SAME xml document the tree was built from; see util/xml/validate.h.
    m.def("validate_config", [](const xml& doc) {
        dsf::xml::ValidationReport r = dsf::xml::validate_config(doc);
        py::dict d;
        d["unused"] = r.unused;             // deck attrs nobody read (typos) — fatal in strict
        d["table_errors"] = r.table_errors; // tables that fell back to empty — fatal in strict
        d["missing"] = r.missing;           // lookups that defaulted — informational
        return d;
    }, "Diff a parsed deck against its attribute-usage record (strict mode)");
}
