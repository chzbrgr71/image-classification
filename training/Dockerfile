FROM tensorflow/tensorflow:1.9.0
#FROM tensorflow/tensorflow:1.9.0-gpu

WORKDIR /tf_classification

COPY ./images /tf_classification/images
COPY ./retrain.py /tf_classification/retrain.py

EXPOSE 6006

CMD ["python","retrain.py","--bottleneck_dir=/tmp/tensorflow/model/bottlenecks","--model_dir=/tmp/tensorflow/model/inception","--summaries_dir=/tf-output/training_summaries/long","--output_graph=/tmp/tensorflow/model/retrained_graph.pb","--output_labels=/tmp/tensorflow/model/retrained_labels.txt","--image_dir=images"]