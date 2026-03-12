/**
 * @file phase_sequencer.h
 * @brief Lightweight phase sequencer for time-ordered mode scheduling.
 *
 * Replaces the ad-hoc Phase struct + vector + index pattern found in
 * F16FCS, AirplaneAutopilot, and StageManager. Provides:
 * - Named phases with arbitrary double parameters
 * - Automatic time-triggered transitions (with optional custom guards)
 * - Transition callbacks for side-effects (ignition, separation, etc.)
 * - Current phase query for external blocks
 *
 * ## Usage
 * @code{.cpp}
 * PhaseSequencer seq;
 * seq.add("idle",      0, {{"throttle", 0}, {"brake", 1}});
 * seq.add("ground_roll", 2, {{"throttle", 1}, {"brake", 0}});
 * seq.add("rotate",   12, {{"pitch", 10}, {"gear", 1}});
 * 
 * seq.on_transition([](auto& from, auto& to) {
 *     cout << "Phase: " << from.name << " -> " << to.name << endl;
 * });
 *
 * // In update():
 * seq.update(t());
 * double throttle = seq.param("throttle", 0.5);  // default if not set
 * @endcode
 *
 * ## XML
 * @code{.xml}
 * <schedule>
 *   <phase name="idle" t="0" throttle="0" brake="1" />
 *   <phase name="climb" t="20" alt="300" speed="130" alt_hold="1" />
 * </schedule>
 * @endcode
 */
#pragma once

#include <string>
#include <vector>
#include <map>
#include <functional>
#include <iostream>

namespace dsf
{
namespace sim
{

/// A single phase in a sequencer.
struct Phase
{
    std::string name;                          ///< Human-readable name
    double t_start = 0.0;                      ///< Time trigger [s]
    std::map<std::string, double> params;      ///< Arbitrary key-value parameters
    std::function<bool()> guard;               ///< Optional custom transition guard

    /// Get a parameter value, or default if not set.
    double get(const std::string& key, double default_val = 0.0) const
    {
        auto it = params.find(key);
        return (it != params.end()) ? it->second : default_val;
    }

    /// Check if a parameter exists.
    bool has(const std::string& key) const
    {
        return params.find(key) != params.end();
    }
};

/// Ordered phase sequencer with time-triggered transitions.
class PhaseSequencer
{
public:
    /// Add a phase. Phases must be added in time order.
    void add(const std::string& name, double t_start,
             std::map<std::string, double> params = {})
    {
        phases_.push_back({name, t_start, std::move(params), nullptr});
    }

    /// Add a phase with a custom guard (fires when guard returns true).
    void add(const std::string& name, double t_start,
             std::map<std::string, double> params,
             std::function<bool()> guard)
    {
        phases_.push_back({name, t_start, std::move(params), std::move(guard)});
    }

    /// Add a Phase struct directly.
    void add(Phase p)
    {
        phases_.push_back(std::move(p));
    }

    /// Subscribe to phase transitions.
    void on_transition(std::function<void(const Phase& from, const Phase& to)> cb)
    {
        callbacks_.push_back(std::move(cb));
    }

    /// Call once per step. Returns true if phase changed this step.
    bool update(double t)
    {
        if (phases_.empty()) return false;

        bool changed = false;
        while (idx_ + 1 < static_cast<int>(phases_.size()))
        {
            const auto& next = phases_[idx_ + 1];
            bool should_advance = false;

            if (next.guard)
                should_advance = next.guard();
            else
                should_advance = (t >= next.t_start);

            if (!should_advance) break;

            const auto& from = phases_[idx_];
            idx_++;
            const auto& to = phases_[idx_];

            std::cout << "[Phase] t=" << t << " '" << from.name
                      << "' -> '" << to.name << "'" << std::endl;

            for (auto& cb : callbacks_)
                cb(from, to);

            changed = true;
        }
        return changed;
    }

    /// Current phase (const reference).
    const Phase& current() const { return phases_[idx_]; }

    /// Current phase name.
    const std::string& current_name() const { return phases_[idx_].name; }

    /// Current phase index.
    int current_index() const { return idx_; }

    /// Number of phases.
    int size() const { return static_cast<int>(phases_.size()); }

    /// Get a parameter from the current phase (with default).
    double param(const std::string& key, double default_val = 0.0) const
    {
        return phases_[idx_].get(key, default_val);
    }

    /// Check if current phase has a parameter.
    bool has_param(const std::string& key) const
    {
        return phases_[idx_].has(key);
    }

    /// Reset to first phase.
    void reset() { idx_ = 0; }

    /// Direct access to phases (for XML loading).
    std::vector<Phase>& phases() { return phases_; }
    const std::vector<Phase>& phases() const { return phases_; }

private:
    std::vector<Phase> phases_;
    int idx_ = 0;
    std::vector<std::function<void(const Phase&, const Phase&)>> callbacks_;
};

} // namespace sim
} // namespace dsf
