# Split.io Feature Flag Setup

This document explains how to set up and use Split.io feature flags in Quantum Bank.

## Configuration

### Server-Side SDK Key

The server-side API key is loaded from environment variables using a `.env` file.

**Setup:**
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your server-side API key:
   ```
   SPLIT_API_KEY=your_server_side_api_key_here
   ```

3. The `.env` file is already in `.gitignore` and will NOT be committed to git.

**Important:** Never commit your `.env` file! The server-side key is a secret.

### Client-Side SDK Key

The client-side SDK key is configured in `static/js/split-client.js`. This key is safe to expose in the browser and enables real-time feature flag updates without page refresh.

## Feature Flags

### home_page_variant
Controls which version of the home page is displayed to users.

**Split Name:** `home_page_variant`

**Treatments:**
- `new_home` - Shows the modern home page (templates/home.html)
- `old_home` - Shows the legacy home page (templates/old_home.html)
- `control` - Default fallback, shows new_home

**User Key:** Currently uses the user's IP address. In production, replace with actual user ID.

## Split.io Dashboard Setup

1. Go to https://app.split.io
2. Create a new Split called `home_page_variant`
3. Add two treatments:
   - `new_home`
   - `old_home`
4. Set targeting rules (e.g., 50/50 split, or based on user attributes)
5. **Turn the split ON**
6. Save and deploy

## Real-Time Flag Updates

The application now supports **real-time feature flag updates** using Split.io's client-side SDK:

- When you change a feature flag in the Split.io dashboard, the browser will detect it automatically
- A confirmation dialog will appear asking if you want to refresh the page
- The page will auto-refresh to show the new variant

**How it works:**
1. Server-side SDK determines initial treatment on page load
2. Client-side SDK listens for treatment changes in real-time
3. On change detection, browser prompts for refresh
4. New treatment is applied after refresh

**Note:** The client-side SDK uses session storage to track users consistently across refreshes.

## Testing

### Testing Server-Side Feature Flags

```bash
# Activate virtual environment
source venv/bin/activate

# Run the app
python app.py

# Visit http://localhost:5001
# Check the console output for Split.io treatment decisions
```

### Testing Real-Time Updates

1. Load the home page at http://localhost:5001
2. Open browser DevTools Console (F12)
3. You should see: `[Split.io] Client ready` and `[Split.io] Initial treatment for home_page_variant: new_home`
4. Go to Split.io dashboard and change the treatment (e.g., switch to 100% `old_home`)
5. Watch the console - you should see: `[Split.io] Treatment changed! Refreshing page...`
6. Click OK on the dialog to refresh and see the old home page

**Console messages to look for:**
- `[Split.io] Client ready` - SDK initialized successfully
- `[Split.io] Initial treatment for home_page_variant: X` - Current treatment
- `[Split.io] Feature flags updated from server` - New data received
- `[Split.io] Treatment changed! Refreshing page...` - Auto-refresh triggered

## Implementation Details

### Server-Side
- **Server initialization:** `split_config.py` - initializes the Split.io server-side SDK
- **Feature flag usage:** `api/home.py` - checks the feature flag and selects template
- **Cleanup:** Automatically destroys the client on app shutdown

### Client-Side
- **Client SDK:** Loaded from Split.io CDN in `templates/home.html` and `templates/old_home.html`
- **Client logic:** `static/js/split-client.js` - handles real-time flag updates and page refresh
- **User tracking:** Uses session storage to maintain consistent user identity across page loads

## Future Feature Flags

Consider adding feature flags for:
- Transfer limits
- New dashboard widgets
- Two-factor authentication
- Dark mode theme
- Premium account features
