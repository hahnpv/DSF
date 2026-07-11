/**
 * @file test_monte_carlo.cpp
 * @brief Unit tests for the Monte Carlo dispersion engine (monte_carlo.h).
 *
 * Pins the dispersion-honesty contract (ROADMAP R3 / sixdof TRIAGE #23):
 *   - <dispersion> draw attributes transmitted by the Python dispatcher
 *     (n_sigma_draw / drawn) are applied VERBATIM — the value the sim runs
 *     is exactly the value the dispatcher records.
 *   - Without transmitted draws, the engine falls back to its own
 *     case-seeded RNG, deterministically.
 *   - A nominal run (case_id < 0) applies no dispersions.
 *   - Dispatcher-only attributes (workers/output_dir) and all dispersion
 *     attributes are consumed, so an MC deck passes strict validation.
 *
 * Registered by CMake as the `cpp_mc_tests` ctest.
 */
#include "../DSF/sim/block.h"
#include "../DSF/sim/monte_carlo.h"
#include "../DSF/sim/SimMetadata.h"
#include "../DSF/util/xml/xml.h"
#include "../DSF/util/xml/validate.h"

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

// ---------------------------------------------------------------------------
// A minimal dispersible block, registered exactly like a real model
// (factory via TClass, BIND'd properties via the SimMetadata macros).
// ---------------------------------------------------------------------------
class MCTestBlock : public Block
{
public:
    double mass = 0.0;
    double cd = 0.0;
};

DSF_METADATA_START(MCTestBlock, dsf::sim::Block)
DSF_PROPERTY_BIND(mass, mass, "double", "0.0", "test mass")
DSF_PROPERTY_BIND(cd,   cd,   "double", "0.0", "test drag coefficient")

// ---------------------------------------------------------------------------
// Fixture: write a deck to disk (the xml layer parses files), parse it, and
// return the <sim> node. The document must outlive the returned node.
// ---------------------------------------------------------------------------
static const char* DECK_PATH = "mc_test_deck_tmp.xml";

static void write_deck(const std::string& dispersion_attrs_gauss,
                       const std::string& dispersion_attrs_uniform)
{
    std::ofstream f(DECK_PATH);
    f << "<sim dt=\"0.1\" tmax=\"1.0\">\n"
      << "  <monte_carlo n=\"3\" seed=\"99\" workers=\"4\" output_dir=\"mc_out/\">\n"
      << "    <dispersion block=\"body\" property=\"mass\" distribution=\"gaussian\" "
      <<          "sigma=\"5.0\" " << dispersion_attrs_gauss << "/>\n"
      << "    <dispersion block=\"body\" property=\"cd\" distribution=\"uniform\" "
      <<          "min=\"1.0\" max=\"4.0\" " << dispersion_attrs_uniform << "/>\n"
      << "  </monte_carlo>\n"
      << "</sim>\n";
}

// ---------------------------------------------------------------------------
// Parsing: specs, transmitted draws, dispatcher-only attrs
// ---------------------------------------------------------------------------
void test_parse_with_transmitted_draws()
{
    write_deck("n_sigma_draw=\"2.0\"", "drawn=\"3.25\"");
    dsf::xml::xml doc(DECK_PATH);
    doc.parse();
    dsf::xml::xmlnode sim_node = dsf::xml::xmlnode(*doc.xmlRoot).search("sim");

    MonteCarloCase mc = parse_mc_xml(sim_node);
    CHECK(mc.n_cases == 3, "n_cases parsed");
    CHECK(mc.master_seed == 99u, "master seed parsed");
    CHECK(mc.dispersions.size() == 2, "two dispersions parsed");

    const Dispersion& g = mc.dispersions[0];
    CHECK(g.distribution == MCDistribution::GAUSSIAN, "gaussian spec");
    CHECK(g.sigma == 5.0, "sigma parsed");
    CHECK(g.has_draw && g.draw == 2.0, "gaussian n_sigma_draw transmitted");

    const Dispersion& u = mc.dispersions[1];
    CHECK(u.distribution == MCDistribution::UNIFORM, "uniform spec");
    CHECK(u.min_val == 1.0 && u.max_val == 4.0, "min/max parsed");
    CHECK(u.has_draw && u.draw == 3.25, "uniform drawn transmitted");

    // The engine must consume every deck attribute it defines — including the
    // dispatcher-only workers/output_dir — or strict mode rejects MC decks.
    dsf::xml::ValidationReport report = dsf::xml::validate_config(doc);
    for (const auto& x : report.unused) std::cerr << "  unused: " << x << "\n";
    CHECK(report.unused.empty(), "MC deck passes strict validation (no unused attrs)");
}

void test_parse_without_draws()
{
    write_deck("", "");
    dsf::xml::xml doc(DECK_PATH);
    doc.parse();
    MonteCarloCase mc = parse_mc_xml(dsf::xml::xmlnode(*doc.xmlRoot).search("sim"));
    CHECK(!mc.dispersions[0].has_draw, "no gaussian draw transmitted");
    CHECK(!mc.dispersions[1].has_draw, "no uniform draw transmitted");
}

// ---------------------------------------------------------------------------
// Application
// ---------------------------------------------------------------------------
static Block* make_tree(MCTestBlock*& body)
{
    Block* root = new Block;
    body = new MCTestBlock;
    body->setName("body");
    body->mass = 100.0;   // "nominal" as if set by configure()
    body->cd = 2.0;
    root->addChild(body);
    return root;
}

void test_apply_transmitted_draws_verbatim()
{
    write_deck("n_sigma_draw=\"2.0\"", "drawn=\"3.25\"");
    dsf::xml::xml doc(DECK_PATH);
    doc.parse();
    MonteCarloCase mc = parse_mc_xml(dsf::xml::xmlnode(*doc.xmlRoot).search("sim"));
    mc.case_id = 0;
    mc.case_seed = 12345;

    MCTestBlock* body = nullptr;
    Block* root = make_tree(body);
    apply_dispersions(root, mc);

    CHECK(body->mass == 100.0 + 2.0 * 5.0,
          "gaussian applied as nominal + n_sigma*sigma exactly");
    CHECK(body->cd == 3.25, "uniform applied verbatim");
    CHECK(mc.dispersions[0].n_sigma == 2.0, "reported n_sigma is the transmitted draw");
    CHECK(mc.dispersions[0].nominal == 100.0, "nominal captured before overwrite");
}

void test_apply_rng_fallback_deterministic()
{
    write_deck("", "");
    dsf::xml::xml doc(DECK_PATH);
    doc.parse();
    MonteCarloCase mc = parse_mc_xml(dsf::xml::xmlnode(*doc.xmlRoot).search("sim"));
    mc.case_id = 1;
    mc.case_seed = 777;

    MCTestBlock* b1 = nullptr;
    apply_dispersions(make_tree(b1), mc);
    double mass1 = b1->mass, cd1 = b1->cd;

    MonteCarloCase mc2 = parse_mc_xml(dsf::xml::xmlnode(*doc.xmlRoot).search("sim"));
    mc2.case_id = 1;
    mc2.case_seed = 777;
    MCTestBlock* b2 = nullptr;
    apply_dispersions(make_tree(b2), mc2);

    CHECK(mass1 == b2->mass && cd1 == b2->cd,
          "same case_seed reproduces the same fallback draws");
    CHECK(cd1 >= 1.0 && cd1 <= 4.0, "uniform fallback draw within [min,max]");
}

void test_nominal_run_is_untouched()
{
    write_deck("n_sigma_draw=\"2.0\"", "drawn=\"3.25\"");
    dsf::xml::xml doc(DECK_PATH);
    doc.parse();
    MonteCarloCase mc = parse_mc_xml(dsf::xml::xmlnode(*doc.xmlRoot).search("sim"));
    // case_id stays -1: nominal
    CHECK(!mc.is_mc(), "case_id=-1 is not an MC case");

    MCTestBlock* body = nullptr;
    apply_dispersions(make_tree(body), mc);
    CHECK(body->mass == 100.0 && body->cd == 2.0, "nominal run applies nothing");
}

int main()
{
    test_parse_with_transmitted_draws();
    test_parse_without_draws();
    test_apply_transmitted_draws_verbatim();
    test_apply_rng_fallback_deterministic();
    test_nominal_run_is_untouched();

    std::remove(DECK_PATH);
    std::cout << "monte_carlo tests: " << tests_passed << " passed, "
              << tests_failed << " failed" << std::endl;
    return tests_failed == 0 ? 0 : 1;
}
