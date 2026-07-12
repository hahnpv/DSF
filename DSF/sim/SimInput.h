/**
 * @file SimInput.h
 * @brief Parse the <sim> element's run configuration (times, output policy,
 *        integrator, Monte-Carlo case identity).
 *
 * THE single reader of <sim> attributes, used by both loaders: the C++
 * `dynamic` executable and (via pybind) `dsf run`. Lived in examples/dynamic
 * until 2026-07-11; relocated so Python cannot drift from it (R8 /
 * LOADER_CONSOLIDATION.md).
 */
#pragma once

#include <string>

#include "log_level.h"
#include "../util/xml/xml.h"

namespace dsf
{
namespace sim
{

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
		outputCfg = n.attrAsString("output");
		logLevel = n.attrAsString("log_level");
		csvLogLevel = n.attrAsString("csv_log_level");
		hdf5LogLevel = n.attrAsString("hdf5_log_level");
		integratorType = n.attrAsString("integrator");
		std::string atol_s = n.attrAsString("atol");
		std::string rtol_s = n.attrAsString("rtol");
		aTol = atol_s.empty() ? 1e-8 : std::stod(atol_s);
		rTol = rtol_s.empty() ? 1e-6 : std::stod(rtol_s);

		// Monte Carlo case identity (patched into case decks by dsf.mc)
		std::string seed_s = n.attrAsString("seed");
		std::string case_s = n.attrAsString("case_id");
		mcSeed = seed_s.empty() ? 0 : (unsigned int)std::stoul(seed_s);
		mcCaseId = case_s.empty() ? -1 : std::stoi(case_s);
	}

	double tmax()	     { return time;       };
	double dt()	     { return delta_time; };
	double rateConsole() { return console;    };
	double rateFile()    { return file;       };
	std::string library(){ return lib;        };

	std::string integrator() { return integratorType; }
	unsigned int seed() { return mcSeed; }
	int caseId() { return mcCaseId; }
	double atol() { return aTol; }
	double rtol() { return rTol; }

	bool isHDF5() { return outputCfg.find("hdf5") != std::string::npos; }
	bool isCSV() { return outputCfg.empty() || outputCfg.find("csv") != std::string::npos; }

	// Helper to parse string to level int (0=Crit, 1=Norm, 2=Verb)
	int parseLevelStr(std::string s) {
		if (s == "verbose") return 2;
		if (s == "critical") return 0;
		return 1; // Normal
	}

	int getLogLevel() { return parseLevelStr(logLevel); }

	int getCSVLogLevel() {
		if (!csvLogLevel.empty()) return parseLevelStr(csvLogLevel);
		if (!logLevel.empty()) return parseLevelStr(logLevel);
		return 1;
	}

	int getHDF5LogLevel() {
		if (!hdf5LogLevel.empty()) return parseLevelStr(hdf5LogLevel);
		if (!logLevel.empty()) return parseLevelStr(logLevel);
		return 1;
	}

	// LogLevel-typed accessors — the one mapping both loaders share.
	static LogLevel toLogLevel(int l) {
		if (l == 0) return LOG_CRITICAL;
		if (l == 2) return LOG_VERBOSE;
		return LOG_NORMAL;
	}
	LogLevel csvLevel()  { return toLogLevel(getCSVLogLevel()); }
	LogLevel hdf5Level() { return toLogLevel(getHDF5LogLevel()); }

private:
	double time;
	double delta_time;
	double console;
	double file;
	std::string lib;
	std::string outputCfg;
	std::string logLevel;
	std::string csvLogLevel;
	std::string hdf5LogLevel;
	std::string integratorType;
	double aTol;
	double rTol;
	unsigned int mcSeed;
	int mcCaseId;
};

} // namespace sim
} // namespace dsf
