/**
 * @file config_errors.h
 * @brief Process-wide collector for configuration-time load errors.
 *
 * Table loaders (tbl/tbl2d/tablend) already print a message and fall back to
 * a safe-empty state when a file or table is missing — which means the sim
 * "runs" with interp() returning 0. They additionally record the error here
 * so validate_config() (xml/validate.h) can surface it, and strict mode can
 * refuse to run.
 *
 * The list is drained by validate_config(); callers that run several sims in
 * one process get a fresh list per validated load. (Process-global like the
 * other registries — see ROADMAP.md R1.)
 */
#pragma once

#include <string>
#include <vector>

namespace dsf {
namespace util {

inline std::vector<std::string>& config_errors() {
    static std::vector<std::string> errors;
    return errors;
}

} // namespace util
} // namespace dsf
