# -*- coding: utf-8 -*-

import flask
import json
import urllib.request


app = flask.Flask(__name__)
app.jinja_env.add_extension('jinja2.ext.do')


@app.route('/', methods=['GET', 'POST'])
def index():
    if flask.request.method == 'POST':
        if 'item_id' in flask.request.form:
            item_id = flask.request.form['item_id']
            property_id = flask.request.form.get('property_id')
            if property_id:
                return flask.redirect(flask.url_for('item_and_property', item_id=item_id, property_id=property_id))
            else:
                return flask.redirect(flask.url_for('item', item_id=item_id))
    return flask.render_template('index.html')

@app.route('/item/<item_id>')
def item(item_id):
    return item_and_property(item_id, property_id='P18')

@app.route('/item/<item_id>/<property_id>')
def item_and_property(item_id, property_id):
    with urllib.request.urlopen('https://www.wikidata.org/w/api.php?format=json&formatversion=2&action=wbgetentities&props=claims&ids=' + item_id) as request:
        item_data = json.load(request)['entities'][item_id]

    image_datavalue = best_value(item_data, property_id)
    if image_datavalue is None:
        return 'no image' # TODO proper error page
    if image_datavalue['type'] != 'string':
        return 'wrong data value type' # TODO proper error page
    image_title = image_datavalue['value']

    depicteds = depicted_items(item_data)
    item_ids = [depicted['item_id'] for depicted in depicteds]
    item_ids.append(item_id)
    labels = load_labels(item_ids)
    for depicted in depicteds:
        depicted['label'] = labels[depicted['item_id']]

    return flask.render_template('item.html',
                                 item_id=item_id,
                                 label=labels[item_id],
                                 image_title=image_title,
                                 depicteds=depicteds)
    

# https://iiif.io/api/image/2.0/#region
@app.template_filter()
def iif_region_to_style(iif_region):
    if iif_region == 'full':
        return 'left: 0px; top: 0px; width: 100%; height: 100%;'
    if iif_region.startswith('pct:'):
        left, top, width, height = iif_region[len('pct:'):].split(',')
        z_index = int(1_000_000 / (float(width)*float(height)))
        return 'left: %s%%; top: %s%%; width: %s%%; height: %s%%; z-index: %s;' % (left, top, width, height, z_index)
    left, top, width, height = iif_region.split(',')
    z_index = int(1_000_000_000 / (int(width)*int(height)))
    return 'left: %spx; top: %spx; width: %spx; height: %spx; z-index: %s;' % (left, top, width, height, z_index)
    

def best_value(item_data, property_id):
    if property_id not in item_data['claims']:
        return None

    statements = item_data['claims'][property_id]
    normal_value = None
    deprecated_value = None

    for statement in statements:
        if statement['mainsnak']['snaktype'] != 'value':
            continue

        datavalue = statement['mainsnak']['datavalue']
        if statement['rank'] == 'preferred':
            return datavalue
        if statement['rank'] == 'normal':
            normal_value = datavalue
        else:
            deprecated_value = datavalue

    return normal_value or deprecated_value

def depicted_items(item_data):
    depicteds = []

    for statement in item_data['claims'].get('P180', []):
        if statement['mainsnak']['snaktype'] != 'value':
            continue
        depicted = {'item_id': statement['mainsnak']['datavalue']['value']['id']}

        for qualifier in statement.get('qualifiers', {}).get('P2677', []):
            if qualifier['snaktype'] != 'value':
                continue
            depicted['iif_region'] = qualifier['datavalue']['value']
            break

        depicteds.append(depicted)
    return depicteds

def load_labels(item_ids):
    item_ids = list(set(item_ids))
    labels = {}
    for chunk in [item_ids[i:i+50] for i in range(0, len(item_ids), 50)]:
        with urllib.request.urlopen('https://www.wikidata.org/w/api.php?format=json&formatversion=2&action=wbgetentities&props=labels&languages=en&ids=' +
                                    '|'.join(chunk)) as request:
            items_data = json.load(request)['entities']
        for item_id, item_data in items_data.items():
            if 'en' in item_data['labels']:
                labels[item_id] = item_data['labels']['en']['value']
            else:
                labels[item_id] = item_id
    return labels
