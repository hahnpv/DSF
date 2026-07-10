#include <time.h>
#include <dlfcn.h>
#include <fstream>

#include "SimInput.h"
#include "sim/sim.h"
#include "sim/event.h"
#include "sim/TRefDict.h"
#include "sim/monte_carlo.h"
#include "sim/xml_config.h"
#include "util/xml/xml.h"
#include "util/xml/validate.h"

#include "boost/program_options.hpp"
namespace po = boost::program_options;

using namespace dsf::sim;
using namespace dsf::xml;

// FIXME relocate to DSF with SimInput

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
                cout << desc << endl;
                cout << "This program parses an XML file to build a simulation" << endl
                        << "(future versions will allow command-line overrides)" << endl
                        << endl
                        << "hahnpv@gmail.com" << endl;
        }

        return vm;
}

int main(int argc, char *argv[])
{
        po::variables_map vm = add_program_options(argc, argv);
        if (argc <= 1)
                return 0;

        xml xmlinput(vm["fname"].as<std::string>().c_str());
	xmlinput.parse();
	xmlnode n = xmlnode(*xmlinput.xmlRoot).search("sim");
        SimInput input( n);

		// Load shared library of models
        dlopen(input.library().c_str(), RTLD_NOW | RTLD_GLOBAL);		// NOTE: you can omit this section
        char * result = dlerror();				// and staticly compile your model files
        if(result!=NULL)					// with this file to generate a static
        {							// executable
		cout << "FATAL ERROR: " << result << endl;	//
		return 1;					// See CMakeLists for an example
        }							//

		// Instantiate classes
        Block * root = new Block;
	int nx = n.numchild();
	for ( int i = 0; i < nx; i++)
	{
		xmlnode child_node = n;
		child_node.child(i);
		std::string child_id = child_node.attrAsString("id");
		if (child_id.empty()) continue;  // skip non-block nodes like <events>
		std::string model = child_node.attrAsString("class");
		if (model == "") model = child_id;
		root->addChild( TRefUnique<Block>( model.c_str()));
	}

    // Map XML LogLevel — must be set BEFORE Vehicle::configure() because
    // vehicles with rpt= create per-vehicle Output objects that read these defaults.
    auto mapLevel = [](int l) {
        if (l == 0) return dsf::sim::LOG_CRITICAL;
        if (l == 2) return dsf::sim::LOG_VERBOSE;
        return dsf::sim::LOG_NORMAL;
    };

    dsf::sim::LogLevel csv_lvl = mapLevel(input.getCSVLogLevel());
    dsf::sim::LogLevel h5_lvl = mapLevel(input.getHDF5LogLevel());

    dsf::sim::Output::defaultCSV() = input.isCSV();
    dsf::sim::Output::defaultHDF5() = input.isHDF5();
    dsf::sim::Output::defaultCSVLevel() = csv_lvl;
    dsf::sim::Output::defaultHDF5Level() = h5_lvl;

	for ( int i = 0, bi = 0; i < nx; i++)
	{
		xmlnode child_node = n;
		child_node.child(i);
		if (std::string(child_node.attrAsString("id")).empty()) continue;
		root->getChild(bi)->configure( child_node);
		// Configure-time metadata check: flag deck attributes this block's
		// DSF_PROPERTY metadata does not declare (likely typos).
		dsf::sim::warn_unknown_attributes(root->getChild(bi), child_node);
		bi++;
	}


		// ── Monte Carlo: apply dispersions (after configure, before load) ──
		// Shared with the Python path via sim/xml_config.h.
	dsf::sim::apply_monte_carlo(root, n, input.caseId(), input.seed());

		// Instantiate simulation
	Sim *sim = new Sim();
	sim->load(root, input.dt(), input.tmax(), input.rateConsole(), input.rateFile(),
	          input.integrator(), input.atol(), input.rtol());

	// Pass XML file info for HDF5 metadata and filename convention
	{
		std::string xml_path = vm["fname"].as<std::string>();
		std::ifstream ifs(xml_path);
		std::string xml_content((std::istreambuf_iterator<char>(ifs)),
		                         std::istreambuf_iterator<char>());
		sim->setXmlInfo(xml_path, xml_content);
	}

	// init first — blocks register output variables during init()
	sim->init();

	// Register <events> from XML (after init so Output has resolved all
	// variable pointers). Shared with the Python path via sim/xml_config.h;
	// register_events() also latches initial values for crossing detection.
	dsf::sim::register_events(*sim, n);

	// Config validation: flag deck attributes nobody read (typos) and
	// table loads that fell back to empty. Strict (refuse to run) is the
	// DEFAULT; opt out with --not-strict or <sim strict="false">.
	bool strict = true;
	if (n.findAttr("strict") && !n.attrAsBool("strict"))
		strict = false;                          // deck opts out
	if (vm["not-strict"].as<bool>())
		strict = false;                          // command line opts out
	dsf::xml::ValidationReport report = dsf::xml::validate_config(xmlinput);
	report.print(std::cerr);
	if (strict && !report.clean())
	{
		report.print_strict_banner(std::cerr);
		return 1;
	}

	sim->exec();

	return 0;
}
