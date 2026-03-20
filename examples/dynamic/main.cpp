#include <time.h>
#include <dlfcn.h>

#include "SimInput.h"
#include "sim/sim.h"
#include "sim/event.h"
#include "sim/TRefDict.h"
#include "util/xml/xml.h"

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
		bi++;
	}


		// Instantiate simulation
	Sim *sim = new Sim();
	sim->load(root, input.dt(), input.tmax(), input.rateConsole(), input.rateFile(),
	          input.integrator(), input.atol(), input.rtol());
    
	// init first — blocks register output variables during init()
	sim->init();

	// Parse <events> from XML (after init so Output has all variable pointers)
	for (int ei = 0; ei < n.numchild(); ei++)
	{
		xmlnode child = n;
		child.child(ei);
		if (std::string(child.name()) != "events") continue;

		for (int ej = 0; ej < child.numchild(); ej++)
		{
			xmlnode ev = child;
			ev.child(ej);
			if (std::string(ev.name()) != "event") continue;

			std::string name   = ev.attrAsString("name");
			std::string type_s = ev.attrAsString("type");
			std::string var_s  = ev.attrAsString("variable");
			double value       = ev.attrAsDouble("value");
			std::string action = ev.attrAsString("action");

			// Resolve condition type
			dsf::sim::EventType etype;
			if      (type_s == "time_ge")  etype = dsf::sim::EventType::TIME_GE;
			else if (type_s == "crosses")  etype = dsf::sim::EventType::CROSSES_VALUE;
			else if (type_s == "rising")   etype = dsf::sim::EventType::RISING;
			else if (type_s == "falling")  etype = dsf::sim::EventType::FALLING;
			else if (type_s == "ge")       etype = dsf::sim::EventType::STATE_GE;
			else if (type_s == "le")       etype = dsf::sim::EventType::STATE_LE;
			else {
				cout << "[Event] Unknown type '" << type_s << "' for event '" << name << "'" << endl;
				continue;
			}

			// Resolve variable pointer via Output
			double* var_ptr = nullptr;
			if (!var_s.empty() && sim->output) {
				var_ptr = sim->output->find_variable(var_s);
				if (!var_ptr) {
					cout << "[Event] WARNING: Variable '" << var_s << "' not found for event '" << name << "'" << endl;
					continue;
				}
			}

			// Build Event
			dsf::sim::Event event;
			event.name = name;
			event.condition.type = etype;
			event.condition.variable = var_ptr;
			event.condition.threshold = value;
			event.one_shot = true;

			// Resolve action
			if (action == "sim.terminate") {
				event.callback = [sim]() {
					cout << "[Event] Terminating simulation" << endl;
					sim->clock->end();
				};
			} else if (action == "log" || action.empty()) {
				event.callback = nullptr; // EventBus prints [Event] line by default
			} else {
				cout << "[Event] Unknown action '" << action << "' for '" << name << "'" << endl;
			}

			int id = dsf::sim::EventBus::Instance()->add(event);
			cout << "[Event] Registered '" << name << "' (id=" << id << " type=" << type_s
			     << " var=" << var_s << " val=" << value << " action=" << action << ")" << endl;
		}
	}

	// Latch initial values for crossing detection, then run
	dsf::sim::EventBus::Instance()->latch();
	sim->exec();

	return 0;
}
