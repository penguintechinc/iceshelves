#!/usr/bin/env python3
"""
IceShelves Agent - Polling Agent for LXD/KVM Deployments

This agent polls the IceShelves server for pending deployments and executes them
on the local LXD or KVM hypervisor.

Usage:
    iceshelves-agent.py --server https://iceshelves.example.com --cluster-id 1 --agent-key YOUR_KEY

Environment Variables:
    ICESHELVES_SERVER - IceShelves server URL
    ICESHELVES_CLUSTER_ID - Cluster ID
    ICESHELVES_AGENT_KEY - Agent authentication key
    ICESHELVES_POLL_INTERVAL - Poll interval in seconds (default: 300)
"""

import os
import sys
import time
import argparse
import logging
import json
import requests
import tempfile
from typing import Dict, List, Optional, Any
from datetime import datetime

try:
    import pylxd
    from pylxd.exceptions import LXDAPIException
    PYLXD_AVAILABLE = True
except ImportError:
    PYLXD_AVAILABLE = False
    print("WARNING: pylxd not available - LXD deployments will fail")

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    print("WARNING: PyYAML not available - cloud-init parsing will fail")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('iceshelves-agent')


class IceShelvesAgent:
    """Agent for polling and executing deployments."""

    def __init__(
        self,
        server_url: str,
        cluster_id: int,
        agent_key: str,
        poll_interval: int = 300
    ):
        """
        Initialize agent.

        Args:
            server_url: IceShelves server URL
            cluster_id: Cluster ID
            agent_key: Agent authentication key
            poll_interval: Poll interval in seconds
        """
        self.server_url = server_url.rstrip('/')
        self.cluster_id = cluster_id
        self.agent_key = agent_key
        self.poll_interval = poll_interval
        self.lxd_client = None

        logger.info(f"IceShelves Agent initialized")
        logger.info(f"Server: {self.server_url}")
        logger.info(f"Cluster ID: {self.cluster_id}")
        logger.info(f"Poll Interval: {self.poll_interval}s")

    def connect_lxd(self) -> bool:
        """Connect to local LXD."""
        if not PYLXD_AVAILABLE:
            logger.error("pylxd not available")
            return False

        try:
            self.lxd_client = pylxd.Client()
            logger.info("Connected to LXD")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to LXD: {e}")
            return False

    def poll_for_deployments(self) -> List[Dict[str, Any]]:
        """Poll server for pending deployments."""
        try:
            url = f"{self.server_url}/api/agent/poll/{self.cluster_id}"
            headers = {
                'X-Agent-Key': self.agent_key,
                'Content-Type': 'application/json'
            }

            response = requests.post(url, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()
            deployments = data.get('deployments', [])

            logger.info(f"Polled server, found {len(deployments)} pending deployments")
            return deployments
        except requests.RequestException as e:
            logger.error(f"Failed to poll server: {e}")
            return []

    def update_deployment_status(
        self,
        deployment_id: int,
        status: str,
        message: str = "",
        instance_info: Optional[Dict] = None,
        error_message: Optional[str] = None
    ):
        """Update deployment status on server."""
        try:
            url = f"{self.server_url}/api/agent/status/{deployment_id}"
            headers = {
                'X-Agent-Key': self.agent_key,
                'Content-Type': 'application/json'
            }

            payload = {
                'status': status,
                'message': message,
                'instance_info': instance_info,
                'error_message': error_message,
                'details': {
                    'agent_hostname': os.uname().nodename,
                    'timestamp': datetime.utcnow().isoformat()
                }
            }

            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()

            logger.info(f"Updated deployment {deployment_id} status to {status}")
        except requests.RequestException as e:
            logger.error(f"Failed to update deployment status: {e}")

    def deploy_lxd_instance(self, deployment: Dict[str, Any]) -> bool:
        """
        Deploy LXD instance.

        Args:
            deployment: Deployment configuration

        Returns:
            True if successful, False otherwise
        """
        deployment_id = deployment['deployment_id']
        instance_name = deployment['instance_name']
        egg_name = deployment['egg_name']

        try:
            # Update status to in_progress
            self.update_deployment_status(deployment_id, 'in_progress', f'Starting deployment of {instance_name}')

            # Parse cloud-init
            cloud_init_yaml = deployment.get('cloud_init')
            if not cloud_init_yaml:
                raise Exception("No cloud-init configuration provided")

            # Create instance config
            source = {
                'type': 'image',
                'alias': 'ubuntu/24.04'  # TODO: Get from egg metadata
            }

            config = {
                'user.cloud-init.user-data': cloud_init_yaml
            }

            # Apply config overrides
            if deployment.get('config_overrides'):
                config.update(deployment['config_overrides'])

            # Create instance
            logger.info(f"Creating instance {instance_name}")
            instance = self.lxd_client.instances.create({
                'name': instance_name,
                'source': source,
                'config': config,
                'profiles': ['default']
            }, wait=True)

            # Start instance
            logger.info(f"Starting instance {instance_name}")
            instance.start(wait=True)

            # Get instance info
            instance_info = {
                'name': instance.name,
                'status': instance.status,
                'architecture': instance.architecture,
                'created_at': instance.created_at,
                'ipv4': instance.state().network.get('eth0', {}).get('addresses', [])
            }

            # Update status to completed
            self.update_deployment_status(
                deployment_id,
                'completed',
                f'Instance {instance_name} deployed successfully',
                instance_info=instance_info
            )

            logger.info(f"Deployment {deployment_id} completed successfully")
            return True

        except LXDAPIException as e:
            error_msg = f"LXD API error: {str(e)}"
            logger.error(f"Deployment {deployment_id} failed: {error_msg}")
            self.update_deployment_status(deployment_id, 'failed', error_message=error_msg)
            return False
        except Exception as e:
            error_msg = f"Deployment error: {str(e)}"
            logger.error(f"Deployment {deployment_id} failed: {error_msg}")
            self.update_deployment_status(deployment_id, 'failed', error_message=error_msg)
            return False

    def process_deployments(self, deployments: List[Dict[str, Any]]):
        """Process pending deployments."""
        for deployment in deployments:
            deployment_type = deployment.get('deployment_type', 'lxd')

            if deployment_type == 'lxd':
                self.deploy_lxd_instance(deployment)
            elif deployment_type == 'kvm':
                logger.warning(f"KVM deployments not yet implemented")
                self.update_deployment_status(
                    deployment['deployment_id'],
                    'failed',
                    error_message='KVM deployments not yet supported by agent'
                )
            else:
                logger.error(f"Unknown deployment type: {deployment_type}")

    def run(self):
        """Main agent loop."""
        logger.info("Starting agent main loop")

        # Connect to LXD
        if not self.connect_lxd():
            logger.error("Failed to connect to LXD, exiting")
            return 1

        # Main loop
        while True:
            try:
                # Poll for deployments
                deployments = self.poll_for_deployments()

                # Process deployments
                if deployments:
                    self.process_deployments(deployments)

                # Sleep until next poll
                logger.debug(f"Sleeping for {self.poll_interval} seconds")
                time.sleep(self.poll_interval)

            except KeyboardInterrupt:
                logger.info("Agent stopped by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                time.sleep(60)  # Sleep for a minute before retrying

        return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='IceShelves Deployment Agent')
    parser.add_argument('--server', help='IceShelves server URL',
                        default=os.getenv('ICESHELVES_SERVER'))
    parser.add_argument('--cluster-id', type=int, help='Cluster ID',
                        default=os.getenv('ICESHELVES_CLUSTER_ID'))
    parser.add_argument('--agent-key', help='Agent authentication key',
                        default=os.getenv('ICESHELVES_AGENT_KEY'))
    parser.add_argument('--poll-interval', type=int, help='Poll interval in seconds',
                        default=int(os.getenv('ICESHELVES_POLL_INTERVAL', '300')))
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate required arguments
    if not args.server:
        print("Error: --server or ICESHELVES_SERVER environment variable required")
        return 1

    if not args.cluster_id:
        print("Error: --cluster-id or ICESHELVES_CLUSTER_ID environment variable required")
        return 1

    if not args.agent_key:
        print("Error: --agent-key or ICESHELVES_AGENT_KEY environment variable required")
        return 1

    # Create and run agent
    agent = IceShelvesAgent(
        server_url=args.server,
        cluster_id=args.cluster_id,
        agent_key=args.agent_key,
        poll_interval=args.poll_interval
    )

    return agent.run()


if __name__ == '__main__':
    sys.exit(main())
