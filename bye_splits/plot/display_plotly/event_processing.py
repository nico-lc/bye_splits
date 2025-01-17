_all_ = [ ]

import os
import pathlib
from pathlib import Path
import sys
parent_dir = os.path.abspath(__file__ + 3 * '/..')
sys.path.insert(0, parent_dir)

import yaml
from utils import params, common
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, State
import dash_bootstrap_components as dbc

import data_handle
from data_handle.data_process import EventDataParticle
from data_handle.geometry import GeometryData
from plot_event import produce_2dplot, produce_3dplot, plot_modules
from plotly.express.colors import sample_colorscale, qualitative
from scripts.run_default_chain import run_chain_radii
import logging
log = logging.getLogger(__name__)

with open(params.CfgPath, 'r') as afile:
        cfg = yaml.safe_load(afile)
        availLayers = [x-1 for x in cfg["selection"]["disconnectedTriggerLayers"]]

data_part_opt = dict(tag='v2', reprocess=False, debug=True, logger=log)
data_particle = {
    'photons 0PU'  : 'photons',
    'photons 200PU': 'photons_PU',
    'electrons'    : 'electrons',
    'pions'        : 'pions'}

geom_data = GeometryData(reprocess=False, logger=log)

pars = {'no_fill': False, 'no_smooth': False, 'no_seed': False, 'no_cluster': False, 'no_validation': False, 'sel': 'all', 'reg': 'Si', 'seed_window': 1, 'smooth_kernel': 'default', 'cluster_algo': 'min_distance', 'user': None, 'cluster_studies': False}
axis = dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="white", showbackground=True, zerolinecolor="white",)

def sph2cart(eta, phi, z=322.):
    theta = 2*np.arctan(np.exp(-eta))
    r = z / np.cos(theta)
    x = r * np.sin(theta) * np.cos(phi)
    y = r * np.sin(theta) * np.sin(phi)
    return x,y

def cil2cart(r, phi):
    x = r * np.cos(phi)
    y = r * np.sin(phi)
    return x,y

def get_pt(energy, eta):
    return energy/np.cosh(eta)

def get_data(event, particles, coefs):
    ds_geom = geom_data.provide(library='plotly')
   
    ds_ev, gen_info, event = run_chain_radii(common.dot_dict(pars), cfg, data_particle[particles], event, coefs)

    tc_keep = {'seed_idx'  : 'seed_idx',
               'tc_mipPt'  : 'mipPt',
               'tc_wu'     : 'waferu',
               'tc_wv'     : 'waferv',
               'tc_cu'     : 'triggercellu',
               'tc_cv'     : 'triggercellv',
               'tc_layer'  : 'layer'}

    for coef in coefs:    
        if particles == 'photons 200PU':
            eta = gen_info['gen_eta'].values[0]
            phi = gen_info['gen_phi'].values[0]
            x_gen, y_gen = sph2cart(eta, phi)
            ds_ev[coef] = ds_ev[coef][np.sqrt((x_gen-ds_ev[coef].tc_x)**2+(y_gen-ds_ev[coef].tc_y)**2)<50]
 
        ds_ev[coef] = ds_ev[coef].rename(columns=tc_keep)
        ds_ev[coef] = ds_ev[coef][tc_keep.values()]

        ds_ev[coef] = pd.merge(left=ds_ev[coef], right=ds_geom['si'], how='inner',
                               on=['layer', 'waferu', 'waferv', 'triggercellu', 'triggercellv'])
        color_continuous = sample_colorscale('viridis', (ds_ev[coef].mipPt-ds_ev[coef].mipPt.min())/(ds_ev[coef].mipPt.max()-ds_ev[coef].mipPt.min()))
        color_discrete   = sample_colorscale(qualitative.Light24, (ds_ev[coef].seed_idx-ds_ev[coef].seed_idx.min())/(ds_ev[coef].seed_idx.max()-ds_ev[coef].seed_idx.min()))
        ds_ev[coef] = ds_ev[coef].assign(color_energy   = color_continuous)
        ds_ev[coef] = ds_ev[coef].assign(color_clusters = color_discrete)
        ds_ev[coef].loc[ds_ev[coef]["seed_idx"] == ds_ev[coef].seed_idx.max(), "color_clusters"] = "rgb(255,255,255)"

    return ds_ev, event, gen_info

def set_3dfigure(df, discrete=False):
    fig = go.Figure(produce_3dplot(df,discrete=discrete))
    
    fig.update_layout(autosize=False, width=1300, height=700,
                      scene_aspectmode='manual',
                      scene_aspectratio=dict(x=1, y=1, z=1),
                      scene=dict(xaxis=axis, yaxis=axis, zaxis=axis,
                                 xaxis_title="z [cm]",yaxis_title="y [cm]",zaxis_title="x [cm]",
                                 xaxis_showspikes=False,yaxis_showspikes=False,zaxis_showspikes=False),
                      showlegend=False,
                      margin=dict(l=0, r=0, t=10, b=10),
                      ) 

    return fig

def update_3dfigure(fig, df, discrete=False):
    list_scatter = produce_3dplot(df, opacity=.2, discrete=discrete)
    for index in range(len(list_scatter)):
        fig.add_trace(list_scatter[index])

def add_3dscintillators(fig, df):
    cart_coord = []
    x0, y0 = cil2cart(df['rmin'], df['phimin'])
    x1, y1 = cil2cart(df['rmax'], df['phimin'])
    x2, y2 = cil2cart(df['rmax'], df['phimax'])
    x3, y3 = cil2cart(df['rmin'], df['phimax'])

    d = np.array([x0.values, x1.values, x2.values, x3.values,
                  y0.values, y1.values, y2.values, y3.values]).T
    df_sci = pd.DataFrame(data=d, columns=['x1','x2','x3','x4','y1','y2','y3','y4'])
    df['diamond_y']= df_sci[['x1','x2','x3','x4']].values.tolist()
    df['diamond_x']= df_sci[['y1','y2','y3','y4']].values.tolist()

    list_scatter = produce_3dplot(df)
    for index in range(len(list_scatter)):
        fig.add_trace(list_scatter[index])

def roi_finder(input_df, threshold=30, nearby=False):
    ''' Choose the (u,v) coordinates of the module corresponding to max dep-energy.
    This choice is performed by grouping modules beloging to different layers, having the same coordinates.
    Extend the selection to the nearby modules with at least 30% max energy and 10 mipT. '''
    module_sums = input_df.groupby(['waferu','waferv']).mipPt.sum()
    module_ROI = list(module_sums[module_sums.values >= threshold].index)

    if nearby:
        selected_modules = []
        for module in module_ROI:
            nearby_modules = [(module[0]+i, module[1]+j) for i in [-1, 0, 1] for j in [-1, 0, 1] if i*j >= 0]
            
            skim = (module_sums.index.isin(nearby_modules)) & (module_sums.values > 0.3 * module_sums[module]) & (module_sums.values > 10)
            skim_nearby_module = list(module_sums[skim].index)
            selected_modules.extend(skim_nearby_module)
        module_ROI = selected_modules
    
    roi_df = input_df[input_df.set_index(['waferu','waferv']).index.isin(module_ROI)]
    return roi_df.drop_duplicates(['waferu', 'waferv', 'layer']), module_ROI

def add_ROI(fig, df, k=4):
    ''' Choose k-layers window based on energy deposited in each layer '''
    initial_layer = 7
    mask = (df.layer>=initial_layer) & (df.layer<(availLayers[availLayers.index(initial_layer)+k]))
    input_df = df[mask]

    roi_df, module_ROI = roi_finder(input_df, threshold=30, nearby=False)

    list_scatter = plot_modules(roi_df)
    for index in range(len(list_scatter)):
        fig.add_trace(list_scatter[index])

def set_2dfigure(df):
    fig = go.Figure(produce_2dplot(df))

    fig.update_layout(autosize=False, width=1300, height=700,
                      scene_aspectmode='manual',
                      scene_aspectratio=dict(x=1, y=1),
                      scene=dict(xaxis=axis, yaxis=axis, 
                                 xaxis_title="x [cm]",yaxis_title="y [cm]",
                                 xaxis_showspikes=False,yaxis_showspikes=False),
                      showlegend=False,
                      margin=dict(l=0, r=0, t=10, b=10),
                      )
    return fig

def update_2dfigure(fig, df):
    list_scatter = produce_2dplot(df, opacity=.2)
    for index in range(len(list_scatter)):
        fig.add_trace(list_scatter[index])


def layout(**options):
    return dbc.Container([html.Div([
        html.Div([
            html.Div([dcc.Dropdown(['photons 0PU', 'photons 200PU', 'electrons', 'pions'], 'photons 0PU', id='particle')], style={'width':'15%'}),
            html.Div([dbc.Checklist(options['checkbox'], [], inline=True, id='checkbox', switch=True)], style={"margin-left": "15px"}),
            html.Div(id='slider-container', children=html.Div(id='out_slider', style={'width':'99%'}), style= {'display': 'block', 'width':'55%'}),
        ], style={'display': 'flex', 'flex-direction': 'row'}),
    
        html.Div([
            html.Div(["Threshold in [mip\u209C]: ", dcc.Input(id='mip', value=1, type='number', step=0.1)], style={'padding': 10}),
            html.Div(["Select manually an event: ", dcc.Input(id='event', value=None, type='number')], style={'padding': 10, 'flex': 1}),
        ], style={'display':'flex', 'flex-direction':'row'}),
    
        html.Div([
            html.Div(["Select a particular clustering radius: "], style={'padding': 10}),
            html.Div([dcc.Slider(0.002, 0.030, 0.002,value=0.030,id='slider_cluster')], style={'width':'60%'}),
        ], style={'display':'flex', 'flex-direction':'row'}),

        html.Div([
            dbc.Button(children='Random event', id='event-val', n_clicks=0),
            dbc.Button(children='Submit selected event', id='submit-val', n_clicks=0, style={'display':'inline-block', "margin-left": "15px"}),
            html.Div(id='event-display', style={'display':'inline-block', "margin-left": "15px"}), 
        ], style={'display':'inline-block', "margin-left": "15px"}),

        dcc.Graph(id='plot'),
        dcc.Store(id='dataframe'),
        dcc.Store(id='dataframe_sci'),
        html.Div(id='page', key=options['page']),
        ]), ])
