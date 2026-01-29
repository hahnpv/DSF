#include <pybind11/stl.h>
#include "bindings.h"
#include "sim/block.h"
#include "sim/clock.h"
#include "sim/output.h"
#include "sim/sim.h"
#include "sim/TRefDict.h"
#include "sim/TClassDict.h" // Added include

using namespace dsf::sim;

// Trampoline for Block
class PyBlock : public Block {
public:
    using Block::Block; // Inherit constructors

    void configure(dsf::xml::xmlnode n) override {
        PYBIND11_OVERRIDE(void, Block, configure, n);
    }
    void init() override {
        PYBIND11_OVERRIDE(void, Block, init, );
    }
    void update() override {
        PYBIND11_OVERRIDE(void, Block, update, );
    }
    void rpt() override {
        PYBIND11_OVERRIDE(void, Block, rpt, );
    }
    void rptSim() override {
        PYBIND11_OVERRIDE(void, Block, rptSim, );
    }
    void finalize() override {
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
        .def("has_children", &Block::has_children)
        // .def("getParent", &Block::getParent) 
        // .def("getChild", &Block::getChild)
        ;

    py::class_<Output, Block>(m, "Output")
        .def(py::init<double>())
        .def("init", &Output::init)
        .def("rpt", &Output::rpt)
        .def("report", &Output::report)
        .def("finalize", &Output::finalize)
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
        .def("load", &Sim::load)
        .def("run", &Sim::run);

    m.def("make_block", [](std::string id) {
             return dsf::sim::TRefUnique<Block>(id);
         }, py::return_value_policy::take_ownership);

    m.def("get_registered_blocks", []() {
        std::vector<std::string> names;
        auto* dict = dsf::sim::TClassDict<Block>::Instance();
        for (auto* factory : dict->classDictPtr) {
            names.push_back(factory->name());
        }
        return names;
    });
}
