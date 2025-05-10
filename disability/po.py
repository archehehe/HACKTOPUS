from flask import Flask, jsonify
import subprocess
import os

app = Flask(__name__)

@app.route('/launch-tts-app', methods=['POST'])
def launch_tts_app():
    try:
        # Get the path to the Python script
        script_path = os.path.join(os.path.dirname(__file__), 'out3.py')
        
        # Launch the script in a new process
        subprocess.Popen(['python', script_path])
        
        return jsonify({'success': True, 'message': 'Application launched successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000)