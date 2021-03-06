#pragma once

#include "util/xml/xml.h"
#include "util/xml/xmlnode.h"
#include <string>
//
//	Input an XML file, parse it, get relevant bits
//      and update sim model
//


class SimInput
{
public:
	SimInput(dsf::xml::xmlnode n)
	{
		parse(n);
	}

	void parse(dsf::xml::xmlnode n)
	{
		time    = n.attrAsDouble("tmax");
		delta_time = n.attrAsDouble("dt");
		console = n.attrAsDouble("console");
		file    = n.attrAsDouble("file");
                lib     = n.attrAsString("library");
	}

	double tmax()	     { return time;       };
	double dt()	     { return delta_time; };
	double rateConsole() { return console;    };
	double rateFile()    { return file;       };
        std::string library(){ return lib;        };

private:
	double time;
	double delta_time;
	double console;
	double file;
        std::string lib;
};
