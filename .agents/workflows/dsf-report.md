---
description: Generate a standard DSF simulation analysis report from dsf_report data
---

# DSF Simulation Report Workflow

Use this workflow after calling `dsf_report(xml_file="...")` to format the returned
JSON data into a standard markdown report.

## Steps

1. **Call `dsf_report`** with the XML file path (and optionally the output file path).
   If it returns an error (no output file, XML parse failure), inform the user and stop.

2. **Create the report** as a markdown artifact with the sections below.
   Fill each section using the JSON data from `dsf_report`.

3. **Embed the plot.** If `plot_file` is non-empty, embed it in the Trajectory Overview
   section. If it is empty, use `dsf_plot_timeseries_csv` to generate one manually.

---

## Report Template

```markdown
# DSF Simulation Report: {simulation.name}

{simulation.description}

**XML:** `{simulation.xml_file}`
**Output:** `{simulation.output_file}` ({simulation.output_format})
**Library:** `{simulation.library}`

## Simulation Configuration

| Setting | Value |
|---------|-------|
| Timestep (dt) | {simulation.dt} s |
| Duration (tmax) | {simulation.tmax} s |
| Output Format | {simulation.output_format} |
| Vehicles | {configuration.num_vehicles} |
| Total Blocks | {configuration.num_blocks} |

### Vehicle & Block Hierarchy

For each vehicle in `configuration.vehicles`, list:
- Vehicle ID, class, and parameters
- Sub-blocks (EOM, guidance, seeker, FCS, etc.) with their classes and key parameters

## Simulation Results

| Metric | Value |
|--------|-------|
| Samples | {results.n_samples} |
| Time Range | {results.t_start} → {results.t_end} s |
| Completion | {results.t_actual_vs_tmax} |

## Timeseries Overview

![Simulation timeseries plot]({plot_file})

## Block Summaries

For each block in `block_summaries`, create a table:

### {block_id}

| Variable | Initial | Final | Min | Max | Mean |
|----------|---------|-------|-----|-----|------|
| ... from block_summaries[block_id] ... |

For Vec3 variables, show initial/final components and magnitude range.

## Notes

(Add any context-specific observations — anomalies, early termination analysis,
engagement outcomes, miss distances, key events, etc.)
```
