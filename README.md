## Tensorflow Image Classification Demo


### Retrain Model Locally

* Training
    ```bash
    export IMAGE_TAG=1.8
    export IMAGE_TAG=1.8-gpu

    # build
    docker build -t chzbrgr71/image-retrain:$IMAGE_TAG -f ./training/Dockerfile ./training

    # push
    docker push chzbrgr71/image-retrain:$IMAGE_TAG

    # run
    docker run -d --name train --volume /Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/tf-output:/tf-output chzbrgr71/image-retrain:$IMAGE_TAG "--how_many_training_steps=4000" "--learning_rate=0.01" "--bottleneck_dir=/tf-output/bottlenecks" "--model_dir=/tf-output/inception" "--summaries_dir=/tf-output/training_summaries/baseline" "--output_graph=/tf-output/retrained_graph.pb" "--output_labels=/tf-output/retrained_labels.txt" "--image_dir=images"
    ```

* Tensorboard
    ```bash
    export IMAGE_TAG=1.8

    # build
    docker build -t chzbrgr71/tensorboard:$IMAGE_TAG -f ./training/Dockerfile.tensorboard ./training

    # push
    docker push chzbrgr71/tensorboard:$IMAGE_TAG

    # run
    docker run -d --name tensorboard -p 80:6006 --volume /Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/tf-output:/tf-output chzbrgr71/tensorboard:$IMAGE_TAG "--logdir" "/tf-output/training_summaries"
    ```

* Label Image with Trained Model
    ```bash
    export IMAGE_TAG=1.8

    # build
    docker build -t chzbrgr71/tf-testing:$IMAGE_TAG -f ./label-image/Dockerfile ./label-image

    # run
    docker run --rm --name tf-testing --volume /Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/label-image:/image chzbrgr71/tf-testing:$IMAGE_TAG /image/edsheeran.jpg
    I am confident this is Ed Sheeran (0.962828)

    docker run --rm --name tf-testing --volume /Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/label-image:/image chzbrgr71/tf-testing:$IMAGE_TAG /image/bradpitt.jpg
    This is not Ed Sheeran (0.048971623)
    ```

### Setup Kubernetes

* Using [acs-engine](https://github.com/Azure/acs-engine) with kubernetes v1.11.3

* Enable Helm

    ```bash
    kubectl create -f ./k8s-setup/tiller-rbac-config.yaml
    
    helm init --service-account tiller --upgrade
    ```

* Scale when needed

    ```bash
    az vmss scale -n k8s-gpuagentpool-18712514-vmss -g briar-ml-110 --new-capacity 1 --no-wait
    ```

* AKS GPU Fix

    https://docs.microsoft.com/en-us/azure/aks/gpu-cluster#troubleshoot

    ```bash
    kubectl apply -f ./k8s-setup/nvidia-device-plugin-ds.yaml
    ```

### Install Kubeflow

* First, install ksonnet version [0.9.2](https://ksonnet.io/#get-started).
* Then run the following commands to deploy Kubeflow in your Kubernetes cluster:

    ```bash
    # Create a namespace for kubeflow deployment
    NAMESPACE=kubeflow
    kubectl create namespace ${NAMESPACE}

    # Which version of Kubeflow to use
    # For a list of releases refer to:
    # https://github.com/kubeflow/kubeflow/releases
    VERSION=v0.2.2

    # Initialize a ksonnet app. Set the namespace for it's default environment.
    APP_NAME=kf-ksonnet8
    ks init ${APP_NAME}
    cd ${APP_NAME}
    ks env set default --namespace ${NAMESPACE}

    # Add a reference to Kubeflow's ksonnet manifests
    ks registry add kubeflow github.com/kubeflow/kubeflow/tree/${VERSION}/kubeflow

    # Install Kubeflow components
    ks pkg install kubeflow/core@${VERSION}
    ks pkg install kubeflow/tf-serving@${VERSION}

    # Create templates for core components
    ks generate kubeflow-core kubeflow-core

    # Customize Kubeflow's installation for AKS or acs-engine
    # ks param set kubeflow-core cloud aks
    ks param set kubeflow-core cloud acsengine
    ks param set kubeflow-core jupyterHubServiceType LoadBalancer

    # Deploy Kubeflow
    ks apply default -c kubeflow-core

    # Check status
    kubectl get pods -n kubeflow
    ```

### Setup Azure Storage

Setup PVC components to persist data in pods. https://docs.microsoft.com/en-us/azure/aks/azure-disks-dynamic-pv 

* briar-kubeflow-eu-01

```bash
export RG_NAME=briar-kubeflow-eu-01
export LOCATION=westeurope

export STORAGE=briartfjob01
az storage account create --resource-group $RG_NAME --name $STORAGE --location $LOCATION --sku Standard_LRS
export STORAGE=briartfjobbackup01
az storage account create --resource-group $RG_NAME --name $STORAGE --location $LOCATION --sku Standard_LRS
```

Setup StorageClass and PVC's
```bash
kubectl create -f ./k8s-setup/sc-eu-01.yaml
kubectl create -f ./k8s-setup/sc-eu-01-backup.yaml
kubectl create -f ./k8s-setup/pvc-eu-01.yaml
kubectl create -f ./k8s-setup/pvc-eu-01-backup.yaml
```

* briar-kubeflow-eu-02

```bash
export RG_NAME=briar-kubeflow-eu-02
export LOCATION=westeurope

export STORAGE=briartfjob02
az storage account create --resource-group $RG_NAME --name $STORAGE --location $LOCATION --sku Standard_LRS
export STORAGE=briartfjobbackup02
az storage account create --resource-group $RG_NAME --name $STORAGE --location $LOCATION --sku Standard_LRS
```

Setup StorageClass and PVC's
```bash
kubectl create -f ./k8s-setup/sc-eu-02.yaml
kubectl create -f ./k8s-setup/sc-eu-02-backup.yaml
kubectl create -f ./k8s-setup/pvc-eu-02.yaml
kubectl create -f ./k8s-setup/pvc-eu-02-backup.yaml
```

* Check status

```bash
kubectl get pvc

NAME                 STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS      AGE
azure-files          Bound    pvc-feecad38-d46b-11e8-9a30-000d3a47182f   10Gi       RWX            sc-eu-01          14s
azure-files-backup   Bound    pvc-ff142681-d46b-11e8-9a30-000d3a47182f   10Gi       RWX            sc-eu-01-backup   13s
```

### Run Training on Kubeflow
    
* Image Classification Re-training TFJob (Inception)

    ```bash
    # helm
    helm install --set container.image=briar.azurecr.io/chzbrgr71/image-retrain,container.imageTag=1.8-gpu,container.pvcName=azure-files-backup,tfjob.name=tfjob-image-training ./training/chart

    helm install --set tensorboard.name=tensorboard-image-training,container.pvcName=azure-files-backup,container.subPath=tfjob-image-training ./training/tensorboard-chart
    ```

* Download model (while TB pod is running)

    ```bash        
    # to download model from pod
    PODNAME=tensorboard-image-training-677fc97b59-g5k64
    kubectl cp default/$PODNAME:/tmp/tensorflow/tf-output/retrained_graph.pb ~/Downloads/retrained_graph.pb
    kubectl cp default/$PODNAME:/tmp/tensorflow/tf-output/retrained_labels.txt ~/Downloads/retrained_labels.txt
    ```

* Run Tensorboard manually (using tensorboard-standalone.yaml)

    ```bash
    # exec into pod
    tensorboard --logdir /tf-output/training_summaries
    ```

* Test locally
    ```bash
    docker run -it --rm --name tf \
        --publish 6006:6006 \
        --volume /Users/brianredmond/gopath/src/github.com/chzbrgr71:/brianredmond \
        --workdir /brianredmond  \
        tensorflow/tensorflow:1.9.0 bash

    python label-image.py edsheeran.jpg
    python label-image.py bradpitt.jpg
    python label-image.py ed-sheeran-puppet.jpg
    ```
    
### Hyperparameter Sweep Demo

This step requires 6-7 nodes in VMSS. Uses the same container image as standard image re-training.

```bash
helm install --set tfjob.name=tfjob-hyperparam-sweep,container.image=briar.azurecr.io/chzbrgr71/image-retrain:1.8-gpu,container.pvcName=azure-files-backup ./hyperparameter/chart

helm install --set tensorboard.name=tensorboard-hyperparam-sweep,container.pvcName=azure-files-backup,container.subPath=tfjob-hps ./hyperparameter/tensorboard-chart
```

### Distributed Tensorflow

This step requires 4 nodes in VMSS.

* Create Docker image

    ```bash
    export IMAGE_TAG=1.8

    # build
    docker build -t chzbrgr71/distributed-tf:$IMAGE_TAG -f ./dist-training/Dockerfile ./dist-training

    # push
    docker push chzbrgr71/distributed-tf:$IMAGE_TAG
    ```

* Helm Chart

    ```bash
    helm install --set container.image=briar.azurecr.io/chzbrgr71/distributed-tf,container.imageTag=1.8,training.workercount=2,container.pvcName=azure-files-backup,tfjob.name=tfjob-dist-training ./dist-training/chart

    helm install --set tensorboard.name=tensorboard-dist-training,container.pvcName=azure-files-backup,container.subPath=tfjob-dist-training ./training/tensorboard-chart
    ```

### Azure Container Registry Tasks Demo

* This demo is in a separate repo. https://github.com/chzbrgr71/image-training 

```bash
ACR_NAME=briaracr    
GIT_PAT=
SLACK_WEBHOOK=

az acr task create \
    --registry $ACR_NAME \
    --name tf-image-training \
    --context https://github.com/chzbrgr71/image-training.git \
    --branch master \
    --file acr-task.yaml \
    --git-access-token $GIT_PAT \
    --set-secret SLACK_WEBHOOK=$SLACK_WEBHOOK
```

* Create helm container for deployment with service principal (Steve Lasker)

https://github.com/AzureCR/cmd/tree/master/helm 


### Model Serving

* Python Flask App

    Running local: 
    ```bash
    FLASK_APP=app.py FLASK_DEBUG=1 python -m flask run

    curl -F "image.jpg=@/Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/label-image/edsheeran.jpg" http://localhost:5000/detect_image

    curl -F "image.jpg=@/Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/label-image/bradpitt.jpg" http://localhost:5000/detect_image

    curl -F "image.jpg=@/Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/label-image/brianredmond.jpg" http://localhost:5000/detect_image

    curl -F "image.jpg=@/Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/label-image/edsheeran.jpg" http://40.78.47.97:5000/detect_image
    ```

    In container:
    ```bash
    docker build -t chzbrgr71/edsheeran-flask-app:1.1 .

    docker push chzbrgr71/edsheeran-flask-app:1.1

    docker run -d --name flask -p 5000:5000 chzbrgr71/edsheeran-flask-app:1.1
    ```

### Argo

* Setup Minio









