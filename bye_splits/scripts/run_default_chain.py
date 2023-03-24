# coding: utf-8

_all_ = []

import os
from pathlib import Path
import sys

parent_dir = os.path.abspath(__file__ + 2 * "/..")
sys.path.insert(0, parent_dir)

import tasks
import utils
from utils import params, common, parsing
import data_handle
from data_handle.data_process import EventDataParticle, get_data_reco_chain_start
from data_handle.geometry import GeometryData
import plot
from plot import chain_plotter

import argparse
import pandas as pd


def run_chain(pars):
    """Run the backend stage 2 reconstruction chain for a single event."""
    df_out = None

    df_gen, df_cl, df_tc = get_data_reco_chain_start(nevents=100, reprocess=True)

    print("There are {} events in the input.".format(df_gen.shape[0]))

    if not pars.no_fill:
        fill_d = params.read_task_params("fill")
        tasks.fill.fill(pars, df_gen, df_cl, df_tc, **fill_d)

    if not pars.no_smooth:
        smooth_d = params.read_task_params("smooth")
        tasks.smooth.smooth(pars, **smooth_d)

    if not pars.no_seed:
        seed_d = params.read_task_params("seed")
        tasks.seed.seed(pars, **seed_d)

    nparameters = 1
    for _ in range(nparameters):  # clustering optimization studies
        if not pars.no_cluster:
            cluster_d = params.read_task_params("cluster")
            nevents_end = tasks.cluster.cluster_default(pars, **cluster_d)
            print("There are {} events in the output.".format(nevents_end))

        if not pars.no_validation:
            # compare CMSSW with local reconstruction
            valid_d = params.read_task_params("valid")
            tasks.validation.validation(pars, **valid_d)

            stats_out = tasks.validation.stats_collector(pars, mode="resolution", **valid_d)
            if df_out is not None:
                df_out = stats_out
            else:
                df_out = pd.concat((df_out, stats_out), axis=0)

    chain_plotter.resolution_plotter(df_out, pars, user='bfontana')

    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Full reconstruction chain.")
    parser.add_argument("--no_fill", action="store_true")
    parser.add_argument("--no_smooth", action="store_true")
    parser.add_argument("--no_seed", action="store_true")
    parser.add_argument("--no_cluster", action="store_true")
    parser.add_argument("--no_validation", action="store_true")
    parsing.add_parameters(parser)
    FLAGS = parser.parse_args()
    assert FLAGS.sel in ("splits_only", "no_splits", "all") or FLAGS.sel.startswith(
        "above_eta_"
    )

    run_chain(common.dot_dict(vars(FLAGS)))