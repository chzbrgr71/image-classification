## Tensorflow Image Classification Demo


### Retrain Model Locally

* Training
    ```
    docker build -t chzbrgr71/image-retrain .

    docker run -d --name tf-images -p 6006:6006 --volume /Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/tf-output:/tf_output chzbrgr71/image-retrain
    ```

* Tensorboard
    ```
    docker build -t chzbrgr71/tensorboard -f ./Dockerfile.tensorboard .

    docker run -d --name tensorboard -p 80:6006 --volume /Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/tf-output:/tf_output chzbrgr71/tensorboard
    ```

### Host Training on Kubeflow (TFJob)


