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
        'scheduler_config': "kubectl get configmap scheduler-config -n default -o yaml"
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

@app.route('/controllers')
def controllers():
    return render_template('controllers.html')

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

@app.route('/functions')
def functions():
    return render_template('functions.html')

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
                print(e)
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

if __name__ == '__main__':
    app.run(debug=True)
