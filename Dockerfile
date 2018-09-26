FROM tensorflow/tensorflow:1.9.0

WORKDIR /tf_classification

COPY ./images /tf_classification/images
COPY ./retrain.py /tf_classification/retrain.py

EXPOSE 6006

CMD ["python","retrain.py","--bottleneck_dir=/tf_output/model/bottlenecks","--model_dir=/tf_output/model/inception","--summaries_dir=/tf_output/model/training_summaries/long","--output_graph=/tf_output/model/retrained_graph.pb","--output_labels=/tf_output/model/retrained_labels.txt","--image_dir=images"]