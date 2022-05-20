function setup() {
    'use strict';

    const csrfTokenElement = document.getElementById('csrf_token'),
          baseUrl = document.querySelector('link[rel=index]').href.replace(/\/$/, ''),
          depictedProperties = JSON.parse(document.getElementsByTagName('main')[0].dataset.depictedProperties);
    let EntityInputWidget; // loaded in addNewDepictedForms

    /** Make a key event handler that calls the given callback when Esc is pressed. */
    function onEscape(callback) {
        return function(eKey) {
            if (eKey.key === 'Escape') {
                return callback.apply(this, arguments);
            }
        };
    }

    function addScaleInputs() {
        document.querySelectorAll('.wd-image-positions--wrapper').forEach(addScaleInput);
    }

    function addScaleInput(wrapper) {
        // remove the no-JS inputs, labels, and <br> before the wrapper
        const nodesToRemove = new Set(['#text', 'BR', 'LABEL', 'INPUT']);
        let node, value = 1;
        while (nodesToRemove.has((node = wrapper.previousSibling).nodeName)) {
            if (node.checked) {
                value = node.value;
            }
            node.remove();
        }
        // create JS input (can be wrapped in a div, unlike the no-JS ones,
        // which must be direct siblings of the wrapper for the CSS to work)
        const div = document.createElement('div');
        const label = document.createElement('label');
        label.textContent = 'Image scale: ';
        const input = document.createElement('input');
        input.type = 'range';
        input.value = value;
        input.min = 0;
        input.max = 5; // arbitrary
        input.step = 'any';
        input.classList.add('wd-image-positions--scale');
        label.append(input);
        div.append(label);
        wrapper.before(div);

        const image = wrapper.firstElementChild;
        const updateScale = () => {
            image.style.setProperty('--scale', input.value);
        };
        input.addEventListener('input', updateScale);
        updateScale();
    }

    function addEditButtons() {
        document.querySelectorAll('.wd-image-positions--depicted-without-region').forEach(addEditButton);
    }

    function addEditButton(element) {
        const entity = element.closest('.wd-image-positions--entity'),
              depictedId = element.firstChild.dataset.entityId,
              scaleInput = entity.querySelector('.wd-image-positions--scale'),
              wrapper = entity.querySelector('.wd-image-positions--wrapper'),
              image = wrapper.firstElementChild;

        const button = document.createElement('button');
        button.type = 'button';
        button.classList.add('btn', 'btn-secondary', 'btn-sm');
        button.textContent = 'add region';
        button.addEventListener('click', onClick);
        element.append(document.createTextNode(' '));
        element.append(button);

        let cropper = null;
        let doneCallback = null;
        const onKeyDown = onEscape(cancelEditing);

        function onClick() {
            if (cropper === null) {
                button.textContent = 'loading...';
                wrapper.classList.add('wd-image-positions--active');
                image.classList.add('wd-image-positions--active');
                button.classList.add('wd-image-positions--active');
                scaleInput.disabled = true;
                doneCallback = ensureImageCroppable(image);
                cropper = new Cropper(image.firstElementChild, {
                    viewMode: 2,
                    movable: false,
                    rotatable: true, // we don’t rotate the image ourselves, but this allows cropper.js to respect JPEG orientation
                    scalable: false,
                    zoomable: false,
                    checkCrossOrigin: false,
                    ready: function() {
                        button.textContent = 'use this region';
                    },
                });
                document.addEventListener('keydown', onKeyDown);
            } else {
                if (button.textContent === 'loading...') {
                    return;
                }

                const depicted = document.createElement('div');
                depicted.classList.add('wd-image-positions--depicted')
                if (depictedId !== undefined) {
                    depicted.dataset.entityId = depictedId;
                }
                depicted.dataset.statementId = element.dataset.statementId;
                depicted.append(element.firstChild.cloneNode(true));
                image.append(depicted);
                button.textContent = 'editing statement…';
                const subject = { id: entity.dataset.entityId, domain: entity.dataset.entityDomain };
                saveCropper(subject, image, depicted, cropper).then(
                    function() {
                        if (depicted.parentElement) {
                            element.remove();
                            if (image.querySelectorAll('.wd-image-positions--depicted').length === 1) {
                                addEditRegionButton(entity);
                            }
                        } else {
                            button.textContent = 'add region';
                            button.classList.remove('wd-image-positions--active');
                        }
                    },
                    function() {
                        element.remove();
                    },
                ).then(doneCallback).finally(() => {
                    document.removeEventListener('keydown', onKeyDown);
                    scaleInput.disabled = false;
                });
                cropper = null;
            }
        }

        function cancelEditing() {
            cropper.destroy();
            cropper = null;
            doneCallback();
            wrapper.classList.remove('wd-image-positions--active');
            image.classList.remove('wd-image-positions--active');
            document.removeEventListener('keydown', onKeyDown);
            button.textContent = 'add region';
            button.classList.remove('wd-image-positions--active');
            scaleInput.disabled = false;
        }
    }

    /**
     * Ensure that the image element is suitable for cropper.js,
     * by temporarily changing its src to the last (presumed highest-resolution) srcset entry.
     * The srcset is assumed to contain PNG/JPG thumbs,
     * whereas the src may be in an unsupported image format, such as TIFF.
     *
     * @param {HTMLElement} image The .wd-image-positions--image containing the <img>
     * (*not* the <img> itself)
     * @return {function} Callback to restore the image to its original src,
     * to be called after the cropper has been destroyed.
     */
    function ensureImageCroppable(image) {
        const img = image.querySelector('img'),
              originalSrc = img.src;

        if (!/\.(?:jpe?g|png|gif)$/i.test(originalSrc)) {
            img.src = img.srcset.split(' ').slice(-2)[0];
        }

        return function() {
            img.src = originalSrc;
        };
    }

    /**
     * Save the cropper as a region qualifier for the depicted.
     *
     * @param {{ id: string, domain: string}} subject The subject entity
     * @param {HTMLElement} image The .wd-image-positions--image (*not* the <img>)
     * @param {HTMLElement} depicted The .wd-image-positions--depicted,
     * with a dataset containing a statementId, optional entityId and optional qualifierHash
     * @param {Cropper} cropper The cropper (will be destroyed)
     * @return {Promise} Rejects in case of error.
     * If it resolves, either the statement was saved successfully,
     * or the user declined to save (in which case the depicted is removed from its parent).
     */
    function saveCropper(subject, image, depicted, cropper) {
        const wrapper = image.parentElement;
        wrapper.classList.remove('wd-image-positions--active');
        image.classList.remove('wd-image-positions--active');
        const cropData = cropper.getData(),
              canvasData = cropper.getCanvasData(),
              x = 100 * cropData.x / canvasData.naturalWidth,
              y = 100 * cropData.y / canvasData.naturalHeight,
              w = 100 * cropData.width / canvasData.naturalWidth,
              h = 100 * cropData.height / canvasData.naturalHeight;
        // note: the browser rounds the percentages a bit,
        // and we’ll use the rounded values for the IIIF region
        depicted.style.left = `${x}%`;
        depicted.style.top = `${y}%`;
        depicted.style.width = `${w}%`;
        depicted.style.height = `${h}%`;
        cropper.destroy();
        function pct(name) {
            return depicted.style[name].replace('%', '');
        }
        const iiifRegion = `pct:${pct('left')},${pct('top')},${pct('width')},${pct('height')}`;

        const statementId = depicted.dataset.statementId,
              qualifierHash = depicted.dataset.qualifierHash,
              csrfToken = csrfTokenElement.textContent,
              formData = new FormData();
        formData.append('statement_id', statementId);
        if (qualifierHash) {
            formData.append('qualifier_hash', qualifierHash);
        }
        formData.append('iiif_region', iiifRegion);
        formData.append('_csrf_token', csrfToken);
        return fetch(`${baseUrl}/api/v2/add_qualifier/${subject.domain}`, {
            method: 'POST',
            body: formData,
            credentials: 'include',
        }).then(response => {
            if (response.ok) {
                return response.json().then(json => {
                    depicted.dataset.qualifierHash = json.qualifier_hash;
                });
            } else {
                return response.text().then(text => {
                    window.alert(`An error occurred:\n\n${text}\n\nThe region drawn is ${iiifRegion}, if you want to add it manually.`);
                    throw new Error('Saving failed');
                });
            }
        });
    }

    function addEditRegionButtons() {
        document.querySelectorAll('.wd-image-positions--entity').forEach(addEditRegionButton);
    }

    function addEditRegionButton(entityElement) {
        const wrapper = entityElement.querySelector('.wd-image-positions--wrapper'),
              image = wrapper.firstElementChild;
        if (!image.querySelector('.wd-image-positions--depicted')) {
            return;
        }
        const scaleInput = entityElement.querySelector('.wd-image-positions--scale');
        const button = document.createElement('button');
        button.type = 'button';
        button.classList.add('btn', 'btn-secondary');
        button.textContent = 'Edit a region';
        button.addEventListener('click', addEditRegionListeners);
        const buttonWrapper = document.createElement('div');
        buttonWrapper.append(button);
        entityElement.append(buttonWrapper);
        const fieldSet = entityElement.querySelector('fieldset');
        if (fieldSet) {
            entityElement.append(fieldSet); // move after buttonWrapper
        }
        let onKeyDown = null;

        function addEditRegionListeners() {
            button.textContent = 'Select a region to edit';
            button.classList.add('wd-image-positions--active');
            for (const depicted of entityElement.querySelectorAll('.wd-image-positions--depicted')) {
                depicted.addEventListener('click', editRegion);
            }
            button.removeEventListener('click', addEditRegionListeners);
            onKeyDown = onEscape(cancelSelectRegion);
            document.addEventListener('keydown', onKeyDown);
        }

        function editRegion(event) {
            event.preventDefault();
            wrapper.classList.add('wd-image-positions--active');
            image.classList.add('wd-image-positions--active');
            scaleInput.disabled = true;
            for (const depicted of entityElement.querySelectorAll('.wd-image-positions--depicted')) {
                depicted.removeEventListener('click', editRegion);
            }
            const depicted = event.target.closest('.wd-image-positions--depicted');
            document.removeEventListener('keydown', onKeyDown);
            onKeyDown = onEscape(cancelEditRegion);
            document.addEventListener('keydown', onKeyDown);
            const doneCallback = ensureImageCroppable(image);
            const cropper = new Cropper(image.firstElementChild, {
                viewMode: 2,
                movable: false,
                rotatable: true, // we don’t rotate the image ourselves, but this allows cropper.js to respect JPEG orientation
                scalable: false,
                zoomable: false,
                checkCrossOrigin: false,
                ready: function() {
                    const canvasData = cropper.getCanvasData();
                    cropper.setData({
                        x: Math.round(parseFloat(depicted.style.left) * canvasData.naturalWidth / 100),
                        y: Math.round(parseFloat(depicted.style.top) * canvasData.naturalHeight / 100),
                        width: Math.round(parseFloat(depicted.style.width) * canvasData.naturalWidth / 100),
                        height: Math.round(parseFloat(depicted.style.height) * canvasData.naturalHeight / 100),
                    });
                    button.textContent = 'use this region';
                    button.addEventListener('click', doEditRegion);
                },
            });

            function doEditRegion() {
                button.removeEventListener('click', doEditRegion);
                button.textContent = 'editing statement…';
                const subject = { id: entityElement.dataset.entityId, domain: entityElement.dataset.entityDomain };
                saveCropper(subject, image, depicted, cropper).then(
                    function() {
                        button.textContent = 'Edit a region';
                        button.classList.remove('wd-image-positions--active');
                        button.addEventListener('click', addEditRegionListeners);
                    },
                    function() {
                        button.textContent = 'Edit a region';
                        button.classList.remove('wd-image-positions--active');
                        button.addEventListener('click', addEditRegionListeners);
                    },
                ).then(doneCallback).finally(() => {
                    document.removeEventListener('keydown', onKeyDown);
                    scaleInput.disabled = false;
                });
            }

            function cancelEditRegion() {
                cropper.destroy();
                doneCallback();
                wrapper.classList.remove('wd-image-positions--active');
                image.classList.remove('wd-image-positions--active');
                button.removeEventListener('click', doEditRegion);
                button.textContent = 'Edit a region';
                button.addEventListener('click', addEditRegionListeners);
                button.classList.remove('wd-image-positions--active');
                document.removeEventListener('keydown', onKeyDown);
                scaleInput.disabled = false;
            }
        }

        function cancelSelectRegion() {
            for (const depicted of entityElement.querySelectorAll('.wd-image-positions--depicted')) {
                depicted.removeEventListener('click', editRegion);
            }
            button.textContent = 'Edit a region';
            button.addEventListener('click', addEditRegionListeners);
            button.classList.remove('wd-image-positions--active');
            document.removeEventListener('keydown', onKeyDown);
        }
    }

    function addNewDepictedForm(entityElement) {
        const entity = entityElement.closest('.wd-image-positions--entity'),
              subjectId = entity.dataset.entityId,
              subjectDomain = entity.dataset.entityDomain,
              propertyIdInput = new OO.ui.DropdownInputWidget({
                  options: Object.entries(depictedProperties).map(entry => ({
                      data: entry[0],
                      label: entry[1][0],
                  })),
                  // for some reason, the propertyIdInput.getInputElement()[0] is not the node in the DOM,
                  // so assign an ID so we can access the actual value in addItemId() below
                  id: 'propertyIdWidget',
              }),
              itemIdInput = new EntityInputWidget({
                  name: 'item_id',
                  required: true,
                  placeholder: 'Q42',
              }),
              itemIdButton = new OO.ui.ButtonWidget({
                  label: 'Add',
              }),
              somevalueButton = new OO.ui.ButtonWidget({
                  label: 'Unknown value',
              }),
              novalueButton = new OO.ui.ButtonWidget({
                  label: 'No value',
              }),
              layout = new OO.ui.FieldsetLayout({
                  items: [
                      new OO.ui.FieldLayout(
                          propertyIdInput,
                      ),
                      new OO.ui.ActionFieldLayout(
                          itemIdInput,
                          itemIdButton,
                          {
                              label: 'Item ID',
                              invisibleLabel: true,
                          },
                      ),
                      new OO.ui.FieldLayout(
                          new OO.ui.ButtonGroupWidget({
                              items: [
                                  somevalueButton,
                                  // novalueButton, // there’s no technical reason not to implement this, but it’s not really useful
                              ],
                          }),
                      ),
                  ],
                  label: 'Add more statements:',
              }),
              layoutElement = layout.$element[0];
        itemIdInput.on('enter', addItemId);
        itemIdButton.on('click', addItemId);
        somevalueButton.on('click', addSomevalue);
        novalueButton.on('click', addNovalue);
        layout.$header.addClass('col-form-label-sm'); // Bootstrap makes OOUI’s <legend> too large by default
        entityElement.append(layoutElement);

        // itemIdInput.getData().getSerialization() can return the wrong item ID after losing focus;
        // only trust item IDs that we get out of the change event instead
        let itemId = undefined;
        itemIdInput.on('change', entity => {
            itemId = entity?.id;
        } );

        function setAllDisabled(disabled) {
            for (const widget of [itemIdInput, itemIdButton, somevalueButton, novalueButton]) {
                widget.setDisabled(disabled);
            }
        }

        function addItemId() {
            if (!itemId) {
                return;
            }
            const formData = new FormData();
            formData.append('snaktype', 'value');
            formData.append('property_id', document.querySelector('#propertyIdWidget select').value);
            formData.append('item_id', itemId);
            addStatement(formData);
        }

        function addSomevalue() {
            const formData = new FormData();
            formData.append('snaktype', 'somevalue');
            addStatement(formData);
        }

        function addNovalue() {
            const formData = new FormData();
            formData.append('snaktype', 'novalue');
            addStatement(formData);
        }

        function addStatement(formData) {
            setAllDisabled(true);
            formData.append('entity_id', subjectId);
            formData.append('_csrf_token', csrfTokenElement.textContent);
            fetch(`${baseUrl}/api/v1/add_statement/${subjectDomain}`, {
                method: 'POST',
                body: formData,
                credentials: 'include',
            }).then(response => {
                if (response.ok) {
                    return response.json().then(json => {
                        const statementId = json.depicted.statement_id;
                        const propertyId = json.depicted.property_id;
                        let depictedsWithoutRegionList = entityElement.querySelector(
                            `.wd-image-positions--depicteds-without-region__${propertyId} ul`,
                        );
                        if (!depictedsWithoutRegionList) {
                            const depictedsWithoutRegionDiv = document.createElement('div'),
                                  depictedsWithoutRegionText = document.createTextNode(
                                      `${depictedProperties[propertyId]?.[1] || propertyId} with no region specified:`,
                                  );
                            depictedsWithoutRegionList = document.createElement('ul');
                            depictedsWithoutRegionDiv.classList.add('wd-image-positions--depicteds-without-region');
                            depictedsWithoutRegionDiv.classList.add(`wd-image-positions--depicteds-without-region__${propertyId}`);
                            depictedsWithoutRegionDiv.append(depictedsWithoutRegionText, depictedsWithoutRegionList);
                            layoutElement.insertAdjacentElement('beforebegin', depictedsWithoutRegionDiv);
                        }
                        const depicted = document.createElement('li');
                        depicted.classList.add('wd-image-positions--depicted-without-region');
                        depicted.dataset.statementId = statementId;
                        depicted.innerHTML = json.depicted_item_link;
                        depictedsWithoutRegionList.append(depicted);
                        addEditButton(depicted);
                    });
                } else {
                    return response.text().then(error => {
                        window.alert(`An error occurred:\n\n${error}`);
                    });
                }
            }).finally(() => {
                setAllDisabled(false);
            });
        }
    }

    function addNewDepictedForms() {
        fixMediaWiki().then(() => {
            mediaWiki.loader.using('wikibase.mediainfo.statements', require => {
                EntityInputWidget = require('wikibase.mediainfo.statements').inputs.EntityInputWidget;
                document.querySelectorAll('.wd-image-positions--entity').forEach(addNewDepictedForm);
            });
        }, console.error);
    }

    function fixMediaWiki() {
        return new Promise((resolve, reject) => {
            // rewrite 'local' source (/w/load.php) to one with explicit domain,
            // and reset modules that could not be loaded from 'local'
            mediaWiki.loader.addSource({
                'commons': 'https://commons.wikimedia.org/w/load.php',
            });
            const needReload = [];
            for (const [name, module] of Object.entries(mediaWiki.loader.moduleRegistry)) {
                if (module.source === 'local') {
                    module.source = 'commons';
                }
                if (module.state === 'loading') {
                    module.state = 'registered';
                    needReload.push(name);
                }
            }
            // configure WikibaseMediaInfo
            mediaWiki.config.set('wbmiExternalEntitySearchBaseUri', 'https://www.wikidata.org/w/api.php');
            // remove private dependencies of modules
            for (const module of Object.values(mediaWiki.loader.moduleRegistry)) {
                const userOptionsDependencyIndex = module.dependencies.indexOf('user.options');
                if (userOptionsDependencyIndex !== -1) {
                    module.dependencies.splice(userOptionsDependencyIndex, 1); // user.options module is private, we can’t load it
                }
            }
            // reload modules that could not be loaded from 'local'
            mediaWiki.loader.enqueue(needReload, resolve, reject);
        }).then(() => {
            return mediaWiki.loader.using('wikibase.api.RepoApi').then(() => {
                if ('getLocationAgnosticMwApi' in wikibase.api) { // used for EntityInputWidget’s search, but cf. T239518
                    wikibase.api.getLocationAgnosticMwApi = function(apiEndpoint) {
                        // original implementation isn’t anonymous, but we can only make anonymous requests
                        return new mediaWiki.ForeignApi(apiEndpoint, { anonymous: true });
                    };
                } else {
                    console.error('no getLocationAgnosticMwApi!');
                }
            });
        });
    }

    addScaleInputs();
    if (csrfTokenElement !== null) {
        addEditButtons();
        addEditRegionButtons();
        addNewDepictedForms();
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setup);
} else {
    setup();
}
