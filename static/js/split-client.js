/**
 * Split.io Client-Side SDK Integration
 * Listens for feature flag changes and triggers page refresh
 */

// Client-side SDK key (safe to expose in browser)
const SPLIT_CLIENT_KEY = '5lra47f9qtsf0dcrgcdur3k5sjhfblck0l67';

// Track if SDK is already initialized (to prevent re-initialization)
// Use window object to persist across content swaps
window.splitClientInstance = window.splitClientInstance || null;
window.splitInitTime = window.splitInitTime || null;

// Get user identifier (IP-based for now, replace with actual user ID in production)
function getUserKey() {
    // For now, use a stored key or generate one
    let userKey = sessionStorage.getItem('split_user_key');
    if (!userKey) {
        // Generate a random key for this session
        userKey = 'user_' + Math.random().toString(36).substring(2, 11);
        sessionStorage.setItem('split_user_key', userKey);
    }
    return userKey;
}

// Show the correct variant based on treatment (instant CSS toggle)
function showVariant(treatment) {
    console.log('[Split.io] 🎨 Showing variant:', treatment);

    // Hide all variants
    const allVariants = document.querySelectorAll('.home-variant');
    allVariants.forEach(variant => {
        variant.classList.remove('active');
    });

    // Show the correct variant
    const newHomeVariant = document.getElementById('new-home-variant');
    const oldHomeVariant = document.getElementById('old-home-variant');

    if (!newHomeVariant || !oldHomeVariant) {
        console.error('[Split.io] Variant elements not found in DOM!');
        return;
    }

    if (treatment === 'old_home') {
        oldHomeVariant.classList.add('active');
        console.log('[Split.io] ✅ Showing OLD home page');
    } else {
        // Default to new_home for 'new_home', 'control', or any other treatment
        newHomeVariant.classList.add('active');
        console.log('[Split.io] ✅ Showing NEW home page');
    }
}

// Dynamically swap page content without full reload
function swapPageContent(url) {
    console.log('[Split.io] Fetching new content from:', url);

    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch new content');
            }
            return response.text();
        })
        .then(html => {
            // Create a temporary container to parse the HTML
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = html;

            // Extract the body content from the fetched page
            const newBody = tempDiv.querySelector('body');

            if (newBody) {
                // Preserve the current scroll position
                const scrollY = window.scrollY;

                // Get all children of the new body except script tags (we keep the existing ones)
                const newContent = Array.from(newBody.children).filter(el => el.tagName !== 'SCRIPT');

                // Remove all content before scripts in current body
                while (document.body.firstChild && document.body.firstChild.tagName !== 'SCRIPT') {
                    document.body.removeChild(document.body.firstChild);
                }

                // Insert new content before scripts
                newContent.reverse().forEach(el => {
                    document.body.insertBefore(el, document.body.firstChild);
                });

                // Restore scroll position
                window.scrollTo(0, scrollY);

                console.log('[Split.io] Content swapped successfully! SDK connection maintained.');
            } else {
                console.error('[Split.io] Could not find body element in fetched content');
                // Fallback to full page reload
                window.location.href = url;
            }
        })
        .catch(error => {
            console.error('[Split.io] Error swapping content:', error);
            // Fallback to full page reload on error
            window.location.href = url;
        });
}

// Initialize Split.io client
function initializeSplitClient() {
    // Check if already initialized
    if (window.splitClientInstance) {
        const timeSinceInit = ((Date.now() - window.splitInitTime) / 1000).toFixed(1);
        console.log('[Split.io] ✓ SDK already initialized (' + timeSinceInit + 's ago) - skipping re-initialization');
        console.log('[Split.io] ✓ Maintaining existing connection - no delay!');
        return window.splitClientInstance;
    }

    // Check if Split.io SDK is available
    // In v11+, the SDK exports as window.splitio (a function)
    if (typeof window.splitio !== 'function') {
        console.error('[Split.io] SDK not loaded! window.splitio is not available.');
        return;
    }

    const userKey = getUserKey();
    window.splitInitTime = Date.now();
    console.log('[Split.io] 🚀 Initializing client for user:', userKey);

    // Create factory (window.splitio IS the factory function in v11+)
    const factory = window.splitio({
        core: {
            authorizationKey: SPLIT_CLIENT_KEY,
            key: userKey
        },
        startup: {
            readyTimeout: 5 // 5 seconds timeout
        }
    });

    const client = factory.client();

    // Store the client instance globally on window object
    window.splitClientInstance = client;

    // Wait for SDK to be ready
    client.on(client.Event.SDK_READY, function() {
        const readyTime = ((Date.now() - window.splitInitTime) / 1000).toFixed(1);
        console.log('[Split.io] ✓ Client ready in ' + readyTime + 's');

        // Get initial treatment
        const treatment = client.getTreatment('home_page_variant');
        console.log('[Split.io] Initial treatment for home_page_variant:', treatment);

        // Show the correct variant immediately
        showVariant(treatment);

        // Store initial treatment
        let currentTreatment = treatment;

        // Listen for treatment updates
        client.on(client.Event.SDK_UPDATE, function() {
            console.log('[Split.io] SDK updated, checking for treatment changes');

            const newTreatment = client.getTreatment('home_page_variant');
            console.log('[Split.io] New treatment for home_page_variant:', newTreatment);

            // Check if treatment actually changed
            if (newTreatment !== currentTreatment) {
                const updateTime = ((Date.now() - window.splitInitTime) / 1000).toFixed(1);
                console.log('[Split.io] ⚡ INSTANT SWITCH! Treatment changed from', currentTreatment, 'to', newTreatment, '(' + updateTime + 's since init)');

                // Update current treatment
                currentTreatment = newTreatment;

                // Instantly show the new variant (no page reload!)
                showVariant(newTreatment);
            }
        });
    });

    client.on(client.Event.SDK_READY_TIMED_OUT, function() {
        console.warn('[Split.io] SDK ready timeout');
    });

    client.on(client.Event.SDK_UPDATE, function() {
        console.log('[Split.io] Feature flags updated from server');
    });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeSplitClient);
} else {
    initializeSplitClient();
}
