from collections import defaultdict
# from concurrent.futures import ThreadPoolExecutor # Keep for future performance enhancements if needed
from datetime import datetime
# from operator import attrgetter # Not used in the refined version below directly
from typing import Union # Optional might be needed if not already imported via other means
import logging

# Assuming sqlalchemy parts are needed if we were to keep old helpers, but not for new version
# from pymysql.err import OperationalError
# from sqlalchemy import and_, bindparam, insert, select, update
# from sqlalchemy.orm import Session
# from sqlalchemy.sql.dml import Insert

from app import scheduler, xray # xray.nodes will be used
from app.db import GetDB, crud # Ensure crud is imported
# Models used for type hinting or direct use if any (mostly in CRUD now)
# from app.db.models import Admin, NodeUsage, NodeUserUsage, System, User
from config import (
    # DISABLE_RECORDING_NODE_USAGE, # This might be checked before scheduling the job itself
    JOB_RECORD_NODE_USAGES_INTERVAL,
    JOB_RECORD_USER_USAGES_INTERVAL,
)
# from xray_api import XRay as XRayAPI # XRayAPI type hint for node.api is good
from xray_api import exc as xray_exc # Corrected alias usage
# from app.utils.concurrency import threaded_function # Removed as per your provided file, but good for jobs

logger = logging.getLogger(__name__)

# --- Old Helper Functions (To be REMOVED as their logic is now in CRUD) ---
# def safe_execute(db: Session, stmt, params=None): ...
# def record_user_stats(params: list, node_id: Union[int, None], consumption_factor: int = 1): ...
# def record_node_stats(params: dict, node_id: Union[int, None]): ...
# def get_users_stats(api: XRayAPI): ...
# def get_outbounds_stats(api: XRayAPI): ...
# --- End of Old Helper Functions ---


# @threaded_function # Consider re-adding if jobs are long and you have it defined
def record_user_usages(ignore_write_to_db: bool = False):
    logger.debug("Job 'record_user_usages' started.")
    if not xray.nodes:
        logger.info("No Xray nodes configured. Skipping user usage recording.")
        return

    current_hour_utc = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    all_user_stats_updates = defaultdict(lambda: {'uplink': 0, 'downlink': 0, 'node_ids_reported': set()})
    email_to_user_id_map = {}

    try:
        with GetDB() as db_initial_users:
            # Assumes crud.get_users_for_usage_mapping is defined and returns [(user_id, account_number), ...]
            users_for_map = crud.get_users_for_usage_mapping(db_initial_users)
            for user_id, account_number_val in users_for_map:
                email_to_user_id_map[f"{user_id}.{account_number_val}"] = user_id
                # Original Marzban also mapped by just account_number for some Xray versions/setups
                email_to_user_id_map[f"{account_number_val}"] = user_id
    except Exception as e:
        logger.error(f"Error fetching users for usage mapping: {e}", exc_info=True)
        return # Cannot proceed without user map

    for node_id, node_instance in list(xray.nodes.items()):
        if not (node_instance and node_instance.connected and hasattr(node_instance, 'api') and node_instance.api):
            logger.warning(f"Node ID {node_id} is not connected or has no API. Skipping for user usage.")
            continue

        try:
            logger.debug(f"Fetching user stats from node ID: {node_id} ({node_instance.address})")
            # get_all_users_traffic is preferred for panels
            stats = node_instance.api.get_all_users_traffic(reset=True, timeout=30)

            for stat_item in stats: # Renamed from 'stat' to avoid conflict if 'stat' module is ever imported
                user_identifier = stat_item.name
                user_id = email_to_user_id_map.get(user_identifier)

                if user_id is None:
                    logger.warning(f"Stat received for unknown user identifier '{user_identifier}' from node {node_id}. Skipping.")
                    continue

                all_user_stats_updates[user_id]['uplink'] += stat_item.uplink
                all_user_stats_updates[user_id]['downlink'] += stat_item.downlink
                all_user_stats_updates[user_id]['node_ids_reported'].add(node_id)

        except xray_exc.XrayError as e: # Corrected usage of xray_exc
            logger.error(f"Xray API error while fetching user stats from node {node_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching user stats from node {node_id}: {e}", exc_info=True)

    if not ignore_write_to_db and all_user_stats_updates:
        updated_count = 0
        try:
            with GetDB() as db:
                for user_id, usage_data in all_user_stats_updates.items():
                    db_user = crud.get_user_by_id(db, user_id)
                    if not db_user:
                        logger.warning(f"User with ID {user_id} not found in DB for usage update.")
                        continue

                    node_coefficient = 1.0
                    if db_user.active_node_id and db_user.active_node_id in xray.nodes:
                        # Ensure xray.nodes[db_user.active_node_id] is not None if key exists
                        active_node_instance = xray.nodes.get(db_user.active_node_id)
                        if active_node_instance:
                             node_coefficient = active_node_instance.usage_coefficient

                    uplink_to_add = int(usage_data['uplink'] * node_coefficient)
                    downlink_to_add = int(usage_data['downlink'] * node_coefficient)
                    total_usage_to_add = uplink_to_add + downlink_to_add

                    if total_usage_to_add > 0:
                        db_user.used_traffic += total_usage_to_add
                        db_user.online_at = datetime.utcnow()

                        if db_user.active_node_id is not None: # Ensure active_node_id is not None
                            # Assumes crud.create_or_update_node_user_usage is defined
                            crud.create_or_update_node_user_usage(
                                db=db,
                                user_id=db_user.id,
                                node_id=db_user.active_node_id,
                                used_traffic_increment=total_usage_to_add,
                                event_hour_utc=current_hour_utc # Pass consistent hourly timestamp
                            )
                        else:
                            logger.warning(f"User ID {user_id} reported traffic but has no active_node_id. Cannot record NodeUserUsage.")
                        updated_count +=1
                db.commit()
                logger.info(f"User usages updated in DB for {updated_count} users based on stats from {len(all_user_stats_updates)} user entries.")
        except Exception as e:
            # db.rollback() # GetDB context manager might handle rollback on exception
            logger.error(f"DB error committing user usages: {e}", exc_info=True)

    elif not all_user_stats_updates:
        logger.info("No user stats updates to process in this cycle.")
    logger.debug("Job 'record_user_usages' finished.")


# @threaded_function # Consider re-adding
def record_node_usages(ignore_write_to_db: bool = False):
    logger.debug("Job 'record_node_usages' started.")
    if not xray.nodes:
        logger.info("No Xray nodes configured. Skipping node responsiveness check.")
        # If not checking responsiveness, and aggregation is main goal, can proceed if NodeUserUsage has data
        # return

    # Check node responsiveness (optional, but good for health monitoring)
    for node_id, node_instance in list(xray.nodes.items()):
        if not (node_instance and node_instance.connected and hasattr(node_instance, 'api') and node_instance.api):
            logger.warning(f"Node ID {node_id} is not connected or has no API. Skipping for sys stats check.")
            continue
        try:
            logger.debug(f"Fetching system stats from node ID: {node_id} ({node_instance.address})")
            stats = node_instance.api.get_sys_stats(timeout=10) # Short timeout for responsiveness check
            if stats and hasattr(stats, 'app_uptime'):
                logger.info(f"Node {node_id} SysStats: Uptime {stats.app_uptime}s, Goroutines {stats.num_goroutine}")
            else:
                logger.warning(f"Could not retrieve valid sys stats from node {node_id}")
        except xray_exc.XrayError as e: # Corrected usage of xray_exc
            logger.error(f"Xray API error while fetching system stats from node {node_id}: {e}")
            # Consider updating node status to 'error' in DB after multiple failures
        except Exception as e:
            logger.error(f"Unexpected error fetching system stats from node {node_id}: {e}", exc_info=True)

    # Aggregate NodeUserUsage data into NodeUsage table
    if not ignore_write_to_db:
        current_aggregation_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        try:
            with GetDB() as db:
                # Assumes crud.aggregate_node_user_usages_to_node_usage is defined
                crud.aggregate_node_user_usages_to_node_usage(db, current_aggregation_hour)
                db.commit()
                logger.info(f"Node usage aggregation for hour {current_aggregation_hour.strftime('%Y-%m-%d %H:00')} completed.")
        except Exception as e:
            # db.rollback() # GetDB context manager might handle rollback
            logger.error(f"DB error during NodeUsage aggregation: {e}", exc_info=True)
    logger.debug("Job 'record_node_usages' finished.")


# Ensure DISABLE_RECORDING_NODE_USAGE is checked appropriately if you want to disable this job
# For example, in app/jobs/__init__.py when scheduling, or here directly.
# if not DISABLE_RECORDING_NODE_USAGE: # This constant is from config
#     scheduler.add_job(record_node_usages, ...)
# else:
#     logger.info("Recording of node usages is disabled via DISABLE_RECORDING_NODE_USAGE.")

scheduler.add_job(record_user_usages, 'interval',
                  id='record_user_usages_job', # Added job ID
                  seconds=JOB_RECORD_USER_USAGES_INTERVAL,
                  coalesce=True, max_instances=1, replace_existing=True)

if not getattr(xray, 'config', {}).get("DISABLE_RECORDING_NODE_USAGE", False): # Check a config flag
    scheduler.add_job(record_node_usages, 'interval',
                      id='record_node_usages_job', # Added job ID
                      seconds=JOB_RECORD_NODE_USAGES_INTERVAL,
                      coalesce=True, max_instances=1, replace_existing=True)
else:
    logger.info("Recording of node usages is disabled (DISABLE_RECORDING_NODE_USAGE in XrayConfig or main config).")