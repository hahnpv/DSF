# DSF Project File Format (`.dsf`)

The `.dsf` file format is a project container that bundles simulation
configuration, vehicle models, and output specifications into a single
package for the DSF simulation framework.

## Structure

A `.dsf` project file is a **directory** with the following layout:

```
myproject.dsf/
├── project.xml        # Top-level configuration (required)
├── vehicles/          # Vehicle XML definitions
│   ├── f16.xml
│   └── target.xml
├── terrain/           # SRTM tiles (optional)
│   └── N35W106.hgt
├── tables/            # Aero/propulsion lookup tables
│   └── cl_alpha.tbl
└── output/            # Simulation output (auto-created)
    └── output1.h5
```

## project.xml

The top-level configuration file defines the simulation:

```xml
<simulation dt="0.01" tmax="300" library="libsixdof.so">
    <output type="h5" file="output/output1.h5" />
    <earth id="WGS84" class="WGS84" />
    <vehicle id="F16" class="Vehicle" file="vehicles/f16.xml" />
</simulation>
```

### Key Elements

| Element       | Description                                    |
|---------------|------------------------------------------------|
| `<simulation>`| Root element — sets timestep, duration, library |
| `<output>`    | Output format (h5, csv) and file path          |
| `<earth>`     | Geodesy/gravity model                          |
| `<vehicle>`   | Vehicle definition (inline or file reference)  |

## Running

```bash
# Run a .dsf project
dsf run myproject.dsf/project.xml

# Or with the CLI pointing to the directory
dsf run myproject.dsf
```

## File vs Directory Resolution

- If the argument is a **directory**, DSF looks for `project.xml` inside it
- If the argument is a **file**, DSF uses it directly as the simulation config
- Relative paths in the XML are resolved relative to the XML file's location
