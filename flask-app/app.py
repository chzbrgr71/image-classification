from flask import Flask, request, Response
from flask import render_template

from pathlib import Path
import tensorflow as tf
import numpy as np

import os, glob
import codecs, json 
from werkzeug.utils import secure_filename

app = Flask(__name__)

ALLOWED_EXTENSIONS = ('png', 'jpg', 'jpeg')
 
@app.route("/")
def index():
    return render_template("index.html") 

@app.route("/detect_image", methods=["POST"])
def detect_image():

    print(
    """
        ===/////
        ===/////
        Detecting images...
        ===/////
        ===/////
    """)
    
    #Filter files with valid image extension, return None by default
    request_image = ([ request.files[f] for f in request.files if f.lower().endswith(ALLOWED_EXTENSIONS) ] or [None])[0]
    
    #If we get None from the file exten sion filter return 400
    if request_image == None:
        print("Invalid image provided! Returning Bad Request.")
        return Response("Invalid image", status=400)

    #Save file to current path
    filename = str(Path.cwd() / secure_filename(request_image.filename))
    request_image.save(filename)

    #Final dict result to jsonify
    result = {
        "image": "",
        "is_ed_sheehan": None,
        "confidence" : 0.0
    }

    image_path = filename
    result["image"] = image_path

    # Read in the image_data
    image_data = tf.gfile.FastGFile(image_path, 'rb').read()

    # Loads label file, strips off carriage return
    label_lines = [line.rstrip() for line 
                    in tf.gfile.GFile("retrained_labels.txt")]

    # Unpersists graph from file
    with tf.gfile.FastGFile("retrained_graph.pb", 'rb') as f:
        graph_def = tf.GraphDef()
        graph_def.ParseFromString(f.read())
        tf.import_graph_def(graph_def, name='')

    with tf.Session() as sess:
        # Feed the image_data as input to the graph and get first prediction
        softmax_tensor = sess.graph.get_tensor_by_name('final_result:0')
        
        predictions = sess.run(softmax_tensor, \
                {'DecodeJpeg/contents:0': image_data})
        
        # Sort to show labels of first prediction in order of confidence
        top_k = predictions[0].argsort()[-len(predictions[0]):][::-1]
        
        
        score = predictions[0][0]

        if score > 0.5:
            print('I am confident this is Ed Sheeran (%s)' % (score))
            result["is_ed_sheehan"] = 1
            result["confidence"] = float(score)


        else:
            print('This is not Ed Sheeran (%s)' % (score))
            result["is_ed_sheehan"] = 0
            result["confidence"] = float(score)
   
    encoded_json = json.dumps(result)
    print(encoded_json)
    return encoded_json
 
 
if __name__ == "__main__":
    #app.run(debug=True)
    app.run(debug=True,host='0.0.0.0')
