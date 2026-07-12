/**
 * @file event.h
 * @brief Event detection and discrete logic framework.
 *
 * Provides zero-crossing detection, time-based triggers, and state-based
 * conditions with an event bus for decoupled publish/subscribe.
 *
 * ## Usage
 * Blocks register events in init(). The EventBus evaluates all armed
 * events once per step after Block::update(). Fired events execute
 * callbacks in crossing-time order.
 *
 * ## XML
 * @code{.xml}
 * <events>
 *   <event name="impact" type="crosses" variable="Altitude" value="0" action="sim.terminate" />
 *   <event name="burnout" type="le" variable="FuelTank.mass" value="0.1" action="log" />
 * </events>
 * @endcode
 */
#pragma once

#include <string>
#include <vector>
#include <functional>
#include <optional>
#include <iostream>

namespace dsf
{
namespace sim
{

class Block;

/// How a condition is evaluated.
enum class EventType
{
    TIME_GE,        ///< Fire when simulation time >= threshold
    CROSSES_ZERO,   ///< Fire when variable crosses zero (either direction)
    CROSSES_VALUE,  ///< Fire when variable crosses a threshold
    STATE_GE,       ///< Fire when variable >= threshold
    STATE_LE,       ///< Fire when variable <= threshold
    RISING,         ///< Fire when variable crosses threshold going up
    FALLING         ///< Fire when variable crosses threshold going down
};

/// Condition that monitors a variable.
struct EventCondition
{
    EventType type = EventType::TIME_GE;
    double* variable = nullptr;  ///< Pointer to monitored variable (null → use sim time)
    double threshold = 0.0;      ///< Crossing/comparison value
    double prev_value = 0.0;     ///< Value at end of previous step (for crossing detection)
    bool initialized = false;    ///< Has prev_value been set?
};

/// Record of a fired event.
struct FiredEvent
{
    int event_id;
    std::string name;
    double fire_time;       ///< Exact interpolated crossing time [s]
    double fraction;        ///< Fraction through the step [0,1] where it fired
};

/// An event: condition + action.
class Event
{
public:
    std::string name;
    EventCondition condition;
    bool armed = true;          ///< Can fire
    bool fired = false;         ///< Has fired at least once
    bool one_shot = true;       ///< Fire once then permanently disarm
    Block* owner = nullptr;     ///< Block that registered this event

    /// Callback invoked when the event fires.
    std::function<void()> callback;

    /// Check if this event should fire given current time and dt.
    /// Returns the fraction through the step [0,1] if firing, nullopt otherwise.
    std::optional<double> check(double t, double dt) const;
};

/// Central event bus, evaluated once per integration step. Each Sim OWNS
/// one (R1); Instance() returns the running Sim's bus via a thread_local
/// context, falling back to a process-wide bus for standalone use.
class EventBus
{
public:
    EventBus() = default;

    static EventBus* Instance();
    /// Set/clear the thread's active bus (Sim-internal; RAII-guarded).
    static void make_current(EventBus* b);
    /// The thread's active bus (null when no Sim is running).
    static EventBus* current();

    /// Register an event. Returns event ID.
    int add(Event e);

    /// Subscribe a callback to a named event (can be called before the event is registered).
    void on(const std::string& event_name, std::function<void()> callback);

    /// Evaluate all armed events. Fires callbacks in crossing-time order.
    /// Call this once per step after Block::update().
    std::vector<FiredEvent> evaluate(double t, double dt);

    /// Update prev_values for all crossing-based conditions.
    /// Call at end of step.
    void latch();

    /// Full history of fired events (for output/telemetry).
    const std::vector<FiredEvent>& history() const { return history_; }

    /// Number of registered events.
    int size() const { return static_cast<int>(events_.size()); }

    /// Clear all events (for test isolation).
    void clear();

private:
    static EventBus* instance_;
    static thread_local EventBus* current_;   ///< Sim-scoped active bus [R1].

    std::vector<Event> events_;
    std::vector<FiredEvent> history_;

    /// Deferred callbacks registered via on() before the event exists.
    struct DeferredCallback {
        std::string event_name;
        std::function<void()> callback;
    };
    std::vector<DeferredCallback> deferred_;
};

} // namespace sim
} // namespace dsf
