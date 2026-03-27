#include <pybind11/stl.h>
#include "bindings.h"
#include "sim/block.h"
#include "sim/clock.h"
#include "sim/output.h"
#include "sim/sim.h"
#include "sim/TRefDict.h"
#include "sim/TClassDict.h" // Added include
#include "util/math/quat.h" // Added for Quaternion introspection

using namespace dsf::sim;

// Trampoline for Block
class PyBlock : public Block {
public:
    using Block::Block; // Inherit constructors

    void configure(dsf::xml::xmlnode n) override {
        std::cout << "[PyBlock::configure] " << this << std::endl;
        pybind11::gil_scoped_acquire gil;
        PYBIND11_OVERRIDE(void, Block, configure, n);
    }
    void init() override {
        std::cout << "[PyBlock::init] " << this << std::endl;
        pybind11::gil_scoped_acquire gil;
        PYBIND11_OVERRIDE(void, Block, init, );
    }
    void update() override {
        std::cout << "[PyBlock::update] " << this << std::endl;
        pybind11::gil_scoped_acquire gil;
        PYBIND11_OVERRIDE(void, Block, update, );
    }
    void rpt() override {
        std::cout << "[PyBlock::rpt] " << this << std::endl;
        pybind11::gil_scoped_acquire gil;
        PYBIND11_OVERRIDE(void, Block, rpt, );
    }
    void rptSim() override {
        std::cout << "[PyBlock::rptSim] " << this << std::endl;
        pybind11::gil_scoped_acquire gil;
        PYBIND11_OVERRIDE(void, Block, rptSim, );
    }
    void finalize() override {
        std::cout << "[PyBlock::finalize] " << this << std::endl;
        pybind11::gil_scoped_acquire gil;
        PYBIND11_OVERRIDE(void, Block, finalize, );
    }
};

void init_sim(py::module_ &m) {
    py::enum_<LogLevel>(m, "LogLevel")
        .value("LOG_CRITICAL", LOG_CRITICAL)
        .value("LOG_NORMAL", LOG_NORMAL)
        .value("LOG_VERBOSE", LOG_VERBOSE)
        .export_values();

    py::class_<Clock>(m, "Clock")
        .def(py::init<>())
        .def(py::init<double, double>())
        .def("t", &Clock::t)
        .def("dt", &Clock::dt)
        .def("set_dt", &Clock::set_dt)
        .def("end", &Clock::end)
        .def("Sample", &Clock::Sample);

    py::class_<Block, PyBlock>(m, "Block")
        .def(py::init<>())
        .def("configure", &Block::configure)
        .def("init", &Block::init)
        .def("update", &Block::update)
        .def("rpt", &Block::rpt)
        .def("rptSim", &Block::rptSim)
        .def("finalize", &Block::finalize)
        .def("t", &Block::t)
        .def("dt", &Block::dt)
        .def("set_dt", &Block::set_dt)
        .def("end", &Block::end)
        .def("sample", &Block::sample)
        .def("addChild", &Block::addChild, py::keep_alive<1, 2>())
        .def("getChildren", &Block::getChildren, py::return_value_policy::reference)
        .def("get_name", &Block::getName)
        .def("setName", &Block::setName)
        .def("set_name", &Block::setName)
        .def("get_class_name", [](Block& self) -> std::string {
            return boost::core::demangle(typeid(self).name());
        })
        .def("has_children", &Block::has_children)
        .def("get_property", [](Block& self, std::string name) -> py::object {
            // 1. Find the factory for this instance's class
            std::string class_name = boost::core::demangle(typeid(self).name());
            auto* dict = dsf::sim::TClassDict<Block>::Instance();
            // Demangled name might need cleanup or direct match
            // TClassDict stores demangled names.
            
            // Search logic in TClassDict is: classDictPtr[i]->name().compare(compareid)
            int idx = dict->search(class_name);
            if (idx == -1) {
                // Fallback: Try regex or manual strip if needed? 
                // For now assuming boost::core::demangle output matches TClass registration exactly.
                throw std::runtime_error("Class not found in registry: " + class_name);
            }
            
            auto* factory = dict->classDictPtr[idx];
            const auto& props = factory->getProperties();
            
            for (const auto& p : props) {
                if (p.name == name) {
                    // std::cout << "DEBUG: get_property " << name << " offset=" << p.offset << std::endl;
                    if (p.offset == 0) {
                        return py::none();
                    }
                    // Use byte pointer arithmetic
                    char* base = reinterpret_cast<char*>(&self);
                    void* ptr = static_cast<void*>(base + p.offset);
                    
                    if (p.type == "double") {
                        return py::cast(*(double*)ptr);
                    } else if (p.type == "int") {
                        return py::cast(*(int*)ptr);
                    } else if (p.type == "bool") {
                        return py::cast(*(bool*)ptr);
                    } else if (p.type == "Vec3" || p.type == "vector") {
                        return py::cast(*(dsf::util::Vec3*)ptr);
                    } else if (p.type == "Mat3") {
                        return py::cast(*(dsf::util::Mat3*)ptr);
                    } else if (p.type == "Quaternion") {
                        return py::cast(*(dsf::util::Quaternion*)ptr);
                    }
                    else {
                        throw std::runtime_error("Unsupported property type for introspection: " + p.type);
                    }
                }
            }
            return py::none();
        });

    py::class_<Output, Block>(m, "Output")
        .def(py::init<double>())
        .def("init", &Output::init)
        .def("rpt", &Output::rpt)
        .def("report", &Output::report)
        .def("finalize", &Output::finalize)
        .def("get_header_names", &Output::get_header_names)
        .def("get_current_values", &Output::get_current_values)
        .def("set_base_name", &Output::setBaseName)
        .def("set_metadata", &Output::setMetadata)
        // add() methods store pointers to variables, unsafe for Python types safely without wrapper
        //.def("add", ...) 
        .def_property_static("defaultCSV", 
            [](py::object) { return Output::defaultCSV(); }, 
            [](py::object, bool v) { Output::defaultCSV() = v; })
        .def_property_static("defaultHDF5", 
            [](py::object) { return Output::defaultHDF5(); }, 
            [](py::object, bool v) { Output::defaultHDF5() = v; })
        .def_property_static("defaultCSVLevel", 
            [](py::object) { return Output::defaultCSVLevel(); }, 
            [](py::object, LogLevel v) { Output::defaultCSVLevel() = v; })
        .def_property_static("defaultHDF5Level", 
            [](py::object) { return Output::defaultHDF5Level(); }, 
            [](py::object, LogLevel v) { Output::defaultHDF5Level() = v; })
        ;

    py::class_<Sim>(m, "Sim")
        .def(py::init<>())
        .def("load", py::overload_cast<Block*, double, double, double, double>(&Sim::load))
        .def("load", py::overload_cast<Block*, double, double, double, double,
             const std::string&, double, double>(&Sim::load),
             py::arg("root"), py::arg("dt"), py::arg("tmax"),
             py::arg("console"), py::arg("file"),
             py::arg("integrator_type"), py::arg("atol") = 1e-8, py::arg("rtol") = 1e-6)
        .def("set_xml_info", &Sim::setXmlInfo,
             py::arg("xml_file"), py::arg("xml_content"))
        .def("run", &Sim::run, py::call_guard<py::gil_scoped_release>()) // Release GIL!
        .def("exec", &Sim::exec, py::call_guard<py::gil_scoped_release>()) // Release GIL!
        .def("step", &Sim::step, py::call_guard<py::gil_scoped_release>()) // Release GIL!
        .def("finalize", &Sim::finalize)
        .def("init", &Sim::init)
        .def_readonly("clock", &Sim::clock, py::return_value_policy::reference)
        .def_readonly("output", &Sim::output, py::return_value_policy::reference);

    m.def("make_block", [](std::string id) {
             return dsf::sim::TRefUnique<Block>(id);
         }, py::return_value_policy::take_ownership);

    py::class_<PropertyMetadata>(m, "PropertyMetadata")
        .def_readonly("name", &PropertyMetadata::name)
        .def_readonly("type", &PropertyMetadata::type)
        .def_readonly("defaultValue", &PropertyMetadata::defaultValue)
        .def_readonly("description", &PropertyMetadata::description);

    py::class_<PortMetadata>(m, "PortMetadata")
        .def_readonly("name", &PortMetadata::name)
        .def_readonly("type", &PortMetadata::type)
        .def_readonly("direction", &PortMetadata::direction);

    m.def("get_block_metadata", [](std::string name) {
        auto* dict = dsf::sim::TClassDict<Block>::Instance();
        int idx = dict->search(name);
        if (idx >= 0) {
            auto* factory = dict->classDictPtr[idx];
            return py::make_tuple(factory->getProperties(), factory->getPorts());
        }
        throw std::runtime_error("Block not found: " + name);
    });

    m.def("get_registered_blocks", []() {
        std::vector<std::string> names;
        auto* dict = dsf::sim::TClassDict<Block>::Instance();
        for (auto* factory : dict->classDictPtr) {
            names.push_back(factory->name());
        }
        return names;
    });
}
