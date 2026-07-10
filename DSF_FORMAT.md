# DSF Project File Format (`.dsf`)

A `.dsf` project is a **single JSON file** describing a block graph (the
simulation's model tree), its connections, and runner metadata. It is the
GUI's native save format and is accepted directly by `dsf run` and
`dsf watch`, which convert it to the XML the C++ core consumes
(`python/dsf/utils/convert_dsf_to_xml.py`).

> Historical note: an earlier revision of this document described a
> directory-based layout (`myproject.dsf/` containing `project.xml`,
> `vehicles/`, `tables/`, ...). That format was never implemented. The
> single-JSON format below is what the code reads and writes.

## Top-level structure

```json
{
    "blocks":      [ ... ],
    "connections": [ ... ],
    "metadata":    { ... }
}
```

## `blocks`

One entry per block in the model tree:

```json
{
    "id": "Equinoctial",
    "type": "Equinoctial",
    "tag": "rbeom",
    "parent_id": "Vehicle",
    "x": 120.0,
    "y": 80.0,
    "parameters": { "rpt": "1000.0" },
    "raw_params": { "semimajor_axis": "26558762.9", "eccentricity": "0.0157" },
    "ports": { "inputs": [], "outputs": [] }
}
```

| Field        | Meaning                                                        |
|--------------|----------------------------------------------------------------|
| `id`         | Unique instance id (becomes the XML `id` attribute)            |
| `type`       | C++ class name, instantiated via the factory (`TClassDict`)    |
| `tag`        | XML element name to emit (`rbeom`, `mass`, `earth`, ...)       |
| `parent_id`  | Parent block instance (`null` for top-level blocks)            |
| `x`, `y`     | GUI canvas position (ignored outside the GUI)                  |
| `parameters` | XML **attributes** to emit — configuration values only          |
| `raw_params` | Child **value elements** to emit (`<semimajor_axis>...</semimajor_axis>`) |
| `ports`      | GUI port list (wiring endpoints; not emitted as XML)           |

**`parameters` must contain only configuration properties** — attributes the
model's `configure()` actually reads. Model classes declare which properties
those are via `DSF_PROPERTY`/`DSF_PROPERTY_BIND` (direction `"config"`);
runtime/telemetry state is declared with `DSF_OUTPUT`/`DSF_OUTPUT_BIND`
(direction `"output"`) and must **not** appear here: the converted XML would
carry attributes nothing reads, which strict-mode config validation flags as
typos and refuses to run. The GUI enforces this by only offering
`direction == "config"` properties in the inspector.

## `connections`

GUI port wiring, resolved to reference attributes (e.g. `guidance_id`) during
XML conversion:

```json
{
    "from_block": "S1_Guidance", "from_port": "cmd_out",
    "to_block":   "S1_Control",  "to_port":   "guidance"
}
```

## `metadata`

Runner policy consumed by `dsf run` / `dsf watch`
(`python/dsf/utils/run_config.py`):

```json
{
    "dt": 0.1,
    "tmax": 3600.0,
    "library": "libsixdof.so",
    "file": 100.0,
    "output": {
        "formats": ["csv", "hdf5"],
        "log_level": "normal",
        "csv_log_level": "normal",
        "hdf5_log_level": "normal"
    },
    "telemetry": {
        "console_rate": 1.0,
        "file_rate": 100.0,
        "watch": ["altitude", "Latitude"]
    }
}
```

| Key                      | Meaning                                          |
|--------------------------|--------------------------------------------------|
| `dt`, `tmax`             | Timestep and duration [s]                        |
| `library` (or `lib_path`)| Model shared library to dlopen                   |
| `file`                   | File-output interval [s]                         |
| `output.formats`         | Any of `csv`, `hdf5`                             |
| `output.*_log_level`     | `critical` / `normal` / `verbose`                |
| `telemetry.console_rate` | Seconds between console updates (`dsf watch`)    |
| `telemetry.file_rate`    | Seconds between file writes                      |
| `telemetry.watch`        | Substring filters for live telemetry display     |

## Running

```bash
dsf run  myproject.dsf [--h5]   # convert → C++ exec loop
dsf watch myproject.dsf         # convert → Python step loop, live telemetry
```

Both paths run strict config validation after the configure pass (see
CLAUDE.md "Config validation / strict mode"); a clean `.dsf` project passes
with no findings.
