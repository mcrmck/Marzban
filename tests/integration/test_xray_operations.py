import pytest
from unittest.mock import Mock, patch, MagicMock
from app.xray.operations import (
    connect_node, restart_node, update_user,
    activate_user_on_node, deactivate_user
)
from app.models.node import NodeStatus
from app.models.user import UserStatus
from app.xray.config import XRayConfig
from app.xray.node import ReSTXRayNode

# Fixtures
@pytest.fixture
def mock_db():
    with patch('app.xray.operations.GetDB') as mock:
        db = Mock()
        mock.return_value.__enter__.return_value = db
        yield db

@pytest.fixture
def mock_node():
    node = Mock()
    node.id = 1
    node.name = "Test Node"
    node.status = NodeStatus.disconnected
    node.api_port = 62051
    node.service_configurations = []
    return node

@pytest.fixture
def mock_user():
    user = Mock()
    user.id = 1
    user.account_number = "test123"
    user.status = UserStatus.active
    user.active_node_id = None
    user.proxies = []
    return user

@pytest.fixture
def mock_xray_node():
    node = Mock(spec=ReSTXRayNode)
    node.id = 1
    node.name = "Test Node"
    node.connected = False
    node.started = False
    node.api = Mock()
    return node

class TestNodeOperations:
    @patch('app.xray.operations.xray.nodes')
    @patch('app.xray.operations.crud')
    def test_connect_node_success(self, mock_crud, mock_xray_nodes, mock_db, mock_node):
        # Setup
        mock_crud.get_node_by_id.return_value = mock_node
        mock_crud.get_users_by_active_node_id.return_value = []

        mock_xray_node = Mock(spec=ReSTXRayNode)
        mock_xray_node.connect.return_value = True
        mock_xray_node.start.return_value = {"status": "success"}
        mock_xray_node.get_version.return_value = "1.8.0"
        mock_xray_nodes.get.return_value = mock_xray_node

        # Execute
        connect_node(mock_node.id)

        # Verify
        mock_crud.get_node_by_id.assert_called_once_with(mock_db, mock_node.id)
        mock_crud.get_users_by_active_node_id.assert_called_once_with(mock_db, mock_node.id)
        mock_xray_node.connect.assert_called_once()
        mock_xray_node.start.assert_called_once()
        assert isinstance(mock_xray_node.start.call_args[0][0], XRayConfig)
        mock_crud.update_node_status.assert_called_with(
            mock_db, mock_node, NodeStatus.connected,
            message="Successfully connected and Xray started.",
            version="1.8.0"
        )

    @patch('app.xray.operations.xray.nodes')
    @patch('app.xray.operations.crud')
    def test_restart_node_success(self, mock_crud, mock_xray_nodes, mock_db, mock_node):
        # Setup
        mock_node.status = NodeStatus.connected
        mock_crud.get_node_by_id.return_value = mock_node
        mock_crud.get_users_by_active_node_id.return_value = []

        mock_xray_node = Mock(spec=ReSTXRayNode)
        mock_xray_node.connected = True
        mock_xray_node.started = True
        mock_xray_node.restart.return_value = {"status": "success"}
        mock_xray_node.get_version.return_value = "1.8.0"
        mock_xray_nodes.get.return_value = mock_xray_node

        # Execute
        restart_node(mock_node.id)

        # Verify
        mock_crud.get_node_by_id.assert_called_once_with(mock_db, mock_node.id)
        mock_crud.get_users_by_active_node_id.assert_called_once_with(mock_db, mock_node.id)
        mock_xray_node.restart.assert_called_once()
        assert isinstance(mock_xray_node.restart.call_args[0][0], XRayConfig)
        mock_crud.update_node_status.assert_called_with(
            mock_db, mock_node, NodeStatus.connected,
            message="Xray core restarted successfully.",
            version="1.8.0"
        )

class TestUserOperations:
    @patch('app.xray.operations.xray.nodes')
    @patch('app.xray.operations.crud')
    def test_update_user_success(self, mock_crud, mock_xray_nodes, mock_db, mock_user, mock_node):
        # Setup
        mock_user.active_node_id = mock_node.id
        mock_crud.get_user_by_id.return_value = mock_user
        mock_crud.get_node_by_id.return_value = mock_node

        mock_xray_node = Mock(spec=ReSTXRayNode)
        mock_xray_node.connected = True
        mock_xray_node.started = True
        mock_xray_node.restart.return_value = {"status": "success"}
        mock_xray_nodes.get.return_value = mock_xray_node

        # Execute
        update_user(mock_user.id)

        # Verify
        mock_crud.get_user_by_id.assert_called_once_with(mock_db, mock_user.id)
        mock_crud.get_node_by_id.assert_called_once_with(mock_db, mock_node.id)
        mock_xray_node.restart.assert_called_once()
        assert isinstance(mock_xray_node.restart.call_args[0][0], XRayConfig)

    @patch('app.xray.operations.xray.nodes')
    @patch('app.xray.operations.crud')
    def test_activate_user_on_node_success(self, mock_crud, mock_xray_nodes, mock_db, mock_user, mock_node):
        # Setup
        mock_crud.get_user_by_id.return_value = mock_user
        mock_crud.get_node_by_id.return_value = mock_node
        mock_crud.get_users_by_active_node_id.return_value = [mock_user]

        mock_xray_node = Mock(spec=ReSTXRayNode)
        mock_xray_node.connected = True
        mock_xray_node.started = True
        mock_xray_node.restart.return_value = {"status": "success"}
        mock_xray_nodes.get.return_value = mock_xray_node

        # Execute
        activate_user_on_node(mock_user.id, mock_node.id)

        # Verify
        mock_crud.get_user_by_id.assert_called_once_with(mock_db, mock_user.id)
        mock_crud.get_node_by_id.assert_called_once_with(mock_db, mock_node.id)
        assert mock_user.active_node_id == mock_node.id
        mock_db.commit.assert_called_once()
        mock_xray_node.restart.assert_called_once()
        assert isinstance(mock_xray_node.restart.call_args[0][0], XRayConfig)

    @patch('app.xray.operations.xray.nodes')
    @patch('app.xray.operations.crud')
    def test_deactivate_user_success(self, mock_crud, mock_xray_nodes, mock_db, mock_user, mock_node):
        # Setup
        mock_user.active_node_id = mock_node.id
        mock_crud.get_user_by_id.return_value = mock_user
        mock_crud.get_node_by_id.return_value = mock_node
        mock_crud.get_users_by_active_node_id.return_value = []

        mock_xray_node = Mock(spec=ReSTXRayNode)
        mock_xray_node.connected = True
        mock_xray_node.started = True
        mock_xray_node.restart.return_value = {"status": "success"}
        mock_xray_nodes.get.return_value = mock_xray_node

        # Execute
        deactivate_user(mock_user.id)

        # Verify
        mock_crud.get_user_by_id.assert_called_once_with(mock_db, mock_user.id)
        mock_crud.get_node_by_id.assert_called_once_with(mock_db, mock_node.id)
        assert mock_user.active_node_id is None
        mock_db.commit.assert_called_once()
        mock_xray_node.restart.assert_called_once()
        assert isinstance(mock_xray_node.restart.call_args[0][0], XRayConfig)

    @patch('app.xray.operations.xray.nodes')
    @patch('app.xray.operations.crud')
    def test_activate_user_on_node_not_connected(self, mock_crud, mock_xray_nodes, mock_db, mock_user, mock_node):
        # Setup
        mock_node.status = NodeStatus.disconnected
        mock_crud.get_user_by_id.return_value = mock_user
        mock_crud.get_node_by_id.return_value = mock_node

        # Execute
        activate_user_on_node(mock_user.id, mock_node.id)

        # Verify
        mock_crud.get_user_by_id.assert_called_once_with(mock_db, mock_user.id)
        mock_crud.get_node_by_id.assert_called_once_with(mock_db, mock_node.id)
        assert mock_user.active_node_id == mock_node.id
        mock_db.commit.assert_called_once()
        # Should not call restart since node is not connected
        mock_xray_nodes.get.assert_not_called()

    @patch('app.xray.operations.xray.nodes')
    @patch('app.xray.operations.crud')
    def test_deactivate_user_not_connected(self, mock_crud, mock_xray_nodes, mock_db, mock_user, mock_node):
        # Setup
        mock_user.active_node_id = mock_node.id
        mock_node.status = NodeStatus.disconnected
        mock_crud.get_user_by_id.return_value = mock_user
        mock_crud.get_node_by_id.return_value = mock_node

        # Execute
        deactivate_user(mock_user.id)

        # Verify
        mock_crud.get_user_by_id.assert_called_once_with(mock_db, mock_user.id)
        mock_crud.get_node_by_id.assert_called_once_with(mock_db, mock_node.id)
        assert mock_user.active_node_id is None
        mock_db.commit.assert_called_once()
        # Should not call restart since node is not connected
        mock_xray_nodes.get.assert_not_called()