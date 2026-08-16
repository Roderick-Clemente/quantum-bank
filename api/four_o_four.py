from flask import request, jsonify


def handle_404():
    # Content-negotiated 404: API paths get a parseable JSON error body,
    # non-API paths keep the existing HTML 404 response.
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found"}), 404
    return "404 Not Found", 404
