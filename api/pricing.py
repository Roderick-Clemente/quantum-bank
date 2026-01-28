from flask import render_template

def handle_pricing():
    """Handle pricing page - renders wrapper with all variants for instant switching"""
    # Render the wrapper template which contains all pricing variants as iframes
    # The client-side Split.io SDK will show/hide the correct one instantly
    return render_template('pricing_wrapper.html')
