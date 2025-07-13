# -*- coding: utf-8 -*-

import cachetools
import collections
import decorator
import flask
import iiif_prezi.factory
import json
from markupsafe import Markup
import mwapi
import mwoauth
import random
import re
import requests
import requests_oauthlib
import string
import threading
import toolforge
import urllib.parse

from exceptions import WrongDataValueType
from toolforge_i18n import ToolforgeI18n, interface_language_code_from_request, lang_autonym, message, pop_html_lang, push_html_lang
import messages


app = flask.Flask(__name__)
app.jinja_env.add_extension('jinja2.ext.do')

def interface_language_code(translations):
    if 'uselang' in flask.request.args:
        return interface_language_code_from_request(translations)
    elif flask.session.get('interface_language_code') in translations:
        return flask.session['interface_language_code']
    else:
        return interface_language_code_from_request(translations)

i18n = ToolforgeI18n(app, interface_language_code)

user_agent = toolforge.set_user_agent('lexeme-forms', email='mail@lucaswerkmeister.de')

requests_session = requests.Session()
requests_session.headers.update({
    'Accept': 'application/json',
    'User-Agent': user_agent,
})

default_property = 'P18'

# maps property IDs to message keys for “… with no region specified:” list labels
# note: currently, these must be item-type properties;
# support for other data types (e.g. P1684 inscription) would need more work
depicted_properties = {
    'P180': 'image-depicted-without-region',
    'P9664': 'image-named-places-on-map-without-region',
}
app.add_template_global(lambda: depicted_properties, 'depicted_properties')
app.add_template_global(
    lambda: {property_id: message(key) for property_id, key in depicted_properties.items()},
    'depicted_properties_messages'
)

has_config = app.config.from_file('config.yaml', load=toolforge.load_private_yaml, silent=True)
if has_config:
    consumer_token = mwoauth.ConsumerToken(app.config['OAUTH']['consumer_key'], app.config['OAUTH']['consumer_secret'])
else:
    print('config.yaml file not found, assuming local development setup')
    app.secret_key = 'fake'

def anonymous_session(domain):
    host = 'https://' + domain
    return mwapi.Session(host=host, user_agent=user_agent, formatversion=2)

def authenticated_session(domain):
    if 'oauth_access_token' not in flask.session:
        return None
    host = 'https://' + domain
    access_token = mwoauth.AccessToken(**flask.session['oauth_access_token'])
    auth = requests_oauthlib.OAuth1(client_key=consumer_token.key, client_secret=consumer_token.secret,
                                    resource_owner_key=access_token.key, resource_owner_secret=access_token.secret)
    return mwapi.Session(host=host, auth=auth, user_agent=user_agent, formatversion=2)


@decorator.decorator
def enableCORS(func, *args, **kwargs):
    rv = func(*args, **kwargs)
    response = flask.make_response(rv)
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


@app.route('/', methods=['GET', 'POST'])
def index():
    if flask.request.method == 'POST':
        if 'item_id' in flask.request.form:
            item_id = parse_item_id_input(flask.request.form['item_id'])
            property_id = flask.request.form.get('property_id')
            if 'manifest' in flask.request.form or 'preview' in flask.request.form:
                manifest_url = full_url('iiif_manifest_with_property', item_id=item_id, property_id=property_id or default_property)
                if 'manifest' in flask.request.form:
                    return flask.redirect(manifest_url)
                else:
                    mirador_protocol = 'https' if manifest_url.startswith('https') else 'http'
                    mirador_url = mirador_protocol + '://tools.wmflabs.org/mirador/?manifest=' + manifest_url
                    return flask.redirect(mirador_url)
            else:
                if property_id:
                    return flask.redirect(flask.url_for('item_and_property', item_id=item_id, property_id=property_id))
                else:
                    return flask.redirect(flask.url_for('item', item_id=item_id))
        if 'iiif_region' in flask.request.form:
            iiif_region = flask.request.form['iiif_region']
            property_id = flask.request.form.get('property_id')
            if property_id:
                return flask.redirect(flask.url_for('iiif_region_and_property', iiif_region=iiif_region, property_id=property_id))
            else:
                return flask.redirect(flask.url_for('iiif_region', iiif_region=iiif_region))
        if 'image_title' in flask.request.form:
            image_title = parse_image_title_input(flask.request.form['image_title'])
            return flask.redirect(flask.url_for('file', image_title=image_title))
    return flask.render_template('index.html',
                                 labels=load_labels(['P2677', 'P180', 'P9664', 'P18']))

def parse_item_id_input(input):
    # note: “item” here (and elsewhere in the tool, though not sure if *everywhere* else) refers to any non-MediaInfo entity type
    pattern = r'''
    (?: # can begin with a wd:, data:, or entity page URL prefix
    http://www\.wikidata\.org/entity/ |
    https://www\.wikidata\.org/wiki/Special:EntityData/ |
    https://www\.wikidata\.org/wiki/
    )?
    ( # the entity ID itself
    [QPL][1-9][0-9]* |
    L[1-9][0-9]*-[FS][1-9][0-9]*
    )
    (?: # optional remaining URL parts
    [?#].*
    )?
    '''
    if match := re.fullmatch(pattern, input, re.VERBOSE):
        return match.group(1)  # unquote() not needed, group 1 cannot contain % characters

    url = urllib.parse.urlparse(input)
    if url.scheme == 'https' and url.hostname == 'www.wikidata.org' and url.path == '/w/index.php':
        query = urllib.parse.parse_qs(url.query)
        title = query.get('title', [''])[-1]
        pattern = r'''
        (Q[1-9][0-9]*) |
        Property:(P[1-9][0-9]*) |
        Lexeme:(L[1-9][0-9]*)
        '''
        if match := re.fullmatch(pattern, title, re.VERBOSE):
            return match.group(1)

    flask.abort(400, Markup(r'Cannot parse an entity ID from <kbd>{}</kbd>.').format(input))

def parse_image_title_input(input):
    if '.' in input and ':' not in input:
        return input.replace(" ", "_")

    if input.startswith('File:'):
        return input[len('File:'):].replace(' ', '_')

    pattern = r'''
    (?: # URL prefix
    https://commons\.wikimedia\.org/wiki/File: |
    https://commons\.wikimedia\.org/wiki/Special:FilePath/
    )
    ( # the file name itself, without File:
    [^/?#]* # very lenient :)
    )
    (?: # optional remaining URL parts
    [?#].*
    )?
    '''
    if match := re.fullmatch(pattern, input, re.VERBOSE):
        return urllib.parse.unquote(match.group(1))

    url = urllib.parse.urlparse(input)
    if url.scheme == 'https' and url.hostname == 'commons.wikimedia.org' and url.path == '/w/index.php':
        query = urllib.parse.parse_qs(url.query)
        title = query.get('title', [''])[-1]
        if title.startswith('File:'):
            return title[len('File:'):]

    pattern = r'''
    (?: # can begin with an sdc: or sdcdata: URL prefix
    https://commons\.wikimedia\.org/entity/ |
    https://commons\.wikimedia\.org/wiki/Special:EntityData/
    )?
    ( # the entity ID itself
    M[1-9][0-9]*
    )
    '''
    if match := re.fullmatch(pattern, input, re.VERBOSE):
        entity_id = match.group(1)  # unquote() not needed, group 1 cannot contain % characters
        session = anonymous_session('commons.wikimedia.org')
        title = session.get(action='query',
                            pageids=[entity_id[1:]],
                            redirects=True,
                            formatversion=2)['query']['pages'][0]['title']
        return title[len('File:'):].replace(' ', '_')

    flask.abort(400, Markup(r'Cannot parse a file name from <kbd>{}</kbd>.').format(input))

@app.get('/settings/')
def settings():
    flask.session['return_to_redirect'] = flask.request.referrer
    return flask.render_template(
        'settings.html',
        languages={
            language_code: lang_autonym(language_code)
            for language_code in i18n.translations
        },
    )

@app.post('/settings/')
def settings_save():
    if 'interface-language-code' in flask.request.form:
        flask.session['interface_language_code'] = flask.request.form['interface-language-code'][:20]
    return flask.redirect(flask.session.pop('return_to_redirect', flask.url_for('index')))

@app.route('/login')
def login():
    redirect, request_token = mwoauth.initiate('https://www.wikidata.org/w/index.php', consumer_token, user_agent=user_agent)
    flask.session['oauth_request_token'] = dict(zip(request_token._fields, request_token))
    flask.session['return_to_redirect'] = flask.request.referrer
    return flask.redirect(redirect)

@app.route('/oauth/callback')
def oauth_callback():
    oauth_request_token = flask.session.pop('oauth_request_token', None)
    if oauth_request_token is None:
        return flask.render_template('oauth-callback-without-request-token.html',
                                     already_logged_in='oauth_access_token' in flask.session,
                                     query_string=flask.request.query_string.decode('utf8'))
    access_token = mwoauth.complete('https://www.wikidata.org/w/index.php', consumer_token, mwoauth.RequestToken(**oauth_request_token), flask.request.query_string, user_agent=user_agent)
    flask.session['oauth_access_token'] = dict(zip(access_token._fields, access_token))
    flask.session.permanent = True
    flask.session.pop('_csrf_token', None)
    return flask.redirect(flask.session.pop('return_to_redirect', flask.url_for('index')))

@app.route('/logout')
def logout():
    flask.session.pop('oauth_access_token', None)
    flask.session.permanent = False
    return flask.redirect(flask.url_for('index'))

@app.route('/item/<item_id>')
def item(item_id):
    return item_and_property(item_id, property_id=default_property)

@app.route('/item/<item_id>/<property_id>')
def item_and_property(item_id, property_id):
    item = load_item_and_property(item_id, property_id, include_depicteds=True)
    if 'image_title' not in item:
        return flask.render_template('item-without-image.html', **item)
    return flask.render_template('item.html', **item)

@app.route('/iiif/<item_id>/manifest.json')
def iiif_manifest(item_id):
    return flask.redirect(flask.url_for('iiif_manifest_with_property', item_id=item_id, property_id=default_property))

@app.route('/iiif/<item_id>/<property_id>/manifest.json')
@enableCORS
def iiif_manifest_with_property(item_id, property_id):
    item = load_item_and_property(item_id, property_id, include_description=True, include_metadata=True)
    if 'image_title' not in item:
        return '', 404
    manifest = build_manifest(item)
    return flask.jsonify(manifest.toJSON(top=True))

@app.route('/iiif/<item_id>/list/annotations.json')
def iiif_annotations(item_id):
    return iiif_annotations_with_property(item_id, property_id=default_property)

@app.route('/iiif/<item_id>/<property_id>/list/annotations.json')
@enableCORS
def iiif_annotations_with_property(item_id, property_id):
    item = load_item_and_property(item_id, property_id, include_depicteds=True)

    url = flask.url_for('iiif_annotations_with_property',
                        item_id=item_id,
                        property_id=property_id,
                        _external=True,
                        _scheme=flask.request.headers.get('X-Forwarded-Proto', 'http'))
    annolist = {
        '@id': url,
        '@type': 'sc:AnnotationList',
        'label': 'Annotations for ' + item['label']['value'],
        'resources': []
    }

    if 'image_title' not in item:
        return flask.jsonify(annolist)

    canvas_url = url[:-len('list/annotations.json')] + 'canvas/c0.json'
    # Although the pct canvas is OK for the image API, we need to target
    # canvas coordinates with the annotations, so we need the w,h
    image_info = load_image_info(item['image_title'])
    width, height = int(image_info['thumbwidth']), int(image_info['thumbheight'])

    for depicted in item['depicteds']:
        if 'item_id' not in depicted:
            continue  # somevalue/novalue not supported for now
        link = 'http://www.wikidata.org/entity/' + Markup.escape(depicted['item_id'])
        label = depicted['label']['value']
        # We can put a lot more in here, but minimum for now, and ensure works in Mirador
        anno = {
            '@id': '#' + depicted['statement_id'],
            '@type': 'oa:Annotation',
            'motivation': 'identifying',
            'on': canvas_url,
            'resource': {
                '@id': link,
                'format': 'text/plain',
                'chars': label
            }
        }
        iiif_region = depicted.get('iiif_region', None)
        if iiif_region:
            parts = iiif_region.replace('pct:', '').split(',')
            x = int(float(parts[0]) * width / 100)
            y = int(float(parts[1]) * height / 100)
            w = int(float(parts[2]) * width / 100)
            h = int(float(parts[3]) * height / 100)
            anno['on'] = anno['on'] + '#xywh=' + ','.join(str(d) for d in [x, y, w, h])
        annolist['resources'].append(anno)
    return flask.jsonify(annolist)

@app.route('/iiif_region/<iiif_region>')
def iiif_region(iiif_region):
    return iiif_region_and_property(iiif_region, default_property)

@app.route('/iiif_region/<iiif_region>/<property_id>')
def iiif_region_and_property(iiif_region, property_id):
    iiif_region_string = '"' + iiif_region.replace('\\', '\\\\').replace('"', '\\"') + '"'
    property_claim_predicates = ' '.join(f'p:{property_id}' for property_id in depicted_properties)
    query = '''
      SELECT DISTINCT ?item WHERE {
        VALUES ?p { %s }
        ?item ?p [ pq:P2677 %s ].
      }
    ''' % (property_claim_predicates, iiif_region_string)
    query_results = requests_session.get('https://query.wikidata.org/sparql',
                                         params={'query': query}).json()

    items = []
    items_without_image = []
    for result in query_results['results']['bindings']:
        item_id = result['item']['value'][len('http://www.wikidata.org/entity/'):]
        item = load_item_and_property(item_id, property_id, include_depicteds=True)
        if 'image_title' not in item:
            items_without_image.append(item_id)
        else:
            items.append(item)

    return flask.render_template('iiif_region.html', items=items, items_without_image=items_without_image)

@app.route('/file/<image_title>')
def file(image_title):
    image_title_ = image_title.replace(' ', '_')
    if image_title_.startswith('File:'):
        image_title_ = image_title_[len('File:'):]
    if image_title_ != image_title:
        return flask.redirect(flask.url_for('file', image_title=image_title_, **flask.request.args))
    file = load_file(image_title.replace('_', ' '))
    if not file:
        return flask.render_template('file-not-found.html', title=image_title), 404
    return flask.render_template('file.html', **file)

@app.route('/api/v1/depicteds_html/file/<image_title>')
@enableCORS
def file_depicteds_html(image_title):
    file = load_file(image_title.replace('_', ' '))
    if not file:
        return flask.render_template('file-not-found.html', title=image_title), 404
    return flask.render_template('depicteds.html', depicteds=file['depicteds'])

@app.route('/api/v1/add_statement/<domain>', methods=['POST'])
def api_add_statement(domain):
    entity_id = flask.request.form.get('entity_id')
    snaktype = flask.request.form.get('snaktype')
    item_id = flask.request.form.get('item_id')
    property_id = flask.request.form.get('property_id', 'P180')
    request_csrf_token = flask.request.form.get('_csrf_token')
    if not entity_id or not snaktype or not request_csrf_token:
        return 'Incomplete form data', 400
    if (snaktype == 'value') != (item_id is not None):
        return 'Inconsistent form data', 400
    if snaktype not in {'value', 'somevalue', 'novalue'}:
        return 'Bad snaktype', 400
    if property_id not in depicted_properties:
        return 'Bad property ID', 400

    if request_csrf_token != csrf_token():
        return 'Wrong CSRF token (try reloading the page).', 403

    if not flask.request.referrer.startswith(full_url('index')):
        return 'Wrong Referer header', 403

    if domain not in {'www.wikidata.org', 'commons.wikimedia.org'}:
        return 'Unsupported domain', 403

    session = authenticated_session(domain)
    if session is None:
        return 'Not logged in', 403

    token = session.get(action='query', meta='tokens', type='csrf')['query']['tokens']['csrftoken']
    depicted = {
        'snaktype': snaktype,
        'property_id': property_id,
    }
    if snaktype == 'value':
        value = json.dumps({'entity-type': 'item', 'id': item_id})
        depicted['item_id'] = item_id
        labels = load_labels([item_id])
        depicted['label'] = labels[item_id]
    else:
        value = None
        if snaktype == 'somevalue':
            depicted['label'] = messages.somevalue(flask.g.interface_language_code)
        elif snaktype == 'novalue':
            depicted['label'] = messages.novalue(flask.g.interface_language_code)
        else:
            raise ValueError('Unknown snaktype')
    try:
        response = session.post(action='wbcreateclaim',
                                entity=entity_id,
                                snaktype=snaktype,
                                property=property_id,
                                value=value,
                                token=token)
    except mwapi.errors.APIError as error:
        return str(error), 500
    statement_id = response['claim']['id']
    depicted['statement_id'] = statement_id
    return flask.jsonify(depicted=depicted,
                         depicted_item_link=depicted_item_link(depicted))

@app.route('/api/v2/add_qualifier/<domain>', methods=['POST'])
def api_add_qualifier(domain):
    statement_id = flask.request.form.get('statement_id')
    iiif_region = flask.request.form.get('iiif_region')
    request_csrf_token = flask.request.form.get('_csrf_token')
    qualifier_hash = flask.request.form.get('qualifier_hash')  # optional
    if not statement_id or not iiif_region or not request_csrf_token:
        return 'Incomplete form data', 400

    if request_csrf_token != csrf_token():
        return 'Wrong CSRF token (try reloading the page).', 403

    if not flask.request.referrer.startswith(full_url('index')):
        return 'Wrong Referer header', 403

    if domain not in {'www.wikidata.org', 'commons.wikimedia.org'}:
        return 'Unsupported domain', 403

    session = authenticated_session(domain)
    if session is None:
        return 'Not logged in', 403

    token = session.get(action='query', meta='tokens', type='csrf')['query']['tokens']['csrftoken']
    try:
        response = session.post(action='wbsetqualifier', claim=statement_id, property='P2677',
                                snaktype='value', value=('"' + iiif_region + '"'),
                                **({'snakhash': qualifier_hash} if qualifier_hash else {}),
                                summary='region drawn manually using [[d:User:Lucas Werkmeister/Wikidata Image Positions|Wikidata Image Positions tool]]',
                                token=token)
    except mwapi.errors.APIError as error:
        if error.code == 'no-such-qualifier':
            return 'This region does not exist (anymore) – it may have been edited in the meantime. Please try reloading the page.', 500
        return str(error), 500
    # find hash of qualifier
    for qualifier in response['claim']['qualifiers']['P2677']:
        if qualifier['snaktype'] == 'value' and qualifier['datavalue']['value'] == iiif_region:
            return flask.jsonify(qualifier_hash=qualifier['hash'])
    return flask.jsonify(qualifier_hash=None)

@app.route('/healthz')
def health():
    return ''


# https://iiif.io/api/image/2.0/#region
@app.template_filter()
def iiif_region_to_style(iiif_region):
    try:
        if iiif_region == 'full':
            return 'left: 0px; top: 0px; width: 100%; height: 100%;'
        if iiif_region.startswith('pct:'):
            left, top, width, height = iiif_region[len('pct:'):].split(',')
            z_index = int(1_000_000 / (float(width) * float(height)))
            return 'left: %s%%; top: %s%%; width: %s%%; height: %s%%; z-index: %s;' % (left, top, width, height, z_index)
        left, top, width, height = iiif_region.split(',')
        z_index = int(1_000_000_000 / (int(width) * int(height)))
        return 'left: %spx; top: %spx; width: %spx; height: %spx; z-index: %s;' % (left, top, width, height, z_index)
    except ValueError:
        flask.abort(400, Markup('Invalid IIIF region <kbd>{}</kbd> encountered. Remove the invalid qualifier manually, then reload.').format(iiif_region))

@app.template_filter()
def user_link(user_name):
    return (Markup(r'<a href="https://www.wikidata.org/wiki/User:') +
            Markup.escape(user_name.replace(' ', '_')) +
            Markup(r'">') +
            Markup(r'<bdi>') +
            Markup.escape(user_name) +
            Markup(r'</bdi>') +
            Markup(r'</a>'))

@app.template_global()
def item_link(item_id, label):
    return (Markup(r'<a href="http://www.wikidata.org/entity/') +
            Markup.escape(item_id) +
            Markup(r'" ') +
            push_html_lang(label['language']) +
            Markup(r' data-entity-id="') +
            Markup.escape(item_id) +
            Markup(r'">') +
            Markup.escape(label['value']) +
            Markup(r'</a') +
            pop_html_lang(label['language']) +
            Markup(r'>'))

@app.template_filter()
def depicted_item_link(depicted):
    if 'item_id' in depicted:
        return item_link(depicted['item_id'], depicted['label'])
    else:
        return (Markup(r'<span class="wd-image-positions--snaktype-not-value" ') +
                push_html_lang(depicted['label']['language']) +
                Markup(r'>') +
                Markup.escape(depicted['label']['value']) +
                Markup(r'</span') +
                pop_html_lang(depicted['label']['language']) +
                Markup(r'>'))

@app.template_global()
def csrf_token() -> str:
    if '_csrf_token' not in flask.session:
        flask.session['_csrf_token'] = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(64))
    return flask.session['_csrf_token']

@app.template_global()
def authentication_area():
    if 'OAUTH' not in app.config:
        return Markup()

    session = authenticated_session('www.wikidata.org')
    if session is None:
        userinfo = None
    else:
        try:
            userinfo = session.get(action='query',
                                   meta='userinfo')['query']['userinfo']
        except mwapi.errors.APIError as e:
            if e.code == 'mwoauth-invalid-authorization':
                # e. g. consumer version updated, treat as not logged in
                flask.session.pop('oauth_access_token')
                userinfo = None
            else:
                raise e

    if userinfo is None:
        return (Markup(r'<a id="login" class="navbar-text" href="') +
                Markup.escape(flask.url_for('login')) +
                Markup(r'">') +
                message('nav-login') +
                Markup(r'</a>'))

    user_name = userinfo['name']
    return (Markup(r'<span class="navbar-text">') +
            Markup(message('nav-logged-in', user_link=user_link(user_name), user_name=user_name)) +
            Markup(r'</span><span id="csrf_token" style="display: none;">') +
            Markup.escape(csrf_token()) +
            Markup(r'</span>'))

@app.template_global()
def user_logged_in():
    return 'oauth_access_token' in flask.session

@app.errorhandler(WrongDataValueType)
def handle_wrong_data_value_type(error):
    response = flask.render_template('wrong-data-value-type.html',
                                     expected_data_value_type=error.expected_data_value_type,
                                     actual_data_value_type=error.actual_data_value_type)
    return response, error.status_code


def load_item_and_property(item_id, property_id,
                           include_depicteds=False, include_description=False, include_metadata=False):
    props = ['claims']
    if include_description:
        props.append('descriptions')

    session = anonymous_session('www.wikidata.org')
    api_response = session.get(action='wbgetentities',
                               props=props,
                               ids=item_id,
                               languages=[flask.g.interface_language_code],
                               languagefallback=True)
    item_data = api_response['entities'][item_id]
    item = {
        'entity_id': item_id,
    }
    entity_ids = [item_id]

    if include_description:
        item['description'] = item_data.get('descriptions', {})\
                                       .get(flask.g.interface_language_code)

    image_datavalue = best_value(item_data, property_id)
    if image_datavalue is not None:
        if image_datavalue['type'] != 'string':
            raise WrongDataValueType(expected_data_value_type='string', actual_data_value_type=image_datavalue['type'])
        image_title = image_datavalue['value']
        item.update(load_image(image_title))

    if include_depicteds:
        depicteds = depicted_items(item_data)
        for depicted in depicteds:
            if 'item_id' in depicted:
                entity_ids.append(depicted['item_id'])

    if include_metadata:
        metadata = entity_metadata(item_data)
        entity_ids += metadata.keys()

    labels = load_labels(entity_ids)
    item['label'] = labels[item_id]

    if include_depicteds:
        for depicted in depicteds:
            depicted['label'] = depicted_label(depicted, labels)
        item['depicteds'] = depicteds

    if include_metadata:
        item['metadata'] = []
        for property_id, values in metadata.items():
            for value in values:
                item['metadata'].append({
                    'label': labels[property_id],
                    'value': value
                })

    return item

def load_file(image_title):
    image = load_image(image_title)
    if image is None:
        return None

    entity_id = 'M' + str(image['image_page_id'])
    file = {
        'entity_id': entity_id,
        **image,
    }
    entity_ids = []

    session = anonymous_session('commons.wikimedia.org')
    api_response = session.get(action='wbgetentities',
                               props=['claims'],
                               ids=[entity_id])
    file_data = api_response['entities'][entity_id]

    depicteds = depicted_items(file_data)
    for depicted in depicteds:
        if 'item_id' in depicted:
            entity_ids.append(depicted['item_id'])

    labels = load_labels(entity_ids)

    for depicted in depicteds:
        depicted['label'] = depicted_label(depicted, labels)
    file['depicteds'] = depicteds

    return file

def load_image(image_title):
    """Load the metadata of an image file on Commons, without structured data."""
    session = anonymous_session('commons.wikimedia.org')

    query_params = query_default_params()
    query_params.setdefault('titles', set()).update(['File:' + image_title])
    image_attribution_query_add_params(query_params, image_title)
    image_url_query_add_params(query_params, image_title)
    image_size_query_add_params(query_params, image_title)

    query_response = session.get(**query_params)
    page = query_response_page(query_response, 'File:' + image_title)
    if page.get('missing', False) or page.get('invalid', False):
        return None

    page_id = page['pageid']
    attribution = image_attribution_query_process_response(query_response, image_title)
    url = image_url_query_process_response(query_response, image_title)
    width, height = image_size_query_process_response(query_response, image_title)
    return {
        'image_page_id': page_id,
        'image_title': image_title,
        'image_attribution': attribution,
        'image_url': url,
        'image_width': width,
        'image_height': height,
    }

def depicted_label(depicted, labels):
    if 'item_id' in depicted:
        return labels[depicted['item_id']]
    elif depicted['snaktype'] == 'somevalue':
        return messages.somevalue(flask.g.interface_language_code)
    elif depicted['snaktype'] == 'novalue':
        return messages.novalue(flask.g.interface_language_code)
    else:
        raise ValueError('depicted has neither item ID nor somevalue/novalue snaktype')

def load_image_info(image_title):
    file_title = 'File:' + image_title.replace(' ', '_')
    session = anonymous_session('commons.wikimedia.org')
    response = session.get(action='query', prop='imageinfo', iiprop='url|mime',
                           iiurlwidth=8000, titles=file_title)

    return response['query']['pages'][0]['imageinfo'][0]

def full_url(endpoint, **kwargs):
    return flask.url_for(endpoint, _external=True, _scheme=flask.request.headers.get('X-Forwarded-Proto', 'http'), **kwargs)

def current_url():
    return full_url(flask.request.endpoint, **flask.request.view_args)

def language_string_wikibase_to_iiif(language_string):
    if language_string is None:
        return None
    return {language_string['language']: language_string['value']}

def build_manifest(item):
    base_url = current_url()[:-len('/manifest.json')]
    fac = iiif_prezi.factory.ManifestFactory()
    fac.set_base_prezi_uri(base_url)
    fac.set_debug('error')

    iiif_item_label = language_string_wikibase_to_iiif(item['label'])
    iiif_item_description = language_string_wikibase_to_iiif(item['description'])

    manifest = fac.manifest(ident='manifest.json')
    if iiif_item_label is not None:
        manifest.label = iiif_item_label
    if iiif_item_description is not None:
        manifest.description = iiif_item_description
    attribution = image_attribution(item['image_title'])
    if attribution is not None:
        manifest.attribution = attribution['attribution_text']
        manifest.license = attribution['license_url']
    for metadata in item['metadata']:
        manifest.set_metadata({
            'label': language_string_wikibase_to_iiif(metadata['label']),
            'value': metadata['value'],
        })
    sequence = manifest.sequence(ident='normal', label='default order')
    canvas = sequence.canvas(ident='c0')
    if iiif_item_label is not None:
        canvas.label = iiif_item_label
    annolist = fac.annotationList(ident='annotations', label='Things depicted on this canvas')
    canvas.add_annotationList(annolist)
    populate_canvas(canvas, item, fac)

    return manifest

def populate_canvas(canvas, item, fac):
    image_info = load_image_info(item['image_title'])
    width, height = image_info['thumbwidth'], image_info['thumbheight']
    canvas.set_hw(height, width)
    anno = canvas.annotation(ident='a0')
    img = anno.image(ident=image_info['thumburl'], iiif=False)
    img.set_hw(height, width)
    img.format = image_info['mime']

    # add a thumbnail to the canvas
    thumbs_path = image_info['thumburl'].replace('/wikipedia/commons/', '/wikipedia/commons/thumb/')
    thumb_400 = thumbs_path + '/400px-' + item['image_title']
    canvas.thumbnail = fac.image(ident=thumb_400)
    canvas.thumbnail.format = image_info['mime']
    thumbwidth, thumbheight = 400, int(height * (400 / width))
    canvas.thumbnail.set_hw(thumbheight, thumbwidth)

def best_value(entity_data, property_id):
    if property_id not in entity_data['claims']:
        return None

    statements = entity_data['claims'][property_id]
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

def best_values(entity_data, property_id):
    if property_id not in entity_data['claims']:
        return []

    statements = entity_data['claims'][property_id]
    preferred_values = []
    normal_values = []
    deprecated_values = []

    for statement in statements:
        if statement['mainsnak']['snaktype'] != 'value':
            continue

        datavalue = statement['mainsnak']['datavalue']
        if statement['rank'] == 'preferred':
            preferred_values.append(datavalue)
        elif statement['rank'] == 'normal':
            normal_values.append(datavalue)
        else:
            deprecated_values.append(datavalue)

    return preferred_values or normal_values or deprecated_values

def depicted_items(entity_data):
    depicteds = []

    statements = entity_data.get('claims', entity_data.get('statements', {}))
    if statements == []:
        statements = {}  # T222159
    for property_id in depicted_properties:
        for statement in statements.get(property_id, []):
            snaktype = statement['mainsnak']['snaktype']
            depicted = {
                'snaktype': snaktype,
                'statement_id': statement['id'],
                'property_id': property_id,
            }
            if snaktype == 'value':
                depicted['item_id'] = statement['mainsnak']['datavalue']['value']['id']

            for qualifier in statement.get('qualifiers', {}).get('P2677', []):
                if qualifier['snaktype'] != 'value':
                    continue
                depicted['iiif_region'] = qualifier['datavalue']['value']
                depicted['qualifier_hash'] = qualifier['hash']
                break

            depicteds.append(depicted)
    return depicteds

def entity_metadata(entity_data):
    # property IDs based on https://www.wikidata.org/wiki/Wikidata:WikiProject_Visual_arts/Item_structure#Describing_individual_objects
    property_ids = [
        'P170',  # creator
        'P1476',  # title
        'P571',  # inception
        'P186',  # material used
        'P2079',  # fabrication method
        'P2048',  # height
        'P2049',  # width
        'P2610',  # thickness
        'P88',  # commissioned by
        'P1071',  # location of final assembly
        'P127',  # owned by
        'P1259',  # coordinates of the point of view
        'P195',  # collection
        'P276',  # location
        'P635',  # coordinate location
        'P1684',  # inscription
        'P136',  # genre
        'P135',  # movement
        'P921',  # main subject
        'P144',  # based on
        'P941',  # inspired by
    ]
    metadata = collections.defaultdict(list)

    session = anonymous_session('www.wikidata.org')
    for property_id in property_ids:
        for value in best_values(entity_data, property_id):
            response = session.get(action='wbformatvalue',
                                   generate='text/html',
                                   datavalue=json.dumps(value),
                                   property=property_id)
            metadata[property_id].append(response['result'])

    return metadata

def load_labels(entity_ids):
    """Load the labels of the given entity IDs in the interface language."""
    entity_ids = list(set(entity_ids))
    labels = {}
    session = anonymous_session('www.wikidata.org')
    for chunk in [entity_ids[i:i + 50] for i in range(0, len(entity_ids), 50)]:
        items_data = session.get(action='wbgetentities',
                                 props='labels',
                                 languages=[flask.g.interface_language_code],
                                 languagefallback=True,
                                 ids=chunk)['entities']
        for entity_id, item_data in items_data.items():
            labels[entity_id] = item_data.get('labels', {})\
                                         .get(flask.g.interface_language_code,
                                              {'language': 'zxx', 'value': entity_id})
    return labels

@cachetools.cached(cache=cachetools.TTLCache(maxsize=1000, ttl=7 * 24 * 60 * 60),
                   lock=threading.RLock())
def depicted_properties_labels():
    """Load the labels of the depicted_properties in all available interface languages.

    This is implemented separately from load_labels() because we can cache this data much better;
    the depicted_properties labels are needed for almost every request,
    whereas individual entity labels loaded by load_labels()
    are probably only needed for one request.
    """
    assert len(depicted_properties) <= 50
    property_ids = list(depicted_properties.keys())
    languages = list(i18n.translations.keys())
    labels = {}
    session = anonymous_session('www.wikidata.org')
    for chunk in [languages[i:i + 50] for i in range(0, len(languages), 50)]:
        properties_data = session.get(action='wbgetentities',
                                      props='labels',
                                      languages=chunk,
                                      languagefallback=True,
                                      ids=property_ids)['entities']
        for property_id, property_data in properties_data.items():
            labels[property_id] = property_data['labels']
    return labels

@app.template_global(name='depicted_properties_labels')
def depicted_properties_labels_in_interface_language():
    return {
        property_id: labels.get(flask.g.interface_language_code,
                                labels['en'])
        for property_id, labels in depicted_properties_labels().items()
    }

def image_attribution(image_title):
    params = query_default_params()
    image_attribution_query_add_params(params, image_title)
    session = anonymous_session('commons.wikimedia.org')
    response = session.get(**params)
    return image_attribution_query_process_response(response, image_title)

def image_attribution_query_add_params(params, image_title):
    params.setdefault('prop', set()).update(['imageinfo'])
    params.setdefault('iiprop', set()).update(['extmetadata'])
    params['iiextmetadatalanguage'] = flask.g.interface_language_code
    params.setdefault('titles', set()).update(['File:' + image_title])

def image_attribution_query_process_response(response, image_title):
    page = query_response_page(response, 'File:' + image_title)
    imageinfo = page['imageinfo'][0]
    metadata = imageinfo['extmetadata']
    no_value = {'value': None}

    attribution_required = metadata.get('AttributionRequired', no_value)['value']
    if attribution_required != 'true':
        return None

    attribution = Markup()

    artist = metadata.get('Artist', no_value)['value']
    if artist:
        attribution += Markup(r', ') + Markup(artist)

    license_short_name = metadata.get('LicenseShortName', no_value)['value']
    license_url = metadata.get('LicenseUrl', no_value)['value']
    if license_short_name and license_url:
        attribution += (Markup(r', <a href="') + Markup.escape(license_url) + Markup(r'">') +
                        Markup.escape(license_short_name) +
                        Markup(r'</a>'))

    credit = metadata.get('Credit', no_value)['value']
    if credit:
        attribution += Markup(r' (') + Markup(credit) + Markup(r')')

    attribution = attribution[len(', '):]

    return {
        'license_url': license_url,
        'attribution_text': attribution.striptags(),
        'attribution_html': attribution,
    }

def image_url(image_title):
    params = query_default_params()
    image_url_query_add_params(params, image_title)
    session = anonymous_session('commons.wikimedia.org')
    response = session.get(**params)
    return image_url_query_process_response(response, image_title)

def image_url_query_add_params(params, image_title):
    params.setdefault('prop', set()).update(['imageinfo'])
    params.setdefault('iiprop', set()).update(['url'])
    params.setdefault('titles', set()).update(['File:' + image_title])

def image_url_query_process_response(response, image_title):
    page = query_response_page(response, 'File:' + image_title)
    imageinfo = page['imageinfo'][0]
    url = imageinfo['url']

    return url

def image_size(image_title):
    params = query_default_params()
    image_size_query_add_params(params, image_title)
    session = anonymous_session('commons.wikimedia.org')
    response = session.get(**params)
    return image_size_query_process_response(response, image_title)

def image_size_query_add_params(params, image_title):
    params.setdefault('prop', set()).update(['imageinfo'])
    params.setdefault('iiprop', set()).update(['size'])
    params.setdefault('titles', set()).update(['File:' + image_title])

def image_size_query_process_response(response, image_title):
    page = query_response_page(response, 'File:' + image_title)
    imageinfo = page['imageinfo'][0]
    width = imageinfo['width']
    height = imageinfo['height']

    return width, height

def query_default_params():
    return {'action': 'query', 'formatversion': 2}

def query_response_page(response, title):
    """Get the page corresponding to a title from a query response."""
    for normalized in response['query'].get('normalized', []):
        if normalized['from'] == title:
            title = normalized['to']
            break
    pages = response['query']['pages']
    return next(page for page in pages if page['title'] == title)

@app.after_request
def denyFrame(response):
    """Disallow embedding the tool’s pages in other websites.

    If other websites can embed this tool’s pages, e. g. in <iframe>s,
    other tools hosted on tools.wmflabs.org can send arbitrary web
    requests from this tool’s context, bypassing the referrer-based
    CSRF protection.
    """
    response.headers['X-Frame-Options'] = 'deny'
    return response
