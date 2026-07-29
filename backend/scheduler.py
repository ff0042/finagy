from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
import json

scheduler = BackgroundScheduler()

def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        logging.info("Background Scheduler started.")

def execute_background_task(task_description: str):
    from backend.llm.llm_service import process_chat
    from backend.routers.portfolio import get_portfolio
    from backend.routers.watchlist import get_watchlist
    from backend.db.database import execute_query
    from backend.constants import DEFAULT_USER_ID

    print(f"\n[BACKGROUND JOB TRIGGERED] Task: {task_description}\n")
    portfolio = get_portfolio()
    wl = get_watchlist()
    context = {
        "portfolio": portfolio,
        "watchlist": wl
    }
    
    # Fetch history
    history_rows = execute_query("SELECT role, content FROM chat_messages WHERE user_id = ? ORDER BY created_at DESC LIMIT 10", (DEFAULT_USER_ID,))
    history = [{"role": r["role"], "content": r["content"]} for r in reversed(history_rows)]
    
    # Save the synthesized "user" message for the background trigger
    execute_query("INSERT INTO chat_messages (user_id, role, content) VALUES (?, ?, ?)", (DEFAULT_USER_ID, "user", f"[BACKGROUND EVALUATION WAKEUP]: {task_description}"))
    
    # Execute chat in background mode
    res = process_chat(task_description, context, history, is_background=True)
    
    # Save the AI's response
    execute_query("INSERT INTO chat_messages (user_id, role, content) VALUES (?, ?, ?)", (DEFAULT_USER_ID, "assistant", json.dumps(res)))
    
    print("\n[BACKGROUND JOB COMPLETED]\n")

def add_cron_job(cron_expression: str, task_description: str):
    try:
        trigger = CronTrigger.from_crontab(cron_expression)
        job = scheduler.add_job(execute_background_task, trigger, args=[task_description])
        return job.id
    except Exception as e:
        raise ValueError(f"Invalid cron expression: {str(e)}")
