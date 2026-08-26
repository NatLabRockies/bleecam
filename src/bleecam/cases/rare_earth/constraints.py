import math
from math import gamma
import pandas as pd
from pyomo.environ import Expression
from .config import ACTIVE_PROCESS_LOCATIONS, DEMAND_LOCATION, ALLOY

def _fix(var, val=0):
    """Fixes a Pyomo variable to the given value if it is not already fixed, suppressing errors.

    :param var: The Pyomo variable element to fix.
    :type var: pyomo.environ.Var
    :param val: Value to fix the variable to, default 0.
    :type val: float
    """
    if not var.is_fixed():
        try:
            var.fix(val)
        except Exception as _a:
            print(f'ERROR fixing var: {_a}')

def fix_inactive_process_locations(model):
    """Zeros out all flowQ variables whose source or destination location is not active for that process, per ACTIVE_PROCESS_LOCATIONS.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    """
    print('Fixing inactive (process, location) pairs...')
    for _a in model.TimePeriods:
        for _b in model.Processes:
            _c = set(ACTIVE_PROCESS_LOCATIONS.get(_b, []))
            for _d in model.Locations:
                for _e in model.Processes2:
                    _f = set(ACTIVE_PROCESS_LOCATIONS.get(_e, []))
                    for _g in model.Locations:
                        for _h in model.materials:
                            _i = (_a, _b, _d, _e, _g, _h)
                            if _i in model.flowQ:
                                if _d not in _c or _g not in _f:
                                    _fix(model.flowQ[_i])
    print('Done fixing inactive (process, location) pairs.')

def fix_disallowed_trade_flows(model, allowed_trade_arcs):
    """Zeros out all cross-country flowQ variables that are not in the allowed trade arc set.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param allowed_trade_arcs: Set of (process_from, loc_from, process_to, loc_to, material) tuples defining permitted cross-country flows.
    :type allowed_trade_arcs: set[tuple]
    """
    print('Fixing disallowed cross-country trade flows...')
    for _a in model.TimePeriods:
        for _b in model.Processes:
            for _c in model.Locations:
                for _d in model.Processes2:
                    for _e in model.Locations:
                        if _c == _e:
                            continue
                        for _f in model.materials:
                            _g = (_a, _b, _c, _d, _e, _f)
                            if _g not in model.flowQ:
                                continue
                            _h = (_b, _c, _d, _e, _f)
                            if _h not in allowed_trade_arcs:
                                _fix(model.flowQ[_g])
    print('Done fixing disallowed trade flows.')

def clay_mining_constraints(model):
    """Restricts clay mining outflows so that only same-location clay-refining receives ion adsorption clay; all other inflows and outflows are fixed to zero.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    """
    _a = 'clay mining'
    _b = 'clay refining'
    _c = 'ion adsorption clay'
    _d = set(ACTIVE_PROCESS_LOCATIONS.get(_a, []))
    for _e in model.TimePeriods:
        for _f in _d:
            for _g in model.Processes:
                for _h in model.Locations:
                    for _i in model.materials:
                        _j = (_e, _g, _h, _a, _f, _i)
                        if _j in model.flowQ:
                            _fix(model.flowQ[_j])
            for _k in model.Processes2:
                for _l in model.Locations:
                    for _i in model.materials:
                        _j = (_e, _a, _f, _k, _l, _i)
                        if _j in model.flowQ:
                            _m = _k == _b and _l == _f and (_i == _c)
                            if not _m:
                                _fix(model.flowQ[_j])

def clay_refining_constraints(model, yield_factor):
    """Enforces mass-balance and co-product ratio constraints for clay refining: NdOx and DyOx outputs are yield-factor multiples of clay input, and their ratio to each downstream reactor is locked proportionally.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param yield_factor: Mapping of (t, process, location, material) to float yield fraction.
    :type yield_factor: dict
    """
    _a = 'clay refining'
    _b = 'clay mining'
    _c = 'ion adsorption clay'
    _d = 'neodynium_oxide'
    _e = 'dysprosium_oxide'
    _f = ['molten_salt electrolysis', 'metallothermic reduction']
    _g = set(ACTIVE_PROCESS_LOCATIONS.get(_a, []))
    for _h in model.TimePeriods:
        for _i in _g:
            for _j in model.Processes:
                for _k in model.Locations:
                    for _l in model.materials:
                        _m = (_h, _j, _k, _a, _i, _l)
                        if _m in model.flowQ:
                            _n = _j == _b and _k == _i and (_l == _c)
                            if not _n:
                                _fix(model.flowQ[_m])
            _o = (_h, _b, _i, _a, _i, _c)
            _p = model.flowQ[_o] if _o in model.flowQ else 0
            _q = float(yield_factor.get((int(_h), _a, _i, _d), 0.0))
            _r = float(yield_factor.get((int(_h), _a, _i, _e), 0.0))
            (_s, _t) = ([], [])
            for _u in _f:
                for _v in model.Locations:
                    _w = (_h, _a, _i, _u, _v, _d)
                    _x = (_h, _a, _i, _u, _v, _e)
                    if _w in model.flowQ and (not model.flowQ[_w].is_fixed()):
                        _s.append((_v, _u, model.flowQ[_w]))
                    if _x in model.flowQ and (not model.flowQ[_x].is_fixed()):
                        _t.append((_v, _u, model.flowQ[_x]))
            if _s:
                model.constraints.add(sum((_z for (_y, _y, _z) in _s)) == _q * _p)
            if _t:
                model.constraints.add(sum((_z for (_y, _y, _z) in _t)) == _r * _p)
            for _u in _f:
                for _v in model.Locations:
                    _w = (_h, _a, _i, _u, _v, _d)
                    _x = (_h, _a, _i, _u, _v, _e)
                    _aa = _w in model.flowQ and (not model.flowQ[_w].is_fixed())
                    _ab = _x in model.flowQ and (not model.flowQ[_x].is_fixed())
                    if _aa and _ab and (_q > 0) and (_r > 0):
                        model.constraints.add(_r * model.flowQ[_w] == _q * model.flowQ[_x])
                    elif _aa and (not _ab):
                        _fix(model.flowQ[_w])
                    elif _ab and (not _aa):
                        _fix(model.flowQ[_x])
            _ac = {_d, _e}
            _ad = set(_f)
            for _ae in model.Processes2:
                for _v in model.Locations:
                    for _l in model.materials:
                        _m = (_h, _a, _i, _ae, _v, _l)
                        if _m in model.flowQ and (not model.flowQ[_m].is_fixed()):
                            if _ae not in _ad or _l not in _ac:
                                _fix(model.flowQ[_m])

def beneficiation_constraints(model, yield_factor):
    """Links beneficiation outputs (phosphate → H2SO4 digestion, flurocarbonate → HCl digestion) to mining inputs via yield factors, and zeroes out all other flows.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param yield_factor: Mapping of (t, process, location, material) to float yield fraction.
    :type yield_factor: dict
    """
    _a = 'beneficiation'
    _b = 'mining'
    _c = 'sulfuric acid digestion'
    _d = 'hydrochloric acid digestion'
    _e = {'phosphate': {'input_ore': 'monazaite', 'destination': _c}, 'flurocarbonate': {'input_ore': 'bastnasite', 'destination': _d}}
    _f = set(ACTIVE_PROCESS_LOCATIONS.get(_a, []))
    for _g in model.TimePeriods:
        for _h in _f:
            (_i, _j) = (set(), set())
            for (_k, _l) in _e.items():
                _m = _l['input_ore']
                _n = _l['destination']
                _i.add((_b, _h, _m))
                _j.add((_n, _h, _k))
                _o = (_g, _b, _h, _a, _h, _m)
                _p = (_g, _a, _h, _n, _h, _k)
                _q = model.flowQ[_o] if _o in model.flowQ else 0
                _r = model.flowQ[_p] if _p in model.flowQ else 0
                _s = float(yield_factor.get((int(_g), _a, _h, _k), 0.0))
                if _p in model.flowQ:
                    model.constraints.add(_r == _s * _q)
            for _t in model.Processes:
                for _u in model.Locations:
                    for _v in model.materials:
                        _w = (_g, _t, _u, _a, _h, _v)
                        if _w in model.flowQ and (_t, _u, _v) not in _i:
                            _fix(model.flowQ[_w])
            for _x in model.Processes2:
                for _y in model.Locations:
                    for _v in model.materials:
                        _w = (_g, _a, _h, _x, _y, _v)
                        if _w in model.flowQ and (_x, _y, _v) not in _j:
                            _fix(model.flowQ[_w])

def sulfuric_acid_digestion_constraints(model, yield_factor):
    """Enforces that NdOx and DyOx outputs from H2SO4 digestion equal yield-factor multiples of the phosphate input, and fixes all other flows.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param yield_factor: Mapping of (t, process, location, material) to float yield fraction.
    :type yield_factor: dict
    """
    _a = 'sulfuric acid digestion'
    _b = 'beneficiation'
    _c = 'phosphate'
    _d = ['molten_salt electrolysis', 'metallothermic reduction']
    _e = ['neodynium_oxide', 'dysprosium_oxide']
    (_f, _g) = ('neodynium_oxide', 'dysprosium_oxide')
    _h = set(ACTIVE_PROCESS_LOCATIONS.get(_a, []))
    for _i in model.TimePeriods:
        for _j in _h:
            _l = [model.flowQ[_i, _b, _k, _a, _j, _c] for _k in model.Locations if (_i, _b, _k, _a, _j, _c) in model.flowQ and (not model.flowQ[_i, _b, _k, _a, _j, _c].is_fixed())]
            _m = sum(_l) if _l else 0
            _n = float(yield_factor.get((int(_i), _a, _j, _f), 0.0))
            _o = float(yield_factor.get((int(_i), _a, _j, _g), 0.0))
            for _p in _e:
                _q = float(yield_factor.get((int(_i), _a, _j, _p), 0.0))
                _t = [model.flowQ[_i, _a, _j, _r, _s, _p] for _r in _d for _s in model.Locations if (_i, _a, _j, _r, _s, _p) in model.flowQ and (not model.flowQ[_i, _a, _j, _r, _s, _p].is_fixed())]
                if _t:
                    model.constraints.add(sum(_t) == _q * _m)
            for _r in _d:
                for _s in model.Locations:
                    _u = (_i, _a, _j, _r, _s, _f)
                    _v = (_i, _a, _j, _r, _s, _g)
                    _w = _u in model.flowQ and (not model.flowQ[_u].is_fixed())
                    _x = _v in model.flowQ and (not model.flowQ[_v].is_fixed())
                    if _w and _x and (_n > 0) and (_o > 0):
                        model.constraints.add(_o * model.flowQ[_u] == _n * model.flowQ[_v])
                    elif _w and (not _x):
                        _fix(model.flowQ[_u])
                    elif _x and (not _w):
                        _fix(model.flowQ[_v])
            _y = {_c}
            _z = {_b}
            for _aa in model.Processes:
                for _k in model.Locations:
                    for _ab in model.materials:
                        _ac = (_i, _aa, _k, _a, _j, _ab)
                        if _ac in model.flowQ and (not model.flowQ[_ac].is_fixed()):
                            if _aa not in _z or _ab not in _y:
                                _fix(model.flowQ[_ac])
            _ad = {(_r, _p) for _r in _d for _p in _e}
            for _ae in model.Processes2:
                for _s in model.Locations:
                    for _ab in model.materials:
                        _ac = (_i, _a, _j, _ae, _s, _ab)
                        if _ac in model.flowQ and (not model.flowQ[_ac].is_fixed()):
                            if (_ae, _ab) not in _ad:
                                _fix(model.flowQ[_ac])

def hydrochloric_acid_digestion_constraints(model, yield_factor):
    """Enforces that NdOx and DyOx outputs from HCl digestion equal yield-factor multiples of the flurocarbonate input, and fixes all other flows.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param yield_factor: Mapping of (t, process, location, material) to float yield fraction.
    :type yield_factor: dict
    """
    _a = 'hydrochloric acid digestion'
    _b = 'beneficiation'
    _c = 'flurocarbonate'
    _d = ['molten_salt electrolysis', 'metallothermic reduction']
    (_e, _f) = ('neodynium_oxide', 'dysprosium_oxide')
    _g = set(ACTIVE_PROCESS_LOCATIONS.get(_a, []))
    for _h in model.TimePeriods:
        for _i in _g:
            _k = [model.flowQ[_h, _b, _j, _a, _i, _c] for _j in model.Locations if (_h, _b, _j, _a, _i, _c) in model.flowQ and (not model.flowQ[_h, _b, _j, _a, _i, _c].is_fixed())]
            _l = sum(_k) if _k else 0
            _m = float(yield_factor.get((int(_h), _a, _i, _e), 0.0))
            _n = float(yield_factor.get((int(_h), _a, _i, _f), 0.0))
            _q = [model.flowQ[_h, _a, _i, _o, _p, _e] for _o in _d for _p in model.Locations if (_h, _a, _i, _o, _p, _e) in model.flowQ and (not model.flowQ[_h, _a, _i, _o, _p, _e].is_fixed())]
            _r = [model.flowQ[_h, _a, _i, _o, _p, _f] for _o in _d for _p in model.Locations if (_h, _a, _i, _o, _p, _f) in model.flowQ and (not model.flowQ[_h, _a, _i, _o, _p, _f].is_fixed())]
            if _q:
                model.constraints.add(sum(_q) == _m * _l)
            if _r:
                model.constraints.add(sum(_r) == _n * _l)
            for _o in _d:
                for _p in model.Locations:
                    _s = (_h, _a, _i, _o, _p, _e)
                    _t = (_h, _a, _i, _o, _p, _f)
                    _u = _s in model.flowQ and (not model.flowQ[_s].is_fixed())
                    _v = _t in model.flowQ and (not model.flowQ[_t].is_fixed())
                    if _u and _v and (_m > 0) and (_n > 0):
                        model.constraints.add(_n * model.flowQ[_s] == _m * model.flowQ[_t])
                    elif _u and (not _v):
                        _fix(model.flowQ[_s])
                    elif _v and (not _u):
                        _fix(model.flowQ[_t])
            for _w in model.Processes:
                for _j in model.Locations:
                    for _x in model.materials:
                        _y = (_h, _w, _j, _a, _i, _x)
                        if _y in model.flowQ and (not model.flowQ[_y].is_fixed()):
                            if _w != _b or _x != _c:
                                _fix(model.flowQ[_y])
            _aa = {(_o, _z) for _o in _d for _z in [_e, _f]}
            for _ab in model.Processes2:
                for _p in model.Locations:
                    for _x in model.materials:
                        _y = (_h, _a, _i, _ab, _p, _x)
                        if _y in model.flowQ and (not model.flowQ[_y].is_fixed()):
                            if (_ab, _x) not in _aa:
                                _fix(model.flowQ[_y])

def metallothermic_reduction_constraints(model, yield_factor):
    """Links dysprosium metal output from metallothermic reduction to DyOx input via yield factor, and fixes all other flows.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param yield_factor: Mapping of (t, process, location, material) to float yield fraction.
    :type yield_factor: dict
    """
    _a = 'metallothermic reduction'
    _b = ['sulfuric acid digestion', 'hydrochloric acid digestion', 'clay refining']
    _c = 'chemical transformation'
    _d = 'dysprosium_oxide'
    _e = 'dysprosium'
    _f = 'neodynium'
    _g = 'neodynium_oxide'
    _h = set(ACTIVE_PROCESS_LOCATIONS.get(_a, []))
    for _i in model.TimePeriods:
        for _j in _h:
            _m = sum((model.flowQ[_i, _k, _l, _a, _j, _d] for _k in _b for _l in model.Locations if (_i, _k, _l, _a, _j, _d) in model.flowQ and (not model.flowQ[_i, _k, _l, _a, _j, _d].is_fixed())))
            _n = float(yield_factor.get((int(_i), _a, _j, _e), 0.0))
            _p = [model.flowQ[_i, _a, _j, _c, _o, _e] for _o in model.Locations if (_i, _a, _j, _c, _o, _e) in model.flowQ and (not model.flowQ[_i, _a, _j, _c, _o, _e].is_fixed())]
            if _p:
                model.constraints.add(sum(_p) == _n * _m)
            for _q in model.Processes2:
                for _o in model.Locations:
                    _r = (_i, _a, _j, _q, _o, _f)
                    if _r in model.flowQ:
                        _fix(model.flowQ[_r])
            _s = {(_k, _d) for _k in _b}
            _t = {(_k, _g) for _k in _b}
            for _u in model.Processes:
                for _l in model.Locations:
                    for _v in model.materials:
                        _r = (_i, _u, _l, _a, _j, _v)
                        if _r in model.flowQ and (not model.flowQ[_r].is_fixed()):
                            if (_u, _v) not in _s and (_u, _v) not in _t:
                                _fix(model.flowQ[_r])
            for _q in model.Processes2:
                for _o in model.Locations:
                    for _v in model.materials:
                        _r = (_i, _a, _j, _q, _o, _v)
                        if _r in model.flowQ and (not model.flowQ[_r].is_fixed()):
                            if _q != _c or _v != _e:
                                _fix(model.flowQ[_r])

def molten_salt_electrolysis_constraints(model, yield_factor):
    """Links neodymium metal output from molten-salt electrolysis to NdOx input via yield factor, and fixes all other flows.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param yield_factor: Mapping of (t, process, location, material) to float yield fraction.
    :type yield_factor: dict
    """
    _a = 'molten_salt electrolysis'
    _b = ['sulfuric acid digestion', 'hydrochloric acid digestion', 'clay refining']
    _c = 'chemical transformation'
    _d = 'neodynium_oxide'
    _e = 'neodynium'
    _f = 'dysprosium'
    _g = 'dysprosium_oxide'
    _h = set(ACTIVE_PROCESS_LOCATIONS.get(_a, []))
    for _i in model.TimePeriods:
        for _j in _h:
            _m = sum((model.flowQ[_i, _k, _l, _a, _j, _d] for _k in _b for _l in model.Locations if (_i, _k, _l, _a, _j, _d) in model.flowQ and (not model.flowQ[_i, _k, _l, _a, _j, _d].is_fixed())))
            _n = float(yield_factor.get((int(_i), _a, _j, _e), 0.0))
            _p = [model.flowQ[_i, _a, _j, _c, _o, _e] for _o in model.Locations if (_i, _a, _j, _c, _o, _e) in model.flowQ and (not model.flowQ[_i, _a, _j, _c, _o, _e].is_fixed())]
            if _p:
                model.constraints.add(sum(_p) == _n * _m)
            for _q in model.Processes2:
                for _o in model.Locations:
                    _r = (_i, _a, _j, _q, _o, _f)
                    if _r in model.flowQ:
                        _fix(model.flowQ[_r])
            _s = {(_k, _d) for _k in _b}
            _t = {(_k, _g) for _k in _b}
            for _u in model.Processes:
                for _l in model.Locations:
                    for _v in model.materials:
                        _r = (_i, _u, _l, _a, _j, _v)
                        if _r in model.flowQ and (not model.flowQ[_r].is_fixed()):
                            if (_u, _v) not in _s and (_u, _v) not in _t:
                                _fix(model.flowQ[_r])
            for _q in model.Processes2:
                for _o in model.Locations:
                    for _v in model.materials:
                        _r = (_i, _a, _j, _q, _o, _v)
                        if _r in model.flowQ and (not model.flowQ[_r].is_fixed()):
                            if _q != _c or _v != _e:
                                _fix(model.flowQ[_r])

def chemical_transformation_constraints(model, yield_factor, ct_mass_ratio_by_t, list_of_processes):
    """Enforces mass-balance for NdFeB alloy production: alloy output equals yield-factor × iron input, and Nd/Dy inputs are set by the time-varying mass-ratio fractions of the alloy output.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param yield_factor: Mapping of (t, process, location, material) to float yield fraction.
    :type yield_factor: dict
    :param ct_mass_ratio_by_t: Time period to (Nd_mass_fraction, Dy_mass_fraction) for the alloy.
    :type ct_mass_ratio_by_t: dict[int, tuple[float, float]]
    :param list_of_processes: Full list of process names for iterating destinations.
    :type list_of_processes: list[str]
    """
    _a = 'chemical transformation'
    _b = 'magnet manufacturing'
    _c = ALLOY
    (_d, _e, _f) = ('neodynium', 'dysprosium', 'iron')
    _g = ['molten_salt electrolysis']
    _h = ['metallothermic reduction']
    _i = list_of_processes
    _j = set(ACTIVE_PROCESS_LOCATIONS.get(_a, []))
    for _k in model.TimePeriods:
        for _l in _j:
            (_m, _n) = ct_mass_ratio_by_t.get(int(_k))
            _q = sum((model.flowQ[_k, _o, _p, _a, _l, _d] for _o in _g for _p in model.Locations if (_k, _o, _p, _a, _l, _d) in model.flowQ and (not model.flowQ[_k, _o, _p, _a, _l, _d].is_fixed())))
            _r = sum((model.flowQ[_k, _o, _p, _a, _l, _e] for _o in _h for _p in model.Locations if (_k, _o, _p, _a, _l, _e) in model.flowQ and (not model.flowQ[_k, _o, _p, _a, _l, _e].is_fixed())))
            _s = sum((model.flowQ[_k, _o, _p, _a, _l, _f] for _o in _i for _p in model.Locations if (_k, _o, _p, _a, _l, _f) in model.flowQ and (not model.flowQ[_k, _o, _p, _a, _l, _f].is_fixed())))
            _t = float(yield_factor.get((int(_k), _a, _l, _c), 1.0))
            _v = [model.flowQ[_k, _a, _l, _b, _u, _c] for _u in model.Locations if (_k, _a, _l, _b, _u, _c) in model.flowQ and (not model.flowQ[_k, _a, _l, _b, _u, _c].is_fixed())]
            if _v:
                model.constraints.add(sum(_v) == _t * (_q + _r + _s))
            model.constraints.add(_n * _q == _m * _r)
            model.constraints.add(_s == 2 * (_q + _r))
            _w = {(_o, _d) for _o in _g} | {(_o, _e) for _o in _h} | {(_o, _f) for _o in _i}
            for _x in model.Processes:
                for _p in model.Locations:
                    for _y in model.materials:
                        _z = (_k, _x, _p, _a, _l, _y)
                        if _z in model.flowQ and (not model.flowQ[_z].is_fixed()):
                            if (_x, _y) not in _w:
                                _fix(model.flowQ[_z])
            for _aa in model.Processes2:
                for _u in model.Locations:
                    for _y in model.materials:
                        _z = (_k, _a, _l, _aa, _u, _y)
                        if _z in model.flowQ and (not model.flowQ[_z].is_fixed()):
                            if _aa != _b or _y != _c:
                                _fix(model.flowQ[_z])

def magnet_manufacturing_constraints(model, yield_factor):
    """Links hp_magnet output from magnet manufacturing to alloy input via yield factor, and fixes irrelevant flows.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param yield_factor: Mapping of (t, process, location, material) to float yield fraction.
    :type yield_factor: dict
    """
    _a = 'magnet manufacturing'
    _b = 'chemical transformation'
    _c = 'magnet_market_mix'
    _d = ['hydrometallurgical', 'pyrometallurgical', 'cryogenic']
    _e = ALLOY
    _f = 'hp_magnet'
    _g = set(ACTIVE_PROCESS_LOCATIONS.get(_a, []))
    for _h in model.TimePeriods:
        for _i in _g:
            _j = float(yield_factor.get((int(_h), _a, _i, _f), 1.0))
            _l = sum((model.flowQ[_h, _b, _k, _a, _i, _e] for _k in model.Locations if (_h, _b, _k, _a, _i, _e) in model.flowQ and (not model.flowQ[_h, _b, _k, _a, _i, _e].is_fixed())))
            _n = sum((model.flowQ[_h, _m, DEMAND_LOCATION, _a, _i, _e] for _m in _d if (_h, _m, DEMAND_LOCATION, _a, _i, _e) in model.flowQ and (not model.flowQ[_h, _m, DEMAND_LOCATION, _a, _i, _e].is_fixed())))
            _o = [model.flowQ[_h, _a, _i, _c, DEMAND_LOCATION, _f]] if (_h, _a, _i, _c, DEMAND_LOCATION, _f) in model.flowQ else []
            if _o:
                model.constraints.add(_j * _l + _n == _o[0])
            _p = {(_b, _e)} | {(_m, _e) for _m in _d}
            for _q in model.Processes:
                for _k in model.Locations:
                    for _r in model.materials:
                        _s = (_h, _q, _k, _a, _i, _r)
                        if _s in model.flowQ and (not model.flowQ[_s].is_fixed()):
                            if (_q, _r) not in _p:
                                _fix(model.flowQ[_s])
            for _t in model.Processes2:
                for _u in model.Locations:
                    for _r in model.materials:
                        _s = (_h, _a, _i, _t, _u, _r)
                        if _s in model.flowQ and (not model.flowQ[_s].is_fixed()):
                            if _t != _c or _u != DEMAND_LOCATION or _r != _f:
                                _fix(model.flowQ[_s])

def magnet_market_mix_constraints(model, high_perf_magnet_required):
    """Routes the hp_magnet market mix output to the use-phase at the demand location, fixing flows equal to total demand for each period.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param high_perf_magnet_required: Time period to required hp_magnet quantity (in FLOW_SCALE units).
    :type high_perf_magnet_required: dict[int, float]
    """
    _a = 'magnet_market_mix'
    _b = DEMAND_LOCATION
    _c = 'magnet manufacturing'
    _d = 'magnet-to-magnet recycling'
    _e = 'direct reuse'
    _f = 'use phase'
    _g = 'hp_magnet'
    _h = set(ACTIVE_PROCESS_LOCATIONS.get(_c, []))
    _i = [_d, _e]
    _l = {(_c, _j, _g) for _j in _h} | {(_k, _b, _g) for _k in _i}
    _m = (_f, _b, _g)
    for _n in model.TimePeriods:
        _q = sum((model.flowQ[_n, _o, _j, _a, _b, _g] for (_o, _j, _p) in _l if (_n, _o, _j, _a, _b, _g) in model.flowQ))
        _r = model.flow_from_stock[_n, _g] if (_n, _g) in model.flow_from_stock else 0
        _s = model.flow_to_stock[_n, _g] if (_n, _g) in model.flow_to_stock else 0
        _t = (_n, _a, _b, _f, _b, _g)
        _u = model.flowQ[_t] if _t in model.flowQ else 0
        model.constraints.add(_q + _r == _u + _s)
        for _o in model.Processes:
            for _j in model.Locations:
                for _p in model.materials:
                    _v = (_n, _o, _j, _a, _b, _p)
                    if _v in model.flowQ and (not model.flowQ[_v].is_fixed()):
                        if (_o, _j, _p) not in _l:
                            _fix(model.flowQ[_v])
        for _w in model.Processes2:
            for _x in model.Locations:
                for _p in model.materials:
                    _v = (_n, _a, _b, _w, _x, _p)
                    if _v in model.flowQ and (not model.flowQ[_v].is_fixed()):
                        if (_w, _x, _p) != _m:
                            _fix(model.flowQ[_v])

def demand_fulfillment_constraints(model, high_perf_magnet_required):
    """Adds constraints requiring that total hp_magnet inflow to the use phase equals demand for each time period, using slack variables to allow infeasibility detection.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param high_perf_magnet_required: Time period to required hp_magnet quantity (in FLOW_SCALE units).
    :type high_perf_magnet_required: dict[int, float]
    """
    _a = 'magnet_market_mix'
    _b = 'use phase'
    _c = DEMAND_LOCATION
    _d = 'hp_magnet'
    for _e in model.TimePeriods:
        _f = high_perf_magnet_required.get(_e, 0)
        _g = (_e, _a, _c, _b, _c, _d)
        if _g in model.flowQ:
            model.constraints.add(model.flowQ[_g] + model.demand_slack_pos[_e] - model.demand_slack_neg[_e] == _f)
        for _h in model.materials:
            if _h != _d:
                _i = (_e, _a, _c, _b, _c, _h)
                if _i in model.flowQ:
                    _fix(model.flowQ[_i])
        for _j in model.Processes2:
            for _k in model.Locations:
                for _h in model.materials:
                    _l = (_e, _a, _c, _j, _k, _h)
                    if _l in model.flowQ and (not model.flowQ[_l].is_fixed()):
                        if _j != _b or _k != _c or _h != _d:
                            _fix(model.flowQ[_l])
        for _m in model.Processes:
            for _n in model.Locations:
                for _h in model.materials:
                    _o = (_e, _m, _n, _b, _c, _h)
                    if _o in model.flowQ and (not model.flowQ[_o].is_fixed()):
                        if _m != _a or _n != _c or _h != _d:
                            _fix(model.flowQ[_o])

def weibull_historic_retirement(model, data_dir='./data'):
    """Computes historic in-use magnet retirements per time period using a Weibull lifetime distribution fitted to fleet deployment data loaded from CSV.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param data_dir: Directory containing Demand_Input_Template.csv.
    :type data_dir: str or Path
    :returns: Time period to historic retirement quantity (in FLOW_SCALE units).
    :rtype: dict[int, float]
    """
    _a = pd.read_excel(f'{data_dir}/historic_installs.xlsx')
    _a = _a[['year', 'original']].rename(columns={'original': 'installs'}).dropna()
    _a['year'] = _a['year'].astype(int)
    _a['installs'] = _a['installs'].astype(float)
    _a = _a[(_a['year'] >= 2000) & (_a['year'] <= 2024)].copy()
    _b = 1.5
    _c = 31.1
    _d = _c / gamma(1.0 + 1.0 / _b)

    def F_weibull(a):
        return 0.0 if a <= 0 else 1.0 - math.exp(-(a / _d) ** _b)

    def delta_F(a):
        return max(0.0, F_weibull(a + 1.0) - F_weibull(a))
    _e = 2025
    _g = {int(_f): 0.0 for _f in model.TimePeriods}
    for _f in model.TimePeriods:
        _h = _e + int(_f)
        for (_i, _j) in _a.iterrows():
            _k = _h - int(_j['year'])
            if _k >= 0:
                _g[int(_f)] += float(_j['installs']) * delta_F(_k)
    print('Weibull retirements computed.')
    return _g

def use_phase_stock_constraints(model, retirement_rate=0.02, initial_use_stock=0.0, historic_retirements_by_t=None):
    """Adds stock balance constraints for the in-use magnet fleet, accounting for annual retirements flowing to end-of-life routes.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param retirement_rate: Annual fraction of in-use stock that retires, default 0.02.
    :type retirement_rate: float
    :param initial_use_stock: Initial installed magnet stock at t=0, default 0.0.
    :type initial_use_stock: float
    :param historic_retirements_by_t: Pre-computed Weibull retirements by period; if None, uses a simple rate-based calculation.
    :type historic_retirements_by_t: dict[int, float] or None
    """
    _a = 'use phase'
    _b = 'magnet_market_mix'
    _c = DEMAND_LOCATION
    _d = 'hp_magnet'
    _e = ['direct reuse', 'magnet-to-magnet recycling', 'hydrometallurgical', 'pyrometallurgical', 'cryogenic', 'export']
    if historic_retirements_by_t is None:
        historic_retirements_by_t = {int(_f): 0.0 for _f in model.TimePeriods}

    def inflow_at(t):
        __a = (t, _b, _c, _a, _c, _d)
        return model.flowQ[__a] if __a in model.flowQ else 0

    def outflow_sum_at(t):
        return sum((model.flowQ[t, _a, _c, __a, _c, _d] for __a in _e if (t, _a, _c, __a, _c, _d) in model.flowQ))
    for _f in model.TimePeriods:
        _g = initial_use_stock if _f == model.T_min else model.use_stock[_f - 1]
        model.constraints.add(outflow_sum_at(_f) <= retirement_rate * _g + float(historic_retirements_by_t[int(_f)]))
        _h = retirement_rate * _g
        _i = initial_use_stock if _f == model.T_min else model.use_stock[_f - 1]
        model.constraints.add(model.use_stock[_f] == _i + inflow_at(_f) - _h)
    for _f in model.TimePeriods:
        for _j in model.Processes2:
            for _k in model.Locations:
                for _l in model.materials:
                    _m = (_f, _a, _c, _j, _k, _l)
                    if _m in model.flowQ and (_l != _d or _j not in _e or _k != _c):
                        _fix(model.flowQ[_m])
        for _n in model.Processes:
            for _o in model.Locations:
                for _l in model.materials:
                    _m = (_f, _n, _o, _a, _c, _l)
                    if _m in model.flowQ and (_l != _d or _n != _b or _o != _c):
                        _fix(model.flowQ[_m])

def fix_eol_outflows_at_t0(model):
    """Fixes all end-of-life outflows from the use phase at t=0 to zero, since no retirements occur at the first period.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    """
    _a = model.T_min
    _b = DEMAND_LOCATION
    _c = ['direct reuse', 'magnet-to-magnet recycling', 'hydrometallurgical', 'pyrometallurgical', 'cryogenic', 'export']
    for _d in _c:
        for _e in model.Processes2:
            for _f in model.Locations:
                for _g in model.materials:
                    _h = (_a, _d, _b, _e, _f, _g)
                    if _h in model.flowQ and (not model.flowQ[_h].is_fixed()):
                        _fix(model.flowQ[_h])

def _eol_lagged_constraints(model, recovery_rate, current_process, destination_process, input_output_map):
    """Adds lagged mass-balance constraints for a generic end-of-life recycling route, linking t-1 retirements to t outputs via recovery rates.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param recovery_rate: Mapping of (t, src, src_loc, dst, dst_loc, mat) to float recovery fraction.
    :type recovery_rate: dict
    :param current_process: Name of the EOL recycling process (e.g. 'direct reuse').
    :type current_process: str
    :param destination_process: Name of the downstream process receiving recovered material.
    :type destination_process: str
    :param input_output_map: Maps each output material to its corresponding input material and recovery key tuple.
    :type input_output_map: dict
    """
    _a = 'use phase'
    _b = DEMAND_LOCATION
    _c = list(input_output_map.keys())
    _d = list(set(input_output_map.values()))
    for _e in model.TimePeriods:
        if _e + 1 in model.TimePeriods:
            for (_f, _g) in input_output_map.items():
                _h = (_e, _a, _b, current_process, _b, _f)
                _i = (_e + 1, current_process, _b, destination_process, _b, _g)
                _j = (_e, _a, _b, current_process, _b, _f)
                _k = model.flowQ[_h] if _h in model.flowQ else 0
                _l = model.flowQ[_i] if _i in model.flowQ else 0
                try:
                    _m = float(recovery_rate[_j])
                except KeyError:
                    print(f'  ERROR ({current_process}): Recovery rate missing {_j}.')
                    continue
                model.constraints.add(_l == _m * _k)
        for _n in model.materials:
            if _n not in _c:
                _o = (_e, _a, _b, current_process, _b, _n)
                if _o in model.flowQ and (not model.flowQ[_o].is_fixed()):
                    _fix(model.flowQ[_o])
            for _p in model.Processes:
                for _q in model.Locations:
                    if _p != _a or _q != _b:
                        _o = (_e, _p, _q, current_process, _b, _n)
                        if _o in model.flowQ and (not model.flowQ[_o].is_fixed()):
                            _fix(model.flowQ[_o])
            if _e + 1 in model.TimePeriods:
                if _n not in _d:
                    _o = (_e + 1, current_process, _b, destination_process, _b, _n)
                    if _o in model.flowQ and (not model.flowQ[_o].is_fixed()):
                        _fix(model.flowQ[_o])
                for _r in model.Processes2:
                    for _s in model.Locations:
                        if _r != destination_process or _s != _b:
                            _o = (_e + 1, current_process, _b, _r, _s, _n)
                            if _o in model.flowQ and (not model.flowQ[_o].is_fixed()):
                                _fix(model.flowQ[_o])
    _t = model.T_min
    for _n in model.materials:
        _o = (_t, current_process, _b, destination_process, _b, _n)
        if _o in model.flowQ and (not model.flowQ[_o].is_fixed()):
            _fix(model.flowQ[_o])

def direct_reuse_constraints(model, recovery_rate):
    """Applies lagged EOL constraints for the direct reuse pathway.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param recovery_rate: Mapping of (t, src, src_loc, dst, dst_loc, mat) to float recovery fraction.
    :type recovery_rate: dict
    """
    _eol_lagged_constraints(model, recovery_rate, current_process='direct reuse', destination_process='magnet_market_mix', input_output_map={'hp_magnet': 'hp_magnet'})

def magnet_to_magnet_recycling_constraints(model, recovery_rate):
    """Applies lagged EOL constraints for the magnet-to-magnet recycling pathway.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param recovery_rate: Mapping of (t, src, src_loc, dst, dst_loc, mat) to float recovery fraction.
    :type recovery_rate: dict
    """
    _eol_lagged_constraints(model, recovery_rate, current_process='magnet-to-magnet recycling', destination_process='magnet_market_mix', input_output_map={'hp_magnet': 'hp_magnet'})

def hydrometallurgical_constraints(model, recovery_rate):
    """Applies lagged EOL constraints for the hydrometallurgical recycling pathway.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param recovery_rate: Mapping of (t, src, src_loc, dst, dst_loc, mat) to float recovery fraction.
    :type recovery_rate: dict
    """
    _eol_lagged_constraints(model, recovery_rate, current_process='hydrometallurgical', destination_process='magnet manufacturing', input_output_map={'hp_magnet': ALLOY})

def pyrometallurgical_constraints(model, recovery_rate):
    """Applies lagged EOL constraints for the pyrometallurgical recycling pathway.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param recovery_rate: Mapping of (t, src, src_loc, dst, dst_loc, mat) to float recovery fraction.
    :type recovery_rate: dict
    """
    _eol_lagged_constraints(model, recovery_rate, current_process='pyrometallurgical', destination_process='magnet manufacturing', input_output_map={'hp_magnet': ALLOY})

def cryogenic_constraints(model, recovery_rate):
    """Applies lagged EOL constraints for the cryogenic recycling pathway.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param recovery_rate: Mapping of (t, src, src_loc, dst, dst_loc, mat) to float recovery fraction.
    :type recovery_rate: dict
    """
    _eol_lagged_constraints(model, recovery_rate, current_process='cryogenic', destination_process='magnet manufacturing', input_output_map={'hp_magnet': ALLOY})

def add_stock_constraints(model, initial_stock, max_stock_capacity):
    """Adds inventory balance constraints (stock[t] = stock[t-1] + inflow - outflow) and capacity upper bounds for all stock materials.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param initial_stock: Material to initial inventory level (in FLOW_SCALE units).
    :type initial_stock: dict[str, float]
    :param max_stock_capacity: Mapping of (t, material) to maximum allowable stock level (in FLOW_SCALE units).
    :type max_stock_capacity: dict[tuple, float]
    """
    print('Applying stock constraints...')
    for _a in model.TimePeriods:
        for _b in model.StockMaterials:
            _c = initial_stock.get(_b, 0) if _a == model.T_min else model.stock_level[_a - 1, _b]
            model.constraints.add(model.stock_level[_a, _b] == _c + model.flow_to_stock[_a, _b] - model.flow_from_stock[_a, _b])
            try:
                model.constraints.add(model.stock_level[_a, _b] <= max_stock_capacity[_a, _b])
            except KeyError:
                print(f'  WARNING: No stock capacity for {(_a, _b)}')
            model.constraints.add(model.flow_to_stock[_a, _b] * model.flow_from_stock[_a, _b] == 0)
    print('Stock constraints applied.')

def apply_capacity_constraints(model, max_output_capacity):
    """Adds upper-bound constraints on total process output per (process, location, material) tuple, using the time-varying capacity map.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param max_output_capacity: Mapping of (process, location, material) to dict[int, float] mapping time period to capacity upper bound (in FLOW_SCALE units).
    :type max_output_capacity: dict
    """
    _a = {'magnet_market_mix', 'use phase'}
    for ((_b, _c, _d), _e) in max_output_capacity.items():
        if _b in _a:
            continue
        for (_f, _g) in _e.items():
            if _f not in model.TimePeriods:
                continue
            _j = [model.flowQ[_f, _b, _c, _h, _i, _d] for _h in model.Processes2 for _i in model.Locations if (_f, _b, _c, _h, _i, _d) in model.flowQ]
            if not _j:
                continue
            if _g == 0:
                for _k in _j:
                    if not _k.is_fixed():
                        _k.fix(0)
            else:
                model.constraints.add(sum(_j) <= _g)

def add_unused_oxides_tracking(model, locations):
    """Adds a Pyomo Expression for the total volume of co-product oxides routed to processes that cannot use them (DyOx to MSE, NdOx to metallothermic reduction), tracking the unused-oxide penalty basis.

    :param model: The BLEECAM Pyomo model.
    :type model: pyomo.environ.ConcreteModel
    :param locations: List of all location codes (e.g. ['CN','JP','AU',...]).
    :type locations: list[str]
    """
    _a = ['sulfuric acid digestion', 'hydrochloric acid digestion', 'clay refining']
    _b = 'molten_salt electrolysis'
    _c = 'metallothermic reduction'
    _d = 'neodynium_oxide'
    _e = 'dysprosium_oxide'
    model.unused_DyOx_to_MSE = Expression(model.TimePeriods, rule=lambda m, t: sum((m.flowQ[t, _f, _g, _b, _h, _e] for _f in _a for _g in locations for _h in locations if (t, _f, _g, _b, _h, _e) in m.flowQ)))
    model.unused_NdOx_to_MR = Expression(model.TimePeriods, rule=lambda m, t: sum((m.flowQ[t, _f, _g, _c, _h, _d] for _f in _a for _g in locations for _h in locations if (t, _f, _g, _c, _h, _d) in m.flowQ)))
    model.unused_oxides = Expression(model.TimePeriods, rule=lambda m, t: m.unused_DyOx_to_MSE[t] + m.unused_NdOx_to_MR[t])
    model.total_unused_oxides = Expression(expr=sum((model.unused_oxides[_i] for _i in model.TimePeriods)))