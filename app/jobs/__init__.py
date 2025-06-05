"""
Job initialization module for Marzban.

This module provides functions to register all scheduled jobs after the app is initialized,
avoiding circular import issues.
"""

def register_all_jobs():
    """Register all scheduled jobs with the scheduler."""
    from app import scheduler
    
    # Register remove expired users job
    from app.jobs.remove_expired_users import remove_expired_users
    scheduler.add_job(remove_expired_users, 'interval', coalesce=True, hours=6, max_instances=1)
    
    # Register reset user data usage job
    from app.jobs.reset_user_data_usage import reset_user_data_usage
    scheduler.add_job(reset_user_data_usage, 'interval', coalesce=True, hours=1)
    
    # Register review users job
    from app.jobs.review_users import review
    from config import JOB_REVIEW_USERS_INTERVAL
    scheduler.add_job(review, 'interval',
                      seconds=JOB_REVIEW_USERS_INTERVAL,
                      coalesce=True, max_instances=1)
    
    # Register record usages jobs
    from app.jobs.record_usages import record_user_usages
    from config import JOB_RECORD_USER_USAGES_INTERVAL
    scheduler.add_job(record_user_usages, 'interval',
                      seconds=JOB_RECORD_USER_USAGES_INTERVAL,
                      coalesce=True, max_instances=1, id="record_users_usages")
    
    # Conditionally register node usage recording 
    from app.jobs.record_usages import record_node_usages
    from config import JOB_RECORD_NODE_USAGES_INTERVAL
    scheduler.add_job(record_node_usages, 'interval',
                      seconds=JOB_RECORD_NODE_USAGES_INTERVAL,
                      coalesce=True, max_instances=1, id="record_nodes_usages")