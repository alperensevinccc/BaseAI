from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/status')
def get_status():
    """
    Returns a JSON response with the status 'ok'.
    """
    return jsonify({'status': 'ok'})