## Tensorflow Image Classification Demo


### Build training container image and run local

* Training
    ```bash
    # set image tag depending on target cpu/gpu
    export IMAGE_TAG=2.1
    export IMAGE_TAG=2.1-gpu
    export ACRNAME=briaracr

    # build/push (ACR or Docker)
    az acr build -t chzbrgr71/image-retrain:$IMAGE_TAG -r $ACRNAME ./training

    docker build -t chzbrgr71/image-retrain:$IMAGE_TAG -f ./training/Dockerfile ./training
    docker push chzbrgr71/image-retrain:$IMAGE_TAG

    # run local
    docker run -d --name train --volume /Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/tf-output:/tf-output chzbrgr71/image-retrain:$IMAGE_TAG "--how_many_training_steps=1000" "--learning_rate=0.01" "--bottleneck_dir=/tf-output/bottlenecks" "--model_dir=/tf-output/inception" "--summaries_dir=/tf-output/training_summaries/baseline" "--output_graph=/tf-output/retrained_graph.pb" "--output_labels=/tf-output/retrained_labels.txt" "--image_dir=images" "--saved_model_dir=/tf-output/saved_models/1"
    ```

* Tensorboard
    ```bash
    export IMAGE_TAG=2.0

    # build/push (ACR or Docker)
    az acr build -t chzbrgr71/tensorboard:$IMAGE_TAG -r $ACRNAME -f ./training/Dockerfile.tensorboard ./training

    docker build -t chzbrgr71/tensorboard:$IMAGE_TAG -f ./training/Dockerfile.tensorboard ./training
    docker push chzbrgr71/tensorboard:$IMAGE_TAG

    # run
    docker run -d --name tensorboard -p 80:6006 --volume /Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/tf-output:/tf-output chzbrgr71/tensorboard:$IMAGE_TAG "--logdir" "/tf-output/training_summaries"
    ```

* Test locally - label Image with trained model
    ```bash
    export IMAGE_TAG=2.0

    # build
    docker build -t chzbrgr71/tf-testing:$IMAGE_TAG -f ./label-image/Dockerfile ./label-image

    # run
    docker run --rm --name tf-testing --volume /Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/label-image:/image chzbrgr71/tf-testing:$IMAGE_TAG /image/edsheeran.jpg
    I am confident this is Ed Sheeran (0.962828)

    docker run --rm --name tf-testing --volume /Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/label-image:/image chzbrgr71/tf-testing:$IMAGE_TAG /image/bradpitt.jpg
    This is not Ed Sheeran (0.048971623)
    ```

### Setup Kubernetes

* Use AKS or [acs-engine](https://github.com/Azure/acs-engine) with kubernetes v1.11.8 or newer

* Enable Helm

    ```bash
    kubectl create -f ./k8s-setup/tiller-rbac-config.yaml
    
    helm init --service-account tiller --upgrade
    ```

* Installing NVIDIA Device Plugin (AKS with GPU only)

    For AKS v1.11 and above, install NVIDIA Device Plugin using: 

    ```bash
    kubectl apply -f https://raw.githubusercontent.com/nvidia/k8s-device-plugin/v1.11/nvidia-device-plugin.yml
    ```

* Scale when needed

    ```bash
    # aks
    az aks scale -n $CLUSTERNAME -g $RGNAME -c 1 --no-wait

    # aks-engine
    az vmss scale -n $VMSSNAME -g $RGNAME --new-capacity 1 --no-wait
    ```

* Virtual Kubelet/Node. https://github.com/virtual-kubelet/virtual-kubelet/tree/aci-gpu  

    Update [Helm Chart YAML](./k8s-setup/vk-helm-values.yaml)
    ```yaml
    targetAKS: true
    clientId:
    clientKey:
    tenantId:
    subscriptionId:
    aciResourceGroup: 
    aciRegion: 
    ```

    Then install the Virtual Kubelet chart in your cluster
    ```bash
    export VK_RELEASE=virtual-kubelet-latest
    export CHART_URL=https://github.com/virtual-kubelet/virtual-kubelet/raw/master/charts/$VK_RELEASE.tgz
    helm install --name vk "$CHART_URL" -f ./k8s-setup/vk-helm-values.yaml

    kubectl get nodes
    ...
    NAME                       STATUS   ROLES   AGE   VERSION
    aks-nodepool1-90656626-0   Ready    agent   15m   v1.11.8
    aks-nodepool1-90656626-1   Ready    agent   15m   v1.11.8
    aks-nodepool1-90656626-2   Ready    agent   15m   v1.11.8
    aks-nodepool1-90656626-3   Ready    agent   15m   v1.11.8
    virtual-kubelet            Ready    agent   4s    v1.11.2
    ```

### Install Kubeflow

* First, install ksonnet version [0.13.1](https://ksonnet.io/#get-started).

* Then run the following commands to deploy Kubeflow in your Kubernetes cluster:

    ```bash
    export KUBEFLOW_SRC=kubeflow
    export KUBEFLOW_TAG=v0.4.1

    mkdir ${KUBEFLOW_SRC}
    cd ${KUBEFLOW_SRC}

    curl https://raw.githubusercontent.com/kubeflow/kubeflow/${KUBEFLOW_TAG}/scripts/download.sh | bash
    cd ..
    ```

    `KUBEFLOW_SRC` a directory where you want to download the source

    `KUBEFLOW_TAG` a tag corresponding to the version to check out, such as master for the latest code

    ```bash
    # Initialize a kubeflow app
    KFAPP=mykubeflowapp
    ${KUBEFLOW_SRC}/scripts/kfctl.sh init ${KFAPP} --platform none

    # Generate kubeflow app
    cd ${KFAPP}
    ../${KUBEFLOW_SRC}/scripts/kfctl.sh generate k8s

    # Deploy Kubeflow app
    ../${KUBEFLOW_SRC}/scripts/kfctl.sh apply k8s

    # Validate install
    kubectl get pods -n kubeflow
    ```

### Setup Azure Storage

Three choices for storage:
1. [Azure Disks](https://docs.microsoft.com/en-us/azure/aks/azure-disks-dynamic-pv)

    * Create PVC (using either `default` or `managed-premium` storage class)
    ```bash
    kubectl create -f ./k8s-setup/azure-disk-pvc.yaml
    ```

    * Check status
    ```bash
    kubectl get pvc

    NAME                 STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS      AGE
    azure-managed-disk   Bound    pvc-f2f9a107-40f1-11e9-bd08-122f8aa7945e   8Gi        RWO            managed-premium   44s
    ```

2. [Azure Files Dynamic](https://docs.microsoft.com/en-us/azure/aks/azure-files-dynamic-pv)

    * Create storage account
    
    > Note: this storage account must be created in the AKS MC_ RG

    ```bash
    export RG_NAME=MC_briar-aks-ml-02_briar-aksgpu-01_eastus
    export LOCATION=eastus
    export STORAGE=briartfjob01 #rename this. must be unique

    az storage account create --resource-group $RG_NAME --name $STORAGE --location $LOCATION --sku Standard_LRS
    ```

    * Setup StorageClass and PVC's
    ```bash
    kubectl create -f ./k8s-setup/azure-files-dynamic-sc.yaml
    kubectl create -f ./k8s-setup/azure-files-dynamic-pvc.yaml
    ```

    * Check status
    ```bash
    kubectl get pvc

    NAME                      STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS          AGE
    pvc-azure-files-dynamic   Bound    pvc-d08933c3-40f2-11e9-bd08-122f8aa7945e   10Gi       RWX            azure-files-dynamic   5s
    ```

3. [Azure Files Static](https://docs.microsoft.com/en-us/azure/aks/azure-files-volume)

    ```bash
    export AKS_PERS_STORAGE_ACCOUNT_NAME=briar$RANDOM
    export AKS_PERS_RESOURCE_GROUP=briar-aks-ml-02
    export AKS_PERS_LOCATION=eastus
    export AKS_PERS_SHARE_NAME=aksshare

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

### Run Training on Kubeflow
    
* Image Classification re-training TFJob (Inception)

    ```bash
    # TFJob
    helm install --name tfjob-image-training-01 --set container.image=briaracr.azurecr.io/chzbrgr71/image-retrain,container.imageTag=2.0-gpu,container.pvcName=pvc-azure-files-dynamic,container.subPath=tfjob-image-training-01,tfjob.name=tfjob-image-training-01 ./training/chart

    helm install --name tfjob-image-training-02 --set container.image=briaracr.azurecr.io/chzbrgr71/image-retrain,container.imageTag=2.1-gpu,container.pvcName=pvc-azure-files-dynamic,container.subPath=tfjob-image-training-02,tfjob.name=tfjob-image-training-02 ./training/chart

    helm install --name tfjob-image-training-03 --set container.image=briaracr.azurecr.io/chzbrgr71/image-retrain,container.imageTag=2.1-gpu,container.pvcName=pvc-azure-files-dynamic,container.subPath=tfjob-image-training-03,tfjob.name=tfjob-image-training-03 ./training/chart

    # Tensorboard
    helm install --name tb-image-training-01 --set tensorboard.name=tb-image-training-01,container.image=briaracr.azurecr.io/chzbrgr71/tensorboard,container.imageTag=2.0-gpu,container.pvcName=pvc-azure-files-dynamic,container.subPath=tfjob-image-training-01 ./training/tensorboard-chart
    ```

    ```bash
    # testing
    export IP=13.68.227.154

    curl -F "image.jpg=@/Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/label-image/edsheeran.jpg" http://$IP:5000/detect_image
    
    curl -F "image.jpg=@/Users/brianredmond/gopath/src/github.com/chzbrgr71/image-classification/label-image/brianredmond.jpg" http://$IP:5000/detect_image
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

This step requires 6-7 nodes in k8s. Uses the same container image as standard image re-training.

```bash
helm install --name tfjob-hyperparam1 --set tfjob.name=tfjob-hyperparam1,container.image=briaracr.azurecr.io/chzbrgr71/image-retrain:2.0-gpu,container.pvcName=pvc-azure-files-dynamic,container.subPath=tfjob-hyperparam1 ./hyperparameter/chart

helm install --name tb-hyperparam1 --set tensorboard.name=tb-hyperparam1,container.pvcName=pvc-azure-files-dynamic,container.subPath=tfjob-hyperparam1 ./hyperparameter/tensorboard-chart
```

#### ACI + Virtual Kubelet

```bash
helm install --name tfjob-hyperparam-vk --set image=chzbrgr71/image-retrain:2.1-gpu,useGPU=true ./hyperparameter/chart-vk
```

### Pytorch Operator

```bash
# mnist
kubectl apply -f ./pytorch/pytorch_job_mnist_gloo.yaml

# smoke-dist
kubectl apply -f ./pytorch/pytorch_job_sendrecv.yaml
```

### Chainer

```bash
kubectl apply -f ./chainer/chainer-job-mn.yaml
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

### TensorFlow Serving

* Local

    ```bash
    docker run -d --rm --name serving_base tensorflow/serving:1.9.0
    docker cp ./tf-output/saved_models serving_base:/models/inception
    docker commit --change "ENV MODEL_NAME inception" serving_base chzbrgr71/edsheeran_serving:2.0
    docker kill serving_base
    docker run -p 8500:8500 -t chzbrgr71/edsheeran_serving:2.0 &

    python serving/inception_client.py --server localhost:8500 --image ./label-image/edsheeran.jpg
    python serving/inception_client.py --server localhost:8500 --image ./label-image/bradpitt.jpg
    python serving/inception_client.py --server localhost:8500 --image ./label-image/brianredmond.jpg
    ```



### Model Serving (Flask App)

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

### Argo Workflow

* Set environment variables for Argo workflow 

    ```bash
    # namespace of all the kubeflow components
    export NAMESPACE=kubeflow
    export AZURE_STORAGEACCOUNT_NAME=minio 
    export AZURE_STORAGEACCOUNT_KEY=minio123
    MINIOIP=$(kubectl get svc minio-service -n ${NAMESPACE} -o jsonpath='{.spec.clusterIP}')
    MINIOPORT=$(kubectl get svc minio-service -n ${NAMESPACE} -o jsonpath='{.spec.ports[0].port}')

    export S3_ENDPOINT=${MINIOIP}:$MINIOPORT
    export AWS_ENDPOINT_URL=${S3_ENDPOINT}
    export AWS_ACCESS_KEY_ID=$AZURE_STORAGEACCOUNT_NAME
    export AWS_SECRET_ACCESS_KEY=$AZURE_STORAGEACCOUNT_KEY
    export BUCKET_NAME=mybucket

    export DOCKER_BASE_URL=docker.io/chzbrgr71 # Update this to fit your scenario
    export S3_DATA_URL=s3://${BUCKET_NAME}/data/retrain/
    export S3_TRAIN_BASE_URL=s3://${BUCKET_NAME}/models
    export AWS_REGION=us-east-1
    export JOB_NAME=myjob-$(uuidgen  | cut -c -5 | tr '[:upper:]' '[:lower:]')
    export TF_MODEL_IMAGE=${DOCKER_BASE_URL}/image-retrain:2.1-gpu
    export TF_WORKER=3
    export MODEL_TRAIN_STEPS=200

    # Create a secret for accessing the Minio server
    kubectl create secret generic aws-creds --from-literal=awsAccessKeyID=${AWS_ACCESS_KEY_ID} \
    --from-literal=awsSecretAccessKey=${AWS_SECRET_ACCESS_KEY} -n ${NAMESPACE}

    # Create a user for the workflow
    kubectl apply -f workflow/tf-user.yaml -n ${NAMESPACE}
    ```

* Submit a workflow to Argo

    ```bash
    argo submit workflow/model-train-serve-workflow.yaml -n ${NAMESPACE} --serviceaccount tf-user \
    -p aws-endpoint-url=${AWS_ENDPOINT_URL} \
    -p s3-endpoint=${S3_ENDPOINT} \
    -p aws-region=${AWS_REGION} \
    -p tf-model-image=${TF_MODEL_IMAGE} \
    -p s3-data-url=${S3_DATA_URL} \
    -p s3-train-base-url=${S3_TRAIN_BASE_URL} \
    -p job-name=${JOB_NAME} \
    -p tf-worker=${TF_WORKER} \
    -p model-train-steps=${MODEL_TRAIN_STEPS} \
    -p namespace=${NAMESPACE} \
    -p tf-tensorboard-image=tensorflow/tensorflow:1.7.0 \
    -p s3-use-https=0 \
    -p s3-verify-ssl=0

    # Check status of the workflow
    argo list -n ${NAMESPACE}
    NAME                STATUS    AGE    DURATION
    tf-workflow-s8k24   Running   5m     5m 

    # Check pods that are created by the workflow
    kubectl get pod -n ${NAMESPACE} -o wide -w

    # Monitor training from tensorboard
    PODNAME=$(kubectl get pod -n ${NAMESPACE} -l app=tensorboard-${JOB_NAME} -o jsonpath='{.items[0].metadata.name}')
    kubectl port-forward ${PODNAME} -n ${NAMESPACE} 6006:6006

    # Get logs from the training pod(s)
    kubectl logs ${JOB_NAME}-master-0 -n ${NAMESPACE} 
    ```

