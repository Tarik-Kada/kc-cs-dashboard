from flask import Flask, render_template, request, jsonify
import subprocess
import yaml
import json

app = Flask(__name__)

def get_command(resource):
    command_map = {
        'nodes': "kubectl get nodes",
        'pods': "kubectl get pods --all-namespaces",
        'services': "kubectl get svc",
        'scheduler_config': "kubectl get configmap scheduler-config -n default -o yaml",
        'functions': "kubectl get ksvc",
        'functions_list': "kubectl get ksvc -o jsonpath='{.items[*].metadata.name}'",
        'custom_scheduler_controller': "kubectl get pods -n custom-scheduler-controller-system -o jsonpath='{.items[*].metadata.name}'",
        'controller_availability_logs': "kubectl get pods -n knative-serving -l app=controller -o name | xargs -I {} sh -c 'kubectl logs {} -n knative-serving | grep \'deploy.go\''"
    }
    return command_map.get(resource)

def run_kubectl_command(command, timeout=5):
    try:
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return f"Error executing command: {e.stderr}"
    except subprocess.TimeoutExpired as e:
        return f"Command timed out after {timeout} seconds. Make sure the cluster is up and running and the kubectl context is set correctly."

def get_scheduler_log(scheduler_name, scheduler_namespace='default'):
    return run_kubectl_command(f"kubectl logs -n {scheduler_namespace} -l app={scheduler_name}")

@app.route('/')
def index():
    return render_template('index.html', code="kubectl config get-contexts")

@app.route('/custom_schedulers')
def custom_schedulers():
    response = get_scheduler_config()
    scheduler_config_output = response.json.get('output', "")
    config = response.json.get('config', {})
    
    schedulers = []
    # Extract scheduler name and namespace for initial load
    if 'data' in config:
        scheduler_name = config['data'].get('schedulerName', '')
        scheduler_namespace = config['data'].get('schedulerNamespace', 'default')
        schedulers.append({'name': scheduler_name, 'namespace': scheduler_namespace})
    return render_template(
        'custom_schedulers.html',
        scheduler_config_output=scheduler_config_output,
        schedulers=schedulers
    )

@app.route('/get_func_deployments/<func_name>')
def get_func_deployments(func_name):
    command = f"kubectl get pod -l serving.knative.dev/service={func_name} -o jsonpath='{{range .items[*]}}{{.metadata.name}} {{.spec.schedulerName}} {{.status.phase}} {{.spec.nodeName}};{{end}}'"
    output = run_kubectl_command(command)

    if output:
        pods_info = output.strip().split(';')
        pods_info = [info.split() for info in pods_info if info]

        pods = [info[0] if len(info) > 0 else "" for info in pods_info]
        schedulerNames = [info[1] if len(info) > 1 else "" for info in pods_info]
        status = [info[2] if len(info) > 2 else "" for info in pods_info]
        podNode = [info[3] if len(info) > 3 else "" for info in pods_info]
        
        max_pod_name_length = max(len(pod) for pod in pods) if pods else 0
        max_scheduler_name_length = max(len(schedulerName) for schedulerName in schedulerNames) if schedulerNames else 0
        max_status_length = max(len(stat) for stat in status) if status else 0
        max_node_length = max(len(node) for node in podNode) if podNode else 0
        
        output = f"{'NAME':<{max_pod_name_length}} \t {'(SCHEDULER NAME)':<{max_scheduler_name_length}} \t {f'(STATUS)':<{max_status_length}} \t {f'NODE':<{max_node_length}} \t Total deployments: {len(pods)}\n"
        
        for pod, schedulerName, stat, node in zip(pods, schedulerNames, status, podNode):
            output += f"{pod:<{max_pod_name_length}} \t ({schedulerName.strip()}) \t {stat.strip()} \t {node.strip()}\n"
        return output
    return f"No deployments found for function: {func_name}"

@app.route('/get_functions_list')
def get_functions_list():
    command = get_command('functions_list')
    if command:
        output = run_kubectl_command(command)
        functions = output.strip().split()
        if output:
            functions = output.split()
            return jsonify({'functions': functions})
    return jsonify({'functions': []})

@app.route('/functions')
def functions():
    functions_command = get_command('functions')
    functions_output = run_kubectl_command(functions_command)

    functions = get_functions_list().json.get('functions', [])
    return render_template(
        'functions.html',
        functions_command=functions_command,
        functions_output=functions_output,
        functions=functions
    )

@app.route('/controllers')
def controllers():
    controllers_command = get_command('custom_scheduler_controller')
    try:
        custom_controller = run_kubectl_command(controllers_command).strip().split()[0]
    except IndexError:
        custom_controller = None

    custom_logs_command = f"kubectl logs {custom_controller} -n custom-scheduler-controller-system"
    custom_logs = run_kubectl_command(custom_logs_command)

    controller_availability_logs_command = get_command('controller_availability_logs')
    controller_availability_logs = run_kubectl_command(controller_availability_logs_command)

    return render_template(
        'controllers.html',
        custom_logs_command=custom_logs_command,
        logs_output=custom_logs,
        controller_availability_logs_command=controller_availability_logs_command,
        controller_availability_logs_output=controller_availability_logs)

@app.route('/get_controller_logs/<controller>')
def get_custom_controller_logs(controller):
    if controller == 'custom':
        controllers_command = get_command('custom_scheduler_controller')
        try:
            custom_controller = run_kubectl_command(controllers_command).strip().split()[0]
            custom_logs_command = f"kubectl logs {custom_controller} -n custom-scheduler-controller-system"
            return run_kubectl_command(custom_logs_command)
        except IndexError:
            custom_controller = None
    elif controller == 'availability':
        controller_availability_logs_command = get_command('controller_availability_logs')
        return run_kubectl_command(controller_availability_logs_command)
    return "Invalid controller query"

@app.route('/cluster_status')
def cluster_status():
    nodes_command = get_command('nodes')
    pods_command = get_command('pods')
    services_command = get_command('services')
    
    nodes_output = run_kubectl_command(nodes_command)
    pods_output = run_kubectl_command(pods_command)
    services_output = run_kubectl_command(services_command)
    
    return render_template(
        'cluster_status.html',
        nodes_command=nodes_command,
        nodes_output=nodes_output,
        pods_command=pods_command,
        pods_output=pods_output,
        services_command=services_command,
        services_output=services_output
    )

@app.route('/get_<resource>')
def get_resource(resource):
    command = get_command(resource)
    if command:
        output = run_kubectl_command(command)
        return output or "Error executing command"
    return "Invalid resource"

class LiteralString(str):
    pass

def literal_string_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')

yaml.add_representer(LiteralString, literal_string_representer)

@app.route('/get_scheduler_config')
def get_scheduler_config():
    command = get_command('scheduler_config')
    if command:
        output = run_kubectl_command(command)
        if output:
            try:
                config = yaml.safe_load(output)
                # Ensure customMetrics and parameters fields are formatted properly
                if 'data' in config:
                    if 'customMetrics' in config['data']:
                        config['data']['customMetrics'] = LiteralString(json.dumps(json.loads(config['data']['customMetrics'])))
                    if 'parameters' in config['data']:
                        config['data']['parameters'] = LiteralString(json.dumps(json.loads(config['data']['parameters'])))
                # Remove unnecessary fields from the metadata
                if 'metadata' in config:
                    to_remove = []
                    for item in config['metadata']:
                        if item not in ['name', 'namespace']:
                            to_remove.append(item)
                    for item in to_remove:
                        config['metadata'].pop(item)
                formatted_yaml = yaml.dump(config, default_flow_style=False)
                return jsonify({"output": formatted_yaml, "config": config})
            except Exception as e:
                return jsonify({"output": output, "error": str(e)})
    return jsonify({"output": "Error executing command", "config": None})

@app.route('/get_logs')
def get_logs():
    scheduler_name = request.args.get('schedulerName')
    scheduler_namespace = request.args.get('schedulerNamespace')
    if scheduler_name and scheduler_namespace:
        command = f"kubectl logs -n {scheduler_namespace} -l app={scheduler_name}"
        if command:
            output = run_kubectl_command(command)
            if output:
                return jsonify({"output": output})
    return jsonify({"output": "Error executing command"})

def validate_yaml(content):
    try:
        yaml.safe_load(content)
        return True, ""
    except yaml.YAMLError as exc:
        return False, str(exc)

@app.route('/apply_changes', methods=['POST'])
def apply_changes():
    data = request.get_json()
    content = data.get('content', '')
    
    if not content:
        return "No content provided", 400

    is_valid, error_message = validate_yaml(content)
    if not is_valid:
        return f"Invalid YAML content: {error_message}", 400
    
    with open('/tmp/scheduler_config.yaml', 'w') as f:
        f.write(content)
    
    command = "kubectl apply -f /tmp/scheduler_config.yaml"
    result = run_kubectl_command(command)
    
    if "configured" in result or "created" in result:
        return "Success"
    else:
        return result, 500

@app.route('/deploy_scheduler', methods=['POST'])
def deploy_scheduler():
    data = request.get_json()
    name = data.get('name')
    container_name = data.get('containerName')
    image = data.get('image')
    port = data.get('port')

    if not all([name, container_name, image, port]):
        return jsonify({'status': 'Failure', 'error': 'Missing required fields'}), 400

    deployment_yaml = f"""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {name}
  namespace: default
  labels:
    app: {name}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {name}
  template:
    metadata:
      labels:
        app: {name}
    spec:
      nodeSelector:
        node-role.kubernetes.io/control-plane: ""
      tolerations:
      - key: "node-role.kubernetes.io/control-plane"
        operator: "Exists"
        effect: "NoSchedule"
      containers:
      - name: {container_name}
        image: {image}
        ports:
        - containerPort: {port}
---
apiVersion: v1
kind: Service
metadata:
  name: {name}
spec:
  selector:
    app: {name}
  ports:
  - protocol: TCP
    port: 80
    targetPort: {port}
"""

    with open('/tmp/deployment.yaml', 'w') as f:
        f.write(deployment_yaml)

    command = "kubectl apply -f /tmp/deployment.yaml"
    result = run_kubectl_command(command)

    if "created" in result or "configured" in result:
        return jsonify({'status': 'Success'})
    else:
        return jsonify({'status': 'Failure', 'error': result}), 500

if __name__ == '__main__':
    app.run(debug=True)