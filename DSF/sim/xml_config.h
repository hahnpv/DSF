/**
 * @file xml_config.h
 * @brief Shared XML-driven configuration helpers: <events> registration and
 *        Monte-Carlo dispersion application.
 *
 * These were previously inline in examples/dynamic/main.cpp only, so the Python
 * run path (dsf run / watch) silently skipped events and dispersions. Extracting
 * them here lets both the C++ executable and the pybind bindings call the SAME
 * logic — one source of truth for turning a parsed <sim> node into events/MC.
 */
#pragma once

#include <string>
#include <iostream>

#include "sim.h"
#include "block.h"
#include "clock.h"
#include "output.h"
#include "event.h"
#include "monte_carlo.h"
#include "../util/xml/xml.h"

namespace dsf
{
namespace sim
{

/// Parse a <montecarlo> section from `sim_node` and apply its dispersions to the
/// tree. `case_id < 0` (the default) means a nominal run — apply_dispersions
/// then no-ops. Call after configure(), before Sim::load().
inline void apply_monte_carlo(Block* root, dsf::xml::xmlnode sim_node,
                              int case_id = -1, unsigned int case_seed = 0)
{
    MonteCarloCase mc = parse_mc_xml(sim_node);
    mc.case_id   = case_id;
    mc.case_seed = case_seed;
    apply_dispersions(root, mc);
}

/// Parse <events><event .../></events> from `sim_node` and register them with
/// the EventBus, then latch initial values for crossing detection. Must be
/// called AFTER Sim::init() so Output has resolved all variable pointers.
inline void register_events(Sim& sim, dsf::xml::xmlnode sim_node)
{
    for (int ei = 0; ei < static_cast<int>(sim_node.numchild()); ei++)
    {
        dsf::xml::xmlnode child = sim_node;
        child.child(ei);
        if (std::string(child.name()) != "events") continue;

        for (int ej = 0; ej < static_cast<int>(child.numchild()); ej++)
        {
            dsf::xml::xmlnode ev = child;
            ev.child(ej);
            if (std::string(ev.name()) != "event") continue;

            std::string name   = ev.attrAsString("name");
            std::string type_s = ev.attrAsString("type");
            std::string var_s  = ev.attrAsString("variable");
            double value       = ev.attrAsDouble("value");
            std::string action = ev.attrAsString("action");

            EventType etype;
            if      (type_s == "time_ge") etype = EventType::TIME_GE;
            else if (type_s == "crosses") etype = EventType::CROSSES_VALUE;
            else if (type_s == "rising")  etype = EventType::RISING;
            else if (type_s == "falling") etype = EventType::FALLING;
            else if (type_s == "ge")      etype = EventType::STATE_GE;
            else if (type_s == "le")      etype = EventType::STATE_LE;
            else {
                std::cout << "[Event] Unknown type '" << type_s
                          << "' for event '" << name << "'" << std::endl;
                continue;
            }

            double* var_ptr = nullptr;
            if (!var_s.empty() && sim.output) {
                var_ptr = sim.output->find_variable(var_s);
                if (!var_ptr) {
                    std::cout << "[Event] WARNING: Variable '" << var_s
                              << "' not found for event '" << name << "'" << std::endl;
                    continue;
                }
            }

            Event event;
            event.name              = name;
            event.condition.type    = etype;
            event.condition.variable = var_ptr;
            event.condition.threshold = value;
            event.one_shot          = true;

            Sim* simptr = &sim;
            if (action == "sim.terminate") {
                event.callback = [simptr]() {
                    std::cout << "[Event] Terminating simulation" << std::endl;
                    simptr->clock->end();
                };
            } else if (action == "log" || action.empty()) {
                event.callback = nullptr;   // EventBus prints a [Event] line by default
            } else {
                std::cout << "[Event] Unknown action '" << action
                          << "' for '" << name << "'" << std::endl;
            }

            int id = EventBus::Instance()->add(event);
            std::cout << "[Event] Registered '" << name << "' (id=" << id
                      << " type=" << type_s << " var=" << var_s
                      << " val=" << value << " action=" << action << ")" << std::endl;
        }
    }

    // Latch initial values so crossing detection has a baseline.
    EventBus::Instance()->latch();
}

} // namespace sim
} // namespace dsf
