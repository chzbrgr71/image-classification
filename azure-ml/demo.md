Azure Machine Learning Service Demo

### Setup

https://docs.microsoft.com/en-us/azure/machine-learning/service/how-to-configure-environment 

* Install conda (one time)
bash Miniconda2-latest-MacOSX-x86_64.sh
conda create --name aml Python=3.6

* Install sdk
pip install --upgrade azureml-sdk
OR
pip install -r requirements.txt

source activate aml
source deactivate
