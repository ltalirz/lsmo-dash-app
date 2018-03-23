# -*- coding: utf-8 -*-
from __future__ import print_function
import collections

from aiida import load_dbenv, is_dbenv_loaded
from aiida.backends import settings
if not is_dbenv_loaded():
    load_dbenv(profile=settings.AIIDADB_PROFILE)

from aiida.orm.querybuilder import QueryBuilder
from aiida.orm.data.parameter import ParameterData

import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objs as go

# search UI
#style = {"description_width":"220px"}
#layout = ipw.Layout(width="90%")
#inp_pks = ipw.Text(description='PKs', placeholder='e.g. 1006 1009 (space separated)', layout=layout, style=style)

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
    return html.Div([dcc.RangeSlider(id=id, min=range[0], max=range[1], value=default, step=1.0), html.Div(desc)])

sliders_dict = collections.OrderedDict()
for k,v in quantities.iteritems():
    desc = "{} [{}]".format(v['label'], v['unit'])
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
    inputs_dict[k] = html.Div([dcc.Dropdown(id=k, options=v['options'], value=v['default']), html.Div(v['label'])])

inputs_html = html.Div( list(inputs_dict.values()), id='sliders' )
inputs_states = [ dash.dependencies.State(k,'value') for k in inputs_dict.keys() ]

app = dash.Dash()
layout = []

btn_plot = html.Div([html.Button('Plot', id='btn_plot'),
    html.Div('', id='plot_info')])

graph = dcc.Graph(
    id='scatter-plot',
)

app.layout = html.Div([sliders_html, inputs_html, btn_plot, graph])

@app.callback(
    #[dash.dependencies.Output('plot_info', 'children'),
    dash.dependencies.Output('scatter-plot', 'figure'),
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
    projections = ['attributes.'+inp_x, 'attributes.'+inp_y, 'attributes.'+inp_clr, 'uuid']
    qb = QueryBuilder()
    qb.append(ParameterData,
          filters=filters,
          project = projections
    )

    nresults = qb.count()
    print("Results: {}".format(nresults))
    if nresults == 0:
        print("No results found.")
        #query_message.value = "No results found."
        return

    #query_message.value = "{} results found. Plotting...".format(nresults)

    l = qb.all()
    res = map(list, zip(*l))
    x = map(float, res[0])
    y = map(float, res[1])
    if inp_clr == 'bond_type':
        def apply_color(bond):
            if bond == "amide":
                return "#1f77b4" #blue
            elif bond == "amine":
                return "#d62728" #red
            elif bond == "imine":
                return  "#ff7f0e" #orange
            elif bond == "CC":
                return "#2ca02c" #green
            elif bond == "mixed":
                return "slategrey" #grey
        clr = list(map(lambda x: apply_color(x), res[2]))
    else:
        #cmap = plt.cm.rainbow
        #clr = cmap(map(float, res[2]))
        clr = map(float, res[2])
    uuid = res[3]

    title = "{} vs {}".format(inp_y, inp_x)

    #qb = QueryBuilder()
    #qb.append(ParameterData, filters=filters,
    #    project = [ 'attributes.'+inp_x.value+'_units', 'attributes.'+inp_y.value+'_units'],
    #)
    #qb.limit(1)
    #xlabel = inp_x.label + ' ['+qb.all()[0][0]+']'
    #ylabel = inp_y.label+ ' ['+qb.all()[0][1]+']'
    xlabel = inp_x
    ylabel = inp_y

    #if btn_mode.value is 'plotly':
    #    plot_plotly(x, y, uuid, title=title, xlabel=xlabel, ylabel=ylabel)
    #elif btn_mode.value is 'plotly_links':
    return plot_dash(x, y, uuid, title=title, xlabel=xlabel, ylabel=ylabel, with_links=True)
#    else:
##         plt.xlabel(xlabel)
##         plt.ylabel(ylabel)
##         plt.title(title)
##         plt.plot(x, y, clr )
#        plt.scatter(x, y, c=clr, s=5, linewidth=0)
#        #plt.scatter(x, clr)  #, s=5, linewidth=0)
#
#    query_message.value = "Plotted {} results.".format(nresults)
#
#
def plot_dash(x, y, uuid, title=None, xlabel=None, ylabel=None, with_links=False):

    trace = go.Scattergl(x=x, y=y, mode='markers',
                       marker=dict(size=10, line=dict(width=2)))

    layout = go.Layout(title=title, xaxis=dict(title=xlabel), yaxis=dict(title=ylabel),
                      hovermode='closest')

    #app_simple.layout = html.Div([
    #    dcc.Graph(
    #        id='scatter-plot',
    #        figure= dict(data = [trace], layout = layout),
    #    )
    #])
    figure= dict(data = [trace], layout = layout)
    return figure

    #app_simple.run_server(debug=True)
    #proc = multiprocessing.Process(target=show_app, args=(app_simple,))
    #proc.start()
#
#
#
#
#
##app = dash.Dash()
##
##app.layout = html.Div(children=[
##    html.H1(children='Hello Dash'),
##
##    html.Div(children='''
##        Dash: A web application framework for Python.
##    '''),
##
##    dcc.Graph(
##        id='example-graph',
##        figure={
##            'data': [
##                {'x': [1, 2, 3], 'y': [4, 1, 2], 'type': 'bar', 'name': 'SF'},
##                {'x': [1, 2, 3], 'y': [2, 4, 5], 'type': 'bar', 'name': u'Montréal'},
##            ],
##            'layout': {
##                'title': 'Dash Data Visualization'
##            }
##        }
##    )
##])
#
if __name__ == '__main__':
    #search()
    app.run_server(debug=True)
    #app.run_server()
