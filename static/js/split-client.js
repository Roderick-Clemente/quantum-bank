/**
 * Split.io Client-Side SDK Integration
 * Listens for feature flag changes and triggers page refresh
 */

// Client-side SDK key (safe to expose in browser)
const SPLIT_CLIENT_KEY = '5lra47f9qtsf0dcrgcdur3k5sjhfblck0l67';

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

// Initialize Split.io client
function initializeSplitClient() {
    // Check if Split.io SDK is available
    // In v11+, the SDK exports as window.splitio (a function)
    if (typeof window.splitio !== 'function') {
        console.error('[Split.io] SDK not loaded! window.splitio is not available.');
        return;
    }

    const userKey = getUserKey();
    console.log('[Split.io] Initializing client for user:', userKey);

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

    // Wait for SDK to be ready
    client.on(client.Event.SDK_READY, function() {
        console.log('[Split.io] Client ready');

        // Get initial treatment
        const treatment = client.getTreatment('home_page_variant');
        console.log('[Split.io] Initial treatment for home_page_variant:', treatment);

        // Store initial treatment
        let currentTreatment = treatment;

        // Listen for treatment updates
        client.on(client.Event.SDK_UPDATE, function() {
            console.log('[Split.io] SDK updated, checking for treatment changes');

            const newTreatment = client.getTreatment('home_page_variant');
            console.log('[Split.io] New treatment for home_page_variant:', newTreatment);

            // Check if treatment actually changed
            if (newTreatment !== currentTreatment) {
                console.log('[Split.io] Treatment changed from', currentTreatment, 'to', newTreatment);
                console.log('[Split.io] Auto-refreshing page...');

                // Immediate refresh
                window.location.reload();
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
