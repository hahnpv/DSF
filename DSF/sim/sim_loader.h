/**
 * @file sim_loader.h
 * @brief THE deck-loading sequence: model library dlopen, output defaults,
 *        block-tree construction, Monte-Carlo application, strict resolution.
 *
 * Shared by both loaders — the C++ `dynamic` executable and (via pybind)
 * `dsf run` / SimSession — so the build sequence exists exactly once and the
 * Python path cannot drift from the C++ one (R8 / LOADER_CONSOLIDATION.md).
 * Follows the xml_config.h pattern that already unified events/Monte-Carlo.
 *
 * Class-name fallback rule (UNIFIED 2026-07-11): a block element's class is
 * `class=` if present, else the CAPITALIZED TAG NAME (<mass .../> → "Mass");
 * its instance name is `name=` if present, else `id`. This standardizes on
 * the former Python rule — `.dsf`-converted decks depend on it. The old C++
 * fallback (class = id) was vestigial: no known deck omits `class=` while
 * relying on its id being a class name.
 */
#pragma once

#include <dlfcn.h>
#include <cctype>
#include <stdexcept>
#include <string>

#include "sim.h"
#include "block.h"
#include "output.h"
#include "SimInput.h"
#include "TRefDict.h"
#include "xml_config.h"
#include "../util/xml/xml.h"

namespace dsf
{
namespace sim
{

/// dlopen a model library with RTLD_GLOBAL (so its class registrations can
/// resolve DSF symbols), falling back to a path relative to the deck's
/// directory — both loaders previously disagreed on this fallback.
/// No-op for an empty path (statically linked models). Throws on failure.
inline void load_model_library(const std::string& lib, const std::string& xml_dir = "")
{
    if (lib.empty())
        return;
    if (dlopen(lib.c_str(), RTLD_NOW | RTLD_GLOBAL))
        return;
    // Capture dlerror() ONCE — it clears itself on read, so calling it a
    // second time returns NULL.
    const char* err = dlerror();
    std::string first_error = err ? err : "unknown dlopen error";
    if (!xml_dir.empty())
    {
        std::string alt = xml_dir + "/" + lib;
        if (dlopen(alt.c_str(), RTLD_NOW | RTLD_GLOBAL))
            return;
    }
    throw std::runtime_error("failed to load model library '" + lib + "': " + first_error);
}

/// Apply the deck's output policy to the process-wide Output defaults.
/// Must run BEFORE the configure pass: vehicles with rpt= create per-vehicle
/// Output objects that read these defaults during configure().
inline void apply_output_defaults(SimInput& input)
{
    Output::defaultCSV()       = input.isCSV();
    Output::defaultHDF5()      = input.isHDF5();
    Output::defaultCSVLevel()  = input.csvLevel();
    Output::defaultHDF5Level() = input.hdf5Level();
}

/// Instantiate and configure the block tree from the <sim> node's children.
/// Elements without an id (e.g. <events>, <monte_carlo>) are skipped.
/// Instantiate-all-then-configure-all, matching both prior loaders.
/// Throws if the factory has no match for a class name.
inline Block* build_tree(dsf::xml::xmlnode sim_node)
{
    Block* root = new Block;
    int nx = sim_node.numchild();

    // Pass 1: instantiate
    for (int i = 0; i < nx; i++)
    {
        dsf::xml::xmlnode child = sim_node;
        child.child(i);
        std::string child_id = child.attrAsString("id");
        if (child_id.empty())
            continue;   // non-block nodes (<events>, <monte_carlo>, comments)

        std::string cls = child.attrAsString("class");
        if (cls.empty())
        {
            std::string tag = child.name();
            if (!tag.empty())
                tag[0] = (char)std::toupper((unsigned char)tag[0]);
            cls = tag;
        }

        Block* block = TRefUnique<Block>(cls);
        if (!block)
        {
            delete root;
            throw std::runtime_error(
                "factory has no class '" + cls + "' (element <" +
                std::string(child.name()) + " id=\"" + child_id +
                "\">) — is the model library loaded and the class name correct?");
        }
        std::string name = child.attrAsString("name");
        block->setName(name.empty() ? child_id : name);
        root->addChild(block);
    }

    // Pass 2: configure (+ metadata check for typo'd attributes)
    for (int i = 0, bi = 0; i < nx; i++)
    {
        dsf::xml::xmlnode child = sim_node;
        child.child(i);
        if (std::string(child.attrAsString("id")).empty())
            continue;
        root->getChild(bi)->configure(child);
        warn_unknown_attributes(root->getChild(bi), child);
        bi++;
    }

    return root;
}

/// The full pre-Sim::load build sequence: model library, output defaults,
/// block tree, Monte-Carlo dispersions. Returns the configured root.
inline Block* build_from_xml(dsf::xml::xmlnode sim_node, SimInput& input,
                             const std::string& xml_dir = "")
{
    load_model_library(input.library(), xml_dir);
    apply_output_defaults(input);
    Block* root = build_tree(sim_node);
    apply_monte_carlo(root, sim_node, input.caseId(), input.seed());
    return root;
}

/// Strict-mode resolution, identical in both loaders: strict is the DEFAULT;
/// the deck opts out with <sim strict="false">, the invocation with a
/// --not-strict flag.
inline bool resolve_strict(dsf::xml::xmlnode sim_node, bool cli_not_strict)
{
    if (cli_not_strict)
        return false;
    if (sim_node.findAttr("strict") && !sim_node.attrAsBool("strict"))
        return false;
    return true;
}

} // namespace sim
} // namespace dsf
