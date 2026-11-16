"""Canonical lock identity prevents scheduling races through equivalent URL IDs."""
from uuid import UUID
from app.services.state import lock_resources


class Recorder:
    def __init__(self):self.keys=[]
    def execute(self,statement,params):self.keys.append(params['key'])


def test_equivalent_uuid_spellings_share_one_lock():
    lodge='abcdefab-cdef-4abc-8def-abcdefabcdef'
    unit='fedcbafe-dcba-4fed-8cba-fedcbafedcba'
    lower,upper,typed=Recorder(),Recorder(),Recorder()
    lock_resources(lower,lodge,('unit',unit))
    lock_resources(upper,lodge.upper(),('unit',unit.upper()))
    lock_resources(typed,UUID(lodge),('unit',UUID(unit)))
    assert lower.keys==upper.keys==typed.keys


def test_resource_locks_deduplicate_and_use_stable_order():
    lodge='abcdefab-cdef-4abc-8def-abcdefabcdef'
    unit='fedcbafe-dcba-4fed-8cba-fedcbafedcba'
    a,b=Recorder(),Recorder()
    lock_resources(a,lodge,('vehicle',unit),('staff',unit),('vehicle',unit.upper()),('guest',None))
    lock_resources(b,lodge,('staff',unit),('vehicle',unit))
    assert a.keys==b.keys and len(a.keys)==2
