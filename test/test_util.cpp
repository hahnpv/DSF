/**
 * @file test_util.cpp
 * @brief Unit tests for the DSF C++ utility layer (tables + math).
 *
 * Regression coverage for the code-review fixes:
 *   - Table  1D interpolation (last-panel / small-table bug)   [A2]
 *   - Table2d below-range read (heap overflow)                 [A3]
 *   - Mat4  det/inv/transpose (were empty stubs)               [A5]
 *   - Vec3  component-wise equality / ordering                 [A18]
 *   - math constants precision (PI, RAD, J2)                   [A20]
 *   - Vec3/Mat3 singularity + out-of-range guards
 *   - XML value parsing (Vec3/Mat3/bool attr forms)            [A24/A46]
 *   - factory instantiation by class-name string               [A46]
 *
 * Built and registered by CMake as the `cpp_util_tests` ctest.
 */
#include "../DSF/sim/block.h"
#include "../DSF/sim/TRefDict.h"
#include "../DSF/util/config_errors.h"
#include "../DSF/util/xml/xml.h"
#include "../DSF/util/xml/validate.h"
#include "../DSF/util/tbl/tbl.h"
#include "../DSF/util/tbl/tbl2d.h"
#include "../DSF/util/tbl/tablend.h"
#include "../DSF/util/math/vec3.h"
#include "../DSF/util/math/mat3.h"
#include "../DSF/util/math/mat4.h"
#include "../DSF/util/math/quat.h"
#include "../DSF/util/math/constants.h"
#include "../DSF/util/math/earth_constants.h"

#include <iostream>
#include <fstream>
#include <cmath>
#include <string>

using namespace dsf::util;

static int tests_passed = 0;
static int tests_failed = 0;

#define CHECK(cond, msg)                                                        \
    do {                                                                        \
        if (!(cond)) {                                                          \
            std::cerr << "FAIL: " << msg << " (line " << __LINE__ << ")\n";     \
            tests_failed++;                                                     \
        } else { tests_passed++; }                                             \
    } while (0)

#define CHECK_NEAR(val, expected, tol, msg)                                     \
    CHECK(std::fabs((val) - (expected)) < (tol),                                \
          std::string(msg) + " got=" + std::to_string(val) +                    \
          " expected=" + std::to_string(expected))

// ---------------------------------------------------------------------------
// Table (legacy 1D) — the last-panel / small-table interpolation bug
// ---------------------------------------------------------------------------

static std::string write_legacy_1d()
{
    const char* path = "/tmp/dsf_test_tbl_1d.txt";
    std::ofstream f(path);
    f << "T1\n4\nX\tY\n0\t0\n1\t10\n2\t20\n3\t30\n";
    return path;
}

void test_table_1d()
{
    Table t(write_legacy_1d(), "T1");

    // Exact breakpoints
    CHECK_NEAR(t.interp(0.0), 0.0, 1e-9, "Table exact x=0");
    CHECK_NEAR(t.interp(3.0), 30.0, 1e-9, "Table exact x=3");

    // Interior panels — the regression: last panel used to return a constant
    CHECK_NEAR(t.interp(0.5), 5.0, 1e-9, "Table mid first panel");
    CHECK_NEAR(t.interp(1.5), 15.0, 1e-9, "Table mid middle panel");
    CHECK_NEAR(t.interp(2.5), 25.0, 1e-9, "Table mid LAST panel (was 20)");
    CHECK_NEAR(t.interp(2.999), 29.99, 1e-6, "Table near-top of last panel");

    // Clamping outside range
    CHECK_NEAR(t.interp(-5.0), 0.0, 1e-9, "Table clamp below");
    CHECK_NEAR(t.interp(99.0), 30.0, 1e-9, "Table clamp above");
}

void test_table_2point()
{
    const char* path = "/tmp/dsf_test_tbl_2pt.txt";
    { std::ofstream f(path); f << "T2\n2\nX\tY\n0\t0\n1\t10\n"; }
    Table t(path, "T2");
    // 2-point tables used to return the low value for every interior query.
    CHECK_NEAR(t.interp(0.5), 5.0, 1e-9, "Table 2pt interior (was 0)");
    CHECK_NEAR(t.interp(0.25), 2.5, 1e-9, "Table 2pt quarter");
}

void test_table_missing_file()
{
    // Missing file must not hang (no cin) and must not crash on interp —
    // and must be recorded for config validation (strict mode, H6) so a sim
    // can't quietly fly with an all-zero table.
    dsf::util::config_errors().clear();
    Table t("/tmp/dsf_no_such_table_file.txt", "Nope");
    CHECK_NEAR(t.interp(1.0), 0.0, 1e-9, "Table missing-file interp safe");
    CHECK(dsf::util::config_errors().size() == 1,
          "Table missing-file recorded in config_errors");

    TableND tn("/tmp/dsf_no_such_tablend_file.txt");
    CHECK(dsf::util::config_errors().size() == 2,
          "TableND missing-file recorded in config_errors");
    dsf::util::config_errors().clear();
}

// ---------------------------------------------------------------------------
// Table2d — below-range read (heap overflow regression)
// ---------------------------------------------------------------------------

static std::string write_2d()
{
    const char* path = "/tmp/dsf_test_tbl_2d.txt";
    std::ofstream f(path);
    f << "n=0\nX Y Z\n0, 0, 0\n1, 10, 100\n2, 20, 200\n3, 30, 300\n";
    return path;
}

void test_table2d()
{
    Table2d t(write_2d());

    // Column interpolation
    CHECK_NEAR(t.interp(2.5, 1), 25.0, 1e-9, "Table2d col1 mid last panel");
    CHECK_NEAR(t.interp(2.5, 2), 250.0, 1e-9, "Table2d col2 mid last panel");

    // Below range — used to read table[-1]
    CHECK_NEAR(t.interp(-5.0, 1), 0.0, 1e-9, "Table2d below-range col1 (was OOB)");
    CHECK_NEAR(t.interp(-5.0, 2), 0.0, 1e-9, "Table2d below-range col2 (was OOB)");

    // Above range — clamp
    CHECK_NEAR(t.interp(99.0, 1), 30.0, 1e-9, "Table2d above-range col1");
}

void test_table2d_bilinear()
{
    // f(r,c) = r + c on a 2x2 grid
    Table2d t({0.0, 1.0}, {0.0, 10.0}, {{0.0, 10.0}, {1.0, 11.0}});
    CHECK_NEAR(t.interp(0.0, 0.0), 0.0, 1e-9, "bilinear corner");
    CHECK_NEAR(t.interp(1.0, 10.0), 11.0, 1e-9, "bilinear far corner");
    CHECK_NEAR(t.interp(0.5, 5.0), 5.5, 1e-9, "bilinear center");
}

// ---------------------------------------------------------------------------
// TableND — high-dim (>8) and single-point axis (were OOB)
// ---------------------------------------------------------------------------

void test_tablend_high_dim()
{
    // 9 axes, each with 2 points; f = sum of coordinates.
    std::vector<std::vector<double>> axes(9, std::vector<double>{0.0, 1.0});
    int n = 1 << 9; // 512 corners
    std::vector<double> data(n);
    for (int i = 0; i < n; i++)
    {
        int s = 0;
        for (int d = 0; d < 9; d++) s += (i >> (9 - 1 - d)) & 1;
        data[i] = s;
    }
    TableND t(axes, data);
    CHECK(t.ndim() == 9, "9D ndim");
    std::vector<double> mid(9, 0.5);
    CHECK_NEAR(t.interp(mid), 4.5, 1e-9, "9D center (was stack overflow)");
}

void test_tablend_single_point_axis()
{
    // 2D table with a degenerate single-point second axis.
    TableND t({{0.0, 1.0}, {5.0}}, {10.0, 20.0});
    CHECK_NEAR(t.interp(0.0, 5.0), 10.0, 1e-9, "single-pt-axis low");
    CHECK_NEAR(t.interp(1.0, 5.0), 20.0, 1e-9, "single-pt-axis high");
    CHECK_NEAR(t.interp(0.5, 999.0), 15.0, 1e-9, "single-pt-axis interp (no OOB)");
}

// ---------------------------------------------------------------------------
// Mat4 — det / inv / transpose (were empty → UB)
// ---------------------------------------------------------------------------

static bool mat4_near_identity(Mat4 m, double tol)
{
    double d[16] = {m.a00,m.a01,m.a02,m.a03, m.a10,m.a11,m.a12,m.a13,
                    m.a20,m.a21,m.a22,m.a23, m.a30,m.a31,m.a32,m.a33};
    double id[16] = {1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1};
    for (int i = 0; i < 16; i++) if (std::fabs(d[i]-id[i]) > tol) return false;
    return true;
}

void test_mat4()
{
    Mat4 I(1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1);
    CHECK_NEAR(I.det(), 1.0, 1e-9, "Mat4 identity det");

    // A non-trivial invertible matrix.
    Mat4 A(2,0,0,1, 0,3,0,0, 0,0,4,0, 0,0,0,5);
    CHECK_NEAR(A.det(), 2*3*4*5, 1e-9, "Mat4 diagonal-ish det");

    Mat4 Ainv = A.inv();
    // A * A^-1 == I  (use the existing Mat4*Mat4? none — check via inverse of inverse)
    Mat4 Ainvinv = Ainv.inv();
    // inverse of inverse ~ A
    CHECK_NEAR(Ainvinv.a00, A.a00, 1e-6, "Mat4 inv(inv) a00");
    CHECK_NEAR(Ainvinv.a11, A.a11, 1e-6, "Mat4 inv(inv) a11");
    CHECK_NEAR(Ainvinv.a03, A.a03, 1e-6, "Mat4 inv(inv) a03");

    // det(inv) == 1/det
    CHECK_NEAR(Ainv.det(), 1.0 / A.det(), 1e-9, "Mat4 det(inv)==1/det");

    // transpose twice == original
    Mat4 At = A.transpose();
    CHECK_NEAR(At.a30, A.a03, 1e-9, "Mat4 transpose a30==a03");
    CHECK(mat4_near_identity(I.transpose(), 1e-9), "Mat4 transpose(I)==I");
}

// ---------------------------------------------------------------------------
// Vec3 — component-wise equality / ordering + guards
// ---------------------------------------------------------------------------

void test_vec3()
{
    Vec3 a(1, 0, 0), b(0, 1, 0), c(1, 0, 0);
    // Same magnitude, different components — used to compare equal.
    CHECK(!(a == b), "Vec3 (1,0,0) != (0,1,0)");
    CHECK(a == c, "Vec3 equal components");
    CHECK(a != b, "Vec3 operator!=");

    // Strict weak ordering: exactly one of a<b, b<a for distinct vectors.
    CHECK((a < b) != (b < a), "Vec3 ordering antisymmetric");
    CHECK(!(a < c) && !(c < a), "Vec3 equal => neither <");

    // unit() of zero vector must not be NaN.
    Vec3 z(0, 0, 0);
    Vec3 zu = z.unit();
    CHECK(!std::isnan(zu.x) && zu.x == 0.0, "Vec3 unit(zero) is zero not NaN");

    Vec3 v(3, 4, 0);
    CHECK_NEAR(v.mag(), 5.0, 1e-9, "Vec3 mag 3-4-5");
    CHECK_NEAR(v.unit().mag(), 1.0, 1e-9, "Vec3 unit mag == 1");
}

// ---------------------------------------------------------------------------
// Mat3 — singular inverse guard, const operator[]
// ---------------------------------------------------------------------------

void test_mat3()
{
    Mat3 I(1,0,0, 0,1,0, 0,0,1);
    CHECK_NEAR(I.det(), 1.0, 1e-9, "Mat3 identity det");

    // const operator[] (the -fpermissive fix path)
    const Mat3 cI = I;
    CHECK_NEAR(cI[0][0], 1.0, 1e-9, "Mat3 const operator[] [0][0]");
    CHECK_NEAR(cI[2][2], 1.0, 1e-9, "Mat3 const operator[] [2][2]");

    // Singular matrix inverse must not divide by zero (returns zero matrix).
    Mat3 S(1,2,3, 2,4,6, 7,8,9); // rows 0,1 linearly dependent → det 0
    Mat3 Sinv = S.inv();
    CHECK(!std::isinf(Sinv.a0[0]) && !std::isnan(Sinv.a0[0]), "Mat3 singular inv guarded");
}

// ---------------------------------------------------------------------------
// quat <-> DCM round trip (exercises const Mat3 access)
// ---------------------------------------------------------------------------

void test_quat_dcm()
{
    // 90-degree yaw
    Quaternion q(std::cos(dsf::util::math::PI/4), 0, 0, std::sin(dsf::util::math::PI/4));
    Mat3 R = q.dcm();
    Quaternion q2 = Quaternion::fromDCM(R);
    // q and q2 represent the same rotation (allow sign flip)
    double dot = q.q0*q2.q0 + q.q1*q2.q1 + q.q2*q2.q2 + q.q3*q2.q3;
    CHECK_NEAR(std::fabs(dot), 1.0, 1e-6, "quat->dcm->quat round trip");
}

// ---------------------------------------------------------------------------
// Config validation (strict mode, H6) — attribute-usage tracking
// ---------------------------------------------------------------------------

void test_config_validation()
{
    // A deck with one consumed attribute, one typo'd attribute nobody reads,
    // one consumed value-element, and one typo'd value-element.
    const char* path = "/tmp/dsf_test_validate.xml";
    {
        std::ofstream f(path);
        f << "<sim dt=\"0.1\" tmax=\"1\">"
             "<vehicle id=\"V\" class=\"Vehicle\">"
             "<rbeom id=\"E\" rpt=\"1\" rptt=\"2\">"
             "<mass>50</mass><mas>60</mas>"
             "</rbeom></vehicle></sim>";
    }

    dsf::xml::xml doc(path);
    doc.parse();
    CHECK(doc.xmlRoot != nullptr, "validate: doc parsed");

    // Simulate a configure pass: read rpt and mass, ask for a missing attr.
    dsf::xml::xmlnode n = *doc.xmlRoot;
    n.search("sim");
    dsf::xml::xmlnode veh = n;
    veh.child(0);                 // <vehicle>
    dsf::xml::xmlnode eom = veh;
    eom.child(0);                 // <rbeom>
    CHECK_NEAR(eom.attrAsDouble("rpt"), 1.0, 1e-12, "validate: rpt read");
    CHECK_NEAR(eom.attrAsDouble("mass"), 50.0, 1e-12, "validate: mass read");
    CHECK_NEAR(eom.attrAsDouble("absent"), 0.0, 1e-12, "validate: absent defaults");

    dsf::xml::ValidationReport r = dsf::xml::validate_config(doc);

    // dt/tmax (sim allowlist), id/class (global allowlist), rpt and mass
    // (read) must NOT be flagged; rptt and <mas> must.
    CHECK(r.unused.size() == 2, "validate: exactly the two typos flagged");
    bool have_rptt = false, have_mas = false;
    for (const auto& u : r.unused) {
        if (u.find("'rptt'") != std::string::npos) have_rptt = true;
        if (u.find("<mas>") != std::string::npos)  have_mas = true;
    }
    CHECK(have_rptt, "validate: typo'd attribute rptt flagged");
    CHECK(have_mas, "validate: typo'd value element <mas> flagged");
    CHECK(!r.missing.empty(), "validate: defaulted lookup recorded");
    CHECK(!r.clean(), "validate: report not clean with typos present");

    std::remove(path);
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

void test_constants()
{
    CHECK_NEAR(dsf::util::math::PI, M_PI, 1e-12, "PI full precision");
    CHECK_NEAR(dsf::util::math::RAD, 180.0 / M_PI, 1e-9, "RAD full precision");
    CHECK_NEAR(dsf::util::math::C_DEG, M_PI / 180.0, 1e-12, "C_DEG full precision");
    CHECK_NEAR(dsf::util::math::RAD * dsf::util::math::C_DEG, 1.0, 1e-12, "RAD*C_DEG==1");
    CHECK_NEAR(dsf::util::earth::J2_EARTH, 1.08262982e-3, 1e-9, "J2 WGS84");
}

// ---------------------------------------------------------------------------
// XML value parsing [A24/A46] — the "silent zero-fill" class. attrAsVec3 /
// attrAsMat3 must accept comma- AND whitespace-separated components; a
// malformed value falls back to zero/identity WITH a warning (xml.h),
// never a silent partial parse. attrAsBool reads "true"/"1".
// ---------------------------------------------------------------------------

void test_xml_value_parsing()
{
    const char* path = "/tmp/dsf_test_values.xml";
    {
        std::ofstream f(path);
        f << "<sim dt=\"0.1\" tmax=\"1\" "
             "p_comma=\"1,2,3\" p_space=\"4 5 6\" p_mixed=\"7, 8,\t9\" "
             "p_short=\"1,2\" "
             "b_true=\"true\" b_one=\"1\" b_false=\"false\" b_zero=\"0\" "
             "m_mixed=\"1,0,0 0,1,0 0,0,2\" />";
    }
    dsf::xml::xml doc(path);
    doc.parse();
    dsf::xml::xmlnode n = *doc.xmlRoot;
    n.search("sim");

    Vec3 a = n.attrAsVec3("p_comma");
    CHECK(a.x == 1 && a.y == 2 && a.z == 3, "attrAsVec3 comma-separated");
    Vec3 b = n.attrAsVec3("p_space");
    CHECK(b.x == 4 && b.y == 5 && b.z == 6, "attrAsVec3 whitespace-separated");
    Vec3 c = n.attrAsVec3("p_mixed");
    CHECK(c.x == 7 && c.y == 8 && c.z == 9, "attrAsVec3 mixed separators");
    Vec3 d = n.attrAsVec3("p_short");
    CHECK(d.x == 0 && d.y == 0 && d.z == 0,
          "attrAsVec3 malformed (2 numbers) falls back to zero, not partial");

    CHECK(n.attrAsBool("b_true") == true,   "attrAsBool 'true'");
    CHECK(n.attrAsBool("b_one") == true,    "attrAsBool '1'");
    CHECK(n.attrAsBool("b_false") == false, "attrAsBool 'false'");
    CHECK(n.attrAsBool("b_zero") == false,  "attrAsBool '0'");

    Mat3 m = n.attrAsMat3("m_mixed");
    CHECK(m[0].x == 1 && m[1].y == 1 && m[2].z == 2 && m[0].y == 0,
          "attrAsMat3 mixed separators, row-major");
}

// ---------------------------------------------------------------------------
// Factory instantiation by class-name string [A46] — the mechanism every
// deck load relies on (TRefUnique<Block>(class_name)).
// ---------------------------------------------------------------------------

class UtilTestBlock : public dsf::sim::Block
{
public:
    int marker = 41;
};

void test_factory_by_name()
{
    using namespace dsf::sim;
    TClass<UtilTestBlock, Block>::Instance();   // register (as models do)

    Block* b = TRefUnique<Block>("UtilTestBlock");
    CHECK(b != nullptr, "factory: registered class instantiates by name");
    UtilTestBlock* tb = dynamic_cast<UtilTestBlock*>(b);
    CHECK(tb != nullptr && tb->marker == 41, "factory: correct derived type");

    Block* b2 = TRefUnique<Block>("UtilTestBlock");
    CHECK(b2 != nullptr && b2 != b, "factory: each TRefUnique is a NEW instance");

    Block* miss = TRefUnique<Block>("NoSuchClass");
    CHECK(miss == nullptr, "factory: unknown class name returns null, no crash");

    delete b;
    delete b2;
}

int main()
{
    std::cout << "=== DSF util unit tests ===\n";

    test_table_1d();
    test_table_2point();
    test_table_missing_file();
    test_config_validation();
    test_table2d();
    test_table2d_bilinear();
    test_tablend_high_dim();
    test_tablend_single_point_axis();
    test_mat4();
    test_vec3();
    test_mat3();
    test_quat_dcm();
    test_constants();
    test_xml_value_parsing();
    test_factory_by_name();

    std::cout << "\n=== Results: " << tests_passed << " passed, "
              << tests_failed << " failed ===\n";
    return tests_failed > 0 ? 1 : 0;
}
