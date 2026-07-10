#include "validate.h"

#include <ostream>
#include <set>

#include "../config_errors.h"

namespace dsf {
namespace xml {

namespace {

// Attributes the framework consumes without going through this document's
// xmlnode accessors, so real reads can't always be recorded for them:
// id/class are read by the loaders, name by Block::configure (via parent()),
// but only on nodes that actually become blocks.
const std::set<std::string> GLOBAL_ATTRS = {"id", "class", "name"};

// <sim> tag attributes. The C++ loader reads them via SimInput and `dsf run`
// via xmlnode (both recorded), but `dsf watch` / GUI / MCP receive dt, tmax,
// output policy etc. from project metadata and never touch the XML attrs —
// they would all be false "unused" there.
const std::set<std::string> SIM_ATTRS = {
    "dt", "tmax", "console", "file", "library", "output",
    "log_level", "csv_log_level", "hdf5_log_level",
    "integrator", "atol", "rtol", "seed", "case_id", "strict",
};

bool special(const std::string& key) {
    return key == "<xmlattr>" || key == "<xmlcomment>" || key == "<xmltext>";
}

std::string trim(const std::string& s) {
    const char* ws = " \t\r\n";
    auto b = s.find_first_not_of(ws);
    if (b == std::string::npos) return "";
    return s.substr(b, s.find_last_not_of(ws) - b + 1);
}

std::string label(const std::string& name, const ptree& node) {
    auto id = node.get_optional<std::string>("<xmlattr>.id");
    return "<" + name + (id ? " id=\"" + id.get() + "\"" : "") + ">";
}

void walk(const ptree& node, const std::string& name, const std::string& path,
          bool is_sim, const ValidationContext& ctx,
          std::vector<std::string>& unused)
{
    if (auto attrs = node.get_child_optional("<xmlattr>")) {
        for (const auto& a : *attrs) {
            if (GLOBAL_ATTRS.count(a.first)) continue;
            if (is_sim && SIM_ATTRS.count(a.first)) continue;
            if (!ctx.was_read(&node, a.first))
                unused.push_back(path + " attribute '" + a.first + "'");
        }
    }

    for (const auto& c : node) {
        if (special(c.first)) continue;
        std::string cpath = path.empty() ? label(c.first, c.second)
                                         : path + " > " + label(c.first, c.second);

        // A value-carrying leaf (<mass>50000</mass>) nobody read. Reads are
        // recorded against the parent (element-fallback lookups) or against
        // the node itself (self-value reads) — accept either.
        bool has_element_children = false;
        for (const auto& gc : c.second)
            if (!special(gc.first)) { has_element_children = true; break; }
        if (!has_element_children && !trim(c.second.get_value<std::string>()).empty()
            && !ctx.was_read(&node, c.first) && !ctx.was_read(&c.second, c.first))
            unused.push_back(cpath + " value element");

        walk(c.second, c.first, cpath, c.first == "sim", ctx, unused);
    }
}

} // namespace

ValidationReport validate_config(const xml& doc)
{
    ValidationReport report;

    if (doc.xmlRoot)
        walk(doc.tree(), "", "", false, doc.validation(), report.unused);

    for (const auto& m : doc.validation().missing())
        report.missing.push_back(m);

    // Drain table-load failures recorded during configure.
    report.table_errors = dsf::util::config_errors();
    dsf::util::config_errors().clear();

    return report;
}

void ValidationReport::print(std::ostream& os) const
{
    for (const auto& u : unused)
        os << "[config] UNUSED (possible typo — value silently ignored): "
           << u << "\n";
    for (const auto& t : table_errors)
        os << "[config] TABLE (interpolating 0): " << t << "\n";

    if (!missing.empty()) {
        os << "[config] " << missing.size()
           << " lookup(s) defaulted (absent attribute/element; often optional):\n";
        size_t shown = 0;
        for (const auto& m : missing) {
            if (shown++ == 20) {
                os << "[config]   ... +" << (missing.size() - 20) << " more\n";
                break;
            }
            os << "[config]   " << m << "\n";
        }
    }
}

void ValidationReport::print_strict_banner(std::ostream& os) const
{
    os <<
"======================================================================\n"
" CONFIG VALIDATION FAILED — this deck did not pass strict mode\n"
"======================================================================\n"
" Strict mode is now the DEFAULT. The [config] lines above list:\n"
"\n"
"   * UNUSED attributes/elements — present in the deck but never read\n"
"     by any model. Usually a typo'd name: the model looked up the\n"
"     correct spelling, found nothing, and silently used 0.\n"
"\n"
"   * TABLE errors — a lookup table failed to load, so the model would\n"
"     interpolate 0 everywhere (e.g. an aero deck flying ballistic).\n"
"\n"
" Decks with these problems used to run anyway — and were quietly\n"
" wrong. Fix the deck (usual case), or opt out of strict mode:\n"
"\n"
"   --not-strict on the command line   (this invocation only)\n"
"   <sim strict=\"false\" ...>           (permanently, per deck)\n"
"======================================================================\n"
       << " Refusing to run: " << unused.size()
       << " unused attribute(s)/element(s), " << table_errors.size()
       << " table error(s).\n";
}

} // namespace xml
} // namespace dsf
