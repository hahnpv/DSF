#include "bindings.h"
#include "sim/block.h"
#include "sim/clock.h"
#include "sim/output.h"
#include "sim/sim.h"

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
        .def("addChild", &Block::addChild)
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
        ;

    py::class_<Sim>(m, "Sim")
        .def(py::init<>());
}
