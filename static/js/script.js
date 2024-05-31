document.addEventListener('DOMContentLoaded', function () {
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarContainer = document.querySelector('.sidebar-container');
    sidebarToggle.addEventListener('click', function () {
        sidebarContainer.classList.toggle('collapsed');
        sidebarToggle.innerHTML = sidebarContainer.classList.contains('collapsed') ? '&#x276D;' : '&#x276C;';
    });

    initializeCollapsibleBlocks();
});

function initializeCollapsibleBlocks() {
    document.querySelectorAll('.collapsible-toggle').forEach(function (toggle) {
        const content = toggle.nextElementSibling;
        const icon = toggle.querySelector('.collapsible-icon');
        const id = toggle.dataset.id;

        const isOpen = localStorage.getItem(id) === 'true';
        if (isOpen) {
            content.style.display = 'block';
            toggle.classList.add('active');
            icon.style.transform = 'rotate(90deg)';
        }

        toggle.addEventListener('click', function () {
            const isOpen = content.style.display === 'block';
            content.style.display = isOpen ? 'none' : 'block';
            toggle.classList.toggle('active');
            icon.style.transform = isOpen ? 'rotate(0deg)' : 'rotate(90deg)';

            // Save the state in local storage
            localStorage.setItem(id, !isOpen);
        });
    });
}

function asyncLoadContent(endpoint, elementId, callback = null) {
    const element = document.getElementById(elementId);
    element.innerHTML = '<span class="buffering">Buffering...</span>';
    fetch(endpoint)
        .then(response => {
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.includes("application/json")) {
                return response.json().then(data => ({ type: "json", data }));
            } else {
                return response.text().then(data => ({ type: "text", data }));
            }
        })
        .then(result => {
            if (result.type === "json") {
                element.innerHTML = `<pre><code>${escapeHtml(result.data.output)}</code></pre>`;
                if (callback && result.data.config) {
                    callback(result.data.config);
                }
            } else {
                element.innerHTML = `<pre><code>${escapeHtml(result.data)}</code></pre>`;
            }
        })
        .catch(error => {
            element.innerHTML = `<span class="error">Error fetching content: ${error}</span>`;
        });
}

// Function to escape HTML characters to ensure proper rendering
function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function enableEdit(elementId) {
    const outputElement = document.getElementById(elementId + '-output');
    const editorElement = document.getElementById(elementId + '-editor');
    const textarea = document.getElementById(elementId + '-textarea');

    textarea.value = outputElement.innerText.trim();
    outputElement.style.display = 'none';
    editorElement.style.display = 'block';
}

function applyChanges(elementId) {
    const textarea = document.getElementById(elementId + '-textarea');
    const newContent = textarea.value;

    fetch('/apply_changes', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content: newContent }),
    })
        .then(response => response.text())
        .then(data => {
            if (data === 'Success') {
                asyncLoadContent('/get_scheduler_config', elementId + '-output');
                document.getElementById(elementId + '-editor').style.display = 'none';
                document.getElementById(elementId + '-output').style.display = 'block';
            } else {
                alert('Failed to apply changes: ' + data);
            }
        })
        .catch(error => {
            alert('Error applying changes: ' + error);
        });
}

function addScheduler() {
    const schedulerName = document.getElementById('scheduler-name').value;
    const schedulerNamespace = localStorage.getItem('schedulerNamespace') || 'default';
    if (schedulerName) {
        const schedulers = JSON.parse(localStorage.getItem('schedulers')) || [];
        if (!schedulers.some(s => s.name === schedulerName && s.namespace === schedulerNamespace)) {
            schedulers.push({ name: schedulerName, namespace: schedulerNamespace });
            localStorage.setItem('schedulers', JSON.stringify(schedulers));
        }
        document.getElementById('scheduler-name').value = '';
        loadSchedulers();
    }
}

function loadSchedulers() {
    const schedulers = JSON.parse(localStorage.getItem('schedulers')) || [];
    const list = document.getElementById('scheduler-list');
    list.innerHTML = '';
    schedulers.forEach(scheduler => {
        const schedulerBlock = `
            <div class="collapsible-container">
                <button class="collapsible-toggle" data-id="${scheduler.name}-toggle" onclick="toggleCollapsibleContent(this)">
                    <span class="collapsible-title">${scheduler.name} (${scheduler.namespace})</span>
                    <span class="collapsible-icon">&#x276F;</span>
                </button>
                <div class="collapsible-content">
                    <div>
                        <button onclick="removeScheduler('${scheduler.name}', '${scheduler.namespace}')">Remove</button>
                        <button onclick="fetchLogs('${scheduler.name}', '${scheduler.namespace}', '${scheduler.name}-logs')">Get Logs</button>
                    </div>
                    <div id="${scheduler.name}-logs" class="code-block">
                        <span class="buffering">Buffering...</span>
                    </div>
                </div>
            </div>
        `;
        list.insertAdjacentHTML('beforeend', schedulerBlock);
        // Automatically fetch logs on page load
        fetchLogs(scheduler.name, scheduler.namespace, `${scheduler.name}-logs`);
    });
    initializeCollapsibleBlocks(); // Ensure collapsible blocks are initialized
}

function removeScheduler(name, namespace) {
    let schedulers = JSON.parse(localStorage.getItem('schedulers')) || [];
    schedulers = schedulers.filter(s => s.name !== name || s.namespace !== namespace);
    localStorage.setItem('schedulers', JSON.stringify(schedulers));
    loadSchedulers();
}

function fetchLogs(schedulerName, schedulerNamespace, elementId) {
    asyncLoadContent(`/get_logs?schedulerName=${schedulerName}&schedulerNamespace=${schedulerNamespace}`, elementId);
}

function saveSchedulerConfig(config) {
    if (config) {
        const schedulerName = config.data.schedulerName;
        const schedulerNamespace = config.data.schedulerNamespace;
        if (schedulerName && schedulerNamespace) {
            localStorage.setItem('schedulerName', schedulerName);
            localStorage.setItem('schedulerNamespace', schedulerNamespace);

            // Add the schedulerName to the list of external schedulers if not already present
            const schedulers = JSON.parse(localStorage.getItem('schedulers')) || [];
            if (!schedulers.some(s => s.name === schedulerName && s.namespace === schedulerNamespace)) {
                schedulers.push({ name: schedulerName, namespace: schedulerNamespace });
                localStorage.setItem('schedulers', JSON.stringify(schedulers));
                loadSchedulers(); // Refresh the scheduler list UI
            }
        }
    }
}

function deployScheduler() {
    const form = document.getElementById('deploy-scheduler-form');
    const formData = new FormData(form);

    const data = {
        name: formData.get('name'),
        containerName: formData.get('container-name'),
        image: formData.get('image'),
        port: formData.get('port')
    };

    fetch('/deploy_scheduler', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'Success') {
                alert('Scheduler deployed successfully');
                loadSchedulers(); // Refresh the list of schedulers
            } else {
                alert('Failed to deploy scheduler: ' + data.error);
            }
        })
        .catch(error => {
            alert('Error deploying scheduler: ' + error);
        });
}