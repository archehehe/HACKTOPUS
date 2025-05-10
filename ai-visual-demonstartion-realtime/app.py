from flask import Flask, render_template, request, jsonify
from video_processor import VideoDescriber
from image_processor import ImageDescriber
from translator import TextTranslator
import hashlib
import json
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
video_describer = VideoDescriber()
image_describer = ImageDescriber()
translator = TextTranslator()

# Route to serve the HTML page
@app.route('/')
def index():
    return render_template('index.html')

# Your existing describe and describe-frame routes
@app.route('/describe', methods=['POST'])
def describe():
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "No file provided"}), 400

    lang = request.form.get('lang', 'en')
    file_bytes = file.read()
    file_hash = hashlib.md5(file_bytes).hexdigest()
    file.seek(0)

    description = None
    if file.filename.endswith(('.jpg', '.png')):
        description = image_describer.describe_image(file)
    elif file.filename.endswith(('.mp4', '.avi')):
        temp_path = f"temp_{secure_filename(file.filename)}"
        file.save(temp_path)
        description = video_describer.describe_video(temp_path)
        os.remove(temp_path)
    else:
        return jsonify({"error": "Unsupported format"}), 400

    if lang != 'en' and description:
        description = translator.translate(description, lang)

    return jsonify({"description": description})

@app.route('/describe-frame', methods=['POST'])
def describe_frame():
    frame = request.files.get('frame')
    if not frame:
        return jsonify({"error": "No frame provided"}), 400

    lang = request.form.get('lang', 'en')
    temp_path = "temp_frame.jpg"
    frame.save(temp_path)
    description = image_describer.describe_image(temp_path)
    os.remove(temp_path)

    translated_description = description
    if lang != 'en':
        translated_description = translator.translate(description, lang)

    return jsonify({
        "description": description,
        "translated_description": translated_description
    })



if __name__ == "__main__":
    app.run(debug=True)
