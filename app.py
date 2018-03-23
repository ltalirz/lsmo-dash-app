# -*- coding: utf-8 -*-
from __future__ import print_function
import collections

from aiida import load_dbenv, is_dbenv_loaded
from aiida.backends import settings
if not is_dbenv_loaded():
    load_dbenv(profile=settings.AIIDADB_PROFILE)

from aiida.orm import load_node
from aiida.orm.querybuilder import QueryBuilder
from aiida.orm.data.parameter import ParameterData

import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objs as go

import numpy as np

from flask import redirect, send_from_directory
import os

# search UI
#style = {"description_width":"220px"}
#layout = ipw.Layout(width="90%")

# quantities
quantities = collections.OrderedDict([
    ('density', dict(label='Density', range=[10.0,1200.0], default=[1000.0,1200.0], unit='kg/m^3')),
    ('deliverable_capacity', dict(label='Deliverable capacity', range=[0.0,300.0], unit='v STP/v')),
    ('absolute_methane_uptake_high_P', dict(label='CH4 uptake High-P', range=[0.0,200.0], unit='mol/kg')),
    ('absolute_methane_uptake_low_P', dict(label='CH4 uptake Low-P', range=[0.0,200.0], unit='mol/kg')),
    ('heat_desorption_high_P', dict(label='CH4 heat of desorption High-P', range=[0.0,30.0], unit='kJ/mol')),
    ('heat_desorption_low_P', dict(label='CH4 heat of desorption Low-P', range=[0.0,30.0], unit='kJ/mol')),    
    ('supercell_volume', dict(label='Supercell volume', range=[0.0,1000000.0], unit='A^3')),
    ('surface_area', dict(label='Geometric surface area', range=[0.0,12000.0], unit='m^2/g')),
])
nq = len(quantities)

bondtype_dict = collections.OrderedDict([
    ('amide', "#1f77b4"), ('amine', "#d62728"), ('imine', "#ff7f0e"),
    ('CC', "#2ca02c"), ('mixed', "#778899"),
])
bondtypes = list(bondtype_dict.keys())
bondtype_colors = list(bondtype_dict.values())

# sliders
#inp_pks = ipw.Text(description='PKs', placeholder='e.g. 1006 1009 (space separated)', layout=layout, style=style)

def get_slider(id, desc, range, default=None):
    if default is None:
        default = range
    #marks = { i : str(i) for i in np.linspace(range[0], range[1], 10) }
    slider = dcc.RangeSlider(id=id, min=range[0], max=range[1], value=default, step=0.1)
    return html.Div([html.Span(slider, className="slider"), html.Span(desc), html.Span('', id=id+"_range")])

sliders_dict = collections.OrderedDict()
for k,v in quantities.iteritems():
    desc = "{} [{}]: ".format(v['label'], v['unit'])
    if not 'default' in v.keys():
        v['default'] = None

    slider = get_slider(k, desc, v['range'], v['default'])
    sliders_dict[k] = slider

sliders_html = html.Div( list(sliders_dict.values()), id='sliders' )
sliders_states = [ dash.dependencies.State(k,'value') for k in sliders_dict.keys() ]


# selectors
plot_options = [ dict(label=v['label'], value=k) for k,v in quantities.iteritems() ]
inputs = collections.OrderedDict([
    ('inp_x', dict(label='X', options=plot_options, default='density')),
    ('inp_y', dict(label='Y', options=plot_options, default='deliverable_capacity')),
    ('inp_clr', dict(label='Color', options=plot_options, default='supercell_volume')),
])
ninps = len(inputs)

inputs_dict = collections.OrderedDict()
for k,v in inputs.iteritems():
    dropdown = dcc.Dropdown(id=k, options=v['options'], value=v['default'])
    inputs_dict[k] = html.Div([html.Span(dropdown, className='dropdown'), html.Span(v['label']) ])

inputs_html = html.Div( list(inputs_dict.values()), id='dropdowns' )
inputs_states = [ dash.dependencies.State(k,'value') for k in inputs_dict.keys() ]

btn_plot = html.Div([html.Button('Plot', id='btn_plot'),
    dcc.Markdown('', id='plot_info')])

css = html.Link(
    rel='stylesheet',
    href='/static/style.css'
)

graph_layout = dict(autosize=False, width=600, height=600) 
graph = html.Span(dcc.Graph(id='scatter_plot',figure=dict(layout=graph_layout)),
        className='plot')


## represents the URL bar, doesn't render anything
#url_bar = dcc.Location(id='url_bar', refresh=False),

hover_info = html.Span(dcc.Markdown('', id='hover_info'))
click_info = html.Div('', id='click_info')


# Creation of dash app
app = dash.Dash()
app.layout = html.Div([css, sliders_html, inputs_html, btn_plot, graph, hover_info,
    click_info])


# needed for css
@app.server.route('/static/<path:path>')
def static_file(path):
    static_folder = os.path.join(os.getcwd(), 'static')
    return send_from_directory(static_folder, path)

# slider ranges
for k,v in sliders_dict.iteritems():
    @app.callback(
            dash.dependencies.Output(k+'_range','children'),
            [dash.dependencies.Input(k,'value')])
    def range_output(value):
        return "{} - {}".format(value[0], value[1])

@app.callback(
    #[dash.dependencies.Output('plot_info', 'children'),
    dash.dependencies.Output('scatter_plot', 'figure'),
    [dash.dependencies.Input('btn_plot', 'n_clicks')],
    sliders_states+inputs_states
    )
def update_output(n_clicks, *args):

    if len(args) != nq + ninps:
        raise ValueError("Expected {} arguments".format(nq + ninps))
    sliders_vals = { sliders_dict.keys()[i] : args[i] for i in range(nq) }
    inputs_vals = { inputs_dict.keys()[i] : args[i+nq] for i in range(ninps) }

    figure = search(sliders_vals, inputs_vals)

    return figure

@app.callback(
    dash.dependencies.Output('hover_info', 'children'),
    [dash.dependencies.Input('scatter_plot', 'hoverData')])
def update_text(hoverData):
    if hoverData is None:
        return ""

    uuid = hoverData['points'][0]['customdata']
    rest_url = 'http://localhost:8000/explore/sssp/details/'

    node = load_node(uuid)
    attrs = node.get_attrs()
    s = "[View AiiDA Node]({})\n".format(rest_url+uuid)
    for k,v in attrs.iteritems():
        if 'units' in k:
            continue
        s += " * {}: {}\n".format(k,v)

    return s

#@app.callback(
#    dash.dependencies.Output('url_bar', 'pathname'),
#    [dash.dependencies.Input('scatter_plot', 'clickData')])
#def update_url(figure, hoverData):
#    if hoverData is None:
#        return 
#
#    point = clickData['points'][0]
#
#    uuid = point['customdata']
#    rest_url = 'http://localhost:8000/explore/sssp/details'
#
#    return rest_url + uuid

#@app.callback(
#    dash.dependencies.Output('scatter_plot', 'figure'),
#    [dash.dependencies.Input('scatter_plot', 'figure'), 
#     dash.dependencies.Input('scatter_plot', 'hoverData')])
#def update_annotation(figure, hoverData):
#    if hoverData is None:
#        return figure
#
#    point = hoverData['points'][0]
#
#    uuid = point['customdata']
#    rest_url = 'http://localhost:8000/explore/sssp/details'
#
#    annotation = dict(x=point['x'], y=point['y'], 
#            text='<a href="{}/{}">o</a>'.format(rest_url, uuids))
#
#    figure['layout']['annotations'] = [annotation]
#    return figure

@app.callback(
    dash.dependencies.Output('click_info', 'children'),
    [dash.dependencies.Input('scatter_plot', 'clickData')])
def display_click_data(clickData):
    if clickData is None:
        return ""

    rest_url = 'http://localhost:8000/explore/sssp/details/'
    uuid = clickData['points'][0]['customdata']

    #redirect(rest_url+uuid, code=302)
    #return "clicked" + uuid
    redirect_string="<script>window.location.href='{}';</script>".format(rest_url+uuid)
    return redirect_string


def search(sliders_vals, inputs_vals):
    """Query AiiDA database"""

    filters = {}
    #pk_list = inp_pks.value.strip().split()
    #if pk_list:
    #    filters['id'] = {'in': pk_list}

    def add_range_filter(bounds, label):
        filters['attributes.'+label] = {'and':[{'>=':bounds[0]}, {'<':bounds[1]}]}

    for k,v in sliders_vals.iteritems():
        add_range_filter(v, k)

    inp_x = inputs_vals['inp_x']
    inp_y = inputs_vals['inp_y']
    inp_clr = inputs_vals['inp_clr']
    qb = QueryBuilder()
    qb.append(ParameterData,
          filters=filters,
          project = ['attributes.'+inp_x, 'attributes.'+inp_y, 
                     'attributes.'+inp_clr, 'uuid']
    )

    nresults = qb.count()
    print("Results: {}".format(nresults))
    if nresults == 0:
        print("No results found.")
        #query_message.value = "No results found."
        return

    #query_message.value = "{} results found. Plotting...".format(nresults)

    # x,y position
    x, y, clrs, uuids = zip(*qb.all())
    x = map(float, x)
    y = map(float, y)

    title = "{} vs {}".format(quantities[inp_y]['label'], quantities[inp_x]['label'])
    xlabel = '{} [{}]'.format(quantities[inp_x]['label'],quantities[inp_x]['unit'])
    ylabel = '{} [{}]'.format(quantities[inp_y]['label'],quantities[inp_y]['unit'])

    clrs = map(float, clrs)
    clr_label = "{} [{}]".format(quantities[inp_clr]['label'], quantities[inp_clr]['unit'])

    uuids = map(str, uuids)

    return  plot_plotly(x, y, uuids, clrs, title=title, xlabel=xlabel, ylabel=ylabel, clr_label=clr_label)

def plot_plotly(x, y, uuids, clrs, title=None, xlabel=None, ylabel=None, clr_label=None):
    """Create plot using plot.ly

    Returns figure object
    """
    colorscale = 'Jet'
    colorbar=go.ColorBar(title=clr_label, titleside='right')

    marker = dict(size=10, line=dict(width=2), color=clrs, colorscale=colorscale, colorbar=colorbar)
    trace = go.Scatter(x=x, y=y, mode='markers', marker=marker, customdata=uuids)
    
    #N = len(x)
    ## workaround for links - for proper handling of click events use plot.ly dash
    #links = [ dict(x=x[i], y=y[i], text='<a href="{}/{}">o</a>'.format(rest_url, uuids[i]),
    #               showarrow=False, font=dict(color='#ffffff'), opacity=0.1) for i in range(N)]
    #
    #if with_links:
    #    layout = go.Layout(annotations=links, title=title, xaxis=dict(title=xlabel), yaxis=dict(title=ylabel))
    graph_layout.update(dict(
            title=title, 
            xaxis=dict(title=xlabel), 
            yaxis=dict(title=ylabel), 
            hovermode='closest'
    ))

    figure= dict(data = [trace], layout = graph_layout)
    return figure

if __name__ == '__main__':
    app.run_server(debug=True)
    #app.run_server()
