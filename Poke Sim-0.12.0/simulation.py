"""Shared identities and cooperative deadlines for deterministic simulations."""
import time


class SimulationTimeout(TimeoutError):
    """The search deadline expired; keep the last accepted builds."""


def check_deadline(deadline):
    if deadline is not None and time.monotonic() >= deadline:
        raise SimulationTimeout('search time budget reached')


def freeze(value):
    """Immutable identity for JSON-like specs and rules, preserving move order."""
    if isinstance(value, dict):
        return tuple((k, freeze(v)) for k, v in sorted(value.items()))
    if isinstance(value, (tuple, list)):
        return tuple(map(freeze, value))
    return value


def battle_signature(spec, natures=None):
    """Keep effective stats and the build inputs used by in-battle form changes."""
    identity = {k: v for k, v in spec.items() if k not in ('build', 'nature')}
    if 'build' in spec:
        build = spec['build']
        nature = build.get('nature')
        modifiers = (natures or {}).get(nature, nature)
        evs = tuple(build.get('evs', {}).get(k, 0) for k in ('hp','atk','defn','spa','sdf','spe'))
        # Sky Shaymin reversion recalculates stats using these original inputs.
        # Called/copied Transform can reach that state from other species too.
        identity['form_stat_inputs'] = (modifiers, evs)
    return freeze(identity)
