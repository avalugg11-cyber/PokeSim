"""Shared semantic validation for CLI and dashboard options."""
import math

BOUNDS = {'passes':(1,100), 'sample':(1,999), 'screen_games':(1,999),
          'confirm_games':(1,999), 'limit':(0,999), 'games':(1,999), 'procs':(1,256)}

def validate(options):
    out = dict(options)
    for key,(low,high) in BOUNDS.items():
        value=out.get(key)
        if value in (None,''):continue
        if isinstance(value,bool):raise ValueError(f'{key} must be an integer')
        try:
            number=int(value)
        except (ValueError,TypeError,OverflowError):raise ValueError(f'{key} must be an integer') from None
        if str(number)!=str(value).strip() or not low<=number<=high:
            raise ValueError(f'{key} must be an integer in {low}..{high}')
        out[key]=number
    for key,low,high in [('margin',0,100),('minutes',0,1000000)]:
        value=out.get(key)
        if value in (None,''):continue
        try:number=float(value)
        except (TypeError,ValueError,OverflowError):raise ValueError(f'{key} must be a finite number') from None
        if not math.isfinite(number) or not low<=number<=high:raise ValueError(f'{key} must be in {low}..{high}')
        out[key]=number
    if out.get('seed') not in (None,''):
        value=out['seed']
        try:number=int(value)
        except (TypeError,ValueError,OverflowError):raise ValueError('seed must be an integer') from None
        if isinstance(value,bool) or str(number)!=str(value).strip():raise ValueError('seed must be an integer')
        out['seed']=number
    return out
