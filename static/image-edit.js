import { createApp } from 'vue';
import * as codex from 'codex';
import * as codexIcons from 'codex-icons';
import Session, { set } from 'm3api/browser.js';

function setup() {
    'use strict';

    const csrfTokenElement = document.getElementById('csrf_token'),
          baseUrl = document.querySelector('link[rel=index]').href.replace(/\/$/, ''),
          mainDataset = document.getElementsByTagName('main')[0].dataset,
          depictedPropertiesLabels = JSON.parse(mainDataset.depictedPropertiesLabels),
          depictedPropertiesMessages = JSON.parse(mainDataset.depictedPropertiesMessages);

    /** Make a key event handler that calls the given callback when Esc is pressed. */
    function onEscape(callback) {
        return function(eKey) {
            if (eKey.key === 'Escape') {
                return callback.apply(this, arguments);
            }
        };
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
        button.classList.add('btn', 'btn-secondary', 'btn-sm', 'ms-2');
        button.textContent = 'add region';
        button.addEventListener('click', onClick);
        element.append(button);

        let cropper = null;
        let doneCallback = null;
        const onKeyDown = onEscape(cancelEditing);
        let cancelButton = null;

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
                    autoCrop: false,
                    ready: function() {
                        button.textContent = 'use this region';

                        cancelButton = document.createElement('button');
                        cancelButton.type = 'button';
                        cancelButton.classList.add('btn', 'btn-secondary', 'btn-sm', 'wd-image-positions--active', 'ms-2');
                        cancelButton.textContent = 'cancel';
                        cancelButton.addEventListener('click', cancelEditing);
                        element.append(cancelButton);
                    },
                });
                document.addEventListener('keydown', onKeyDown);
            } else {
                if (button.textContent === 'loading...') {
                    return;
                }
                const cropData = cropper.getData();
                if (!cropData.width || !cropData.height) {
                    window.alert('Please select a region first. (Drag the mouse across an area, then adjust as needed.)');
                    return;
                }

                const depicted = document.createElement('div');
                depicted.classList.add('wd-image-positions--depicted')
                const propertyId = [...element.closest('.wd-image-positions--depicteds-without-region').classList]
                      .filter(klass => klass.startsWith('wd-image-positions--depicteds-without-region__'))
                      .map(klass => klass.slice('wd-image-positions--depicteds-without-region__'.length))[0];
                depicted.classList.add(`wd-image-positions--depicted__${propertyId}`)
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
                        element.remove();
                        if (image.querySelectorAll('.wd-image-positions--depicted').length === 1) {
                            addEditRegionButton(entity);
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
            if (cancelButton !== null) {
                cancelButton.remove();
                cancelButton = null;
            }
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
     * @return {Promise}
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
        const cancelButton = document.createElement('button');
        cancelButton.type = 'button';
        cancelButton.classList.add('btn', 'btn-secondary', 'wd-image-positions--active', 'ms-2');
        cancelButton.textContent = 'cancel';
        const buttonWrapper = document.createElement('div');
        buttonWrapper.append(button);
        // cancelButton is not appended yet
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
            buttonWrapper.append(cancelButton);
            cancelButton.addEventListener('click', cancelSelectRegion);
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
            cancelButton.removeEventListener('click', cancelSelectRegion);
            onKeyDown = onEscape(cancelEditRegion);
            document.addEventListener('keydown', onKeyDown);
            cancelButton.addEventListener('click', cancelEditRegion);
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
                    cancelButton.remove();
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
                cancelButton.remove();
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
            cancelButton.remove();
        }
    }

    function addNewDepictedForm(entityElement) {
        const session = new Session( 'www.wikidata.org', {
            formatversion: 2,
            origin: '*',
        }, {
            userAgent: 'Wikidata-Image-Positions (https://wd-image-positions.toolforge.org/)',
        } );
        const entity = entityElement.closest('.wd-image-positions--entity'),
              subjectId = entity.dataset.entityId,
              subjectDomain = entity.dataset.entityDomain,
              newDepictedFormRoot = document.createElement('div');
        entityElement.append(newDepictedFormRoot);

        createApp({
            template: `
<form class="wd-image-positions--add-new-depicted-form">
    <h3>Add more statements:</h3>
    <div class="wd-image-positions--add-new-depicted-form-row">
        <cdx-select
            v-model:selected="selectedProperty"
            :menu-items="properties"
        />
    </div>
    <div class="wd-image-positions--add-new-depicted-form-row">
        <cdx-lookup
            v-model:selected="selectedItem"
            :menu-items="searchResults"
            :menu-config="{'visible-item-limit': searchLimit}"
            :disabled="disabled"
            @input="onSearchInput"
            @load-more="onSearchLoadMore"
        />
        <cdx-button
            :disabled="disabled"
            @click.prevent="onAddItem"
        >
            <cdx-icon :icon="cdxIconAdd" />
            Add statement
        </cdx-button>
    </div>
    <div class="wd-image-positions--add-new-depicted-form-row">
        <cdx-button
            :disabled="disabled"
            @click.prevent="onAddNonValue('somevalue')"
        >
            <cdx-icon :icon="cdxIconAdd" />
            Add “unknown value” statement
        </cdx-button>
        <!-- there’s no technical reason not to implement this, but it’s not really useful
        <cdx-button
            :disabled="disabled"
            @click.prevent="onAddNonValue('novalue')"
        >
            No value
        </cdx-button>
        -->
    </div>
</form>
`,
            components: codex,
            data() {
                const properties = Object.entries(depictedPropertiesLabels).map(entry => ({
                    value: entry[0],
                    label: entry[1].value,
                }));
                return {
                    disabled: false,
                    properties,
                    selectedProperty: properties[0].value,
                    selectedItem: null,
                    searchResults: [],
                    searchValue: '',
                    searchLimit: 5,
                    searchOffset: 0,
                    ...codexIcons,
                };
            },
            methods: {
                async onSearchInput(value) {
                    this.searchValue = value;
                    this.searchOffset = 0;
                    if (!value) {
                        this.searchResults = [];
                        return;
                    }
                    const searchResults = await this.doSearch(value, this.searchOffset);
                    if (this.searchValue !== value) {
                        return; // changed during the request
                    }
                    this.searchResults = searchResults;
                    this.searchOffset += this.searchLimit;
                },

                async onSearchLoadMore() {
                    const value = this.searchValue;
                    const moreResults = await this.doSearch(value, this.searchOffset);
                    if (this.searchValue !== value) {
                        return; // changed during the request
                    }
                    this.searchResults.push(...moreResults);
                    this.searchOffset += this.searchLimit;
                },

                async doSearch(value, offset) {
                    const response = await session.request({
                        action: 'wbsearchentities',
                        search: value,
                        language: 'en',
                        type: 'item',
                        limit: this.searchLimit,
                        continue: this.searchOffset,
                        props: set(),
                    });
                    return response.search.map(result => ({
                        value: result.id,
                        label: result.display?.label?.value,
                        description: result.display?.description?.value,
                        match: result.match.type === 'alias' ? `(${result.match.text})` : '',
                        language: {
                            label: result.display?.label?.language,
                            description: result.display?.description?.language,
                            match: result.match.type === 'alias' ? result.match.language : undefined,
                        },
                    }));
                },

                onAddItem() {
                    if (!this.selectedItem) {
                        return;
                    }
                    const formData = new FormData();
                    formData.append('snaktype', 'value');
                    formData.append('property_id', this.selectedProperty);
                    formData.append('item_id', this.selectedItem);
                    this.addStatement(formData);
                },

                onAddNonValue(snakType) {
                    const formData = new FormData();
                    formData.append('snaktype', snakType);
                    this.addStatement(formData);
                },

                addStatement(formData) {
                    this.disabled = true;
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
                                              depictedPropertiesMessages[propertyId],
                                          );
                                    depictedsWithoutRegionList = document.createElement('ul');
                                    depictedsWithoutRegionDiv.classList.add('wd-image-positions--depicteds-without-region');
                                    depictedsWithoutRegionDiv.classList.add(`wd-image-positions--depicteds-without-region__${propertyId}`);
                                    depictedsWithoutRegionDiv.append(depictedsWithoutRegionText, depictedsWithoutRegionList);
                                    newDepictedFormRoot.insertAdjacentElement('beforebegin', depictedsWithoutRegionDiv);
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
                        this.disabled = false;
                    });
                }

            },
        }).mount(newDepictedFormRoot);
    }

    function addNewDepictedForms() {
        document.querySelectorAll('.wd-image-positions--entity').forEach(entityElement => {
            addNewDepictedForm(entityElement);
        });
    }

    addEditButtons();
    addEditRegionButtons();
    addNewDepictedForms();
}

setup();
