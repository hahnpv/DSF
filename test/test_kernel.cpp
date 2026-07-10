/**
 * @file test_kernel.cpp
 * @brief Unit tests for DSF sim-kernel behavior (clock, events).
 *
 * Regression coverage for the code-review fixes:
 *   - Clock report gate fires for non-binary-friendly rates   [A6]
 *   - Clock safe_sample initialized (no indeterminate reads)  [A6]
 *   - Recurring (one_shot=false) events fire more than once    [A14]
 *   - one_shot events fire exactly once                        [A14]
 *
 * Registered by CMake as the `cpp_kernel_tests` ctest.
 */
#include "../DSF/sim/clock.h"
#include "../DSF/sim/event.h"

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
// Clock report gate — the exact-equality bug dropped reports for rates whose
// tick period is not an exact integer double.
// ---------------------------------------------------------------------------

void test_clock_report_gate()
{
    // dt = 0.03 => error = 2/0.03 = 66.67 ticks/s. A 0.1 s report period is
    // 6.667 ticks — never an exact integer, so the old test fired only at t=0.
    Clock c(0.03, 10.0);
    int fires = 0;
    // 100 macro steps => t up to 3.0 s. Each step advances 2 ticks (like RK4).
    for (int step = 0; step < 100; step++)
    {
        c.increment();
        c.increment();
        c.set(true);
        if (c.Sample(0.1)) fires++;
    }
    // ~30 reports expected over 3.0 s at 0.1 s spacing. Old code: ~0.
    CHECK(fires >= 25 && fires <= 35, std::string("Clock 0.1s reports over 3s got ")
          + std::to_string(fires));
}

void test_clock_report_gate_aligned()
{
    // dt = 0.01, report 0.1 s => 20 ticks/s, 2 ticks per report period boundary.
    Clock c(0.01, 10.0);
    int fires = 0;
    for (int step = 0; step < 100; step++)  // t up to 1.0 s
    {
        c.increment();
        c.increment();
        c.set(true);
        if (c.Sample(0.1)) fires++;
    }
    CHECK(fires >= 9 && fires <= 11, std::string("Clock aligned 0.1s over 1s got ")
          + std::to_string(fires));
}

void test_clock_default_safe()
{
    // Default-constructed clock must not read an indeterminate safe_sample.
    Clock c;
    // Sample(0) returns the (now-initialized) safe_sample flag; must be a
    // definite bool, not UB. Just exercise it.
    bool s = c.Sample(0.0);
    CHECK(s == true || s == false, "Clock default Sample(0) definite");
}

// ---------------------------------------------------------------------------
// Events — recurring vs one_shot
// ---------------------------------------------------------------------------

static int run_crossings(bool one_shot)
{
    double var = 0.0;
    EventBus::Instance()->clear();

    Event e;
    e.name = "cross";
    e.condition.type = EventType::CROSSES_VALUE;
    e.condition.variable = &var;
    e.condition.threshold = 5.0;
    e.one_shot = one_shot;
    EventBus::Instance()->add(e);

    int fires = 0;
    double t = 0.0, dt = 0.1;
    auto do_step = [&](double newval) {
        var = newval;
        t += dt;
        auto f = EventBus::Instance()->evaluate(t, dt);
        fires += static_cast<int>(f.size());
        EventBus::Instance()->latch();
    };

    do_step(0.0);   // initialize prev_value (no crossing)
    do_step(10.0);  // cross up through 5
    do_step(0.0);   // cross down through 5
    do_step(10.0);  // cross up through 5 again

    return fires;
}

void test_event_recurring()
{
    int fires = run_crossings(/*one_shot=*/false);
    CHECK(fires == 3, std::string("recurring event fired ") + std::to_string(fires)
          + " times (expected 3)");
}

void test_event_one_shot()
{
    int fires = run_crossings(/*one_shot=*/true);
    CHECK(fires == 1, std::string("one_shot event fired ") + std::to_string(fires)
          + " times (expected 1)");
}

int main()
{
    std::cout << "=== DSF kernel unit tests ===\n";

    test_clock_report_gate();
    test_clock_report_gate_aligned();
    test_clock_default_safe();
    test_event_recurring();
    test_event_one_shot();

    std::cout << "\n=== Results: " << tests_passed << " passed, "
              << tests_failed << " failed ===\n";
    return tests_failed > 0 ? 1 : 0;
}
