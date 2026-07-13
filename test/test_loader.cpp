/**
 * @file test_loader.cpp
 * @brief Unit tests for the shared deck loader (SimInput + sim_loader.h).
 *
 * Both the `dynamic` executable and `dsf run` (via bindings) call exactly
 * this code — these tests pin the behaviors that used to drift between the
 * two loaders (R8 / LOADER_CONSOLIDATION.md):
 *   - <sim> attribute parsing incl. string log levels and MC case identity
 *   - the UNIFIED class-name fallback rule (capitalized tag; name= honored)
 *   - unknown class → exception (not a null-deref later)
 *   - strict-mode resolution (deck opt-out + CLI opt-out)
 *
 * Registered by CMake as the `cpp_loader_tests` ctest.
 */
#include "../DSF/sim/block.h"
#include "../DSF/sim/SimInput.h"
#include "../DSF/sim/sim_loader.h"
#include "../DSF/util/xml/xml.h"

#include <cstdio>
#include <fstream>
#include <iostream>
#include <string>

using namespace dsf::sim;

static int tests_passed = 0;
static int tests_failed = 0;

#define CHECK(cond, msg)                                                        \
    do {                                                                        \
        if (!(cond)) {                                                          \
            std::cerr << "FAIL: " << msg << " (line " << __LINE__ << ")\n";     \
            tests_failed++;                                                     \
        } else { tests_passed++; }                                             \
    } while (0)

// A registered test model, as a model library would provide.
class LoaderProbe : public Block
{
public:
    double gain = 0.0;
    void configure(dsf::xml::xmlnode n) override
    {
        if (n.findAttr("gain")) gain = n.attrAsDouble("gain");
    }
};
static bool _reg = (TClass<LoaderProbe, Block>::Instance(), true);

static const char* DECK = "/tmp/dsf_test_loader.xml";

static dsf::xml::xml* parse(const std::string& body)
{
    { std::ofstream f(DECK); f << body; }
    auto* doc = new dsf::xml::xml(DECK);
    doc->parse();
    return doc;
}

void test_siminput_parsing()
{
    auto* doc = parse(
        "<sim dt=\"0.05\" tmax=\"12\" console=\"1\" file=\"0.5\" "
        "library=\"libx.so\" output=\"csv,hdf5\" "
        "log_level=\"critical\" hdf5_log_level=\"verbose\" "
        "integrator=\"RK45\" atol=\"1e-9\" rtol=\"1e-5\" "
        "seed=\"77\" case_id=\"3\"/>");
    SimInput in(dsf::xml::xmlnode(*doc->xmlRoot).search("sim"));

    CHECK(in.dt() == 0.05 && in.tmax() == 12.0, "dt/tmax parsed");
    CHECK(in.rateConsole() == 1.0 && in.rateFile() == 0.5, "rates parsed");
    CHECK(in.library() == "libx.so", "library parsed");
    CHECK(in.isCSV() && in.isHDF5(), "output policy parsed");
    CHECK(in.integrator() == "RK45", "integrator parsed");
    CHECK(in.atol() == 1e-9 && in.rtol() == 1e-5, "tolerances parsed");
    CHECK(in.seed() == 77u && in.caseId() == 3, "MC case identity parsed");
    // Log levels: specific attr wins, else global, string names (the deck
    // convention) — run.py used to reimplement this mapping.
    CHECK(in.csvLevel() == LOG_CRITICAL, "csv level falls back to global 'critical'");
    CHECK(in.hdf5Level() == LOG_VERBOSE, "hdf5 level from specific 'verbose'");
    delete doc;
}

void test_siminput_defaults()
{
    auto* doc = parse("<sim dt=\"0.1\" tmax=\"1\"/>");
    SimInput in(dsf::xml::xmlnode(*doc->xmlRoot).search("sim"));
    CHECK(in.isCSV() && !in.isHDF5(), "default output: CSV only");
    CHECK(in.atol() == 1e-8 && in.rtol() == 1e-6, "default tolerances");
    CHECK(in.caseId() == -1 && in.seed() == 0u, "default: nominal run");
    CHECK(in.csvLevel() == LOG_NORMAL, "default log level normal");
    delete doc;
}

void test_build_tree_fallback_rule()
{
    // The UNIFIED rule: class= wins; else capitalized tag; name= overrides id.
    auto* doc = parse(
        "<sim dt=\"0.1\" tmax=\"1\">"
        "<block id=\"A\" class=\"LoaderProbe\" gain=\"2\"/>"
        "<loaderProbe id=\"B\"/>"                        // tag → "LoaderProbe"
        "<block id=\"C\" class=\"LoaderProbe\" name=\"Custom\"/>"
        "<events/>"                                       // no id → skipped
        "</sim>");
    dsf::xml::xmlnode n = dsf::xml::xmlnode(*doc->xmlRoot).search("sim");

    Block* root = build_tree(n);
    auto kids = root->getChildren();
    CHECK(kids.size() == 3, "three blocks built, <events> skipped");
    CHECK(kids[0]->getName() == "A", "id used as name");
    CHECK(dynamic_cast<LoaderProbe*>(kids[0]) != nullptr, "class= instantiated");
    CHECK(dynamic_cast<LoaderProbe*>(kids[0])->gain == 2.0, "configure() ran");
    CHECK(dynamic_cast<LoaderProbe*>(kids[1]) != nullptr,
          "capitalized-tag fallback instantiated (loaderProbe → LoaderProbe)");
    CHECK(kids[2]->getName() == "Custom", "name= overrides id");
    for (Block* k : kids) delete k;   // ~Block doesn't delete children
    delete root;
    delete doc;
}

void test_build_tree_unknown_class_throws()
{
    auto* doc = parse(
        "<sim dt=\"0.1\" tmax=\"1\"><block id=\"X\" class=\"NoSuchModel\"/></sim>");
    dsf::xml::xmlnode n = dsf::xml::xmlnode(*doc->xmlRoot).search("sim");
    bool threw = false;
    try { build_tree(n); }
    catch (const std::runtime_error& e) {
        threw = std::string(e.what()).find("NoSuchModel") != std::string::npos;
    }
    CHECK(threw, "unknown class throws with the class name in the message");
    delete doc;
}

void test_resolve_strict()
{
    auto* strict_doc = parse("<sim dt=\"0.1\" tmax=\"1\"/>");
    dsf::xml::xmlnode n1 = dsf::xml::xmlnode(*strict_doc->xmlRoot).search("sim");
    CHECK(resolve_strict(n1, false) == true,  "strict is the default");
    CHECK(resolve_strict(n1, true)  == false, "CLI --not-strict opts out");
    delete strict_doc;

    auto* lax_doc = parse("<sim dt=\"0.1\" tmax=\"1\" strict=\"false\"/>");
    dsf::xml::xmlnode n2 = dsf::xml::xmlnode(*lax_doc->xmlRoot).search("sim");
    CHECK(resolve_strict(n2, false) == false, "deck strict=\"false\" opts out");
    delete lax_doc;
}

void test_load_model_library_errors()
{
    bool threw = false;
    try { load_model_library("libdoes_not_exist_dsf.so", "/tmp"); }
    catch (const std::runtime_error&) { threw = true; }
    CHECK(threw, "missing library throws instead of silently continuing");
    load_model_library("");   // empty = statically linked models: no-op
    CHECK(true, "empty library path is a no-op");
}

int main()
{
    test_siminput_parsing();
    test_siminput_defaults();
    test_build_tree_fallback_rule();
    test_build_tree_unknown_class_throws();
    test_resolve_strict();
    test_load_model_library_errors();

    std::remove(DECK);
    std::cout << "loader tests: " << tests_passed << " passed, "
              << tests_failed << " failed" << std::endl;
    return tests_failed == 0 ? 0 : 1;
}
