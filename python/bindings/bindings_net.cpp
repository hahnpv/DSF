#include "bindings.h"
#include "net/NetClient.h"
#include "net/NetServer.h"

// using namespace dsf::net; // Net classes are global

void init_net(py::module_ &m) {
    py::class_<NetClient>(m, "NetClient")
        .def(py::init<>())
        .def("connect", &NetClient::connect)
        .def("send_xml_file", &NetClient::send_xml_file)
        .def("close", &NetClient::close);
        // receive<T> is a template, cannot bind directly without instantiation

    py::class_<NetServer, dsf::sim::Block>(m, "NetServer")
        .def(py::init<>())
        .def("init", &NetServer::init)
        .def("server_init", &NetServer::server_init)
        .def("listen", &NetServer::listen)
        .def("get_xml_file", &NetServer::get_xml_file)
        .def("rpt", &NetServer::rpt);
        // send<T> is a template
}
