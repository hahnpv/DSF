/**
 * @file validate.h
 * @brief Post-configure validation of a simulation deck ("strict mode").
 *
 * The silent-zero pattern — a typo'd attribute reads as 0, a missing table
 * interpolates 0, a defaulted value goes unnoticed — lets a sim run while
 * being quietly wrong. This pass closes the loop after configure():
 *
 * - **unused**: attributes / value-elements present in the deck that no model
 *   ever read. Almost always a typo'd name (the model read the correctly
 *   spelled attribute, missed, and defaulted). High-signal; fatal in strict.
 * - **table_errors**: table files/entries that failed to load (the table
 *   fell back to safe-empty and interpolates 0). Fatal in strict.
 * - **missing**: lookups models made that found nothing. Often legitimately
 *   optional attributes, so informational only — but the place to look when
 *   a value is unexpectedly zero.
 *
 * Usage (after configure + event registration, before exec):
 * @code{.cpp}
 *   ValidationReport r = validate_config(doc);
 *   r.print(std::cerr);
 *   if (strict && !r.clean()) abort_run();
 * @endcode
 *
 * Strictness comes from `<sim strict="true">` or the runner's --strict flag.
 */
#pragma once

#include <iosfwd>
#include <string>
#include <vector>

#include "xml.h"

namespace dsf {
namespace xml {

struct ValidationReport {
    std::vector<std::string> unused;        ///< present in deck, never read (typos)
    std::vector<std::string> table_errors;  ///< table loads that fell back to empty
    std::vector<std::string> missing;       ///< reads that defaulted (informational)

    /// No fatal findings (missing reads are informational, never fatal).
    bool clean() const { return unused.empty() && table_errors.empty(); }

    /// Human-readable summary to `os`; prints nothing when there are no findings.
    void print(std::ostream& os) const;

    /// Verbose refusal banner for strict-mode failures — strict is the
    /// default, so first contact with it deserves a full explanation and the
    /// opt-outs (--not-strict / <sim strict="false">).
    void print_strict_banner(std::ostream& os) const;
};

/// Diff the parsed document against its attribute-usage record and drain any
/// pending table load errors. Call after the configure pass.
ValidationReport validate_config(const xml& doc);

} // namespace xml
} // namespace dsf
