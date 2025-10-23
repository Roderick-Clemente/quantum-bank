# Split.io Feature Flag Setup

This document explains how to set up and use Split.io feature flags in Quantum Bank.

## Configuration

### Environment Variable (Recommended for Production)
Set the `SPLIT_API_KEY` environment variable:
```bash
export SPLIT_API_KEY=your_api_key_here
```

### Hardcoded (Current Setup - Development Only)
The API key is currently hardcoded in `split_config.py`. **Change this before deploying to production!**

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

## Testing

To test the feature flag locally:

```bash
# Activate virtual environment
source venv/bin/activate

# Run the app
python app.py

# Visit http://localhost:5001
# Check the console output for Split.io treatment decisions
```

## Implementation Details

- **Client initialization:** `split_config.py` - initializes the Split.io SDK
- **Feature flag usage:** `api/home.py` - checks the feature flag and selects template
- **Cleanup:** Automatically destroys the client on app shutdown

## Future Feature Flags

Consider adding feature flags for:
- Transfer limits
- New dashboard widgets
- Two-factor authentication
- Dark mode theme
- Premium account features
