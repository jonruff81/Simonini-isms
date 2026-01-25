/**
 * Simonini-isms Main JavaScript
 */

// Toast notification function
function showToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '1100';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">${message}</div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    container.appendChild(toast);

    const bsToast = new bootstrap.Toast(toast, { delay: 3000 });
    bsToast.show();

    toast.addEventListener('hidden.bs.toast', () => toast.remove());
}

// Back to top button
document.addEventListener('DOMContentLoaded', function() {
    const backToTop = document.getElementById('back-to-top');
    if (backToTop) {
        window.addEventListener('scroll', function() {
            if (window.pageYOffset > 300) {
                backToTop.classList.add('visible');
            } else {
                backToTop.classList.remove('visible');
            }
        });

        backToTop.addEventListener('click', function(e) {
            e.preventDefault();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    // TOC toggle for mobile
    const tocToggle = document.getElementById('toc-toggle');
    const tocList = document.getElementById('toc-list');
    if (tocToggle && tocList) {
        tocToggle.addEventListener('click', function() {
            tocList.classList.toggle('d-none');
            const icon = this.querySelector('i');
            icon.classList.toggle('fa-chevron-up');
            icon.classList.toggle('fa-chevron-down');
        });
    }

    // Smooth scroll for TOC links
    document.querySelectorAll('.toc-list a').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

    // Search functionality on index page
    const searchInput = document.getElementById('search-input');
    const searchButton = document.getElementById('search-button');
    const searchResults = document.getElementById('search-results');

    if (searchInput && searchButton) {
        async function performSearch() {
            const query = searchInput.value.trim();
            if (!query) {
                searchResults.classList.add('d-none');
                return;
            }

            try {
                const response = await fetch(`/api/rules?q=${encodeURIComponent(query)}`);
                const results = await response.json();

                searchResults.classList.remove('d-none');

                if (results.length === 0) {
                    searchResults.innerHTML = `
                        <div class="alert alert-info">No results found for "${query}"</div>
                    `;
                    return;
                }

                searchResults.innerHTML = `
                    <p class="text-muted">Found ${results.length} result(s)</p>
                    <div class="list-group">
                        ${results.slice(0, 10).map(r => `
                            <a href="/rule/${r.rule_id}" class="list-group-item list-group-item-action">
                                <span class="badge bg-primary me-2">${r.phase_code}</span>
                                ${r.rule_text.substring(0, 100)}...
                            </a>
                        `).join('')}
                    </div>
                `;
            } catch (e) {
                console.error('Search error:', e);
            }
        }

        searchButton.addEventListener('click', performSearch);
        searchInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') performSearch();
        });
    }

    // Bookmark functionality
    document.querySelectorAll('.bookmark-btn').forEach(btn => {
        btn.addEventListener('click', async function() {
            const ruleId = this.dataset.ruleId;
            const isBookmarked = this.classList.contains('active');

            try {
                if (isBookmarked) {
                    const response = await fetch(`/api/bookmarks/${ruleId}`, { method: 'DELETE' });
                    if (response.ok) {
                        this.classList.remove('active');
                        showToast('Bookmark removed', 'success');
                    }
                } else {
                    const response = await fetch('/api/bookmarks', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ rule_id: parseInt(ruleId) })
                    });
                    if (response.ok) {
                        this.classList.add('active');
                        showToast('Bookmarked!', 'success');
                    }
                }
            } catch (e) {
                showToast('Error updating bookmark', 'danger');
            }
        });
    });

    // Note modal functionality
    const noteModal = document.getElementById('noteModal');
    if (noteModal) {
        document.querySelectorAll('.note-btn').forEach(btn => {
            btn.addEventListener('click', async function() {
                const ruleId = this.dataset.ruleId;
                document.getElementById('noteRuleId').value = ruleId;

                // Load existing note
                try {
                    const response = await fetch(`/api/notes/rule/${ruleId}`);
                    const note = await response.json();
                    document.getElementById('noteText').value = note ? note.note_text : '';
                } catch (e) {
                    document.getElementById('noteText').value = '';
                }

                new bootstrap.Modal(noteModal).show();
            });
        });

        document.getElementById('saveNoteBtn').addEventListener('click', async function() {
            const ruleId = document.getElementById('noteRuleId').value;
            const noteText = document.getElementById('noteText').value;

            try {
                const response = await fetch('/api/notes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ rule_id: parseInt(ruleId), note_text: noteText })
                });

                if (response.ok) {
                    bootstrap.Modal.getInstance(noteModal).hide();
                    showToast('Note saved!', 'success');
                }
            } catch (e) {
                showToast('Error saving note', 'danger');
            }
        });

        document.getElementById('deleteNoteBtn').addEventListener('click', async function() {
            const ruleId = document.getElementById('noteRuleId').value;

            try {
                await fetch(`/api/notes/rule/${ruleId}`, { method: 'DELETE' });
                bootstrap.Modal.getInstance(noteModal).hide();
                showToast('Note deleted', 'success');
            } catch (e) {
                showToast('Error deleting note', 'danger');
            }
        });
    }

    // Share functionality
    const shareModal = document.getElementById('shareModal');
    if (shareModal) {
        document.querySelectorAll('.share-btn').forEach(btn => {
            btn.addEventListener('click', async function() {
                const type = this.dataset.type;
                const id = this.dataset.id;

                try {
                    const response = await fetch('/api/share/generate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ type, id: parseInt(id) })
                    });

                    const data = await response.json();

                    document.getElementById('shareUrl').value = data.url;
                    document.getElementById('emailShareBtn').href = data.links.email;
                    document.getElementById('smsShareBtn').href = data.links.sms;

                    new bootstrap.Modal(shareModal).show();
                } catch (e) {
                    showToast('Error generating share link', 'danger');
                }
            });
        });

        document.getElementById('copyShareBtn').addEventListener('click', function() {
            const url = document.getElementById('shareUrl');
            url.select();
            document.execCommand('copy');
            showToast('Link copied!', 'success');
        });
    }
});
