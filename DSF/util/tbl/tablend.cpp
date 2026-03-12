#include "tablend.h"
#include <fstream>
#include <sstream>
#include <iostream>
#include <algorithm>
#include <cmath>
#include <numeric>
#include <cassert>

namespace dsf
{
namespace util
{

// ============================================================================
// Construction
// ============================================================================

TableND::TableND()
    : extrap_(Extrap::CLAMP)
{
}

TableND::TableND(const std::vector<double>& x_breaks,
                 const std::vector<double>& values)
    : extrap_(Extrap::CLAMP)
{
    assert(x_breaks.size() == values.size());
    axes_.push_back(x_breaks);
    data_ = values;
    compute_strides();
}

TableND::TableND(const std::vector<double>& x_breaks,
                 const std::vector<double>& y_breaks,
                 const std::vector<std::vector<double>>& grid)
    : extrap_(Extrap::CLAMP)
{
    axes_.push_back(x_breaks);
    axes_.push_back(y_breaks);

    // Flatten row-major
    data_.reserve(x_breaks.size() * y_breaks.size());
    for (const auto& row : grid)
    {
        for (double v : row)
            data_.push_back(v);
    }
    compute_strides();
}

TableND::TableND(const std::vector<std::vector<double>>& axes,
                 const std::vector<double>& flat_data)
    : axes_(axes), data_(flat_data), extrap_(Extrap::CLAMP)
{
    compute_strides();
}

TableND::TableND(const std::string& filename)
    : extrap_(Extrap::CLAMP)
{
    // Peek at first line to detect format
    std::ifstream probe(filename);
    if (!probe.is_open())
    {
        std::cerr << "TableND: error opening file " << filename << std::endl;
        return;
    }

    std::string first_line;
    std::getline(probe, first_line);
    probe.close();

    if (first_line.find("# TableND") != std::string::npos ||
        first_line.find("#TableND")  != std::string::npos)
    {
        load_tablend_csv(filename);
    }
    else
    {
        // Try CSV with headers (comma-separated)
        // If that fails, fall back to legacy DSF format
        if (first_line.find(',') != std::string::npos)
        {
            // Looks like CSV — but this constructor doesn't know which columns.
            // Load as a TableND CSV if it has axis metadata, otherwise error.
            load_tablend_csv(filename);
        }
        else
        {
            load_legacy(filename);
        }
    }
}

TableND TableND::fromCSV(const std::string& filename,
                         const std::string& x_col,
                         const std::string& y_col)
{
    std::ifstream f(filename);
    if (!f.is_open())
    {
        std::cerr << "TableND::fromCSV: error opening " << filename << std::endl;
        return TableND();
    }

    // Parse header
    std::string line;
    if (!std::getline(f, line)) return TableND();

    std::vector<std::string> headers;
    std::stringstream ss(line);
    std::string cell;
    while (std::getline(ss, cell, ','))
    {
        // Trim whitespace
        size_t s = cell.find_first_not_of(" \r\n\t");
        size_t e = cell.find_last_not_of(" \r\n\t");
        if (s != std::string::npos)
            headers.push_back(cell.substr(s, e - s + 1));
        else
            headers.push_back("");
    }

    int x_idx = -1, y_idx = -1;
    for (size_t i = 0; i < headers.size(); i++)
    {
        if (headers[i] == x_col) x_idx = static_cast<int>(i);
        if (headers[i] == y_col) y_idx = static_cast<int>(i);
    }

    if (x_idx == -1 || y_idx == -1)
    {
        std::cerr << "TableND::fromCSV: columns '" << x_col << "' or '"
                  << y_col << "' not found in " << filename << std::endl;
        return TableND();
    }

    // Read data
    std::vector<double> x_data, y_data;
    while (std::getline(f, line))
    {
        if (line.empty() || line[0] == '#' || line[0] == '\r') continue;

        std::stringstream row_ss(line);
        std::string val;
        int col = 0;
        double x_val = 0, y_val = 0;
        while (std::getline(row_ss, val, ','))
        {
            if (col == x_idx) x_val = std::atof(val.c_str());
            if (col == y_idx) y_val = std::atof(val.c_str());
            col++;
        }
        x_data.push_back(x_val);
        y_data.push_back(y_val);
    }

    return TableND(x_data, y_data);
}

// ============================================================================
// Stride computation
// ============================================================================

void TableND::compute_strides()
{
    int D = static_cast<int>(axes_.size());
    strides_.resize(D);
    if (D == 0) return;

    strides_[D - 1] = 1;
    for (int i = D - 2; i >= 0; i--)
    {
        strides_[i] = strides_[i + 1] * axes_[i + 1].size();
    }
}

// ============================================================================
// Bracket search
// ============================================================================

int TableND::find_bracket(const std::vector<double>& breaks, double val)
{
    int n = static_cast<int>(breaks.size());
    if (n < 2) return 0;
    if (val <= breaks[0]) return 0;
    if (val >= breaks[n - 1]) return n - 2;

    // Binary search for bracket
    int lo = 0, hi = n - 2;
    while (lo < hi)
    {
        int mid = (lo + hi) / 2;
        if (val < breaks[mid])
            hi = mid - 1;
        else if (val >= breaks[mid + 1])
            lo = mid + 1;
        else
            return mid;
    }
    return lo;
}

// ============================================================================
// Core N-D interpolation
// ============================================================================

double TableND::interp_impl(const double* point, int ndim) const
{
    if (data_.empty()) return 0.0;

    int D = static_cast<int>(axes_.size());
    if (ndim != D)
    {
        std::cerr << "TableND::interp: expected " << D << " dims, got "
                  << ndim << std::endl;
        return 0.0;
    }

    // 1. Find bracket and fractional weight for each axis
    // Stack-allocate for up to 8 dimensions (covers all practical cases)
    int    idx[8];
    double frac[8];

    for (int d = 0; d < D; d++)
    {
        const auto& ax = axes_[d];
        idx[d] = find_bracket(ax, point[d]);
        int j = idx[d];

        double span = ax[j + 1] - ax[j];
        if (span > 0.0)
            frac[d] = (point[d] - ax[j]) / span;
        else
            frac[d] = 0.0;

        // Apply extrapolation policy
        if (extrap_ == Extrap::CLAMP)
        {
            if (frac[d] < 0.0) frac[d] = 0.0;
            if (frac[d] > 1.0) frac[d] = 1.0;
        }
        else if (extrap_ == Extrap::THROW)
        {
            if (point[d] < ax.front() || point[d] > ax.back())
                throw std::out_of_range("TableND::interp: point out of range");
        }
        // LINEAR: frac can go negative or > 1 naturally
    }

    // 2. Iterate over 2^D corners and blend
    int num_corners = 1 << D;
    double result = 0.0;

    for (int c = 0; c < num_corners; c++)
    {
        double weight = 1.0;
        size_t flat_idx = 0;

        for (int d = 0; d < D; d++)
        {
            int bit = (c >> (D - 1 - d)) & 1;  // 0 = low corner, 1 = high corner
            weight *= (bit == 0) ? (1.0 - frac[d]) : frac[d];
            flat_idx += (idx[d] + bit) * strides_[d];
        }

        result += weight * data_[flat_idx];
    }

    return result;
}

// ============================================================================
// Convenience overloads (delegate to interp_impl)
// ============================================================================

double TableND::interp(double x) const
{
    return interp_impl(&x, 1);
}

double TableND::interp(double x, double y) const
{
    double pt[2] = {x, y};
    return interp_impl(pt, 2);
}

double TableND::interp(double x, double y, double z) const
{
    double pt[3] = {x, y, z};
    return interp_impl(pt, 3);
}

double TableND::interp(const std::vector<double>& point) const
{
    return interp_impl(point.data(), static_cast<int>(point.size()));
}

// ============================================================================
// File loaders
// ============================================================================

/// Trim whitespace from a string
static std::string trim(const std::string& s)
{
    size_t start = s.find_first_not_of(" \t\r\n");
    size_t end   = s.find_last_not_of(" \t\r\n");
    if (start == std::string::npos) return "";
    return s.substr(start, end - start + 1);
}

/// Parse a comma-separated list of doubles from a string
static std::vector<double> parse_doubles(const std::string& s)
{
    std::vector<double> result;
    std::stringstream ss(s);
    std::string tok;
    while (std::getline(ss, tok, ','))
    {
        std::string t = trim(tok);
        if (!t.empty())
            result.push_back(std::atof(t.c_str()));
    }
    return result;
}

void TableND::load_tablend_csv(const std::string& filename)
{
    std::ifstream f(filename);
    if (!f.is_open())
    {
        std::cerr << "TableND: error opening " << filename << std::endl;
        return;
    }

    std::string line;
    std::vector<std::string> axis_names;

    // Parse metadata headers
    while (std::getline(f, line))
    {
        std::string tl = trim(line);
        if (tl.empty()) continue;
        if (tl[0] != '#') break;  // First non-comment line = data

        // Parse "# axes: alpha, delta_ht"
        if (tl.find("# axes:") != std::string::npos || tl.find("#axes:") != std::string::npos)
        {
            size_t colon = tl.find(':');
            std::string names_str = tl.substr(colon + 1);
            std::stringstream ss(names_str);
            std::string name;
            while (std::getline(ss, name, ','))
            {
                axis_names.push_back(trim(name));
            }
            continue;
        }

        // Parse "# alpha: -0.175, -0.087, ..."
        // Check if this line defines a named axis
        bool is_axis_def = false;
        for (const auto& aname : axis_names)
        {
            std::string prefix = "# " + aname + ":";
            if (tl.find(prefix) != std::string::npos)
            {
                size_t colon = tl.find(':', 1); // skip first # char
                std::vector<double> brk = parse_doubles(tl.substr(colon + 1));
                axes_.push_back(brk);
                is_axis_def = true;
                break;
            }
        }
        if (is_axis_def) continue;

        // Other comment lines (e.g. "# TableND: CL") — skip
    }

    // Read data lines (first non-comment line already in `line`)
    data_.clear();
    // Process the line we already read
    if (!line.empty() && line[0] != '#')
    {
        auto vals = parse_doubles(line);
        data_.insert(data_.end(), vals.begin(), vals.end());
    }

    while (std::getline(f, line))
    {
        std::string tl = trim(line);
        if (tl.empty() || tl[0] == '#') continue;
        auto vals = parse_doubles(tl);
        data_.insert(data_.end(), vals.begin(), vals.end());
    }

    // If no axes were defined in the header, infer 1D
    if (axes_.empty() && !data_.empty())
    {
        // Assume single column — breakpoints are 0, 1, 2, ...
        std::vector<double> brk(data_.size());
        for (size_t i = 0; i < data_.size(); i++)
            brk[i] = static_cast<double>(i);
        axes_.push_back(brk);
    }

    compute_strides();
}

void TableND::load_legacy(const std::string& filename)
{
    // Legacy DSF format: header line, size line, column header line, then tab-delimited data
    std::ifstream f(filename);
    if (!f.is_open())
    {
        std::cerr << "TableND: error opening legacy file " << filename << std::endl;
        return;
    }

    std::string line;

    // Skip header (table name)
    std::getline(f, line);
    // Read number of lines
    std::getline(f, line);
    int n = std::atoi(line.c_str());
    // Skip column headers
    std::getline(f, line);

    // Read n rows of tab-delimited data (x, y)
    std::vector<double> x_vals, y_vals;
    for (int i = 0; i < n; i++)
    {
        if (!std::getline(f, line)) break;
        std::string::size_type pos = line.find_first_of("\t");
        if (pos != std::string::npos)
        {
            x_vals.push_back(std::atof(line.substr(0, pos).c_str()));
            y_vals.push_back(std::atof(line.substr(pos + 1).c_str()));
        }
    }

    axes_.push_back(x_vals);
    data_ = y_vals;
    compute_strides();
}

} // namespace util
} // namespace dsf
