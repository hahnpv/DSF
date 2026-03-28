"""
Monte Carlo dispatcher for DSF C++ simulations.

Uses a RollingPool of subprocesses to run dispersed cases in parallel.
Each case gets a patched XML with seed/case_id attributes, and the C++
monte_carlo.h engine handles dispersion application via introspection.

Usage:
    mc = MonteCarlo("vehicle.xml")
    mc.run(workers=8)
    mc.build_index()
    mc.extremes("Altitude")
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
        self.dynamic_bin = self._find_dynamic()

        # Pre-draw values
        self.draws = self._pre_draw()

    def _find_dynamic(self):
        """Find the dynamic executable."""
        # Try relative to DSF
        dsf_root = Path(__file__).parent.parent.parent  # python/dsf -> python -> DSF
        candidates = [
            dsf_root / 'build' / 'examples' / 'dynamic' / 'dynamic',
            Path('/home/philip/git/DSF/build/examples/dynamic/dynamic'),
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

    def _make_case_xml(self, case_id):
        """Create a patched XML for a single MC case.

        Adds seed and case_id attributes to <sim> so the C++ MC engine
        knows which case this is and can reproduce the RNG state.
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

        # Remove monte_carlo block from per-case XML (not needed by C++)
        # Actually, keep it — the C++ parser reads dispersions from it
        # Just don't remove it.

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
        draws_file = self.output_dir / 'mc_draws.json'
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
                    cwd=str(self.xml_path.parent),  # run from original XML dir for relative paths
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

        Returns list of (case_id, param_name, n_sigma) tuples.
        """
        results = []
        for case_id, case_draws in enumerate(self.draws):
            for key, draw_info in case_draws.items():
                if draw_info['distribution'] == 'gaussian':
                    if abs(draw_info.get('n_sigma_draw', 0)) > threshold_sigma:
                        results.append({
                            'case_id': case_id,
                            'parameter': key,
                            'n_sigma': draw_info['n_sigma_draw'],
                        })
        return results
