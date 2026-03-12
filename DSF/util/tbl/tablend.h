#pragma once

#include <vector>
#include <array>
#include <string>
#include <stdexcept>

namespace dsf
{
namespace util
{

/**
 * @class TableND
 * @brief N-dimensional regular-grid interpolation table.
 *
 * Unified replacement for Table (1D) and Table2d (2D). Supports 1D through
 * N-D multilinear interpolation over a regular grid with configurable
 * extrapolation policy.
 *
 * Data is stored as a flat contiguous array in row-major order (last axis
 * varies fastest). Breakpoints are stored per-axis.
 *
 * ## Usage Examples
 *
 * ### 1D
 * @code
 * TableND t({0, 1, 2, 3}, {0, 10, 30, 60});
 * double y = t.interp(1.5);  // 20.0
 * double y = t(1.5);         // operator() shorthand
 * @endcode
 *
 * ### 2D (e.g. CL vs alpha, delta_ht)
 * @code
 * TableND t(alpha_breaks, dht_breaks, {{...}, {...}, ...});
 * double CL = t.interp(alpha, delta_ht);
 * @endcode
 *
 * ### 3D (e.g. CL vs alpha, beta, Mach)
 * @code
 * TableND t({alpha_brk, beta_brk, mach_brk}, flat_data);
 * double CL = t.interp(alpha, beta, mach);
 * @endcode
 *
 * ### From file
 * @code
 * TableND t("aero_tables/CL.csv");
 * TableND t = TableND::fromCSV("ref.csv", "time", "gamma");
 * @endcode
 */
class TableND
{
public:
    /// Extrapolation policy for out-of-bounds queries
    enum class Extrap { CLAMP, LINEAR, THROW };

    // ---- Constructors ----

    /// Default constructor (empty table, 0-D, returns 0)
    TableND();

    /// 1D from breakpoints and values
    TableND(const std::vector<double>& x_breaks,
            const std::vector<double>& values);

    /// 2D from breakpoints and row-major grid
    TableND(const std::vector<double>& x_breaks,
            const std::vector<double>& y_breaks,
            const std::vector<std::vector<double>>& grid);

    /// N-D from axes and flat row-major data
    TableND(const std::vector<std::vector<double>>& axes,
            const std::vector<double>& flat_data);

    /// Load from file (auto-detects CSV with TableND header, or legacy DSF format)
    explicit TableND(const std::string& filename);

    /// Load a 1D table from two named columns of a multi-column CSV
    static TableND fromCSV(const std::string& filename,
                           const std::string& x_col,
                           const std::string& y_col);

    // ---- Interpolation ----

    /// 1D interpolation
    double interp(double x) const;

    /// 2D interpolation
    double interp(double x, double y) const;

    /// 3D interpolation
    double interp(double x, double y, double z) const;

    /// N-D general interpolation (heap-allocated point)
    double interp(const std::vector<double>& point) const;

    /// N-D interpolation (stack-allocated, zero-alloc for hot paths)
    template<size_t N>
    double interp(const std::array<double, N>& point) const;

    /// Operator shorthand for 1D
    double operator()(double x) const { return interp(x); }

    // ---- Metadata ----

    /// Number of dimensions
    int ndim() const { return static_cast<int>(axes_.size()); }

    /// Number of breakpoints along dimension i
    int axis_size(int i) const { return static_cast<int>(axes_[i].size()); }

    /// Breakpoint vector for dimension i
    const std::vector<double>& axis(int i) const { return axes_[i]; }

    /// Total number of data points
    size_t size() const { return data_.size(); }

    /// Set extrapolation policy
    void set_extrap(Extrap policy) { extrap_ = policy; }

private:
    std::vector<std::vector<double>> axes_;   ///< breakpoints per dimension
    std::vector<double> data_;                ///< flat row-major data
    std::vector<size_t> strides_;             ///< precomputed strides for indexing
    Extrap extrap_ = Extrap::CLAMP;

    /// Compute strides from axes dimensions
    void compute_strides();

    /// Find bracket index: returns j such that breaks[j] <= val < breaks[j+1]
    /// Clamps to [0, n-2] for out-of-range values.
    static int find_bracket(const std::vector<double>& breaks, double val);

    /// Core N-D interpolation implementation (pointer to D doubles)
    double interp_impl(const double* point, int ndim) const;

    /// Parse a TableND CSV file (with # metadata header)
    void load_tablend_csv(const std::string& filename);

    /// Parse a legacy DSF table file
    void load_legacy(const std::string& filename);
};

// ---- Template implementation (must be in header) ----

template<size_t N>
double TableND::interp(const std::array<double, N>& point) const
{
    return interp_impl(point.data(), N);
}

} // namespace util
} // namespace dsf
