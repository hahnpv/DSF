/**
 * @file test_tablend.cpp
 * @brief Unit tests for the TableND N-dimensional interpolation class.
 *
 * Compile and run:
 *   cd build && cmake --build . -j$(nproc)
 *   ./test_tablend
 */
#include "../DSF/util/tbl/tablend.h"
#include <iostream>
#include <cmath>
#include <cassert>
#include <fstream>

using dsf::util::TableND;

static int tests_passed = 0;
static int tests_failed = 0;

#define CHECK(cond, msg) \
    do { \
        if (!(cond)) { \
            std::cerr << "FAIL: " << msg << " (line " << __LINE__ << ")" << std::endl; \
            tests_failed++; \
        } else { \
            tests_passed++; \
        } \
    } while(0)

#define CHECK_NEAR(val, expected, tol, msg) \
    CHECK(std::fabs((val) - (expected)) < (tol), \
          std::string(msg) + " got=" + std::to_string(val) + " expected=" + std::to_string(expected))

// ============================================================================
// 1D Tests
// ============================================================================

void test_1d_basic()
{
    std::vector<double> x = {0, 1, 2, 3};
    std::vector<double> y = {0, 10, 30, 60};
    TableND t(x, y);

    CHECK(t.ndim() == 1, "1D ndim");
    CHECK(t.axis_size(0) == 4, "1D axis_size");
    CHECK(t.size() == 4, "1D data size");

    // Exact breakpoints
    CHECK_NEAR(t.interp(0.0), 0.0, 1e-10, "1D exact x=0");
    CHECK_NEAR(t.interp(1.0), 10.0, 1e-10, "1D exact x=1");
    CHECK_NEAR(t.interp(2.0), 30.0, 1e-10, "1D exact x=2");
    CHECK_NEAR(t.interp(3.0), 60.0, 1e-10, "1D exact x=3");

    // Midpoint interpolation
    CHECK_NEAR(t.interp(0.5), 5.0, 1e-10, "1D mid x=0.5");
    CHECK_NEAR(t.interp(1.5), 20.0, 1e-10, "1D mid x=1.5");
    CHECK_NEAR(t.interp(2.5), 45.0, 1e-10, "1D mid x=2.5");

    // Operator()
    CHECK_NEAR(t(1.5), 20.0, 1e-10, "1D operator()");
}

void test_1d_clamp()
{
    TableND t({0, 1, 2}, {10, 20, 30});

    // Below range — clamp to first value
    CHECK_NEAR(t.interp(-1.0), 10.0, 1e-10, "1D clamp below");
    CHECK_NEAR(t.interp(-100.0), 10.0, 1e-10, "1D clamp far below");

    // Above range — clamp to last value
    CHECK_NEAR(t.interp(3.0), 30.0, 1e-10, "1D clamp above");
    CHECK_NEAR(t.interp(100.0), 30.0, 1e-10, "1D clamp far above");
}

void test_1d_linear_extrap()
{
    TableND t({0, 1, 2}, {10, 20, 30});
    t.set_extrap(TableND::Extrap::LINEAR);

    // Below: extrapolate with slope of first segment (10/1 = 10)
    CHECK_NEAR(t.interp(-1.0), 0.0, 1e-10, "1D linear extrap below");

    // Above: extrapolate with slope of last segment (10/1 = 10)
    CHECK_NEAR(t.interp(3.0), 40.0, 1e-10, "1D linear extrap above");
}

void test_1d_single_point()
{
    std::vector<double> xb = {5.0};
    std::vector<double> yb = {42.0};
    TableND t(xb, yb);
    CHECK_NEAR(t.interp(5.0), 42.0, 1e-10, "1D single point exact");
    CHECK_NEAR(t.interp(0.0), 42.0, 1e-10, "1D single point below");
    CHECK_NEAR(t.interp(99.0), 42.0, 1e-10, "1D single point above");
}

// ============================================================================
// 2D Tests
// ============================================================================

void test_2d_basic()
{
    // Simple 3x3 grid: f(x,y) = x + y
    std::vector<double> x = {0, 1, 2};
    std::vector<double> y = {0, 10, 20};
    std::vector<std::vector<double>> grid = {
        {0, 10, 20},   // x=0: f = y
        {1, 11, 21},   // x=1: f = 1+y
        {2, 12, 22}    // x=2: f = 2+y
    };
    TableND t(x, y, grid);

    CHECK(t.ndim() == 2, "2D ndim");
    CHECK(t.size() == 9, "2D data size");

    // Corner values
    CHECK_NEAR(t.interp(0.0, 0.0), 0.0, 1e-10, "2D corner (0,0)");
    CHECK_NEAR(t.interp(2.0, 20.0), 22.0, 1e-10, "2D corner (2,20)");
    CHECK_NEAR(t.interp(0.0, 20.0), 20.0, 1e-10, "2D corner (0,20)");
    CHECK_NEAR(t.interp(2.0, 0.0), 2.0, 1e-10, "2D corner (2,0)");

    // Center
    CHECK_NEAR(t.interp(1.0, 10.0), 11.0, 1e-10, "2D center (1,10)");

    // Interpolated midpoint
    CHECK_NEAR(t.interp(0.5, 5.0), 5.5, 1e-10, "2D mid (0.5,5)");
}

void test_2d_asymmetric()
{
    // f(alpha, dht) — 2x3 grid
    std::vector<double> alpha = {0.0, 0.5};
    std::vector<double> dht = {-1.0, 0.0, 1.0};
    std::vector<std::vector<double>> grid = {
        {100, 200, 300},   // alpha=0
        {110, 220, 330}    // alpha=0.5
    };
    TableND t(alpha, dht, grid);

    // Exact corners
    CHECK_NEAR(t.interp(0.0, -1.0), 100.0, 1e-10, "2D asym (0,-1)");
    CHECK_NEAR(t.interp(0.5, 1.0), 330.0, 1e-10, "2D asym (0.5,1)");

    // Mid alpha, exact dht
    CHECK_NEAR(t.interp(0.25, 0.0), 210.0, 1e-10, "2D asym mid-alpha");
}

// ============================================================================
// 3D Tests
// ============================================================================

void test_3d_basic()
{
    // f(x,y,z) = x + 10*y + 100*z on a 2x2x2 grid
    std::vector<double> x = {0, 1};
    std::vector<double> y = {0, 1};
    std::vector<double> z = {0, 1};

    // Flat data in row-major order (last axis fastest):
    // (0,0,0)=0, (0,0,1)=100, (0,1,0)=10, (0,1,1)=110,
    // (1,0,0)=1, (1,0,1)=101, (1,1,0)=11, (1,1,1)=111
    std::vector<double> data = {0, 100, 10, 110, 1, 101, 11, 111};

    TableND t({x, y, z}, data);

    CHECK(t.ndim() == 3, "3D ndim");
    CHECK(t.size() == 8, "3D data size");

    // Exact corners
    CHECK_NEAR(t.interp(0, 0, 0), 0.0, 1e-10, "3D (0,0,0)");
    CHECK_NEAR(t.interp(1, 1, 1), 111.0, 1e-10, "3D (1,1,1)");
    CHECK_NEAR(t.interp(0, 0, 1), 100.0, 1e-10, "3D (0,0,1)");
    CHECK_NEAR(t.interp(1, 0, 0), 1.0, 1e-10, "3D (1,0,0)");

    // Center: f(0.5, 0.5, 0.5) = 0.5 + 5 + 50 = 55.5
    CHECK_NEAR(t.interp(0.5, 0.5, 0.5), 55.5, 1e-10, "3D center");

    // Edge midpoints
    CHECK_NEAR(t.interp(0.5, 0.0, 0.0), 0.5, 1e-10, "3D x-mid");
    CHECK_NEAR(t.interp(0.0, 0.5, 0.0), 5.0, 1e-10, "3D y-mid");
    CHECK_NEAR(t.interp(0.0, 0.0, 0.5), 50.0, 1e-10, "3D z-mid");

    // Template variant
    std::array<double, 3> pt = {0.5, 0.5, 0.5};
    CHECK_NEAR(t.interp(pt), 55.5, 1e-10, "3D template interp");
}

// ============================================================================
// CSV loading
// ============================================================================

void test_csv_from_columns()
{
    // Write a temp CSV
    const char* path = "/tmp/test_tablend_csv.csv";
    {
        std::ofstream f(path);
        f << "time,gamma,alpha,throttle\n";
        f << "0.0,1.5708,0.01,1.0\n";
        f << "10.0,1.2,0.02,0.9\n";
        f << "20.0,0.8,0.03,0.8\n";
        f << "30.0,0.5,0.04,0.0\n";
    }

    TableND t = TableND::fromCSV(path, "time", "gamma");

    CHECK(t.ndim() == 1, "CSV ndim");
    CHECK(t.axis_size(0) == 4, "CSV axis_size");

    CHECK_NEAR(t.interp(0.0), 1.5708, 1e-4, "CSV t=0");
    CHECK_NEAR(t.interp(30.0), 0.5, 1e-4, "CSV t=30");
    CHECK_NEAR(t.interp(15.0), 1.0, 1e-4, "CSV t=15 (midpoint)");
}

void test_tablend_csv_format()
{
    // Write a 2D table in the TableND CSV format
    const char* path = "/tmp/test_tablend_2d.csv";
    {
        std::ofstream f(path);
        f << "# TableND: test_func\n";
        f << "# axes: x, y\n";
        f << "# x: 0, 1, 2\n";
        f << "# y: 0, 10\n";
        f << "0, 10\n";
        f << "1, 11\n";
        f << "2, 12\n";
    }

    TableND t(path);

    CHECK(t.ndim() == 2, "TableND CSV ndim");
    CHECK(t.axis_size(0) == 3, "TableND CSV x size");
    CHECK(t.axis_size(1) == 2, "TableND CSV y size");

    CHECK_NEAR(t.interp(0.0, 0.0), 0.0, 1e-10, "TableND CSV (0,0)");
    CHECK_NEAR(t.interp(2.0, 10.0), 12.0, 1e-10, "TableND CSV (2,10)");
    CHECK_NEAR(t.interp(1.0, 5.0), 6.0, 1e-10, "TableND CSV (1,5) mid");
}

// Fixture directory, injected by CMake as the test/ source dir so the test
// runs from any build location (local, CI, ASan builds).
#ifndef TEST_DATA_DIR
#define TEST_DATA_DIR "."
#endif

void test_legacy_format()
{
    // Use the existing test file
    const std::string path = std::string(TEST_DATA_DIR) + "/table_1d.txt";
    TableND t(path.c_str());

    CHECK(t.ndim() == 1, "Legacy ndim");
    if (t.ndim() != 1) return;   // file missing/unparsed — don't index into nothing
    CHECK(t.axis_size(0) == 4, "Legacy axis_size");

    CHECK_NEAR(t.interp(0.0), 0.0, 1e-10, "Legacy x=0");
    CHECK_NEAR(t.interp(3.0), 30.0, 1e-10, "Legacy x=3");
    CHECK_NEAR(t.interp(1.5), 15.0, 1e-10, "Legacy x=1.5");
}

// ============================================================================
// Stress / edge cases
// ============================================================================

void test_2_point_table()
{
    TableND t({0, 1}, {100, 200});
    CHECK_NEAR(t.interp(0.0), 100.0, 1e-10, "2pt x=0");
    CHECK_NEAR(t.interp(1.0), 200.0, 1e-10, "2pt x=1");
    CHECK_NEAR(t.interp(0.5), 150.0, 1e-10, "2pt x=0.5");
    CHECK_NEAR(t.interp(-1.0), 100.0, 1e-10, "2pt clamp below");
    CHECK_NEAR(t.interp(2.0), 200.0, 1e-10, "2pt clamp above");
}

void test_vector_interp()
{
    TableND t({0, 1, 2}, {0, 10, 30});
    std::vector<double> pt = {1.5};
    CHECK_NEAR(t.interp(pt), 20.0, 1e-10, "vector interp 1D");
}

// ============================================================================
// Grid convergence (code verification)
// ============================================================================
//
// The tests above use data that linear interpolation reproduces EXACTLY, so
// they cannot see a weighting defect that stays exact at nodes and midpoints
// (e.g. a smoothstepped fraction). Sampling a curved analytic function pins
// the order of accuracy: linear interpolation error is ~h²/8·|f''|, so
// halving the grid spacing must cut the max error ~4x.

void test_1d_grid_convergence()
{
    // f(x) = sin(x) on [0, pi]; max|f''| = 1.
    auto max_err = [](int n) {
        std::vector<double> x(n), y(n);
        for (int i = 0; i < n; i++) {
            x[i] = M_PI * i / (n - 1);
            y[i] = std::sin(x[i]);
        }
        TableND t(x, y);
        double e = 0.0;
        for (int k = 0; k <= 400; k++) {
            double p = M_PI * k / 400.0;
            e = std::max(e, std::fabs(t.interp(p) - std::sin(p)));
        }
        return e;
    };
    double h  = M_PI / 8.0;
    double e1 = max_err(9);      // spacing h
    double e2 = max_err(17);     // spacing h/2
    CHECK(e1 < 0.3 * h * h,      // theory: e1 ~ h²/8 ≈ 0.019
          std::string("1D interp error magnitude ~h^2/8, got ") + std::to_string(e1));
    double ratio = e1 / (e2 + 1e-300);
    CHECK(ratio > 3.2 && ratio < 4.8,
          std::string("1D interp error ratio (h halved) ~4, got ") + std::to_string(ratio));
}

void test_2d_grid_convergence()
{
    // f(x,y) = sin(x)·cos(y) on [0, pi]²; bilinear error ~(h²/8)(|fxx|+|fyy|).
    auto max_err = [](int n) {
        std::vector<double> ax(n);
        for (int i = 0; i < n; i++)
            ax[i] = M_PI * i / (n - 1);
        std::vector<std::vector<double>> grid(n, std::vector<double>(n));
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++)
                grid[i][j] = std::sin(ax[i]) * std::cos(ax[j]);
        TableND t(ax, ax, grid);
        double e = 0.0;
        for (int ki = 0; ki <= 100; ki++)
            for (int kj = 0; kj <= 100; kj++) {
                double px = M_PI * ki / 100.0;
                double py = M_PI * kj / 100.0;
                e = std::max(e, std::fabs(t.interp(px, py)
                                          - std::sin(px) * std::cos(py)));
            }
        return e;
    };
    double h  = M_PI / 8.0;
    double e1 = max_err(9);      // spacing h
    double e2 = max_err(17);     // spacing h/2
    CHECK(e1 < 0.6 * h * h,      // theory: e1 ~ h²/4 ≈ 0.039
          std::string("2D interp error magnitude ~h^2/4, got ") + std::to_string(e1));
    double ratio = e1 / (e2 + 1e-300);
    CHECK(ratio > 3.2 && ratio < 4.8,
          std::string("2D interp error ratio (h halved) ~4, got ") + std::to_string(ratio));
}

// ============================================================================
// Main
// ============================================================================

int main()
{
    std::cout << "=== TableND Unit Tests ===" << std::endl;

    test_1d_basic();
    test_1d_clamp();
    test_1d_linear_extrap();
    test_1d_single_point();
    test_2d_basic();
    test_2d_asymmetric();
    test_3d_basic();
    test_csv_from_columns();
    test_tablend_csv_format();
    test_legacy_format();
    test_2_point_table();
    test_vector_interp();
    test_1d_grid_convergence();
    test_2d_grid_convergence();

    std::cout << "\n=== Results: " << tests_passed << " passed, "
              << tests_failed << " failed ===" << std::endl;

    return tests_failed > 0 ? 1 : 0;
}
