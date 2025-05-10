# filepath: c:\Users\HP\Desktop\disability\run.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route('/speech-solution', methods=['POST'])
def launch_tts_app():
    try:
        # Replace 'python' with 'python3' if needed
        subprocess.Popen(['python', 'text2speech.py'], shell=True)
    except Exception as e:
        print(f"Error: {e}")  # Log the error to the console
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/mobility-resources', methods=['POST'])
def launch_mobility_resources():
    try:
        # Replace 'python' with 'python3' if needed
        subprocess.Popen(['python', 'text2speech.py'], shell=True)
        return jsonify({'success': True, 'message': 'Mobility resources launched successfully!'})
    except Exception as e:
        print(f"Error: {e}")  # Log the error to the console
        return jsonify({'success': False, 'message': str(e)}), 500
    

if __name__ == '__main__':
    app.run(debug=True)