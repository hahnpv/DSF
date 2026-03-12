#include "event.h"
#include "clock.h"
#include <algorithm>
#include <cmath>

namespace dsf
{
namespace sim
{

// -------------------------------------------------------------------------
// Event::check
// -------------------------------------------------------------------------
std::optional<double> Event::check(double t, double dt) const
{
    if (!armed || fired)
        return std::nullopt;

    const auto& c = condition;

    switch (c.type)
    {
    case EventType::TIME_GE:
    {
        // Fire when sim time crosses the threshold this step
        double t_prev = t - dt;
        if (t_prev < c.threshold && t >= c.threshold)
        {
            double frac = (dt > 0) ? (c.threshold - t_prev) / dt : 0.0;
            return frac;
        }
        return std::nullopt;
    }

    case EventType::CROSSES_ZERO:
    {
        if (!c.initialized) return std::nullopt;
        double curr = *c.variable;
        if ((c.prev_value > 0 && curr <= 0) || (c.prev_value < 0 && curr >= 0))
        {
            double denom = c.prev_value - curr;
            double frac = (std::fabs(denom) > 1e-30) ? c.prev_value / denom : 0.5;
            frac = std::clamp(frac, 0.0, 1.0);
            return frac;
        }
        return std::nullopt;
    }

    case EventType::CROSSES_VALUE:
    {
        if (!c.initialized) return std::nullopt;
        double prev_rel = c.prev_value - c.threshold;
        double curr_rel = *c.variable - c.threshold;
        if ((prev_rel > 0 && curr_rel <= 0) || (prev_rel < 0 && curr_rel >= 0))
        {
            double denom = prev_rel - curr_rel;
            double frac = (std::fabs(denom) > 1e-30) ? prev_rel / denom : 0.5;
            frac = std::clamp(frac, 0.0, 1.0);
            return frac;
        }
        return std::nullopt;
    }

    case EventType::RISING:
    {
        if (!c.initialized) return std::nullopt;
        double prev_rel = c.prev_value - c.threshold;
        double curr_rel = *c.variable - c.threshold;
        if (prev_rel < 0 && curr_rel >= 0)
        {
            double denom = prev_rel - curr_rel;
            double frac = (std::fabs(denom) > 1e-30) ? prev_rel / denom : 0.5;
            frac = std::clamp(frac, 0.0, 1.0);
            return frac;
        }
        return std::nullopt;
    }

    case EventType::FALLING:
    {
        if (!c.initialized) return std::nullopt;
        double prev_rel = c.prev_value - c.threshold;
        double curr_rel = *c.variable - c.threshold;
        if (prev_rel > 0 && curr_rel <= 0)
        {
            double denom = prev_rel - curr_rel;
            double frac = (std::fabs(denom) > 1e-30) ? prev_rel / denom : 0.5;
            frac = std::clamp(frac, 0.0, 1.0);
            return frac;
        }
        return std::nullopt;
    }

    case EventType::STATE_GE:
    {
        if (!c.variable) return std::nullopt;
        if (*c.variable >= c.threshold)
            return 0.5;  // no interpolation for state checks
        return std::nullopt;
    }

    case EventType::STATE_LE:
    {
        if (!c.variable) return std::nullopt;
        if (*c.variable <= c.threshold)
            return 0.5;
        return std::nullopt;
    }
    }

    return std::nullopt;
}

// -------------------------------------------------------------------------
// EventBus singleton
// -------------------------------------------------------------------------
EventBus* EventBus::instance_ = nullptr;

EventBus* EventBus::Instance()
{
    if (!instance_)
        instance_ = new EventBus;
    return instance_;
}

int EventBus::add(Event e)
{
    int id = static_cast<int>(events_.size());

    // Resolve any deferred callbacks for this event name
    for (auto it = deferred_.begin(); it != deferred_.end(); )
    {
        if (it->event_name == e.name)
        {
            // Chain with existing callback if any
            auto existing = e.callback;
            auto deferred_cb = it->callback;
            if (existing)
                e.callback = [existing, deferred_cb]() { existing(); deferred_cb(); };
            else
                e.callback = deferred_cb;
            it = deferred_.erase(it);
        }
        else
            ++it;
    }

    events_.push_back(std::move(e));
    return id;
}

void EventBus::on(const std::string& event_name, std::function<void()> callback)
{
    // Try to attach to existing event
    for (auto& e : events_)
    {
        if (e.name == event_name)
        {
            auto existing = e.callback;
            if (existing)
                e.callback = [existing, callback]() { existing(); callback(); };
            else
                e.callback = callback;
            return;
        }
    }
    // Event not yet registered — defer
    deferred_.push_back({event_name, callback});
}

std::vector<FiredEvent> EventBus::evaluate(double t, double dt)
{
    std::vector<FiredEvent> fired_this_step;

    for (int i = 0; i < static_cast<int>(events_.size()); i++)
    {
        auto& e = events_[i];
        auto result = e.check(t, dt);
        if (result.has_value())
        {
            double frac = result.value();
            double fire_time = t - dt + frac * dt;

            FiredEvent fe;
            fe.event_id = i;
            fe.name = e.name;
            fe.fire_time = fire_time;
            fe.fraction = frac;
            fired_this_step.push_back(fe);

            e.fired = true;
            if (e.one_shot)
                e.armed = false;
        }
    }

    // Sort by crossing time (earliest first)
    std::sort(fired_this_step.begin(), fired_this_step.end(),
              [](const FiredEvent& a, const FiredEvent& b) {
                  return a.fraction < b.fraction;
              });

    // Execute callbacks in order and record history
    for (auto& fe : fired_this_step)
    {
        auto& e = events_[fe.event_id];
        if (e.callback)
        {
            std::cout << "[Event] t=" << fe.fire_time << " '" << fe.name << "'" << std::endl;
            e.callback();
        }
        history_.push_back(fe);
    }

    return fired_this_step;
}

void EventBus::latch()
{
    for (auto& e : events_)
    {
        if (e.condition.variable)
        {
            e.condition.prev_value = *e.condition.variable;
            e.condition.initialized = true;
        }
    }
}

void EventBus::clear()
{
    events_.clear();
    history_.clear();
    deferred_.clear();
}

} // namespace sim
} // namespace dsf
