#include <time.h>

#include "SimInput.h"
#include "sim/sim.h"
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

		// Instantiate classes
        Block * root = new Block;
	int nx = n.numchild();
	for ( int i = 0; i < nx; i++)
	{
		root->addChild( TRefUnique<Block>( n.child( i).attrAsString("id")));
		n.parent();
	}
	for ( int i = 0; i < nx; i++)
	{
		n.child( i).attrAsString("id");
		root->getChild(i)->configure( n);
		n.parent();
	}

		// Instantiate simulation
	Sim *sim = new Sim();
	sim->load(root, input.dt(), input.tmax(), input.rateConsole(), input.rateFile());
	sim->run();

	return 0;
}
