/**
 * Simonini-isms Text Highlighting
 * Allows users to select and highlight text within rules
 */

document.addEventListener('DOMContentLoaded', function() {
    // Handle text selection for highlighting
    document.querySelectorAll('.rule-content').forEach(container => {
        container.addEventListener('mouseup', handleTextSelection);
    });

    function handleTextSelection(e) {
        const selection = window.getSelection();
        const selectedText = selection.toString().trim();

        if (!selectedText || selectedText.length < 3) {
            return;
        }

        const container = e.currentTarget;
        const ruleId = container.dataset.ruleId;

        // Calculate offsets
        const range = selection.getRangeAt(0);

        // Get text content before the selection
        const preCaretRange = range.cloneRange();
        preCaretRange.selectNodeContents(container);
        preCaretRange.setEnd(range.startContainer, range.startOffset);
        const startOffset = preCaretRange.toString().length;
        const endOffset = startOffset + selectedText.length;

        // Show highlight popup
        showHighlightPopup(ruleId, startOffset, endOffset, selectedText, e.pageX, e.pageY);
    }

    function showHighlightPopup(ruleId, startOffset, endOffset, text, x, y) {
        // Remove existing popup
        const existingPopup = document.getElementById('highlight-popup');
        if (existingPopup) existingPopup.remove();

        const popup = document.createElement('div');
        popup.id = 'highlight-popup';
        popup.className = 'position-absolute bg-white border rounded shadow-sm p-2';
        popup.style.left = `${x}px`;
        popup.style.top = `${y + 10}px`;
        popup.style.zIndex = '1000';
        popup.innerHTML = `
            <div class="d-flex gap-1">
                <button class="btn btn-sm btn-warning highlight-color" data-color="yellow" title="Yellow">
                    <i class="fas fa-highlighter"></i>
                </button>
                <button class="btn btn-sm btn-success highlight-color" data-color="green" title="Green">
                    <i class="fas fa-highlighter"></i>
                </button>
                <button class="btn btn-sm btn-info highlight-color" data-color="blue" title="Blue">
                    <i class="fas fa-highlighter"></i>
                </button>
                <button class="btn btn-sm btn-secondary" id="cancel-highlight">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;

        document.body.appendChild(popup);

        // Handle color selection
        popup.querySelectorAll('.highlight-color').forEach(btn => {
            btn.addEventListener('click', async function() {
                const color = this.dataset.color;
                await saveHighlight(ruleId, startOffset, endOffset, text, color);
                popup.remove();
            });
        });

        // Handle cancel
        popup.querySelector('#cancel-highlight').addEventListener('click', function() {
            popup.remove();
        });

        // Remove popup when clicking outside
        document.addEventListener('click', function closePopup(e) {
            if (!popup.contains(e.target)) {
                popup.remove();
                document.removeEventListener('click', closePopup);
            }
        }, { once: true });
    }

    async function saveHighlight(ruleId, startOffset, endOffset, text, color) {
        try {
            const response = await fetch('/api/highlights', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    rule_id: parseInt(ruleId),
                    start_offset: startOffset,
                    end_offset: endOffset,
                    highlighted_text: text,
                    highlight_color: color
                })
            });

            if (response.ok) {
                const highlight = await response.json();
                applyHighlight(ruleId, startOffset, endOffset, color, highlight.highlight_id);
                showToast('Text highlighted!', 'success');

                // Update highlights list if on rule page
                updateHighlightsList(highlight);
            }
        } catch (e) {
            showToast('Error saving highlight', 'danger');
        }
    }

    function applyHighlight(ruleId, startOffset, endOffset, color, highlightId) {
        const container = document.querySelector(`.rule-content[data-rule-id="${ruleId}"]`);
        if (!container) return;

        const text = container.textContent;
        const before = text.substring(0, startOffset);
        const highlighted = text.substring(startOffset, endOffset);
        const after = text.substring(endOffset);

        container.innerHTML = `${escapeHtml(before)}<mark class="highlight-${color}" data-highlight-id="${highlightId}">${escapeHtml(highlighted)}</mark>${escapeHtml(after)}`;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function updateHighlightsList(highlight) {
        const list = document.getElementById('highlightsList');
        const noHighlights = document.getElementById('noHighlights');
        const countBadge = document.getElementById('highlightCount');

        if (noHighlights) noHighlights.remove();

        if (list) {
            const item = document.createElement('li');
            item.className = 'mb-2 p-2 rounded highlight-item';
            item.style.backgroundColor = `${highlight.highlight_color}30`;
            item.dataset.highlightId = highlight.highlight_id;
            item.innerHTML = `
                <div class="d-flex justify-content-between align-items-start">
                    <span class="small">"${highlight.highlighted_text.substring(0, 50)}${highlight.highlighted_text.length > 50 ? '...' : ''}"</span>
                    <button class="btn btn-sm btn-link text-danger p-0 delete-highlight"
                            data-highlight-id="${highlight.highlight_id}">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `;
            list.appendChild(item);

            // Bind delete event
            item.querySelector('.delete-highlight').addEventListener('click', async function() {
                const response = await fetch(`/api/highlights/${this.dataset.highlightId}`, { method: 'DELETE' });
                if (response.ok) {
                    item.remove();
                    const count = document.querySelectorAll('.highlight-item').length;
                    if (countBadge) countBadge.textContent = count;
                    showToast('Highlight removed', 'success');
                }
            });
        }

        if (countBadge) {
            countBadge.textContent = parseInt(countBadge.textContent) + 1;
        }
    }

    // Apply existing highlights on page load
    if (typeof existingHighlights !== 'undefined' && typeof currentRuleId !== 'undefined') {
        existingHighlights.forEach(h => {
            applyHighlight(currentRuleId, h.start_offset, h.end_offset, h.highlight_color, h.highlight_id);
        });
    }
});

// Add highlight styles
const style = document.createElement('style');
style.textContent = `
    .highlight-yellow { background-color: #fff3cd; }
    .highlight-green { background-color: #d4edda; }
    .highlight-blue { background-color: #cce5ff; }
    .highlight-yellow:hover, .highlight-green:hover, .highlight-blue:hover {
        opacity: 0.8;
        cursor: pointer;
    }
`;
document.head.appendChild(style);
