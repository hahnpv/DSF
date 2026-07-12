/**
 * @file test_multisim.cpp
 * @brief Multi-Sim isolation tests (R1 — Sim-owned registries).
 *
 * Pins the bugs retired by giving each Sim its OWN integrand registry and
 * event bus (thread_local "current" context; see R1_SINGLETONS.md):
 *   - loading sim B no longer wipes live sim A's integrands (the old
 *     clear-on-load tradeoff): interleaved stepping matches solo runs
 *   - events registered on sim A never fire (or dangle) from sim B's step
 *   - destroying one sim leaves the other fully functional (ASan-checked
 *     in the sanitizer CI job)
 *   - two sims on two THREADS step concurrently (thread_local isolation)
 *   - the no-Sim fallback registry still serves standalone harnesses
 *
 * Registered by CMake as the `cpp_multisim_tests` ctest.
 */
#include "../DSF/sim/sim.h"
#include "../DSF/sim/block.h"
#include "../DSF/sim/clock.h"
#include "../DSF/sim/event.h"
#include "../DSF/sim/output.h"
#include "../DSF/sim/TClassDict.h"
#include "../DSF/sim/TIntDict.h"

#include <cmath>
#include <iostream>
#include <string>
#include <thread>

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

// Exponential decay y' = -lambda*y — registers its integrand in init()
// through the SAME Instance() call sites real models use.
class Decay : public Block
{
public:
    double y = 1.0, dy = 0.0, lambda = 1.0;
    void init() override
    {
        TClassIntegrandDict<Block>::Instance()->add(
            TClass<Decay, Block>::Instance(), y, dy);
    }
    void update() override { dy = -lambda * y; }
};

struct Rig
{
    Sim* sim;
    Decay* model;
};

static Rig make_sim(double lambda, double dt = 0.01, double tmax = 1e6)
{
    auto* m = new Decay;
    m->lambda = lambda;
    auto* root = new Block;
    root->addChild(m);
    auto* s = new Sim;
    s->load(root, dt, tmax, 0.0, 1e9);
    s->init();
    return {s, m};
}

void test_interleaved_matches_solo()
{
    // Solo baselines
    Rig a1 = make_sim(1.0);
    for (int k = 0; k < 100; k++) a1.sim->step();
    double ya_solo = a1.model->y;

    Rig b1 = make_sim(3.0);
    for (int k = 0; k < 100; k++) b1.sim->step();
    double yb_solo = b1.model->y;

    // Interleaved: loading/stepping B must not perturb A (the old global
    // registry meant B's load() CLEARED A's integrands — A froze).
    Rig a2 = make_sim(1.0);
    Rig b2 = make_sim(3.0);
    for (int k = 0; k < 100; k++) { a2.sim->step(); b2.sim->step(); }

    CHECK(a2.model->y == ya_solo, "interleaved A bit-identical to solo A");
    CHECK(b2.model->y == yb_solo, "interleaved B bit-identical to solo B");
    CHECK(std::fabs(a2.model->y - std::exp(-1.0)) < 1e-6,
          "A integrated correctly (y(1) = e^-1)");
    CHECK(std::fabs(b2.model->y - std::exp(-3.0)) < 1e-6,
          "B integrated correctly (y(1) = e^-3)");
}

void test_event_isolation()
{
    Rig a = make_sim(1.0);
    Rig b = make_sim(1.0);

    // Event on A's state: fire when y <= 0.9.
    bool fired = false;
    Event e;
    e.name = "a_decayed";
    e.condition.type = EventType::STATE_LE;
    e.condition.variable = &a.model->y;
    e.condition.threshold = 0.9;
    e.callback = [&fired]() { fired = true; };
    a.sim->events()->add(e);

    // B steps past the point where A's condition WOULD hold for B's own
    // state — on the old shared bus this evaluated (and fired) A's event.
    for (int k = 0; k < 50; k++) b.sim->step();
    CHECK(!fired, "sim B's steps do not evaluate sim A's events");
    CHECK(a.sim->events()->history().empty(), "A's bus has no fired history yet");

    // A steps: fires on A's own bus.
    for (int k = 0; k < 50; k++) a.sim->step();
    CHECK(fired, "A's event fires from A's own step");
    CHECK(a.sim->events()->history().size() == 1, "exactly one firing recorded on A");
    CHECK(b.sim->events()->history().empty(), "B's bus history untouched");
}

void test_destroy_one_continue_other()
{
    Rig a = make_sim(1.0);
    Rig b = make_sim(2.0);
    for (int k = 0; k < 10; k++) { a.sim->step(); b.sim->step(); }

    // Destroy A entirely (its registry + bus die with it). On the old
    // globals, A's integrand pointers stayed registered → B's next steps
    // integrated freed memory (the ASan job verifies this stays clean).
    delete a.sim;   // (Blocks/model intentionally leak — Sim doesn't own them)

    for (int k = 0; k < 90; k++) b.sim->step();
    CHECK(std::fabs(b.model->y - std::exp(-2.0)) < 1e-6,
          "B unaffected by A's destruction (y(1) = e^-2)");
}

void test_two_threads_concurrent()
{
    double ya = 0.0, yb = 0.0;
    auto worker = [](double lambda, double* out) {
        Rig r = make_sim(lambda);
        for (int k = 0; k < 100; k++) r.sim->step();
        *out = r.model->y;
    };
    std::thread ta(worker, 1.0, &ya);
    std::thread tb(worker, 4.0, &yb);
    ta.join(); tb.join();

    CHECK(std::fabs(ya - std::exp(-1.0)) < 1e-6, "thread A correct (thread_local context)");
    CHECK(std::fabs(yb - std::exp(-4.0)) < 1e-6, "thread B correct (thread_local context)");
}

void test_no_sim_fallback_registry()
{
    // Standalone harnesses (no Sim anywhere) keep working on the fallback.
    CHECK(TClassIntegrandDict<Block>::current() == nullptr,
          "no active Sim context outside lifecycle calls");
    auto* d = TClassIntegrandDict<Block>::Instance();
    CHECK(d != nullptr, "fallback registry exists");
    d->clear();
    double x = 0, dx = 0;
    d->add(TClass<Decay, Block>::Instance(), x, dx);
    CHECK(d->x.size() == 1, "fallback registry accepts registrations");
    d->clear();

    // And a Sim's registrations never leak into the fallback.
    Rig a = make_sim(1.0);
    CHECK(TClassIntegrandDict<Block>::Instance()->x.empty(),
          "Sim registrations land in the Sim, not the fallback");
    CHECK(a.sim->integrands()->x.size() == 1, "Sim owns its one integrand");
}

int main()
{
    // No output files from these sims.
    Output::defaultCSV() = false;
    Output::defaultHDF5() = false;

    test_interleaved_matches_solo();
    test_event_isolation();
    test_destroy_one_continue_other();
    test_two_threads_concurrent();
    test_no_sim_fallback_registry();

    std::cout << "multisim tests: " << tests_passed << " passed, "
              << tests_failed << " failed" << std::endl;
    return tests_failed == 0 ? 0 : 1;
}
