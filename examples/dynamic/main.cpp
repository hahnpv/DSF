/**
 * The canonical C++ deck loader: parse XML, build, validate, run.
 *
 * Every step here is shared code (sim/SimInput.h, sim/sim_loader.h,
 * sim/xml_config.h, util/xml/validate.h) also reached by `dsf run` through
 * the pybind bindings — this file is deliberately thin so the two loaders
 * cannot drift (R8 / LOADER_CONSOLIDATION.md).
 */
#include <fstream>
#include <iostream>

#include "sim/sim.h"
#include "sim/SimInput.h"
#include "sim/sim_loader.h"
#include "sim/xml_config.h"
#include "util/xml/xml.h"
#include "util/xml/validate.h"

#include "boost/program_options.hpp"
namespace po = boost::program_options;

using namespace dsf::sim;
using namespace dsf::xml;

po::variables_map add_program_options(int argc, char * argv[])
{
        // program option variable map
        po::options_description desc("Command Line Parameters:");
        desc.add_options()
                ("fname", po::value<std::string>(),  "XML configuration file")
                ("not-strict", po::bool_switch(),
                 "run despite config-validation findings (strict is the default)")
                ;

        po::positional_options_description p;
        p.add("fname", 1);

        po::variables_map vm;
        po::store(po::command_line_parser(argc, argv).options(desc).positional(p).run(), vm);
        po::notify(vm);

        if (argc <= 1)
        {
                std::cout << desc << std::endl;
                std::cout << "This program parses an XML file to build a simulation" << std::endl
                        << std::endl
                        << "hahnpv@gmail.com" << std::endl;
        }

        return vm;
}

int main(int argc, char *argv[])
{
	po::variables_map vm = add_program_options(argc, argv);
	if (argc <= 1)
		return 0;

	std::string xml_path = vm["fname"].as<std::string>();
	xml xmlinput(xml_path.c_str());
	xmlinput.parse();
	xmlnode n = xmlnode(*xmlinput.xmlRoot).search("sim");
	SimInput input(n);

	// Shared build sequence: model library dlopen, output defaults, block
	// tree (instantiate + configure + typo check), Monte-Carlo dispersions.
	std::string xml_dir = ".";
	auto slash = xml_path.find_last_of('/');
	if (slash != std::string::npos)
		xml_dir = xml_path.substr(0, slash);

	Block* root = nullptr;
	try {
		root = build_from_xml(n, input, xml_dir);
	} catch (const std::exception& e) {
		std::cout << "FATAL ERROR: " << e.what() << std::endl;
		return 1;
	}

	Sim* sim = new Sim();
	sim->load(root, input.dt(), input.tmax(), input.rateConsole(), input.rateFile(),
	          input.integrator(), input.atol(), input.rtol());

	// Pass XML file info for HDF5 metadata and filename convention
	{
		std::ifstream ifs(xml_path);
		std::string xml_content((std::istreambuf_iterator<char>(ifs)),
		                         std::istreambuf_iterator<char>());
		sim->setXmlInfo(xml_path, xml_content);
	}

	// init first — blocks register output variables during init()
	sim->init();

	// Register <events> from XML (after init so Output has resolved all
	// variable pointers); also latches initial values for crossing detection.
	register_events(*sim, n);

	// Config validation: strict (refuse to run) is the DEFAULT; opt out with
	// --not-strict or <sim strict="false">.
	dsf::xml::ValidationReport report = dsf::xml::validate_config(xmlinput);
	report.print(std::cerr);
	if (resolve_strict(n, vm["not-strict"].as<bool>()) && !report.clean())
	{
		report.print_strict_banner(std::cerr);
		return 1;
	}

	sim->exec();

	return 0;
}
