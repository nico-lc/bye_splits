# coding: utf-8

_all_ = [ 'EventData' ]

import os
from pathlib import Path
import sys
parent_dir = os.path.abspath(__file__ + 2 * '/..')
sys.path.insert(0, parent_dir)

import shutil
import yaml
import uproot as up
import pandas as pd
import awkward as ak
import dask.dataframe as dd

from utils import params
from data_handle.base import BaseData

class EventData(BaseData):
    def __init__(self, inname='', tag='v0', default_events=[], reprocess=False):
        super().__init__(inname, tag)
        
        with open(params.viz_kw['CfgEventPath'], 'r') as afile:
            cfg = yaml.safe_load(afile)
            self.var = cfg['varEvents']
            
        self.cache = None
        self.events = default_events
        self.cache_events(self.events, reprocess=reprocess)

    def cache_events(self, events, reprocess):
        """Read dataset from parquet to cache"""
        if not os.path.exists(self.outpath) or reprocess:
            self.store()
        if not isinstance(events, (tuple,list)):
            events = [events]

        ds = ak.from_parquet(self.outpath)
        evmask = False
        for ev in events:
            evmask = evmask | (ds.event==ev)
        ds = ak.to_dataframe(ds[evmask])

        if not self.cache: #first cache_events() call
            self.cache = ds
        else:
            self.cache = dd.concat([self.cache, ds], axis=0)
        #self.cache = self.cache.persist() only for dask dataframes

    def provide(self):
        if not os.path.exists(self.outpath):
            self.store()
        return ak.from_parquet(self.outpath)

    def provide_event(self, event):
        """Provide single event, checking if it is in cache"""
        if event not in self.events:
            self.events += [event]
            self.cache_events(event, False)
        ret = self.cache[self.cache.event==event].drop(['event'], axis=1)
        ret = ret.apply(pd.Series.explode).reset_index(drop=True)
        return ret
    
    def select(self):
        adir = 'FloatingpointMixedbcstcrealsig4DummyHistomaxxydr015GenmatchGenclustersntuple'
        atree = 'HGCalTriggerNtuple'
        print('chec 0')
        with up.open(str(self.inpath), array_cache='550 MB', num_workers=8) as f:
            # print(tree.show())
            tree = f[adir + '/' + atree]
            data = tree.arrays(filter_name='/' + '|'.join(self.var.values()) + '/',
                               library='ak',
                               #entry_stop=50, debug
                               )
        # data[self.var.v] = data.waferv
        # data[self.newvar.vs] = -1 * data.waferv
        # data[self.newvar.c] = "#8a2be2"
        return data

    def store(self):
        data = self.select()
        if os.path.exists(self.outpath):
            shutil.rmtree(self.outpath)
        print('chec A')
        ak.to_parquet(data, self.outpath)
        print('chec B')
