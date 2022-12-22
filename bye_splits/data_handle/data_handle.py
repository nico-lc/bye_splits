# coding: utf-8

_all_ = [ 'data_handle' ]

import os
from pathlib import Path
import sys
parent_dir = os.path.abspath(__file__ + 2 * '/..')
sys.path.insert(0, parent_dir)

import yaml

from utils import params
from data_handle.geometry import GeometryData
from data_handle.event import EventData

class EventDataParticle:
    def __init__(self, particles, tag, reprocess=False):
        assert particles in ('photons', 'electrons')
        self.particles = particles
        self.tag = self.particles + '_' + tag
        with open(params.viz_kw['CfgEventPath'], 'r') as afile:
            self.config = yaml.safe_load(afile)

        in_name = '_'.join(('skim', self.particles, '0PU_bc_stc_hadd.root'))    
        default_events = self.config['defaultEvents'][self.particles]
        self.data = EventData(in_name, self.tag, default_events, reprocess=reprocess)

    def provide_event(self, event):
        return self.data.provide_event(event)
