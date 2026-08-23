"""
Monte Carlo dispatcher for DSF C++ simulations.

Uses a RollingPool of subprocesses to run dispersed cases in parallel.
Each case gets a patched XML with seed/case_id attributes, and the C++
monte_carlo.h engine handles dispersion application via introspection.

Usage:
    mc = MonteCarlo("vehicle.xml")
    mc.run(workers=8)
    mc.build_index()
    mc.extremes(threshold_sigma=2.0)

Honesty guarantee: the values recorded in mc_draws.json are the values each
case APPLIES. The pre-drawn values are patched into every case's XML
(n_sigma_draw / drawn attributes on <dispersion>) and the C++ engine uses
them verbatim instead of re-drawing, so reported statistics cannot diverge
from what the sims actually ran.
"""

import os
import sys
import json
import copy
import time
import hashlib
import subprocess
import numpy as np
from pathlib import Path
from xml.etree import ElementTree as ET
from concurrent.futures import ProcessPoolExecutor, as_completed


# ─── State File Convention ───
MC_STATE_FILE = '.dsf_mc.json'
MC_STOP_FILE  = '.dsf_mc_stop'
MC_LOG_FILE   = '.dsf_mc.log'
MC_DRAWS_FILE = 'mc_draws.json'


# ─── Draw-record helpers (single source for the runner AND the CLI) ───

def load_draws(output_dir):
    """Load the mc_draws.json record from a batch output dir (None if absent)."""
    draws_file = Path(output_dir) / MC_DRAWS_FILE
    if not draws_file.exists():
        return None
    return json.loads(draws_file.read_text())


def draw_stats(draws):
    """Per-parameter statistics over a list of per-case draw dicts.

    Returns {key: {'distribution', 'mean', 'std', 'min', 'max'}} where the
    values are in sigma units for gaussian draws and absolute for uniform.
    """
    stats = {}
    if not draws:
        return stats
    for key in draws[0].keys():
        values = []
        dist = draws[0][key].get('distribution', 'gaussian')
        for case_draws in draws:
            d = case_draws.get(key, {})
            if d.get('distribution') == 'gaussian':
                values.append(d.get('n_sigma_draw', 0.0))
            elif d.get('distribution') == 'uniform':
                values.append(d.get('drawn', 0.0))
        if not values:
            continue
        arr = np.array(values)
        stats[key] = {
            'distribution': dist,
            'mean': float(arr.mean()), 'std': float(arr.std()),
            'min': float(arr.min()), 'max': float(arr.max()),
        }
    return stats


def extreme_draws(draws, threshold_sigma=2.0):
    """Cases with any gaussian draw beyond threshold_sigma.

    Returns [{'case_id', 'parameter', 'n_sigma'}], most extreme first.
    """
    results = []
    for case_id, case_draws in enumerate(draws):
        for key, d in case_draws.items():
            if d.get('distribution') != 'gaussian':
                continue
            ns = d.get('n_sigma_draw', 0.0)
            if abs(ns) > threshold_sigma:
                results.append({'case_id': case_id, 'parameter': key,
                                'n_sigma': ns})
    return sorted(results, key=lambda e: abs(e['n_sigma']), reverse=True)


def _derive_case_seed(master_seed, case_id):
    """Derive a deterministic per-case seed from master seed + case ID."""
    h = hashlib.md5(f"{master_seed}_{case_id}".encode()).hexdigest()
    return int(h[:8], 16)


def _fmt_elapsed(secs):
    s = int(secs)
    if s >= 3600:
        return f"{s // 3600}h{(s % 3600) // 60:02d}m"
    elif s >= 60:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s}s"


class MonteCarlo:
    """Monte Carlo batch runner for DSF simulations.

    Reads a <monte_carlo> block from the sim XML, pre-draws dispersed values,
    and spawns parallel C++ processes.
    """

    def __init__(self, xml_path):
        self.xml_path = Path(xml_path).resolve()
        self.tree = ET.parse(str(self.xml_path))
        self.root = self.tree.getroot()

        # Find sim node (could be root or child)
        self.sim_node = self.root if self.root.tag == 'sim' else self.root.find('.//sim')
        if self.sim_node is None:
            raise ValueError(f"No <sim> node found in {xml_path}")

        # Find <monte_carlo> block
        self.mc_node = self.sim_node.find('monte_carlo')
        if self.mc_node is None:
            raise ValueError(f"No <monte_carlo> block found in {xml_path}")

        self.n_cases = int(self.mc_node.get('n', '100'))
        self.master_seed = int(self.mc_node.get('seed', '42'))
        self.workers = int(self.mc_node.get('workers', '8'))
        self.output_dir = Path(self.mc_node.get('output_dir', 'mc_results'))
        if not self.output_dir.is_absolute():
            self.output_dir = self.xml_path.parent / self.output_dir

        # Parse dispersions
        self.dispersions = []
        for dnode in self.mc_node.findall('dispersion'):
            disp = {
                'block': dnode.get('block'),
                'property': dnode.get('property'),
                'distribution': dnode.get('distribution', 'gaussian'),
                'sigma': float(dnode.get('sigma', '0.0')),
                'min': float(dnode.get('min', '0.0')),
                'max': float(dnode.get('max', '0.0')),
            }
            self.dispersions.append(disp)

        # Extract sim config
        self.library = self.sim_node.get('library', '')
        self.dynamic_bin = None   # resolved lazily in run() — analysis-only
                                  # uses (draws, case XML) need no executable

        # Pre-draw values
        self.draws = self._pre_draw()

    def _find_dynamic(self):
        """Find the dynamic executable."""
        # Try relative to DSF
        dsf_root = Path(__file__).parent.parent.parent  # python/dsf -> python -> DSF
        candidates = [
            dsf_root / 'build' / 'examples' / 'dynamic' / 'dynamic',
            Path('/opt/DSF/build/examples/dynamic/dynamic'),
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        raise FileNotFoundError("Cannot find 'dynamic' executable")

    def _pre_draw(self):
        """Pre-draw all dispersion values for all cases using NumPy RNG."""
        rng = np.random.default_rng(self.master_seed)
        draws = []

        for case_id in range(self.n_cases):
            case_draws = {}
            for d in self.dispersions:
                key = f"{d['block']}.{d['property']}"
                if d['distribution'] == 'gaussian' and d['sigma'] > 0:
                    # We just draw the delta (n_sigma draw)
                    # The actual nominal comes from the C++ configure()
                    case_draws[key] = {
                        'n_sigma_draw': float(rng.normal()),
                        'sigma': d['sigma'],
                        'distribution': 'gaussian',
                    }
                elif d['distribution'] == 'uniform':
                    case_draws[key] = {
                        'drawn': float(rng.uniform(d['min'], d['max'])),
                        'min': d['min'],
                        'max': d['max'],
                        'distribution': 'uniform',
                    }
                else:
                    case_draws[key] = {
                        'n_sigma_draw': 0.0,
                        'sigma': 0.0,
                        'distribution': 'gaussian',
                    }
            draws.append(case_draws)

        return draws

    def _absolutize_paths(self, node):
        """Rewrite relative path attributes to absolute, anchored on the
        ORIGINAL deck's directory.

        A case runs from output_dir/case_NNNN/, two levels below the deck,
        and the loader resolves a path-bearing attribute against the process
        CWD (dlopen) or the case dir (its xml_dir fallback) — never against
        where the deck actually lives. So every relative reference in the
        deck (`library="../../build/libsixdof.so"`, `data_dir="../terrain"`)
        silently misses and the case dies before the first step. Anchoring
        them here, once, at case-XML generation is the only point that still
        knows where the deck came from.

        An attribute is a path reference iff it names something that EXISTS
        relative to the deck dir. That test is what keeps `units="m/s"` and
        other incidental slashes out, and it deliberately leaves bare
        sonames (`library="libsixdof.so"`) alone so the dynamic linker
        resolves them from LD_LIBRARY_PATH as intended.

        normpath, not realpath: `libsixdof.so` must not be rewritten to the
        `libsixdof.so.1.0.0` it points at, or the case pins a soname the
        build may not carry after a version bump.
        """
        deck_dir = str(self.xml_path.parent)
        for elem in node.iter():
            for attr, value in list(elem.attrib.items()):
                if not value:
                    continue
                candidate = os.path.normpath(os.path.join(deck_dir, value))
                if candidate != value and os.path.exists(candidate):
                    elem.set(attr, candidate)

    def _make_case_xml(self, case_id):
        """Create a patched XML for a single MC case.

        Adds seed and case_id attributes to <sim> so the C++ MC engine
        knows which case this is and can reproduce the RNG state, and
        rewrites the deck's relative paths so they still resolve from the
        case directory.
        """
        case_dir = self.output_dir / f"case_{case_id:04d}"
        case_dir.mkdir(parents=True, exist_ok=True)

        # Deep copy the tree
        tree = copy.deepcopy(self.tree)
        root = tree.getroot()
        sim_node = root if root.tag == 'sim' else root.find('.//sim')

        # Set case-specific attributes
        case_seed = _derive_case_seed(self.master_seed, case_id)
        sim_node.set('seed', str(case_seed))
        sim_node.set('case_id', str(case_id))

        # Transmit this case's pre-drawn values into the <dispersion> elements
        # so the C++ engine applies EXACTLY what mc_draws.json records
        # (gaussian: n_sigma units, nominal added C++-side after configure();
        # uniform: absolute value). Without these attrs the C++ engine draws
        # its own values and the dispatcher's records are fiction.
        case_draws = self.draws[case_id]
        for dnode in sim_node.find('monte_carlo').findall('dispersion'):
            key = f"{dnode.get('block')}.{dnode.get('property')}"
            info = case_draws.get(key)
            if info is None:
                continue
            if info['distribution'] == 'gaussian':
                dnode.set('n_sigma_draw', repr(info['n_sigma_draw']))
            else:
                dnode.set('drawn', repr(info['drawn']))

        # Anchor relative paths on the deck dir before the case XML moves
        # two levels away from it.
        self._absolutize_paths(root)

        # Belt and braces: data files are now referenced absolutely by the
        # XML, but a table can name a companion file relative to the CWD it
        # is read from. Symlinking the deck's siblings keeps those working.
        src_dir = self.xml_path.parent
        for f in src_dir.iterdir():
            if f.is_file() and f.suffix in ('.dat', '.dt2', '.tbl'):
                link = case_dir / f.name
                if not link.exists():
                    try:
                        link.symlink_to(f.resolve())
                    except OSError:
                        pass

        # Write patched XML
        xml_path = case_dir / 'case.xml'
        tree.write(str(xml_path), xml_declaration=False)

        return str(xml_path), str(case_dir), case_seed

    def run(self, workers=None, fg=True):
        """Run all MC cases.

        Args:
            workers: Number of parallel workers (default: from XML, or 8).
            fg: If True, run in foreground. If False, daemonize.
        """
        n_workers = workers or self.workers
        if self.dynamic_bin is None:
            self.dynamic_bin = self._find_dynamic()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        state_file = self.output_dir / MC_STATE_FILE
        stop_file = self.output_dir / MC_STOP_FILE

        if stop_file.exists():
            stop_file.unlink()

        # Generate all case XMLs
        cases = []
        for case_id in range(self.n_cases):
            xml_path, case_dir, case_seed = self._make_case_xml(case_id)
            cases.append({
                'case_id': case_id,
                'xml_path': xml_path,
                'case_dir': case_dir,
                'case_seed': case_seed,
            })

        # Write initial state
        state = {
            'status': 'running',
            'n_cases': self.n_cases,
            'workers': n_workers,
            'master_seed': self.master_seed,
            'started': time.strftime('%Y-%m-%d %H:%M:%S'),
            'running': 0,
            'done': 0,
            'failed': 0,
            'done_list': [],
            'failed_list': [],
            'finished': False,
        }
        state_file.write_text(json.dumps(state, indent=2))

        # Save pre-drawn values
        draws_file = self.output_dir / MC_DRAWS_FILE
        draws_file.write_text(json.dumps({
            'master_seed': self.master_seed,
            'n_cases': self.n_cases,
            'dispersions': [d for d in self.dispersions],
            'draws': self.draws,
        }, indent=2))

        # Run cases
        done = []
        failed = []
        start_time = time.time()

        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            futures = {}
            for case in cases:
                env = os.environ.copy()
                if self.library:
                    env['LD_PRELOAD'] = self.library

                future = pool.submit(
                    subprocess.run,
                    [self.dynamic_bin, case['xml_path']],
                    cwd=case['case_dir'],  # each case writes output to its own dir
                    env=env,
                    capture_output=True,
                    text=True,
                )
                futures[future] = case

            for future in as_completed(futures):
                case = futures[future]
                try:
                    result = future.result()
                    elapsed = time.time() - start_time

                    # Save stdout log
                    log_path = Path(case['case_dir']) / 'sim.log'
                    log_path.write_text(result.stdout + result.stderr)

                    if result.returncode == 0:
                        done.append(case['case_id'])
                        print(f"  ✓ Case {case['case_id']:4d} done")
                    else:
                        failed.append(case['case_id'])
                        print(f"  ✗ Case {case['case_id']:4d} failed (rc={result.returncode})")

                except Exception as e:
                    failed.append(case['case_id'])
                    print(f"  ✗ Case {case['case_id']:4d} error: {e}")

                # Check stop signal
                if stop_file.exists():
                    print("\nStop signal received. Cancelling remaining cases...")
                    pool.shutdown(wait=False, cancel_futures=True)
                    break

                # Update state
                state['done'] = len(done)
                state['failed'] = len(failed)
                state['running'] = self.n_cases - len(done) - len(failed)
                state['elapsed'] = _fmt_elapsed(time.time() - start_time)
                try:
                    state_file.write_text(json.dumps(state, indent=2))
                except Exception:
                    pass

        # Final state
        state['finished'] = True
        state['status'] = 'complete'
        state['elapsed'] = _fmt_elapsed(time.time() - start_time)
        state['done_list'] = sorted(done)
        state['failed_list'] = sorted(failed)
        state_file.write_text(json.dumps(state, indent=2))

        print(f"\n{'=' * 50}")
        print(f"MC complete: {len(done)} succeeded, {len(failed)} failed "
              f"out of {self.n_cases} ({state['elapsed']})")

        return state

    @staticmethod
    def status(output_dir):
        """Read and return the current MC state."""
        state_file = Path(output_dir) / MC_STATE_FILE
        if not state_file.exists():
            return None
        return json.loads(state_file.read_text())

    @staticmethod
    def stop(output_dir):
        """Signal a running MC batch to stop."""
        stop_file = Path(output_dir) / MC_STOP_FILE
        stop_file.write_text("stop")

    def build_index(self):
        """Build aggregated mc_index.json from all completed cases.

        Scans case directories for HDF5/CSV output and collects
        terminal metrics and dispersion draws.
        """
        index = {
            'master_seed': self.master_seed,
            'n_cases': self.n_cases,
            'dispersions': self.dispersions,
            'cases': [],
        }

        for case_id in range(self.n_cases):
            case_dir = self.output_dir / f"case_{case_id:04d}"
            case_entry = {
                'case_id': case_id,
                'case_seed': _derive_case_seed(self.master_seed, case_id),
                'draws': self.draws[case_id] if case_id < len(self.draws) else {},
                'status': 'done' if (case_dir / 'sim.log').exists() else 'missing',
            }
            index['cases'].append(case_entry)

        index_path = self.output_dir / 'mc_index.json'
        index_path.write_text(json.dumps(index, indent=2))
        print(f"Index written to {index_path}")
        return index

    def extremes(self, threshold_sigma=2.0):
        """Find cases with any draw exceeding threshold_sigma.

        Returns list of {'case_id', 'parameter', 'n_sigma'} dicts.
        """
        return extreme_draws(self.draws, threshold_sigma)
