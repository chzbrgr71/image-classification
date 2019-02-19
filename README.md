## Tensorflow Image Classification Demo


### Retrain Model Locally

* Training
    ```bash
    export IMAGE_TAG=1.10
    export IMAGE_TAG=1.10-gpu

    # build/push
    docker build -t chzbrgr71/image-retrain:$IMAGE_TAG -f ./training/Dockerfile ./training
    docker push chzbrgr71/image-retrain:$IMAGE_TAG

    # run
    docker run -d --name train --volume /Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/tf-output:/tf-output chzbrgr71/image-retrain:$IMAGE_TAG "--how_many_training_steps=4000" "--learning_rate=0.01" "--bottleneck_dir=/tf-output/bottlenecks" "--model_dir=/tf-output/inception" "--summaries_dir=/tf-output/training_summaries/baseline" "--output_graph=/tf-output/retrained_graph.pb" "--output_labels=/tf-output/retrained_labels.txt" "--image_dir=images"
    ```

* Tensorboard
    ```bash
    export IMAGE_TAG=1.10

    # build/push
    docker build -t chzbrgr71/tensorboard:$IMAGE_TAG -f ./training/Dockerfile.tensorboard ./training
    docker push chzbrgr71/tensorboard:$IMAGE_TAG

    # run
    docker run -d --name tensorboard -p 80:6006 --volume /Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/tf-output:/tf-output chzbrgr71/tensorboard:$IMAGE_TAG "--logdir" "/tf-output/training_summaries"
    ```

* Test locally - label Image with trained model
    ```bash
    export IMAGE_TAG=1.10

    # build
    docker build -t chzbrgr71/tf-testing:$IMAGE_TAG -f ./label-image/Dockerfile ./label-image

    # run
    docker run --rm --name tf-testing --volume /Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/label-image:/image chzbrgr71/tf-testing:$IMAGE_TAG /image/edsheeran.jpg
    I am confident this is Ed Sheeran (0.962828)

    docker run --rm --name tf-testing --volume /Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/label-image:/image chzbrgr71/tf-testing:$IMAGE_TAG /image/bradpitt.jpg
    This is not Ed Sheeran (0.048971623)
    ```

### Setup Kubernetes

* Use AKS or [acs-engine](https://github.com/Azure/acs-engine) with kubernetes v1.11.3

* Enable Helm

    ```bash
    kubectl create -f ./k8s-setup/tiller-rbac-config.yaml
    
    helm init --service-account tiller --upgrade
    ```

* Scale when needed

    ```bash
    az vmss scale -n k8s-gpuagentpool-12345678-vmss -g ml-100 --new-capacity 1 --no-wait
    ```

* Virtual Kubelet

    Update YAML
    ```yaml
    targetAKS:
    clientId:
    clientKey:
    tenantId:
    subscriptionId:
    aciRegion:
    ```

    Then install the Virtual Kubelet chart in your cluster
    ```bash
    export VK_RELEASE=virtual-kubelet-latest
    CHART_URL=https://github.com/virtual-kubelet/virtual-kubelet/raw/master/charts/$VK_RELEASE.tgz
    helm install --name vk "$CHART_URL" -f ./hyperparameter/virtual-kubelet/values.yaml

    kubectl get nodes
    ...
    virtual-kubelet                     Ready     agent     5s        v1.11.2
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
    APP_NAME=kf-ksonnet10
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
    ks generate argo kubeflow-argo --name=kubeflow-argo --namespace=${NAMESPACE}

    # Customize Kubeflow's installation for AKS or acs-engine
    # ks param set kubeflow-core cloud aks
    ks param set kubeflow-core cloud acsengine
    ks param set kubeflow-core jupyterHubServiceType LoadBalancer

    # Deploy Kubeflow
    ks apply default -c kubeflow-core
    ks apply default -c kubeflow-argo

    # Check status
    kubectl get pods -n kubeflow
    ```

### Setup Azure Storage

Setup PVC components to persist data in pods. https://docs.microsoft.com/en-us/azure/aks/azure-disks-dynamic-pv 

* kubeflow-eu-01

```bash
export RG_NAME=briar-tf-training
export RG_NAME=MC_briar-aks-ml-gpu_briar-aks-ml-gpu_eastus
export LOCATION=eastus

export STORAGE=briartfjob02 #rename this. must be unique
az storage account create --resource-group $RG_NAME --name $STORAGE --location $LOCATION --sku Standard_LRS
```

Setup StorageClass and PVC's
```bash
kubectl create -f ./k8s-setup/sc-eu-01.yaml
kubectl create -f ./k8s-setup/pvc-eu-01.yaml
```

* Check status

```bash
kubectl get pvc

NAME                 STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS      AGE
azure-files          Bound    pvc-feecad38-d46b-11e8-9a30-000d3a47182f   10Gi       RWX            sc-eu-01          14s
```

### Run Training on Kubeflow
    
* Image Classification Re-training TFJob (Inception)

    ```bash
    # TFJob
    helm install --name tfjob-image-training-02 --set container.image=briarhackfest.azurecr.io/chzbrgr71/image-retrain,container.imageTag=1.10-gpu,container.pvcName=pvc-azure-files,tfjob.name=tfjob-image-training-02 ./training/chart

    # Tensorboard
    helm install --name tb-image-training-02 --set tensorboard.name=tensorboard-image-training-02,container.pvcName=pvc-azure-files,container.subPath=tfjob-image-training-02 ./training/tensorboard-chart
    ```

* Download model (while TB pod is running)

    ```bash        
    # to download model from pod
    PODNAME=
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
helm install --name tfjob-hyperparam2 --set tfjob.name=tfjob-hyperparam-sweep1,container.image=briarhackfest.azurecr.io/chzbrgr71/image-retrain:1.10-gpu,container.pvcName=pvc-azure-files ./hyperparameter/chart

helm install --name tb-hyperparam2 --set tensorboard.name=tensorboard-hyperparam-sweep1,container.pvcName=pvc-azure-files,container.subPath=tfjob-hps2 ./hyperparameter/tensorboard-chart
```

ACI + Virtual Kubelet

Use Azure Files Static for ACI's. https://docs.microsoft.com/en-us/azure/aks/azure-files-volume 

```bash
AKS_PERS_STORAGE_ACCOUNT_NAME=briar$RANDOM
AKS_PERS_RESOURCE_GROUP=briar-aks-ml-gpu
AKS_PERS_LOCATION=eastus
AKS_PERS_SHARE_NAME=aksshare

# Create the storage account
az storage account create -n $AKS_PERS_STORAGE_ACCOUNT_NAME -g $AKS_PERS_RESOURCE_GROUP -l $AKS_PERS_LOCATION --sku Standard_LRS

# Export the connection string as an environment variable, this is used when creating the Azure file share
export AZURE_STORAGE_CONNECTION_STRING=`az storage account show-connection-string -n $AKS_PERS_STORAGE_ACCOUNT_NAME -g $AKS_PERS_RESOURCE_GROUP -o tsv`

# Create the file share
az storage share create -n $AKS_PERS_SHARE_NAME

# Get storage account key
STORAGE_KEY=$(az storage account keys list --resource-group $AKS_PERS_RESOURCE_GROUP --account-name $AKS_PERS_STORAGE_ACCOUNT_NAME --query "[0].value" -o tsv)

# Echo storage account name and key
echo Storage account name: $AKS_PERS_STORAGE_ACCOUNT_NAME
echo Storage account key: $STORAGE_KEY

kubectl create secret generic azure-file-secret --from-literal=azurestorageaccountname=$AKS_PERS_STORAGE_ACCOUNT_NAME --from-literal=azurestorageaccountkey=$STORAGE_KEY
```

```bash
helm install --name tfjob-hyperparam-aci ./hyperparameter/chart-vk
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
    helm install --set container.image=briar.azurecr.io/chzbrgr71/distributed-tf,container.imageTag=1.8,training.workercount=2,container.pvcName=azure-files,tfjob.name=tfjob-dist-training2 ./dist-training/chart

    helm install --set tensorboard.name=tensorboard-dist-training2,container.pvcName=azure-files,container.subPath=tfjob-dist-training2 ./training/tensorboard-chart
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

### Model Serving

* This demo is in a separate repo. https://github.com/chzbrgr71/flask-tf 

* Python Flask App

    Running local: 
    ```bash
    FLASK_APP=app.py FLASK_DEBUG=1 python -m flask run

    curl -F "image.jpg=@/Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/label-image/edsheeran.jpg" http://localhost:5000/detect_image

    curl -F "image.jpg=@/Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/label-image/bradpitt.jpg" http://localhost:5000/detect_image

    curl -F "image.jpg=@/Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/label-image/brianredmond.jpg" http://localhost:5000/detect_image
    ```

    In container:
    ```bash
    IMAGE_TAG=1.5

    docker build -t chzbrgr71/edsheeran-flask-app:$IMAGE_TAG -f ./flask-app/Dockerfile ./flask-app

    docker push chzbrgr71/edsheeran-flask-app:$IMAGE_TAG
    docker tag chzbrgr71/edsheeran-flask-app:$IMAGE_TAG briarhackfest.azurecr.io/chzbrgr71/edsheeran-flask-app:$IMAGE_TAG
    docker push briarhackfest.azurecr.io/chzbrgr71/edsheeran-flask-app:$IMAGE_TAG

    docker run -d --name flask -p 5000:5000 chzbrgr71/edsheeran-flask-app:$IMAGE_TAG

    helm upgrade --install flask-tf --set deploy.image=briarhackfest.azurecr.io/chzbrgr71/edsheeran-flask-app,deploy.imageTag=$IMAGE_TAG ./flask-app/chart
    ```


    Testing:
    ```bash
    IMAGE=edsheeran.jpg
    IMAGE=bradpitt.jpg
    IMAGE=brianredmond.jpg
    IMAGE=ed-sheeran-puppet.jpg

    IP=13.68.208.133 && curl -F "image.jpg=@/Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/label-image/$IMAGE" http://$IP:5000/detect_image
    ```

* Create helm container for deployment with service principal (Steve Lasker) https://github.com/AzureCR/cmd/tree/master/helm 

* ACR Task / Github Webhook

```bash
ACR_NAME=
GIT_PAT=
SLACK_WEBHOOK=
SP=
PASSWORD=
TENANT=
CLUSTER_RESOURCE_GROUP=
CLUSTER_NAME=

az acr task create \
    --registry $ACR_NAME \
    --name flask-tf \
    --context https://github.com/chzbrgr71/flask-tf.git \
    --branch master \
    --file acr-task.yaml \
    --git-access-token $GIT_PAT \
    --set-secret SLACK_WEBHOOK=$SLACK_WEBHOOK \
    --set-secret SP=$SP \
    --set-secret PASSWORD=$PASSWORD \
    --set-secret TENANT=$TENANT \
    --set-secret CLUSTER_RESOURCE_GROUP=$CLUSTER_RESOURCE_GROUP \
    --set-secret CLUSTER_NAME=$CLUSTER_NAME
```






