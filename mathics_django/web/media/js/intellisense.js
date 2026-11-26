// -*- mode: js; js-indent-level: 4; -*-
/**
 * Mathics3 Notebook IntelliSense:
 *  - Live symbol & function autocompletion popup (with call signatures and summary docs)
 *  - Context-aware Signature Help tooltip inside function brackets Func[...]
 *  - Smart auto-closing brackets [...], {...}, (...)
 */

const MathicsIntelliSense = (() => {
    let symbols = [];
    let symbolMap = new Map();
    let popupEl = null;
    let sigTooltipEl = null;
    let activeItems = [];
    let selectedIndex = 0;
    let currentToken = null;
    let activeTextarea = null;

    const PRIORITY_SYMBOLS = new Set([
        'Integrate', 'NIntegrate', 'D', 'Derivative', 'Limit', 'Series',
        'Solve', 'FindRoot', 'DSolve', 'Simplify', 'FullSimplify',
        'Expand', 'Factor', 'Apart', 'Together', 'TrigReduce', 'TrigExpand',
        'TrigToExp', 'ExpToTrig', 'Plot', 'Plot3D', 'ListPlot',
        'ParametricPlot', 'PolarPlot', 'Table', 'Map', 'Apply', 'Select',
        'Sin', 'Cos', 'Tan', 'Cot', 'Sec', 'Csc', 'ArcTan', 'ArcSin', 'ArcCos',
        'Sinh', 'Cosh', 'Tanh', 'Exp', 'Log', 'Sqrt', 'Gamma', 'Zeta',
        'Pi', 'E', 'I', 'Infinity', 'N'
    ]);

    function injectStyles() {
        if (document.getElementById('mathics-intellisense-styles')) {
            return;
        }
        const style = document.createElement('style');
        style.id = 'mathics-intellisense-styles';
        style.textContent = `
            #mathics-intellisense-popup {
                position: fixed;
                z-index: 99999;
                background: #1e222a;
                color: #e6edf3;
                border: 1px solid #3b4252;
                border-radius: 6px;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
                font-family: Consolas, "Fira Code", Menlo, monospace;
                font-size: 13px;
                min-width: min(320px, calc(100vw - 16px));
                max-width: min(560px, calc(100vw - 16px));
                max-height: 260px;
                overflow-y: auto;
                display: none;
                padding: 4px 0;
            }
            .mi-item {
                display: flex;
                align-items: baseline;
                justify-content: space-between;
                gap: 12px;
                padding: 5px 10px;
                cursor: pointer;
                border-left: 3px solid transparent;
            }
            .mi-item.mi-selected {
                background: #2d3648;
                border-left-color: #58a6ff;
            }
            .mi-item:hover {
                background: #262c3a;
            }
            .mi-left {
                display: flex;
                align-items: baseline;
                gap: 7px;
                white-space: nowrap;
            }
            .mi-badge {
                display: inline-block;
                width: 16px;
                height: 16px;
                line-height: 16px;
                text-align: center;
                border-radius: 3px;
                font-size: 11px;
                font-weight: bold;
            }
            .mi-badge-fn {
                background: rgba(163, 113, 247, 0.2);
                color: #d2a8ff;
            }
            .mi-badge-sym {
                background: rgba(88, 166, 255, 0.2);
                color: #79c0ff;
            }
            .mi-name {
                color: #f0f6fc;
                font-weight: 600;
            }
            .mi-match {
                color: #58a6ff;
                text-decoration: underline;
            }
            .mi-sig {
                color: #8b949e;
                font-size: 12px;
            }
            .mi-summary {
                color: #9ca3af;
                font-size: 11.5px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                max-width: 280px;
            }
            .mi-footer {
                padding: 3px 10px;
                border-top: 1px solid #30363d;
                color: #8b949e;
                font-size: 10.5px;
                display: flex;
                justify-content: space-between;
                background: #161b22;
            }
            #mathics-signature-tooltip {
                position: fixed;
                z-index: 99998;
                background: #161b22;
                color: #e6edf3;
                border: 1px solid #3b4252;
                border-radius: 5px;
                box-shadow: 0 4px 14px rgba(0, 0, 0, 0.28);
                padding: 4px 8px;
                font-family: Consolas, "Fira Code", Menlo, monospace;
                font-size: 12px;
                display: none;
                max-width: min(540px, calc(100vw - 16px));
                pointer-events: none;
            }
            .ms-sig-line {
                color: #79c0ff;
                font-weight: 600;
            }
            .ms-doc-line {
                color: #9ca3af;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                font-size: 11.5px;
                margin-top: 2px;
            }
        `;
        document.head.appendChild(style);
    }

    function ensureDOM() {
        injectStyles();
        if (!popupEl) {
            popupEl = document.createElement('div');
            popupEl.id = 'mathics-intellisense-popup';
            popupEl.setAttribute('role', 'listbox');
            document.body.appendChild(popupEl);
        }
        if (!sigTooltipEl) {
            sigTooltipEl = document.createElement('div');
            sigTooltipEl.id = 'mathics-signature-tooltip';
            document.body.appendChild(sigTooltipEl);
        }
    }

    function loadSymbols() {
        fetch('ajax/completions/')
            .then((r) => r.json())
            .then((data) => {
                if (data && Array.isArray(data.symbols)) {
                    symbols = data.symbols;
                    symbolMap.clear();
                    symbols.forEach((s) => symbolMap.set(s.name, s));
                }
            })
            .catch((err) => {
                console.warn('MathicsIntelliSense: could not load symbol completions:', err);
            });
    }

    function extractTokenAtCaret(textarea) {
        const pos = textarea.selectionStart;
        const textBefore = textarea.value.slice(0, pos);
        const match = textBefore.match(/([A-Za-z$][A-Za-z0-9$]*)$/);
        if (!match) {
            return null;
        }
        return {
            word: match[1],
            start: pos - match[1].length,
            end: pos
        };
    }

    function findEnclosingCall(textarea) {
        const pos = textarea.selectionStart;
        const text = textarea.value.slice(0, pos);
        let depthSquare = 0;
        let depthCurly = 0;
        let depthParen = 0;
        for (let i = text.length - 1; i >= 0; i--) {
            const ch = text[i];
            if (ch === ']') depthSquare++;
            else if (ch === '}') depthCurly++;
            else if (ch === ')') depthParen++;
            else if (ch === '{' && depthCurly > 0) depthCurly--;
            else if (ch === '(' && depthParen > 0) depthParen--;
            else if (ch === '[') {
                if (depthSquare > 0) {
                    depthSquare--;
                } else {
                    const beforeBracket = text.slice(0, i);
                    const fnMatch = beforeBracket.match(/([A-Za-z$][A-Za-z0-9$]*)\s*$/);
                    if (fnMatch) {
                        return {
                            name: fnMatch[1],
                            bracketIndex: i - fnMatch[0].length
                        };
                    }
                    return null;
                }
            }
        }
        return null;
    }

    function rankMatches(word) {
        if (!word) {
            return [];
        }
        const wLow = word.toLowerCase();
        const exactCasePrefix = [];
        const caseInsensitivePrefix = [];
        const substringMatch = [];

        for (let i = 0; i < symbols.length; i++) {
            const item = symbols[i];
            const name = item.name;
            const nLow = name.toLowerCase();
            if (name.startsWith(word)) {
                exactCasePrefix.push(item);
            } else if (nLow.startsWith(wLow)) {
                caseInsensitivePrefix.push(item);
            } else if (word.length >= 2 && nLow.includes(wLow)) {
                substringMatch.push(item);
            }
        }

        const sortFn = (a, b) => {
            const pa = PRIORITY_SYMBOLS.has(a.name) ? 0 : 1;
            const pb = PRIORITY_SYMBOLS.has(b.name) ? 0 : 1;
            if (pa !== pb) return pa - pb;
            if (a.name.length !== b.name.length) return a.name.length - b.name.length;
            return a.name.localeCompare(b.name);
        };

        exactCasePrefix.sort(sortFn);
        caseInsensitivePrefix.sort(sortFn);
        substringMatch.sort(sortFn);

        return [...exactCasePrefix, ...caseInsensitivePrefix, ...substringMatch].slice(0, 10);
    }

    function getCaretCoordinates(textarea, charIndex) {
        const rect = textarea.getBoundingClientRect();
        const cs = window.getComputedStyle(textarea);

        const mirror = document.createElement('div');
        const copyProps = [
            'boxSizing', 'width', 'fontFamily', 'fontSize', 'fontWeight',
            'fontStyle', 'letterSpacing', 'textTransform', 'wordSpacing',
            'textIndent', 'whiteSpace', 'wordWrap', 'lineHeight',
            'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
            'borderTopWidth', 'borderRightWidth', 'borderBottomWidth', 'borderLeftWidth'
        ];
        copyProps.forEach((p) => {
            mirror.style[p] = cs[p];
        });
        mirror.style.position = 'fixed';
        mirror.style.left = `${rect.left}px`;
        mirror.style.top = `${rect.top}px`;
        mirror.style.visibility = 'hidden';
        mirror.style.whiteSpace = 'pre-wrap';
        mirror.style.wordWrap = 'break-word';
        mirror.style.overflow = 'hidden';

        mirror.textContent = textarea.value.slice(0, charIndex);
        const marker = document.createElement('span');
        marker.textContent = textarea.value.slice(charIndex, charIndex + 1) || '|';
        mirror.appendChild(marker);
        document.body.appendChild(mirror);

        const markerRect = marker.getBoundingClientRect();
        const lineH = parseFloat(cs.lineHeight) || markerRect.height || 18;
        const coords = {
            left: markerRect.left - textarea.scrollLeft,
            top: markerRect.top - textarea.scrollTop + lineH + 2,
            caretTop: markerRect.top - textarea.scrollTop,
            lineHeight: lineH
        };
        document.body.removeChild(mirror);
        return coords;
    }

    function hidePopup() {
        if (popupEl) {
            popupEl.style.display = 'none';
        }
        activeItems = [];
        selectedIndex = 0;
        currentToken = null;
    }

    function hideSignatureTooltip() {
        if (sigTooltipEl) {
            sigTooltipEl.style.display = 'none';
        }
    }

    function isPopupVisible() {
        return Boolean(popupEl && popupEl.style.display === 'block' && activeItems.length > 0);
    }

    function renderPopup(textarea, token, items) {
        ensureDOM();
        activeTextarea = textarea;
        currentToken = token;
        activeItems = items;
        if (selectedIndex >= items.length) {
            selectedIndex = 0;
        }

        popupEl.innerHTML = '';
        items.forEach((item, idx) => {
            const row = document.createElement('div');
            row.className = 'mi-item' + (idx === selectedIndex ? ' mi-selected' : '');
            row.setAttribute('role', 'option');

            const left = document.createElement('div');
            left.className = 'mi-left';

            const badge = document.createElement('span');
            badge.className = 'mi-badge ' + (item.is_function ? 'mi-badge-fn' : 'mi-badge-sym');
            badge.textContent = item.is_function ? 'ƒ' : '𝑥';

            const nameSpan = document.createElement('span');
            nameSpan.className = 'mi-name';
            nameSpan.textContent = item.name;

            left.appendChild(badge);
            left.appendChild(nameSpan);

            if (item.signatures && item.signatures.length > 0) {
                const sigSpan = document.createElement('span');
                sigSpan.className = 'mi-sig';
                const firstSig = item.signatures[0];
                const bracketIdx = firstSig.indexOf('[');
                sigSpan.textContent = bracketIdx >= 0 ? firstSig.slice(bracketIdx) : '';
                left.appendChild(sigSpan);
            }

            const summarySpan = document.createElement('div');
            summarySpan.className = 'mi-summary';
            summarySpan.textContent = item.summary || '';

            row.appendChild(left);
            row.appendChild(summarySpan);

            row.addEventListener('mousedown', (e) => {
                e.preventDefault();
                e.stopPropagation();
                selectedIndex = idx;
                applyCompletion(item);
            });

            popupEl.appendChild(row);
        });

        const footer = document.createElement('div');
        footer.className = 'mi-footer';
        footer.innerHTML = '<span><b>Tab</b> / <b>Enter</b> to insert · <b>↑↓</b> navigate · <b>Esc</b> close</span><span>Mathics3 IntelliSense</span>';
        popupEl.appendChild(footer);

        const coords = getCaretCoordinates(textarea, token.start);
        popupEl.style.display = 'block';
        const maxLeft = Math.max(6, window.innerWidth - popupEl.offsetWidth - 8);
        popupEl.style.left = `${Math.max(6, Math.min(coords.left, maxLeft))}px`;
        popupEl.style.top = `${coords.top}px`;
    }

    function updateSignatureTooltip(textarea) {
        ensureDOM();
        const resultInfo = findEnclosingCall(textarea);
        if (!resultInfo || !symbolMap.has(resultInfo.name)) {
            hideSignatureTooltip();
            return;
        }
        const info = symbolMap.get(resultInfo.name);
        const sigText = (info.signatures && info.signatures.length > 0)
            ? info.signatures.join('  |  ')
            : `${resultInfo.name}[...]`;

        sigTooltipEl.innerHTML = '';
        const sigLine = document.createElement('div');
        sigLine.className = 'ms-sig-line';
        sigLine.textContent = sigText;
        sigTooltipEl.appendChild(sigLine);

        if (info.summary) {
            const docLine = document.createElement('div');
            docLine.className = 'ms-doc-line';
            docLine.textContent = info.summary;
            sigTooltipEl.appendChild(docLine);
        }

        // Anchor the signature tooltip directly to the opening bracket `Func[`
        const coords = getCaretCoordinates(textarea, resultInfo.bracketIndex);
        sigTooltipEl.style.display = 'block';
        const maxLeft = Math.max(6, window.innerWidth - sigTooltipEl.offsetWidth - 8);
        sigTooltipEl.style.left = `${Math.max(6, Math.min(coords.left, maxLeft))}px`;
        if (isPopupVisible()) {
            sigTooltipEl.style.top = `${Math.max(4, coords.caretTop - sigTooltipEl.offsetHeight - 4)}px`;
        } else {
            sigTooltipEl.style.top = `${coords.top}px`;
        }
    }

    function applyCompletion(item) {
        if (!activeTextarea || !currentToken) {
            return;
        }
        const ta = activeTextarea;
        const before = ta.value.slice(0, currentToken.start);
        const after = ta.value.slice(currentToken.end);

        let insertion = item.name;
        let caretShift = insertion.length;

        if (item.is_function && !after.startsWith('[')) {
            insertion += '[]';
            caretShift = item.name.length + 1;
        }

        ta.value = before + insertion + after;
        const newPos = currentToken.start + caretShift;
        ta.focus();
        ta.setSelectionRange(newPos, newPos);
        if (typeof refreshInputSize === 'function') {
            refreshInputSize(ta);
        }
        hidePopup();
        updateSignatureTooltip(ta);
    }

    function updateForTextarea(textarea, forceOpen = false) {
        const token = extractTokenAtCaret(textarea);
        if (!token || (!forceOpen && token.word.length < 1)) {
            hidePopup();
            updateSignatureTooltip(textarea);
            return;
        }
        const matches = rankMatches(token.word);
        // Hide if the only match is already completely typed
        if (!forceOpen && matches.length === 1 && matches[0].name === token.word) {
            hidePopup();
            updateSignatureTooltip(textarea);
            return;
        }
        if (matches.length === 0) {
            hidePopup();
            updateSignatureTooltip(textarea);
            return;
        }
        renderPopup(textarea, token, matches);
        updateSignatureTooltip(textarea);
    }

    function onKeyDownCapture(event) {
        let ta = event.target;
        if ((!ta || ta.tagName !== 'TEXTAREA' || !ta.classList.contains('request')) && isPopupVisible() && activeTextarea) {
            ta = activeTextarea;
        }
        if (!ta || ta.tagName !== 'TEXTAREA' || !ta.classList.contains('request')) {
            return;
        }

        // Ctrl+Space manual trigger
        if (event.ctrlKey && (event.code === 'Space' || event.key === ' ')) {
            event.preventDefault();
            event.stopPropagation();
            const token = extractTokenAtCaret(ta) || {
                word: 'I',
                start: ta.selectionStart,
                end: ta.selectionStart
            };
            const matches = rankMatches(token.word);
            if (matches.length > 0) {
                renderPopup(ta, token, matches);
            }
            return;
        }

        if (isPopupVisible()) {
            if (event.key === 'ArrowDown') {
                event.preventDefault();
                event.stopPropagation();
                selectedIndex = (selectedIndex + 1) % activeItems.length;
                renderPopup(ta, currentToken, activeItems);
                return;
            }
            if (event.key === 'ArrowUp') {
                event.preventDefault();
                event.stopPropagation();
                selectedIndex = (selectedIndex - 1 + activeItems.length) % activeItems.length;
                renderPopup(ta, currentToken, activeItems);
                return;
            }
            if (event.key === 'Tab' || (event.key === 'Enter' && !event.shiftKey)) {
                event.preventDefault();
                event.stopPropagation();
                applyCompletion(activeItems[selectedIndex]);
                return;
            }
            if (event.key === 'Escape') {
                event.preventDefault();
                event.stopPropagation();
                hidePopup();
                hideSignatureTooltip();
                return;
            }
        }

        // Auto-closing brackets [...], {...}, (...)
        const pairs = { '[': ']', '{': '}', '(': ')' };
        const closers = new Set([']', '}', ')']);
        const pos = ta.selectionStart;
        const selEnd = ta.selectionEnd;

        if (pos === selEnd && closers.has(event.key) && ta.value[pos] === event.key) {
            event.preventDefault();
            ta.setSelectionRange(pos + 1, pos + 1);
            updateSignatureTooltip(ta);
            return;
        }

        if (pos === selEnd && pairs[event.key] && !event.ctrlKey && !event.altKey && !event.metaKey) {
            const nextCh = ta.value[pos] || '';
            if (!/[A-Za-z0-9$]/.test(nextCh)) {
                event.preventDefault();
                const openCh = event.key;
                const closeCh = pairs[openCh];
                ta.value = ta.value.slice(0, pos) + openCh + closeCh + ta.value.slice(pos);
                ta.setSelectionRange(pos + 1, pos + 1);
                hidePopup();
                updateSignatureTooltip(ta);
                return;
            }
        }
    }

    function onInputOrKeyUp(event) {
        const ta = event.target;
        if (!ta || ta.tagName !== 'TEXTAREA' || !ta.classList.contains('request')) {
            return;
        }
        if (['ArrowDown', 'ArrowUp', 'Enter', 'Tab', 'Escape', 'Shift', 'Control', 'Alt'].includes(event.key)) {
            if (event.key === 'Enter' && (event.shiftKey || event.location === 3)) {
                hidePopup();
                hideSignatureTooltip();
                setTimeout(loadSymbols, 400);
            }
            if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
                updateSignatureTooltip(ta);
            }
            return;
        }
        updateForTextarea(ta, false);
    }

    function init() {
        ensureDOM();
        loadSymbols();
        document.addEventListener('keydown', onKeyDownCapture, true);
        document.addEventListener('keyup', onInputOrKeyUp, true);
        document.addEventListener('click', (e) => {
            const ta = e.target;
            if (ta && ta.tagName === 'TEXTAREA' && ta.classList.contains('request')) {
                updateSignatureTooltip(ta);
            } else if (!popupEl || !popupEl.contains(e.target)) {
                hidePopup();
                hideSignatureTooltip();
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return {
        loadSymbols,
        updateForTextarea,
        hidePopup,
        isPopupVisible
    };
})();
