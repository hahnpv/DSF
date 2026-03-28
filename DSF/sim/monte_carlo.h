/**
 * @file monte_carlo.h
 * @brief Monte Carlo dispersion engine for DSF simulations.
 *
 * Reads <monte_carlo> XML specifications, draws dispersed parameter values
 * using the introspection registry (DSF_PROPERTY_BIND offsets), and writes
 * MC metadata to HDF5 output files.
 *
 * Each MC case runs as a separate process. The Python dispatcher
 * (dsf.mc) manages the job queue and aggregates results.
 */
#pragma once

#include <vector>
#include <string>
#include <cmath>
#include <iostream>

#include "block.h"
#include "TClassDict.h"
#include "../util/gauss.h"
#include "../util/demangle.h"
#include "../util/xml/xml.h"

namespace dsf
{
namespace sim
{

/**
 * @brief Distribution types for Monte Carlo dispersions.
 */
enum class MCDistribution
{
    GAUSSIAN,
    UNIFORM
};

/**
 * @brief Specification for a single dispersed parameter.
 */
struct Dispersion
{
    std::string block_id;       ///< XML id of the target block
    std::string property_name;  ///< DSF_PROPERTY_BIND name
    MCDistribution distribution;

    // Gaussian parameters
    double sigma = 0.0;

    // Uniform parameters
    double min_val = 0.0;
    double max_val = 0.0;

    // Computed at draw time
    double nominal = 0.0;       ///< Value after configure() (before dispersion)
    double drawn = 0.0;         ///< Actual dispersed value applied
    double n_sigma = 0.0;       ///< How many sigmas from nominal (gaussian only)
};

/**
 * @brief Monte Carlo case metadata.
 */
struct MonteCarloCase
{
    unsigned int master_seed = 0;   ///< Master seed for the batch
    int case_id = -1;               ///< This case index (-1 = not an MC run)
    unsigned int case_seed = 0;     ///< Derived seed for this case
    int n_cases = 0;                ///< Total cases in batch
    std::vector<Dispersion> dispersions;

    bool is_mc() const { return case_id >= 0; }
};


// ─────────────────────────────────────────────────────────
// XML Parsing
// ─────────────────────────────────────────────────────────

/**
 * @brief Parse <monte_carlo> block from XML into a MonteCarloCase.
 *
 * Only parses the dispersion specs. case_id and case_seed are set
 * by the Python dispatcher via CLI args or env vars.
 */
inline MonteCarloCase parse_mc_xml(dsf::xml::xmlnode sim_node)
{
    MonteCarloCase mc;

    // Search for <monte_carlo> child node
    for (int i = 0; i < sim_node.numchild(); i++)
    {
        dsf::xml::xmlnode child = sim_node;
        child.child(i);
        if (std::string(child.name()) != "monte_carlo") continue;

        mc.n_cases = (int)child.attrAsDouble("n");
        mc.master_seed = (unsigned int)child.attrAsDouble("seed");

        // Parse <dispersion> children
        for (int j = 0; j < child.numchild(); j++)
        {
            dsf::xml::xmlnode dnode = child;
            dnode.child(j);
            if (std::string(dnode.name()) != "dispersion") continue;

            Dispersion d;
            d.block_id = dnode.attrAsString("block");
            d.property_name = dnode.attrAsString("property");

            std::string dist = dnode.attrAsString("distribution");
            if (dist == "uniform")
            {
                d.distribution = MCDistribution::UNIFORM;
                d.min_val = dnode.attrAsDouble("min");
                d.max_val = dnode.attrAsDouble("max");
            }
            else
            {
                d.distribution = MCDistribution::GAUSSIAN;
                d.sigma = dnode.attrAsDouble("sigma");
            }

            mc.dispersions.push_back(d);
        }
        break;  // only one <monte_carlo> block
    }

    return mc;
}


// ─────────────────────────────────────────────────────────
// Block Tree Traversal
// ─────────────────────────────────────────────────────────

/**
 * @brief Recursively find a Block in the tree by its instance name (XML id).
 */
inline Block* find_block_by_id(Block* root, const std::string& id)
{
    if (!root) return nullptr;

    // Check this block's name
    if (root->getName() == id)
        return root;

    // Search children recursively
    for (Block* child : root->getChildren())
    {
        Block* found = find_block_by_id(child, id);
        if (found) return found;
    }
    return nullptr;
}

/**
 * @brief Look up a property's offset in the TClassDict registry.
 *
 * Given a block pointer, demangle its typeid to get the class name,
 * then search the TClassDict for that class and find the property.
 *
 * @param block Pointer to the block instance.
 * @param property_name Name of the DSF_PROPERTY_BIND property.
 * @param[out] offset The byte offset of the member in the class.
 * @return true if found, false otherwise.
 */
inline bool lookup_property_offset(Block* block, const std::string& property_name, size_t& offset)
{
    std::string class_name = dsf::util::demangle(typeid(*block).name());

    auto* dict = TClassDict<Block>::Instance();
    for (auto* entry : dict->classDictPtr)
    {
        if (entry->name() == class_name)
        {
            for (const auto& prop : entry->getProperties())
            {
                if (prop.name == property_name && prop.offset > 0)
                {
                    offset = prop.offset;
                    return true;
                }
            }
            std::cout << "[MC] Property '" << property_name
                      << "' not found (or not BIND'd) in class '" << class_name << "'" << std::endl;
            return false;
        }
    }
    std::cout << "[MC] Class '" << class_name << "' not found in TClassDict" << std::endl;
    return false;
}


// ─────────────────────────────────────────────────────────
// Dispersion Application
// ─────────────────────────────────────────────────────────

/**
 * @brief Apply all dispersions to the block tree.
 *
 * Must be called AFTER configure() and BEFORE init().
 * Seeds RNG with case_seed, reads nominal values via offsetof,
 * draws dispersed values, and writes them back.
 *
 * @param root Root block of the simulation tree.
 * @param mc MonteCarloCase with dispersion specs (modified in-place with drawn values).
 */
inline void apply_dispersions(Block* root, MonteCarloCase& mc)
{
    if (!mc.is_mc() || mc.dispersions.empty()) return;

    // Seed RNG for this case
    dsf::util::set_seed(mc.case_seed);

    std::cout << "\n[MC] Case " << mc.case_id << "/" << mc.n_cases
              << " (seed=" << mc.case_seed << ")" << std::endl;

    for (auto& d : mc.dispersions)
    {
        // Find the block in the tree
        Block* block = find_block_by_id(root, d.block_id);
        if (!block)
        {
            std::cout << "[MC] WARNING: Block '" << d.block_id << "' not found" << std::endl;
            continue;
        }

        // Look up property offset
        size_t offset = 0;
        if (!lookup_property_offset(block, d.property_name, offset))
            continue;

        // Read nominal value (set by configure())
        double* member_ptr = reinterpret_cast<double*>(
            reinterpret_cast<char*>(block) + offset);
        d.nominal = *member_ptr;

        // Draw dispersed value
        switch (d.distribution)
        {
        case MCDistribution::GAUSSIAN:
            d.drawn = dsf::util::get_gauss(d.nominal, d.sigma);
            d.n_sigma = (d.sigma > 0.0) ? (d.drawn - d.nominal) / d.sigma : 0.0;
            break;

        case MCDistribution::UNIFORM:
            d.drawn = dsf::util::getUniform(d.min_val, d.max_val);
            d.n_sigma = 0.0;  // not meaningful for uniform
            break;
        }

        // Write dispersed value
        *member_ptr = d.drawn;

        std::cout << "[MC]   " << d.block_id << "." << d.property_name
                  << ": nominal=" << d.nominal << " drawn=" << d.drawn;
        if (d.distribution == MCDistribution::GAUSSIAN)
            std::cout << " (" << d.n_sigma << " sigma)";
        std::cout << std::endl;
    }
    std::cout << std::endl;
}


// ─────────────────────────────────────────────────────────
// Property Enumeration (for template generation)
// ─────────────────────────────────────────────────────────

/**
 * @brief Collect all DSF_PROPERTY_BIND properties across all registered classes.
 *
 * Used by `dsf mc template` to auto-generate MC XML.
 *
 * @return Vector of (class_name, PropertyMetadata) pairs for properties with offset > 0.
 */
inline std::vector<std::pair<std::string, PropertyMetadata>> enumerate_all_properties()
{
    std::vector<std::pair<std::string, PropertyMetadata>> result;
    auto* dict = TClassDict<Block>::Instance();
    for (auto* entry : dict->classDictPtr)
    {
        for (const auto& prop : entry->getProperties())
        {
            if (prop.offset > 0)  // only BIND'd properties are dispersible
            {
                result.push_back({entry->name(), prop});
            }
        }
    }
    return result;
}

}  // namespace sim
}  // namespace dsf
