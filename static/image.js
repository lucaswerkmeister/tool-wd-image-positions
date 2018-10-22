function addEditButtons() {
    document.querySelectorAll('.depicted-without-region').forEach(addEditButton);
}

function addEditButton(element) {
    const item = element.closest('.item'),
          subjectId = item.dataset.entityId,
          depictedId = element.firstChild.dataset.entityId,
          image = item.querySelector('.image');
    const button = document.createElement('button');
    button.type = 'button';
    button.classList.add('btn', 'btn-secondary', 'btn-sm');
    button.textContent = 'add region';
    button.addEventListener('click', onClick)
    element.append(document.createTextNode(' '));
    element.append(button);

    function onClick() {
        image.classList.add('active');
        image.addEventListener('mousedown', onMouseDown, { once: true });
        button.textContent = 'click and drag on the image to define the region';
    }
    function onMouseDown(eDown) {
        eDown.preventDefault();
        const downX = eDown.offsetX,
              downY = eDown.offsetY,
              width = eDown.target.offsetWidth,
              height = eDown.target.offsetHeight;
        const depicted = document.createElement('div');
        depicted.classList.add('depicted')
        depicted.append(element.firstChild.cloneNode(true));
        depicted.style.left = (100 * downX / width) + '%';
        depicted.style.top = (100 * downY / height) + '%';
        image.append(depicted);
        image.addEventListener('mousemove', onMouseMove);
        image.addEventListener('mouseup', onMouseUp, { once: true });
        document.addEventListener('keypress', onKeyPress);

        function onMouseMove(eMove) {
            depicted.style.width = (100 * (eMove.offsetX - downX) / width) + '%';
            depicted.style.height = (100 * (eMove.offsetY - downY) / height) + '%';
        }
        function onMouseUp(eUp) {
            image.classList.remove('active');
            image.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('keypress', onKeyPress);
            button.textContent = 'add region';
            if (window.confirm('Copy the new region to the clipboard (in QuickStatements syntax)?')) {
                const x = depicted.style.left.replace('%', ''),
                      y = depicted.style.top.replace('%', ''),
                      w = depicted.style.width.replace('%', ''),
                      h = depicted.style.height.replace('%', '');
                navigator.clipboard.writeText(`${subjectId}\tP180\t${depictedId}\tP2677\t"pct:${x},${y},${w},${h}"`);
                element.remove();
            } else {
                depicted.remove();
            }
        }
        function onKeyPress(eKey) {
            if (eKey.key === 'Escape') {
                image.classList.remove('active');
                image.removeEventListener('mousemove', onMouseMove);
                image.removeEventListener('mouseup', onMouseUp);
                document.removeEventListener('keypress', onKeyPress);
                button.textContent = 'add region';
                depicted.remove();
            }
        }
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', addEditButtons);
} else {
    addEditButtons();
}
