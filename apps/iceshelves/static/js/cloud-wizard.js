/**
 * IceShelves Cloud Provider Wizard JavaScript
 *
 * Handles multi-step wizards for AWS, GCP, and other cloud provider configuration
 */

// ============================================================================
// WIZARD NAVIGATION
// ============================================================================

let currentStep = 1;
const totalSteps = 4;

function showStep(stepNumber) {
    // Hide all steps
    for (let i = 1; i <= totalSteps; i++) {
        const stepElement = document.getElementById(`step-${i}`);
        if (stepElement) {
            stepElement.classList.remove('is-active');
        }
    }

    // Show current step
    const currentStepElement = document.getElementById(`step-${stepNumber}`);
    if (currentStepElement) {
        currentStepElement.classList.add('is-active');
    }

    // Update progress indicators
    updateProgressIndicators(stepNumber);

    // Update navigation buttons
    updateNavigationButtons(stepNumber);

    currentStep = stepNumber;
}

function updateProgressIndicators(stepNumber) {
    for (let i = 1; i <= totalSteps; i++) {
        const indicator = document.querySelector(`.step-indicator[data-step="${i}"]`);
        if (indicator) {
            if (i < stepNumber) {
                indicator.classList.add('is-completed');
                indicator.classList.remove('is-active');
            } else if (i === stepNumber) {
                indicator.classList.add('is-active');
                indicator.classList.remove('is-completed');
            } else {
                indicator.classList.remove('is-active', 'is-completed');
            }
        }
    }
}

function updateNavigationButtons(stepNumber) {
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    const submitBtn = document.getElementById('submit-btn');

    if (prevBtn) {
        prevBtn.style.display = stepNumber === 1 ? 'none' : 'inline-block';
    }

    if (nextBtn && submitBtn) {
        if (stepNumber === totalSteps) {
            nextBtn.style.display = 'none';
            submitBtn.style.display = 'inline-block';
        } else {
            nextBtn.style.display = 'inline-block';
            submitBtn.style.display = 'none';
        }
    }
}

function nextStep() {
    if (currentStep < totalSteps) {
        showStep(currentStep + 1);
    }
}

function prevStep() {
    if (currentStep > 1) {
        showStep(currentStep - 1);
    }
}

// ============================================================================
// CREDENTIAL MANAGEMENT
// ============================================================================

async function loadUserCredentials(credentialType) {
    try {
        const response = await fetch(`/iceshelves/api/user/credentials?type=${credentialType}`);
        const data = await response.json();

        const selectElement = document.getElementById(`${credentialType}-credential-select`) ||
                              document.getElementById('credential-select');

        if (selectElement && data.credentials) {
            selectElement.innerHTML = '<option value="">-- Select credentials --</option>';

            data.credentials.forEach(cred => {
                const option = document.createElement('option');
                option.value = cred.id;
                option.textContent = `${cred.name} (added ${new Date(cred.created_on).toLocaleDateString()})`;
                selectElement.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Failed to load credentials:', error);
        showNotification('Failed to load saved credentials', 'danger');
    }
}

function toggleCredentialSource(source) {
    const savedSection = document.getElementById('saved-credentials-section') ||
                        document.getElementById('aws-saved-credentials-section') ||
                        document.getElementById('gcp-saved-credentials-section');
    const inlineSection = document.getElementById('inline-credentials-section') ||
                         document.getElementById('aws-inline-credentials-section');
    const uploadSection = document.getElementById('gcp-upload-credentials-section');
    const iamSection = document.getElementById('iam-role-section');

    // Hide all sections
    [savedSection, inlineSection, uploadSection, iamSection].forEach(section => {
        if (section) section.style.display = 'none';
    });

    // Show selected section
    if (source === 'saved' && savedSection) {
        savedSection.style.display = 'block';
        loadUserCredentials(window.location.pathname.includes('aws') ? 'aws' : 'gcp');
    } else if (source === 'inline' && inlineSection) {
        inlineSection.style.display = 'block';
    } else if (source === 'upload' && uploadSection) {
        uploadSection.style.display = 'block';
    } else if (source === 'iam' && iamSection) {
        iamSection.style.display = 'block';
    }
}

// ============================================================================
// AWS WIZARD FUNCTIONS
// ============================================================================

async function testAWSConnection() {
    const accessKeyId = document.getElementById('aws-access-key-id').value;
    const secretAccessKey = document.getElementById('aws-secret-access-key').value;
    const region = document.getElementById('region').value;

    if (!accessKeyId || !secretAccessKey) {
        showNotification('Please enter AWS credentials', 'warning');
        return;
    }

    const testBtn = document.getElementById('test-connection-btn');
    const originalText = testBtn.textContent;
    testBtn.classList.add('is-loading');
    testBtn.disabled = true;

    try {
        const response = await fetch('/iceshelves/api/aws/test-connection', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                aws_access_key_id: accessKeyId,
                aws_secret_access_key: secretAccessKey,
                region: region
            })
        });

        const data = await response.json();

        if (data.success) {
            showNotification(data.message, 'success');
            // Load VPCs and other resources
            await loadAWSResources();
        } else {
            showNotification(`Connection failed: ${data.message}`, 'danger');
        }
    } catch (error) {
        console.error('Connection test failed:', error);
        showNotification('Connection test failed', 'danger');
    } finally {
        testBtn.classList.remove('is-loading');
        testBtn.disabled = false;
        testBtn.textContent = originalText;
    }
}

async function loadAWSResources() {
    const credentialId = document.getElementById('credential-select')?.value;
    const region = document.getElementById('region').value;

    if (!credentialId) {
        showNotification('Please select credentials first', 'warning');
        return;
    }

    try {
        // Load VPCs, Security Groups, and AMIs concurrently
        const [vpcsData, amisData] = await Promise.all([
            fetch('/iceshelves/api/aws/vpcs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ credential_id: credentialId, region })
            }).then(r => r.json()),

            fetch('/iceshelves/api/aws/amis', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ credential_id: credentialId, region })
            }).then(r => r.json())
        ]);

        // Populate VPC dropdown
        if (vpcsData.success && vpcsData.vpcs) {
            const vpcSelect = document.getElementById('vpc-id');
            vpcSelect.innerHTML = '<option value="">-- Select VPC --</option>';

            vpcsData.vpcs.forEach(vpc => {
                const option = document.createElement('option');
                option.value = vpc.vpc_id;
                const vpcName = vpc.tags.Name || vpc.vpc_id;
                option.textContent = `${vpcName} (${vpc.cidr_block})${vpc.is_default ? ' [Default]' : ''}`;
                vpcSelect.appendChild(option);
            });
        }

        // Populate AMI dropdown
        if (amisData.success && amisData.amis) {
            const amiSelect = document.getElementById('ami');
            amiSelect.innerHTML = '<option value="">-- Select AMI --</option>';

            amisData.amis.forEach(ami => {
                const option = document.createElement('option');
                option.value = ami.ami_id;
                option.textContent = `${ami.name} (${ami.ami_id})`;
                amiSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Failed to load AWS resources:', error);
        showNotification('Failed to load AWS resources', 'danger');
    }
}

async function loadAWSSubnets(vpcId) {
    const credentialId = document.getElementById('credential-select')?.value;
    const region = document.getElementById('region').value;

    if (!vpcId || !credentialId) return;

    try {
        const response = await fetch('/iceshelves/api/aws/subnets', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ credential_id: credentialId, region, vpc_id: vpcId })
        });

        const data = await response.json();

        if (data.success && data.subnets) {
            const subnetSelect = document.getElementById('subnet-id');
            subnetSelect.innerHTML = '<option value="">-- Select Subnet --</option>';

            data.subnets.forEach(subnet => {
                const option = document.createElement('option');
                option.value = subnet.subnet_id;
                const subnetName = subnet.tags.Name || subnet.subnet_id;
                option.textContent = `${subnetName} (${subnet.cidr_block}) - ${subnet.availability_zone}`;
                subnetSelect.appendChild(option);
            });
        }

        // Also load security groups for this VPC
        await loadAWSSecurityGroups(vpcId);
    } catch (error) {
        console.error('Failed to load AWS subnets:', error);
        showNotification('Failed to load subnets', 'danger');
    }
}

async function loadAWSSecurityGroups(vpcId) {
    const credentialId = document.getElementById('credential-select')?.value;
    const region = document.getElementById('region').value;

    if (!vpcId || !credentialId) return;

    try {
        const response = await fetch('/iceshelves/api/aws/security-groups', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ credential_id: credentialId, region, vpc_id: vpcId })
        });

        const data = await response.json();

        if (data.success && data.security_groups) {
            const sgContainer = document.getElementById('security-groups-container');
            sgContainer.innerHTML = '';

            data.security_groups.forEach(sg => {
                const checkbox = document.createElement('label');
                checkbox.className = 'checkbox';
                checkbox.innerHTML = `
                    <input type="checkbox" name="security_groups[]" value="${sg.group_id}">
                    ${sg.group_name} (${sg.group_id}) - ${sg.description}
                `;
                sgContainer.appendChild(checkbox);
                sgContainer.appendChild(document.createElement('br'));
            });
        }
    } catch (error) {
        console.error('Failed to load AWS security groups:', error);
        showNotification('Failed to load security groups', 'danger');
    }
}

// ============================================================================
// GCP WIZARD FUNCTIONS
// ============================================================================

async function testGCPConnection() {
    const serviceAccountJson = document.getElementById('gcp-service-account-json').value;
    const projectId = document.getElementById('gcp-project-id').value;
    const zone = document.getElementById('zone').value;

    if (!serviceAccountJson || !projectId) {
        showNotification('Please enter GCP credentials', 'warning');
        return;
    }

    const testBtn = document.getElementById('test-gcp-connection-btn');
    const originalText = testBtn.textContent;
    testBtn.classList.add('is-loading');
    testBtn.disabled = true;

    try {
        const response = await fetch('/iceshelves/api/gcp/test-connection', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                gcp_service_account_json: serviceAccountJson,
                gcp_project_id: projectId,
                zone: zone
            })
        });

        const data = await response.json();

        if (data.success) {
            showNotification(data.message, 'success');
            // Load GCP resources
            await loadGCPResources();
        } else {
            showNotification(`Connection failed: ${data.message}`, 'danger');
        }
    } catch (error) {
        console.error('Connection test failed:', error);
        showNotification('Connection test failed', 'danger');
    } finally {
        testBtn.classList.remove('is-loading');
        testBtn.disabled = false;
        testBtn.textContent = originalText;
    }
}

async function loadGCPResources() {
    const credentialId = document.getElementById('gcp-credential-select')?.value;
    const zone = document.getElementById('zone').value;

    if (!credentialId) {
        showNotification('Please select credentials first', 'warning');
        return;
    }

    try {
        // Load Networks, Machine Types, and Images concurrently
        const [networksData, machineTypesData, imagesData] = await Promise.all([
            fetch('/iceshelves/api/gcp/networks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ credential_id: credentialId, zone })
            }).then(r => r.json()),

            fetch('/iceshelves/api/gcp/machine-types', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ credential_id: credentialId, zone })
            }).then(r => r.json()),

            fetch('/iceshelves/api/gcp/images', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ credential_id: credentialId, zone, family: 'ubuntu-2404-lts' })
            }).then(r => r.json())
        ]);

        // Populate Network dropdown
        if (networksData.success && networksData.networks) {
            const networkSelect = document.getElementById('network');
            networkSelect.innerHTML = '<option value="">-- Select Network --</option>';

            networksData.networks.forEach(network => {
                const option = document.createElement('option');
                option.value = network.name;
                option.textContent = `${network.name} (${network.routing_mode})`;
                networkSelect.appendChild(option);
            });
        }

        // Populate Machine Type dropdown (keep existing options, just update)
        if (machineTypesData.success && machineTypesData.machine_types) {
            // Filter for common types
            const commonTypes = machineTypesData.machine_types.filter(mt =>
                mt.name.startsWith('e2-') || mt.name.startsWith('n2-') || mt.name.startsWith('c2-')
            );

            // Update descriptions with actual values
            console.log('Available machine types:', commonTypes.map(mt => mt.name));
        }
    } catch (error) {
        console.error('Failed to load GCP resources:', error);
        showNotification('Failed to load GCP resources', 'danger');
    }
}

function parseServiceAccountJSON(jsonText) {
    try {
        const data = JSON.parse(jsonText);
        const projectIdField = document.getElementById('gcp-project-id');

        if (data.project_id && projectIdField) {
            projectIdField.value = data.project_id;
            showNotification('Project ID extracted from service account JSON', 'success');
        }
    } catch (error) {
        console.error('Invalid JSON:', error);
        showNotification('Invalid service account JSON', 'danger');
    }
}

// ============================================================================
// FIREWALL TAG MANAGEMENT
// ============================================================================

function addFirewallTag() {
    const input = document.getElementById('firewall-tag-input');
    const tagValue = input.value.trim();

    if (!tagValue) return;

    const container = document.getElementById('firewall-tags-container');
    const tag = document.createElement('span');
    tag.className = 'tag is-info is-medium';
    tag.innerHTML = `
        ${tagValue}
        <button class="delete is-small" onclick="removeFirewallTag(this)"></button>
        <input type="hidden" name="firewall_tags[]" value="${tagValue}">
    `;

    container.appendChild(tag);
    input.value = '';
}

function removeFirewallTag(button) {
    button.parentElement.remove();
}

// ============================================================================
// FORM SUBMISSION
// ============================================================================

async function submitAWSWizard() {
    const submitBtn = document.getElementById('submit-btn');
    submitBtn.classList.add('is-loading');
    submitBtn.disabled = true;

    try {
        const formData = {
            name: document.getElementById('name').value,
            description: document.getElementById('description').value,
            region: document.getElementById('region').value,
            credential_source: document.querySelector('input[name="credential_source"]:checked').value,
            credential_id: document.getElementById('credential-select')?.value,
            instance_type: document.getElementById('instance-type').value,
            ami: document.getElementById('ami').value,
            vpc_id: document.getElementById('vpc-id').value,
            subnet_id: document.getElementById('subnet-id').value,
            security_group_ids: Array.from(document.querySelectorAll('input[name="security_groups[]"]:checked'))
                                      .map(cb => cb.value),
            ebs_volume_size: parseInt(document.getElementById('ebs-volume-size').value),
            ebs_volume_type: document.getElementById('ebs-volume-type').value
        };

        // Add inline credentials if selected
        if (formData.credential_source === 'inline') {
            formData.aws_access_key_id = document.getElementById('aws-access-key-id').value;
            formData.aws_secret_access_key = document.getElementById('aws-secret-access-key').value;
        }

        const response = await fetch('/iceshelves/clouds/add/aws', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        const data = await response.json();

        if (data.success) {
            showNotification(data.message, 'success');
            setTimeout(() => {
                window.location.href = `/iceshelves/clusters/view/${data.target_id}`;
            }, 1500);
        } else {
            showNotification(`Error: ${data.message}`, 'danger');
        }
    } catch (error) {
        console.error('Form submission failed:', error);
        showNotification('Form submission failed', 'danger');
    } finally {
        submitBtn.classList.remove('is-loading');
        submitBtn.disabled = false;
    }
}

async function submitGCPWizard() {
    const submitBtn = document.getElementById('submit-btn');
    submitBtn.classList.add('is-loading');
    submitBtn.disabled = true;

    try {
        const formData = {
            name: document.getElementById('name').value,
            description: document.getElementById('description').value,
            zone: document.getElementById('zone').value,
            credential_source: document.querySelector('input[name="credential_source"]:checked').value,
            credential_id: document.getElementById('gcp-credential-select')?.value,
            machine_type: document.getElementById('machine-type').value,
            image_project: 'ubuntu-os-cloud',
            image_family: 'ubuntu-2404-lts',
            network: document.getElementById('network').value,
            firewall_tags: Array.from(document.querySelectorAll('input[name="firewall_tags[]"]'))
                                 .map(input => input.value),
            disk_size_gb: parseInt(document.getElementById('disk-size-gb').value),
            disk_type: document.getElementById('disk-type').value
        };

        // Add uploaded credentials if selected
        if (formData.credential_source === 'upload') {
            formData.gcp_service_account_json = document.getElementById('gcp-service-account-json').value;
            formData.gcp_project_id = document.getElementById('gcp-project-id').value;
        }

        const response = await fetch('/iceshelves/clouds/add/gcp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        const data = await response.json();

        if (data.success) {
            showNotification(data.message, 'success');
            setTimeout(() => {
                window.location.href = `/iceshelves/clusters/view/${data.target_id}`;
            }, 1500);
        } else {
            showNotification(`Error: ${data.message}`, 'danger');
        }
    } catch (error) {
        console.error('Form submission failed:', error);
        showNotification('Form submission failed', 'danger');
    } finally {
        submitBtn.classList.remove('is-loading');
        submitBtn.disabled = false;
    }
}

// ============================================================================
// NOTIFICATIONS
// ============================================================================

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification is-${type} is-light`;
    notification.innerHTML = `
        <button class="delete"></button>
        ${message}
    `;

    // Add to notification container
    const container = document.getElementById('notification-container');
    if (container) {
        container.appendChild(notification);
    } else {
        // Fallback: prepend to body
        document.body.insertBefore(notification, document.body.firstChild);
    }

    // Add delete functionality
    const deleteBtn = notification.querySelector('.delete');
    deleteBtn.addEventListener('click', () => {
        notification.remove();
    });

    // Auto-remove after 5 seconds
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

// ============================================================================
// INITIALIZATION
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    // Initialize wizard on page 1
    showStep(1);

    // Load saved credentials on page load if needed
    const credentialSelect = document.getElementById('credential-select') ||
                            document.getElementById('gcp-credential-select');

    if (credentialSelect) {
        const isAWS = window.location.pathname.includes('aws');
        const isGCP = window.location.pathname.includes('gcp');

        if (isAWS) {
            loadUserCredentials('aws');
        } else if (isGCP) {
            loadUserCredentials('gcp');
        }
    }

    // Event listeners for VPC change (AWS)
    const vpcSelect = document.getElementById('vpc-id');
    if (vpcSelect) {
        vpcSelect.addEventListener('change', (e) => {
            if (e.target.value) {
                loadAWSSubnets(e.target.value);
            }
        });
    }

    // Event listener for service account JSON parsing (GCP)
    const serviceAccountTextarea = document.getElementById('gcp-service-account-json');
    if (serviceAccountTextarea) {
        serviceAccountTextarea.addEventListener('blur', (e) => {
            if (e.target.value) {
                parseServiceAccountJSON(e.target.value);
            }
        });
    }

    // Event listener for firewall tag input (GCP)
    const firewallTagInput = document.getElementById('firewall-tag-input');
    if (firewallTagInput) {
        firewallTagInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                addFirewallTag();
            }
        });
    }
});
