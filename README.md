## Tensorflow Image Classification Demo


### Retrain Model Locally

* Training
    ```bash
    export IMAGE_TAG=1.5

    # build
    docker build -t chzbrgr71/image-retrain:$IMAGE_TAG -f ./training/Dockerfile ./training

    # push
    docker push chzbrgr71/image-retrain:$IMAGE_TAG

    # run
    docker run -d --name train -p 6006:6006 --volume /Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/tf-output:/tmp/tensorflow --volume /Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/tf-output:/tf-output chzbrgr71/image-retrain:$IMAGE_TAG
    ```

* Tensorboard
    ```bash
    export IMAGE_TAG=1.5

    # build
    docker build -t chzbrgr71/tensorboard:$IMAGE_TAG -f ./training/Dockerfile.tensorboard ./training

    # push
    docker push chzbrgr71/tensorboard:$IMAGE_TAG

    # run
    docker run -d --name tensorboard -p 80:6006 --volume /Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/tf-output:/tf-output chzbrgr71/tensorboard:$IMAGE_TAG
    ```

* Label Image with Trained Model
    ```bash
    export IMAGE_TAG=1.5

    # build
    docker build -t chzbrgr71/tf-label-image:$IMAGE_TAG -f ./label-image/Dockerfile ./label-image

    # run
    docker run -it --rm --name tf-label-image chzbrgr71/tf-label-image:$IMAGE_TAG

    root@016bdde8ecb1:/# python label-image.py edsheeran.jpg
    I am confident this is Ed Sheeran (0.96276665)
    root@016bdde8ecb1:/# python label-image.py bradpitt.jpg
    This is not Ed Sheeran (0.050988954)
    ```

### Setup Kubernetes

* Using [acs-engine](https://github.com/Azure/acs-engine) with kubernetes v1.11.3


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
    APP_NAME=kf-ksonnet2
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

* Setup PVC components to persist data in pods

    https://docs.microsoft.com/en-us/azure/aks/azure-disks-dynamic-pv 

    Setup storage account for Azure Files
    ```bash
    export RG_NAME=briar-ml-104-prom
    export STORAGE=briartfjobstorage

    az storage account create --resource-group $RG_NAME --name $STORAGE --sku Standard_LRS
    ```

    Setup StorageClass, Roles, and PVC's
    ```bash
    kubectl create -f ./k8s-setup/azure-pvc-roles.yaml

    kubectl create -f ./k8s-setup/azure-file-sc.yaml
    kubectl create -f ./k8s-setup/azure-file-pvc.yaml

    kubectl create -f ./k8s-setup/azure-disk-pvc.yaml
    ```

    Check status
    ```bash
    kubectl get pvc

    NAME                STATUS    VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
    azurefile           Bound     pvc-b95edfeb-c1bb-11e8-b9a1-000d3a1f8011   5Gi        RWX            kfazurefile    10s
    azure-managed-disk  Bound     pvc-7bdb43d3-c561-11e8-8100-000d3a4f8d42   5Gi        RWO            managed-premium    7h
    ```


### Host Training on Kubeflow (TFJob)

* Deploy TFJob and tensorboard

    With Azure Files
    ```
    kubectl create -f ./kubeflow/train-model-tfjob-azurefiles.yaml
    ```

    With Azure Disk (cannot run at the same time)
    ```
    kubectl create -f ./kubeflow/train-model-tfjob-azuredisk.yaml
    kubectl create -f ./kubeflow/tensorboard-standalone.yaml
    ```