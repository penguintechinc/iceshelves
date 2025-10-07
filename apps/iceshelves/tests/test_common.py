"""
Unit tests for IceShelves common utilities

These tests validate core functionality without external dependencies.
Network isolation: All tests use mocks for external connections.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import common
import yaml


class TestCloudInitValidation(unittest.TestCase):
    """Test cloud-init YAML validation."""

    def test_valid_cloud_init(self):
        """Test validation of valid cloud-init YAML."""
        valid_yaml = """
#cloud-config
hostname: test-host
packages:
  - vim
  - curl
"""
        is_valid, message, data = common.validate_cloud_init(valid_yaml)
        self.assertTrue(is_valid)
        self.assertIsNotNone(data)
        self.assertIn('packages', data)

    def test_invalid_yaml(self):
        """Test validation of invalid YAML."""
        invalid_yaml = """
#cloud-config
hostname: test
packages
  - vim
"""
        is_valid, message, data = common.validate_cloud_init(invalid_yaml)
        self.assertFalse(is_valid)
        self.assertIsNone(data)
        self.assertIn('YAML', message)

    def test_non_dict_cloud_init(self):
        """Test validation of non-dictionary cloud-init."""
        invalid_yaml = """
- item1
- item2
"""
        is_valid, message, data = common.validate_cloud_init(invalid_yaml)
        self.assertFalse(is_valid)
        self.assertIn('dictionary', message)


class TestCloudInitTemplateRendering(unittest.TestCase):
    """Test cloud-init template rendering."""

    def test_render_template(self):
        """Test basic template rendering."""
        template = """
#cloud-config
hostname: {{ hostname }}
packages:
  - {{ package }}
"""
        variables = {'hostname': 'test-host', 'package': 'vim'}
        result = common.render_cloud_init_template(template, variables)

        self.assertIn('test-host', result)
        self.assertIn('vim', result)

    def test_render_template_with_loops(self):
        """Test template rendering with loops."""
        template = """
#cloud-config
packages:
{% for pkg in packages %}
  - {{ pkg }}
{% endfor %}
"""
        variables = {'packages': ['vim', 'curl', 'git']}
        result = common.render_cloud_init_template(template, variables)

        self.assertIn('vim', result)
        self.assertIn('curl', result)
        self.assertIn('git', result)


class TestCloudInitMerging(unittest.TestCase):
    """Test cloud-init configuration merging."""

    def test_merge_simple(self):
        """Test simple merge of cloud-init configs."""
        base = """
#cloud-config
hostname: base-host
packages:
  - vim
"""
        overrides = {'hostname': 'override-host'}
        result = common.merge_cloud_init(base, overrides)

        result_data = yaml.safe_load(result)
        self.assertEqual(result_data['hostname'], 'override-host')
        self.assertIn('packages', result_data)

    def test_merge_deep(self):
        """Test deep merge of nested structures."""
        base = """
write_files:
  - path: /etc/test
    content: original
users:
  - name: ubuntu
"""
        overrides = {
            'write_files': [
                {'path': '/etc/new', 'content': 'new content'}
            ]
        }

        result = common.merge_cloud_init(base, overrides)
        result_data = yaml.safe_load(result)

        # Overrides should replace, not append
        self.assertIsInstance(result_data.get('write_files'), list)


class TestAgentKeyGeneration(unittest.TestCase):
    """Test agent key generation."""

    def test_generate_agent_key(self):
        """Test agent key generation produces unique keys."""
        key1 = common.generate_agent_key()
        key2 = common.generate_agent_key()

        self.assertIsInstance(key1, str)
        self.assertIsInstance(key2, str)
        self.assertNotEqual(key1, key2)
        self.assertGreater(len(key1), 20)  # Should be long enough


class TestAgentKeyVerification(unittest.TestCase):
    """Test agent key verification."""

    @patch('common.db')
    def test_verify_valid_key(self, mock_db):
        """Test verification of valid agent key."""
        # Mock database cluster record
        mock_cluster = Mock()
        mock_cluster.connection_method = 'agent-poll'
        mock_cluster.agent_key = 'test-key-12345'
        mock_db.lxd_clusters.__getitem__.return_value = mock_cluster

        result = common.verify_agent_key(1, 'test-key-12345')
        self.assertTrue(result)

    @patch('common.db')
    def test_verify_invalid_key(self, mock_db):
        """Test verification of invalid agent key."""
        mock_cluster = Mock()
        mock_cluster.connection_method = 'agent-poll'
        mock_cluster.agent_key = 'test-key-12345'
        mock_db.lxd_clusters.__getitem__.return_value = mock_cluster

        result = common.verify_agent_key(1, 'wrong-key')
        self.assertFalse(result)

    @patch('common.db')
    def test_verify_wrong_connection_method(self, mock_db):
        """Test verification fails for non-agent-poll clusters."""
        mock_cluster = Mock()
        mock_cluster.connection_method = 'direct-api'
        mock_db.lxd_clusters.__getitem__.return_value = mock_cluster

        result = common.verify_agent_key(1, 'any-key')
        self.assertFalse(result)


class TestEggPathGeneration(unittest.TestCase):
    """Test egg path generation."""

    def test_get_egg_path(self):
        """Test egg path generation."""
        egg_name = 'test-egg'
        path = common.get_egg_path(egg_name)

        self.assertIn('test-egg', str(path))
        self.assertTrue(str(path).endswith('test-egg'))


if __name__ == '__main__':
    unittest.main()
