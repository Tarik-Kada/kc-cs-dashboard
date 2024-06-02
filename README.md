# Dashboard for Knative Serving Custom Scheduler extension

This repository contains the dashboard functionalities for configuring and operating the Knative Serving extension.
The dashboard is intended to run as a locally hosted webserver. It is important to first [deploy your cluster with the custom scheduler services](https://github.com/Tarik-Kada/knative-serving) and set your Kubernetes context accordingly.
The functionalities of the dashboard require the Kubernetes Command Line Tool (kubectl) to operate on the cluster.

## Get started
To get started, clone this repository to your local machine.
Then install the requirements using `pip install -r requirements.txt` and run the `app.py` file using Python3. 
Now the dashboard will be running locally. Open the dashboard in your browser by entering the URL shown in the command line where you executed `app.py`.
