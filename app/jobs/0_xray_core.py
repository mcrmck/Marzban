import time
import traceback

import logging
from app.db import GetDB, crud
from app.models.node import NodeStatus
from config import JOB_CORE_HEALTH_CHECK_INTERVAL
from xray_api import exc as xray_exc

# Import app, scheduler, and xray but avoid circular import
def get_app_components():
    from app import app, scheduler, xray
    return app, scheduler, xray


def core_health_check():
    app, scheduler, xray = get_app_components()
    config = None  # Initialize config as it might be needed for node operations

    # nodes' core
    for node_id, node in list(xray.nodes.items()):
        if node.connected:
            try:
                assert node.started
                # It's good practice to ensure config is generated if needed before potential restart
                if not node.api.get_sys_stats(timeout=2): # Assuming get_sys_stats could return False on issues
                     raise AssertionError("Sys stats check failed or returned falsy")
            except (ConnectionError, xray_exc.XrayError, AssertionError):
                if not config:
                    config = xray.config.include_db_users()
                xray.operations.restart_node(node_id, config)

        # Check connection status separately, as a node might be disconnected without an error during the previous check
        if not node.connected:
            if not config:
                config = xray.config.include_db_users()
            xray.operations.connect_node(node_id)


def start_core():
    app, scheduler, xray = get_app_components()
    logging.getLogger("marzban").info("Panel startup: Preparing to connect to configured Xray nodes.")

    # Generate the base configuration that might be used for connecting nodes
    # This assumes xray.config.include_db_users() is still the way to get a suitable config
    # for external nodes. This might need adjustment later if config handling changes significantly.
    start_time = time.time()
    config_for_nodes = xray.config.include_db_users()
    logging.getLogger("marzban").info(f"Base node config generated in {(time.time() - start_time):.2f} seconds")

    # Connect to all enabled nodes defined in the database
    logging.getLogger("marzban").info("Attempting to connect to enabled Xray nodes.")
    with GetDB() as db:
        dbnodes = crud.get_nodes(db=db, enabled=True)
        node_ids_to_connect = []
        for dbnode in dbnodes:
            # Set status to connecting before attempting connection
            crud.update_node_status(db, dbnode, NodeStatus.connecting)
            node_ids_to_connect.append(dbnode.id)

    # It's important that xray.operations.connect_node does not assume it always needs a full 'config'
    # if the node is already configured and just needs a connection attempt.
    # However, passing it is safer if connect_node might also (re)start the Xray process on the node.
    for node_id in node_ids_to_connect:
        xray.operations.connect_node(node_id)

    # Schedule the health check for connected nodes
    scheduler.add_job(core_health_check, 'interval',
                      seconds=JOB_CORE_HEALTH_CHECK_INTERVAL,
                      coalesce=True, max_instances=1)


def app_shutdown():
    app, scheduler, xray = get_app_components()
    logging.getLogger("marzban").info("Panel shutdown: Disconnecting from all managed Xray nodes.")
    for node_id in list(xray.nodes.keys()): # Iterate by keys to avoid issues if node disconnects itself from dict
        node = xray.nodes.get(node_id)
        if node:
            try:
                logging.getLogger("marzban").info(f"Disconnecting from node ID: {node_id}")
                node.disconnect()
            except Exception as e:
                logging.getLogger("marzban").error(f"Error disconnecting from node ID {node_id}: {e}")
                pass