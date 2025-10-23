from flask import render_template

def handle_home():
    """Handle home page - renders wrapper with both variants for instant switching"""
    # Render the wrapper template which contains both page variants as iframes
    # The client-side Split.io SDK will show/hide the correct one instantly
    return render_template('home_wrapper.html')